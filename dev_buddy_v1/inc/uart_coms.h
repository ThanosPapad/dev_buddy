/** @file uart_coms.h
 * 
 * @brief Global information used and visible by all files
 *
 * @par       
 * COPYRIGHT NOTICE: (c) TP Industries Group.  All rights reserved.
 */ 

#ifndef UART_COMS
#define UART_COMS
#include <stdint.h>
#include "pico/unique_id.h"
#include "hardware/uart.h"
#include "hardware/dma.h"

#define UART_ID uart0
#define BAUD_RATE 250000
#define UART_TX_PIN 0
#define UART_RX_PIN 1

#define RX_MAX_LEN 113

#define RX_BUF_SIZE         256
#define RX_BUF_MASK         (RX_BUF_SIZE - 1)


typedef enum
{
    IDLE_CONNECTION,
    COM_CONNECTED,
    COM_BUSY,
    COM_FULL,
    COM_FULL_CONFIRMCON

} connection_status_t;

typedef struct __attribute__((packed))
{
    uint8_t chip_id[8];
    uint8_t  handshake_value;
    uint8_t device_number;
    uint8_t data[100];
    uint16_t payload_length;

} handshake_packet_t;

extern connection_status_t conn_stat;

// void handle_uart_rcv();

void uart_dma_write(const uint8_t *data, size_t len);
void process_rx_dma(void);
void serial_init(void);
void handle_uart_rcv(void);

#endif