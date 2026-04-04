#include "uart_rx_pio.h"
#include "hardware/irq.h"
#include <string.h>

pio_uart_inst_t     pio_uarts[3];
pio_uart_tx_inst_t  pio_tx[3];
ring_buffer_t       pio_uart_rx_buf[3];
volatile uint32_t   pio_uart_rx_dropped[3];
agg_channel_t       agg_channels[AGG_NUM_CHANNELS];

// ── Internal helpers ────────────────────────────────────────────

static float _baud_to_clkdiv(uint32_t baud_rate) {
    return (float)clock_get_hz(clk_sys) / (float)(baud_rate * PIO_UART_OVERSAMPLING);
}

// ── IRQ handler — runs on PIO0_IRQ_0 ───────────────────────────

static void _pio_uart_irq_handler(void) {
    for (uint8_t i = 0; i < 3; i++) {
        pio_uart_inst_t *inst = &pio_uarts[i];
        while (!pio_sm_is_rx_fifo_empty(inst->pio, inst->sm)) {
            io_rw_8 *rxfifo_shift = (io_rw_8*)&inst->pio->rxf[inst->sm] + 3;
            uint8_t byte = (uint8_t)*rxfifo_shift;
            uint16_t next_head = (pio_uart_rx_buf[i].head + 1) & RING_BUFFER_MASK;
            if (next_head == pio_uart_rx_buf[i].tail) {
                pio_uart_rx_dropped[i]++;
            } else {
                rb_push(&pio_uart_rx_buf[i], byte);
            }
        }
    }
}

// ── Init helpers ────────────────────────────────────────────────

static void _init_single(pio_uart_inst_t *inst, uint offset, uint32_t baud_rate) {
    inst->sm = pio_claim_unused_sm(inst->pio, true);
    uart_rx_program_init(inst->pio, inst->sm, offset, inst->rx_pin, baud_rate);
}

static void _init_tx_single(pio_uart_tx_inst_t *inst, uint offset, uint32_t baud_rate) {
    inst->sm   = pio_claim_unused_sm(inst->pio, true);
    inst->busy = false;
    inst->len  = 0;
    inst->pos  = 0;
    uart_tx_program_init(inst->pio, inst->sm, offset, inst->tx_pin, baud_rate);
}

static void _setup_irq(PIO pio) {
    pio_set_irq0_source_enabled(pio, pis_sm0_rx_fifo_not_empty, true);
    pio_set_irq0_source_enabled(pio, pis_sm1_rx_fifo_not_empty, true);
    pio_set_irq0_source_enabled(pio, pis_sm2_rx_fifo_not_empty, true);
    irq_set_exclusive_handler(PIO0_IRQ_0, _pio_uart_irq_handler);
    irq_set_priority(PIO0_IRQ_0, 64);
    irq_set_enabled(PIO0_IRQ_0, true);
}

// ── Public init ─────────────────────────────────────────────────

void pio_uart_init_all(uint32_t baud_rate) {
    // ── RX on PIO0 ──────────────────────────────────────────────
    PIO pio_r = PIO_UART_INSTANCE;
    memset(pio_uart_rx_buf, 0, sizeof(pio_uart_rx_buf));
    memset((void*)pio_uart_rx_dropped, 0, sizeof(pio_uart_rx_dropped));

    uint rx_offset = pio_add_program(pio_r, &uart_rx_program);

    pio_uarts[0] = (pio_uart_inst_t){ .pio = pio_r, .rx_pin = PIO_UART0_RX_PIN };
    pio_uarts[1] = (pio_uart_inst_t){ .pio = pio_r, .rx_pin = PIO_UART1_RX_PIN };
    pio_uarts[2] = (pio_uart_inst_t){ .pio = pio_r, .rx_pin = PIO_UART2_RX_PIN };

    _init_single(&pio_uarts[0], rx_offset, baud_rate);
    _init_single(&pio_uarts[1], rx_offset, baud_rate);
    _init_single(&pio_uarts[2], rx_offset, baud_rate);
    _setup_irq(pio_r);

    // ── TX on PIO1 ──────────────────────────────────────────────
    PIO pio_t = PIO_UART_TX_INSTANCE;
    uint tx_offset = pio_add_program(pio_t, &uart_tx_program);

    pio_tx[0] = (pio_uart_tx_inst_t){ .pio = pio_t, .tx_pin = PIO_UART0_TX_PIN };
    pio_tx[1] = (pio_uart_tx_inst_t){ .pio = pio_t, .tx_pin = PIO_UART1_TX_PIN };
    pio_tx[2] = (pio_uart_tx_inst_t){ .pio = pio_t, .tx_pin = PIO_UART2_TX_PIN };

    _init_tx_single(&pio_tx[0], tx_offset, baud_rate);
    _init_tx_single(&pio_tx[1], tx_offset, baud_rate);
    _init_tx_single(&pio_tx[2], tx_offset, baud_rate);
}

// ── Baud rate ────────────────────────────────────────────────────

