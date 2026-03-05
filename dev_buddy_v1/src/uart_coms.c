#include "uart_coms.h"
#include "pico/stdlib.h"
#include "globals.h"
#include "hardware/uart.h"
#include "hardware/dma.h"
#include "hardware/irq.h"
#include <string.h>
#include "timer_handler.h"

static int dma_tx_ch;
static int dma_rx_ch;

static uint8_t rx_dma_buf[RX_BUF_SIZE] __attribute__((aligned(RX_BUF_SIZE)));
static volatile uint32_t last_rx_idx = 0;

static char rx_line[RX_MAX_LEN + 1];
static uint8_t line_index = 0;

pico_unique_board_id_t id;

handshake_packet_t pack = {0};

void uart_dma_write(const uint8_t *data, size_t len) {
    // Wait only if a previous transfer is still running
    while (dma_channel_is_busy(dma_tx_ch)) {
        tight_loop_contents();
    }

    dma_channel_config_t c = dma_channel_get_default_config(dma_tx_ch);
    channel_config_set_transfer_data_size(&c, DMA_SIZE_8);
    channel_config_set_read_increment(&c, true);
    channel_config_set_write_increment(&c, false);
    channel_config_set_dreq(&c, uart_get_dreq(UART_ID, true));

    dma_channel_configure(dma_tx_ch, &c,
        &uart_get_hw(UART_ID)->dr,
        data,
        len,
        true);  // start immediately — CPU is now free
    
}

void process_rx_dma(void) {
    // Get current write pointer from DMA (address after last write)
    uint32_t write_addr = dma_hw->ch[dma_rx_ch].write_addr;
    uint32_t current_idx = (write_addr - (uint32_t)rx_dma_buf) & RX_BUF_MASK;

    // Calculate number of new bytes received
    int32_t new_bytes = (current_idx - last_rx_idx) & RX_BUF_MASK;
    if (new_bytes == 0) return;

    // Process each new byte
    for (int i = 0; i < new_bytes; i++) {
        uint32_t idx = (last_rx_idx + i) & RX_BUF_MASK;
        uint8_t ch = rx_dma_buf[idx];

        // Line framing logic (same as original interrupt handler)
        if (ch == '\n' || ch == '\r') {
            rx_line[line_index] = '\0';

            // Update connection state based on current state
            if (conn_stat == IDLE_CONNECTION)
                conn_stat = COM_FULL_CONFIRMCON;
            else if (conn_stat == COM_CONNECTED)
                conn_stat = COM_FULL;

            line_index = 0;  // Ready for next line
        } else {
            if (line_index < RX_MAX_LEN) {
                rx_line[line_index++] = ch;
            } else {
                line_index = 0;  // Buffer overflow, discard line
            }
        }
    }

    last_rx_idx = current_idx;
}

void serial_init(void) {
    
    uart_init(UART_ID, BAUD_RATE);
    gpio_set_function(UART_TX_PIN, UART_FUNCSEL_NUM(UART_ID, UART_TX_PIN));
    gpio_set_function(UART_RX_PIN, UART_FUNCSEL_NUM(UART_ID, UART_RX_PIN));
    uart_set_hw_flow(UART_ID, false, false);
    uart_set_format(UART_ID, 8, 1, UART_PARITY_NONE);
    uart_set_fifo_enabled(UART_ID, false); 
    // Claim channels
    dma_tx_ch = dma_claim_unused_channel(true);
    dma_rx_ch = dma_claim_unused_channel(true);
    // RX DMA circular buffer
    dma_channel_config_t rx_cfg = dma_channel_get_default_config(dma_rx_ch);
    channel_config_set_transfer_data_size(&rx_cfg, DMA_SIZE_8);
    channel_config_set_read_increment(&rx_cfg, false);      // read from fixed UART DR
    channel_config_set_write_increment(&rx_cfg, true);      // write to buffer with increment
    channel_config_set_dreq(&rx_cfg, uart_get_dreq(UART_ID, false)); // RX DREQ
    channel_config_set_ring(&rx_cfg, true, 8);              // ring buffer size 256 (2^8)

    dma_channel_configure(dma_rx_ch, &rx_cfg,
                          rx_dma_buf,                        // write address (start)
                          &uart_get_hw(UART_ID)->dr,         // read address (UART DR)
                          UINT32_MAX,                         // huge count, never stop
                          true);                              // start immediately

    // TX DMA
    dma_channel_config_t tx_cfg = dma_channel_get_default_config(dma_tx_ch);
    channel_config_set_transfer_data_size(&tx_cfg, DMA_SIZE_8);
    channel_config_set_read_increment(&tx_cfg, true);
    channel_config_set_write_increment(&tx_cfg, false);
    channel_config_set_dreq(&tx_cfg, uart_get_dreq(UART_ID, true)); // TX DREQ
    dma_channel_configure(dma_tx_ch, &tx_cfg,
                          &uart_get_hw(UART_ID)->dr,         // dest (fixed)
                          NULL,                                // src set later
                          0,                                   // count set later
                          false);                              // don't start yet
}

