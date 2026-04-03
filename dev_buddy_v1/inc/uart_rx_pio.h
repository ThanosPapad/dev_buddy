
// uart_rx_pio.h
#ifndef UART_RX_PIO_H
#define UART_RX_PIO_H

#include "pico/stdlib.h"
#include "hardware/pio.h"
#include "hardware/clocks.h"
#include "hardware/gpio.h"
#include "uart_rx.pio.h"
#include "ring_buffer.h"

// ── Configuration ──────────────────────────────────────────────
#define PIO_UART_BAUD_DEFAULT   115200
#define PIO_UART_OVERSAMPLING   8       // must match .pio: 8 cycles per bit

// GPIO pin assignments — adjust freely
#define PIO_UART0_RX_PIN   6
#define PIO_UART1_RX_PIN   8
#define PIO_UART2_RX_PIN   10

#define PIO_UART_INSTANCE  pio0

#define AGG_BUF_SIZE        100         // bytes per channel staging buffer
#define AGG_NUM_CHANNELS    3
#define AGG_TIMEOUT_MS      50          // flush partial buffer after this many ms
// ───────────────────────────────────────────────────────────────

typedef struct {
    PIO     pio;
    uint    sm;
    uint    rx_pin;
} pio_uart_inst_t;

// Per-channel staging buffer + state
typedef struct {
    uint8_t  buf[AGG_BUF_SIZE];
    uint8_t  len;                       
    volatile bool ready;                
    uint32_t first_byte_time_ms;        
    bool     timing;                    
} agg_channel_t;

// All 3 channels — read `ready` and `buf`/`len` from your PC transmit code
extern agg_channel_t agg_channels[AGG_NUM_CHANNELS];

extern pio_uart_inst_t pio_uarts[3];
extern ring_buffer_t pio_uart_rx_buf[3];

// ── API ─────────────────────────────────────────────────────────
void    pio_uart_init_all(uint32_t baud_rate);
void    pio_uart_set_baud(uint8_t channel, uint32_t new_baud_rate);
void    pio_uart_set_baud_all(uint32_t new_baud_rate);
bool    pio_uart_rx_available(uint8_t channel);
uint8_t pio_uart_rx_read(uint8_t channel);
void check_pio_buffers ();
void aggregator_init(void);
void aggregator_update(void);
void aggregator_consume(uint8_t channel);

#endif