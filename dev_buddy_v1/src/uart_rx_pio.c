
#include "uart_rx_pio.h"
#include "hardware/irq.h"

pio_uart_inst_t  pio_uarts[3];
ring_buffer_t    pio_uart_rx_buf[3];
volatile uint32_t pio_uart_rx_dropped[3];

agg_channel_t agg_channels[AGG_NUM_CHANNELS];

// ── Internal helpers ────────────────────────────────────────────

static float _baud_to_clkdiv(uint32_t baud_rate) {
    return (float)clock_get_hz(clk_sys) / (float)(baud_rate * PIO_UART_OVERSAMPLING);
}

// ── IRQ handler — runs on PIO0_IRQ_0 ───────────────────────────
// Drains all 3 SM FIFOs into their ring buffers as fast as possible.
// Keep this lean — no function calls with overhead, no blocking.

static void _pio_uart_irq_handler(void) {
    for (uint8_t i = 0; i < 3; i++) {
        pio_uart_inst_t *inst = &pio_uarts[i];

        // Drain everything available in this SM's FIFO right now
        while (!pio_sm_is_rx_fifo_empty(inst->pio, inst->sm)) {
            // Left-justified read — same as uart_rx_program_getc()
            io_rw_8 *rxfifo_shift = (io_rw_8*)&inst->pio->rxf[inst->sm] + 3;
            uint8_t byte = (uint8_t)*rxfifo_shift;

            // Check if ring buffer has room before pushing
            uint16_t next_head = (pio_uart_rx_buf[i].head + 1) & RING_BUFFER_MASK;
            if (next_head == pio_uart_rx_buf[i].tail) {
                pio_uart_rx_dropped[i]++;   // overflow — count it, drop the byte
            } else {
                rb_push(&pio_uart_rx_buf[i], byte);
            }
        }
    }
    // No need to clear a PIO IRQ flag here — the RX FIFO not-empty IRQ
    // de-asserts automatically once the FIFO is drained
}

// ── Init helpers ────────────────────────────────────────────────

static void _init_single(pio_uart_inst_t *inst, uint offset, uint32_t baud_rate) {
    inst->sm = pio_claim_unused_sm(inst->pio, true);
    uart_rx_program_init(inst->pio, inst->sm, offset, inst->rx_pin, baud_rate);
}

static void _setup_irq(PIO pio) {
    // Enable RX FIFO not-empty interrupt for all 3 SMs on PIO0_IRQ_0
    // RXNEMPTY interrupt source per SM: PIO_INTR_SM0_RXNEMPTY_LSB + sm_index
    pio_set_irq0_source_enabled(pio, pis_sm0_rx_fifo_not_empty, true);
    pio_set_irq0_source_enabled(pio, pis_sm1_rx_fifo_not_empty, true);
    pio_set_irq0_source_enabled(pio, pis_sm2_rx_fifo_not_empty, true);

    // Register our handler on PIO0_IRQ_0
    irq_set_exclusive_handler(PIO0_IRQ_0, _pio_uart_irq_handler);

    // Set priority — higher than default so UART bytes aren't delayed
    // RP2350 priority: 0 = highest, 255 = lowest. 64 is a safe elevated priority.
    irq_set_priority(PIO0_IRQ_0, 64);

    irq_set_enabled(PIO0_IRQ_0, true);
}

// ── Public API ──────────────────────────────────────────────────

void pio_uart_init_all(uint32_t baud_rate) {
    PIO pio = PIO_UART_INSTANCE;

    // Zero out ring buffers and drop counters
    memset(pio_uart_rx_buf, 0, sizeof(pio_uart_rx_buf));
    memset((void*)pio_uart_rx_dropped, 0, sizeof(pio_uart_rx_dropped));

    uint offset = pio_add_program(pio, &uart_rx_program);

    pio_uarts[0] = (pio_uart_inst_t){ .pio = pio, .rx_pin = PIO_UART0_RX_PIN };
    pio_uarts[1] = (pio_uart_inst_t){ .pio = pio, .rx_pin = PIO_UART1_RX_PIN };
    pio_uarts[2] = (pio_uart_inst_t){ .pio = pio, .rx_pin = PIO_UART2_RX_PIN };

    _init_single(&pio_uarts[0], offset, baud_rate);
    _init_single(&pio_uarts[1], offset, baud_rate);
    _init_single(&pio_uarts[2], offset, baud_rate);

    _setup_irq(pio);
}

void pio_uart_set_baud(uint8_t channel, uint32_t new_baud_rate) {
    assert(channel < 3);
    pio_uart_inst_t *inst = &pio_uarts[channel];
    float div = _baud_to_clkdiv(new_baud_rate);

    pio_sm_set_enabled(inst->pio, inst->sm, false);
    pio_sm_set_clkdiv(inst->pio, inst->sm, div);
    pio_sm_restart(inst->pio, inst->sm);
    pio_sm_set_enabled(inst->pio, inst->sm, true);
}

void pio_uart_set_baud_all(uint32_t new_baud_rate) {
    for (uint8_t i = 0; i < 3; i++) {
        pio_uart_set_baud(i, new_baud_rate);
    }
}

// ── Main-loop facing API (reads from ring buffer, not FIFO) ─────

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

static void _reset_channel(uint8_t ch) {
    agg_channels[ch].len               = 0;
    agg_channels[ch].timing            = false;
    agg_channels[ch].first_byte_time_ms = 0;
    // NOTE: we do NOT touch .ready here — that's the PC transmit side's job
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

        // ── Skip this channel if PC hasn't consumed the last buffer yet ──
        if (c->ready) continue;

        // ── Drain ring buffer into staging buffer ────────────────────────
        uint8_t byte;
        while (c->len < AGG_BUF_SIZE && rb_pop(&pio_uart_rx_buf[ch], &byte)) {

            // Start the timeout timer on the first byte of a new fill
            if (!c->timing) {
                c->first_byte_time_ms = now;
                c->timing = true;
            }

            c->buf[c->len++] = byte;
        }

        // ── Check flush conditions ───────────────────────────────────────

        // Condition 1: buffer is exactly full
        bool full = (c->len == AGG_BUF_SIZE);

        // Condition 2: timeout — we have at least 1 byte and 50 ms have passed
        bool timed_out = c->timing &&
                         (now - c->first_byte_time_ms >= AGG_TIMEOUT_MS);

        if (full || timed_out) {
            // Only flag if we actually have something to send
            if (c->len > 0) {
                c->ready = true;    // signal PC transmit side
                // Do NOT call _reset_channel here — PC still needs buf/len
            } else {
                // Timed out with zero bytes — just reset the timer silently
                c->timing = false;
            }
        }
    }
}

void aggregator_consume(uint8_t channel) {
    assert(channel < AGG_NUM_CHANNELS);
    // PC transmit is done — clear flag and reset staging state for next fill
    agg_channels[channel].ready = false;
    _reset_channel(channel);
}