/**
 * UART with DMA for RP2350
 */

#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "inc/globals.h"
#include "inc/uart_coms.h"
#include "pico/unique_id.h"
#include "pico/multicore.h"
#include "in_out_ctrl.h"
#include "timer_handler.h"
#include "i2c_drive.h"
#include "usb_descriptors.h"
#include "tusb.h"
#include "uart_rx_pio.h"

connection_status_t conn_stat = IDLE_CONNECTION;
output_control_t out_status = {0};
input_read_t in_status = {0};
channel_voltages_t adc_meas = {0};

repeat_timer_t led_timer = {0};
repeat_timer_t adc_tlm_timer = {0};
repeat_timer_ex_t adc_timer = {0};

bool output_set_flag = 0;
bool read_ins_flag = 0;
bool set_dac_flag = 0;

uint16_t set_dac_1_value = 2047;
uint16_t set_dac_2_value = 2047;

mcp4725_t dac;
mcp4725_t dac_2;

volatile bool usb_active = false;


// Here runs core 1
void core1_entry() {
    // Only initialize the tlm timer so it doesn't start straight away
    adc_tlm_timer.interval_ms = 1000;
    adc_tlm_timer.callback = transmit_adc_meas;
    adc_tlm_timer.next_time = make_timeout_time_ms(1000);
    adc_tlm_timer.initialized = true;
    adc_tlm_timer.enabled = false;
    
    mcp4725_fill(&dac, I2C_PORT, MCP4725_ADDR_DEFAULT);
    mcp4725_init(&dac);
    mcp4725_fill(&dac_2, I2C_PORT, MCP4725_ADDR_SECOND);
    mcp4725_init(&dac_2);

    int res = mcp4725_write_fast(&dac, 1595);
    if (res == PICO_ERROR_GENERIC)
    {
        sleep_ms(100);
    }

    uint16_t dac_val, eeprom_val;
    bool ready;
    mcp4725_read(&dac, &dac_val, &eeprom_val, &ready);

    while (1){

        if(output_set_flag == true) update_outputs();
        if(read_ins_flag == true) read_input_channels(&in_status);
        repeat_every_ex(&adc_timer, 100, read_adc_channels_wrapper, &adc_meas);
        if(conn_stat == COM_CONNECTED){
            repeat_every(&adc_tlm_timer, 1000, transmit_adc_meas);
        } 
        if (set_dac_flag == true){
            mcp4725_write_fast (&dac, set_dac_1_value);
            mcp4725_write_fast (&dac_2, set_dac_2_value);
            set_dac_flag = false;
        }
        tight_loop_contents();
        // sleep_ms(100);
    }  
}

// Here runs core 0
int main() {
    pico_led_init();
    init_inputs();
    init_outputs();
    adc_init_internal();
    tusb_init();
    serial_init();
    pio_uart_init_all(PIO_UART_BAUD_DEFAULT);
    aggregator_init();

    multicore_launch_core1(core1_entry);

    while (true) {

        process_rx_dma();

        handle_uart_rcv();

        pio_uart_tx_update();

        repeat_every(&led_timer, 1000, toggle_led);

        tud_task();

        feed_usb_rx();

        aggregator_update();
        transmit_pio_uart_channels();

        tight_loop_contents();
    }
}