void pio_uart_set_baud(uint8_t channel, uint32_t new_baud_rate) {
    assert(channel < 3);
    float div = _baud_to_clkdiv(new_baud_rate);

    // RX SM
    pio_sm_set_enabled(pio_uarts[channel].pio, pio_uarts[channel].sm, false);
    pio_sm_set_clkdiv(pio_uarts[channel].pio, pio_uarts[channel].sm, div);
    pio_sm_restart(pio_uarts[channel].pio, pio_uarts[channel].sm);
    pio_sm_set_enabled(pio_uarts[channel].pio, pio_uarts[channel].sm, true);

    // TX SM — wait for in-progress TX to finish first to avoid mid-byte corruption
    while (pio_tx[channel].busy) tight_loop_contents();
    pio_sm_set_enabled(pio_tx[channel].pio, pio_tx[channel].sm, false);
    pio_sm_set_clkdiv(pio_tx[channel].pio, pio_tx[channel].sm, div);
    pio_sm_restart(pio_tx[channel].pio, pio_tx[channel].sm);
    pio_sm_set_enabled(pio_tx[channel].pio, pio_tx[channel].sm, true);
}

void pio_uart_set_baud_all(uint32_t new_baud_rate) {
    for (uint8_t i = 0; i < 3; i++) {
        pio_uart_set_baud(i, new_baud_rate);
    }
}

// ── RX API ───────────────────────────────────────────────────────

bool pio_uart_rx_available(uint8_t channel) {
    assert(channel < 3);
    return rb_available(&pio_uart_rx_buf[channel]) > 0;
}

uint8_t pio_uart_rx_read(uint8_t channel) {
    assert(channel < 3);
    uint8_t byte = 0;
    rb_pop(&pio_uart_rx_buf[channel], &byte);
    return byte;
}

// ── Aggregator ───────────────────────────────────────────────────

static void _reset_channel(uint8_t ch) {
    agg_channels[ch].len                = 0;
    agg_channels[ch].timing             = false;
    agg_channels[ch].first_byte_time_ms = 0;
}

void aggregator_init(void) {
    for (uint8_t ch = 0; ch < AGG_NUM_CHANNELS; ch++) {
        agg_channels[ch].ready = false;
        _reset_channel(ch);
    }
}

void aggregator_update(void) {
    uint32_t now = to_ms_since_boot(get_absolute_time());

    for (uint8_t ch = 0; ch < AGG_NUM_CHANNELS; ch++) {
        agg_channel_t *c = &agg_channels[ch];

        if (c->ready) continue;

        uint8_t byte;
        while (c->len < AGG_BUF_SIZE && rb_pop(&pio_uart_rx_buf[ch], &byte)) {
            if (!c->timing) {
                c->first_byte_time_ms = now;
                c->timing = true;
            }
            c->buf[c->len++] = byte;
        }

        bool full      = (c->len == AGG_BUF_SIZE);
        bool timed_out = c->timing && (now - c->first_byte_time_ms >= AGG_TIMEOUT_MS);

        if (full || timed_out) {
            if (c->len > 0) {
                c->ready = true;
            } else {
                c->timing = false;
            }
        }
    }
}

void aggregator_consume(uint8_t channel) {
    assert(channel < AGG_NUM_CHANNELS);
    agg_channels[channel].ready = false;
    _reset_channel(channel);
}

// ── TX API ───────────────────────────────────────────────────────

bool pio_uart_tx_send(uint8_t channel, const uint8_t *data, uint8_t len) {
    assert(channel < 3);
    assert(len <= PIO_TX_BUF_SIZE);

    if (pio_tx[channel].busy) return false;  // still sending — caller retries next loop

    memcpy(pio_tx[channel].buf, data, len);
    pio_tx[channel].len  = len;
    pio_tx[channel].pos  = 0;
    pio_tx[channel].busy = true;

    return true;
}

bool pio_uart_tx_busy(uint8_t channel) {
    assert(channel < 3);
    return pio_tx[channel].busy;
}

void pio_uart_tx_update(void) {
    for (uint8_t i = 0; i < 3; i++) {
        pio_uart_tx_inst_t *t = &pio_tx[i];

        if (!t->busy) continue;

        while (t->pos < t->len) {
            if (pio_sm_is_tx_fifo_full(t->pio, t->sm)) break;
            // No shift — byte goes in bottom bits, OSR shifts right, LSB first
            pio_sm_put(t->pio, t->sm, (uint32_t)t->buf[t->pos]);
            t->pos++;
        }

        if (t->pos >= t->len && pio_sm_is_tx_fifo_empty(t->pio, t->sm)) {
            t->busy = false;
        }
    }
}

// ── Debug helper ─────────────────────────────────────────────────

void check_pio_buffers(void) {
    for (uint8_t ch = 0; ch < 3; ch++) {
        uint16_t avail   = rb_available(&pio_uart_rx_buf[ch]);
        uint32_t dropped = pio_uart_rx_dropped[ch];
        bool     tx_busy = pio_tx[ch].busy;
        bool     rdy     = agg_channels[ch].ready;
        // Hook this up to your preferred debug output, e.g.:
        // printf("CH%d: ring=%d dropped=%lu tx_busy=%d agg_ready=%d\n",
        //         ch, avail, dropped, tx_busy, rdy);
        (void)avail; (void)dropped; (void)tx_busy; (void)rdy;
    }
}