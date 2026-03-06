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

connection_status_t conn_stat = IDLE_CONNECTION;
output_control_t out_status = {0};
input_read_t in_status = {0};
channel_voltages_t adc_meas = {0};

repeat_timer_t led_timer = {0};
repeat_timer_t adc_tlm_timer = {0};
repeat_timer_ex_t adc_timer = {0};

bool output_set_flag = 0;
bool read_ins_flag = 0;



// Here runs core 1
void core1_entry() {
    // Only initialize the tlm timer so it doesn't start straight away
    adc_tlm_timer.interval_ms = 1000;
    adc_tlm_timer.callback = transmit_adc_meas;
    adc_tlm_timer.next_time = make_timeout_time_ms(1000);
    adc_tlm_timer.initialized = true;
    adc_tlm_timer.enabled = false;

    while (1){

        if(output_set_flag == true) update_outputs();
        if(read_ins_flag == true) read_input_channels(&in_status);
        repeat_every_ex(&adc_timer, 100, read_adc_channels_wrapper, &adc_meas);
        if(conn_stat == COM_CONNECTED){
            repeat_every(&adc_tlm_timer, 1000, transmit_adc_meas);
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
    serial_init();
    

    multicore_launch_core1(core1_entry);

    while (true) {

        process_rx_dma();

        handle_uart_rcv();

        repeat_every(&led_timer, 1000, toggle_led);

        tight_loop_contents();
    }
}