void handle_uart_rcv(void) {

    
    pico_get_unique_board_id(&id);
    // Perform initial handshake
    if (conn_stat == COM_FULL_CONFIRMCON) {
        memcpy(&pack, rx_line, sizeof(handshake_packet_t));
        if (pack.handshake_value == 111 && pack.device_number == 99) {
            memcpy(pack.chip_id, id.id, 8);
            pack.handshake_value = 112;
            memset(pack.data, 0, sizeof(pack.data));
            // Send response via DMA
            uart_dma_write((uint8_t*)&pack, sizeof(pack));
            uart_dma_write((uint8_t*)"\n", 1);

            conn_stat = COM_CONNECTED;
        } else {
            conn_stat = IDLE_CONNECTION;
        }
    }
    // Normal communication 
    if (conn_stat == COM_FULL) {
        memcpy(&pack, rx_line, sizeof(handshake_packet_t));
        switch (pack.handshake_value){
            case SET_DEVICE_OUTPUTS:
                memcpy(&out_status, pack.data, sizeof(output_control_t));
                output_set_flag = true;
                break;
            case GET_DEVICE_OUTPUTS_REQ:
                read_ins_flag = true;
                absolute_time_t timeout = make_timeout_time_ms(50);
                while (read_ins_flag && !time_reached(timeout))
                {
                    tight_loop_contents();
                }
                read_ins_flag = false; // In case of timeout make sure that the flag is reset
                // Create response packet
                
                memcpy(pack.chip_id, id.id, 8);
                pack.handshake_value = GET_DEVICE_OUTPUTS_RESP;
                memcpy(pack.data, &in_status, sizeof(input_read_t));
                uart_dma_write((uint8_t*)&pack, sizeof(pack));
                uart_dma_write((uint8_t*)"\n", 1);
                break;
            case SET_ADC_INTERVAL_REQ:
                uint32_t new_adc_interval = (uint32_t)pack.data[0] |
                                            ((uint32_t)pack.data[1] << 8) |
                                            ((uint32_t)pack.data[2] << 16) |
                                            ((uint32_t)pack.data[3] << 24);
                bool res = change_timer_period(&adc_tlm_timer, new_adc_interval);
                pack.data[0] = (uint8_t)res;
                memcpy(&pack.data[1], &new_adc_interval, sizeof(new_adc_interval));
                pack.handshake_value = GET_DEVICE_OUTPUTS_RESP;
                uart_dma_write((uint8_t*)&pack, sizeof(pack));
                uart_dma_write((uint8_t*)"\n", 1);
                break;
            case SET_ADC_INTERVAL_STATE_REQ:
                uint8_t adc_state_set = pack.data[0];
                // if (adc_state_set == 1) timer_enable(&adc_timer);
                // else if (adc_state_set == 0) timer_disable(&adc_timer);
                pack.handshake_value = SET_ADC_INTERVAL_STATE_RESP;
                uart_dma_write((uint8_t*)&pack, sizeof(pack));
                uart_dma_write((uint8_t*)"\n", 1);
                break;
        }

        // uart_dma_write((uint8_t*)rx_line, strlen(rx_line));
        conn_stat = COM_CONNECTED;
    }
}

void transmit_adc_meas()
{
    // handshake_packet_t pack = {0};
    memcpy(pack.chip_id, id.id, 8);
    pack.handshake_value = ADC_TELEMETRY_TRANS;
    pack.device_number = 99;
    memcpy(pack.data, &adc_meas, sizeof(channel_voltages_t));
    pack.payload_length = 112;
    uart_dma_write((uint8_t *)&pack, sizeof(pack));
    uart_dma_write((uint8_t *)"\n", 1);
}