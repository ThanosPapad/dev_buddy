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

connection_status_t conn_stat = IDLE_CONNECTION;
output_control_t out_status = {0};
input_read_t in_status = {0};
bool output_set_flag = 0;

void repeat_every(repeat_timer_t *timer,
                  uint32_t interval_ms,
                  void (*callback)(void))
{
    // First time setup
    if (!timer->initialized)
    {
        timer->interval_ms = interval_ms;
        timer->callback = callback;
        timer->next_time = make_timeout_time_ms(interval_ms);
        timer->initialized = true;
        return;
    }

    // Check if time reached
    if (time_reached(timer->next_time))
    {
        timer->callback();

        // Schedule next execution WITHOUT drift
        timer->next_time = delayed_by_ms(timer->next_time,
                                         timer->interval_ms);
    }
}


// Here runs core 1
void core1_entry() {
    uint32_t counter = 0;
    while (1){
        counter++;
        if(output_set_flag == true) update_outputs();
        tight_loop_contents();
        // sleep_ms(1000);
    }  
}

// Here runs core 0
int main() {
    pico_led_init();
    init_inputs();
    init_outputs();
    serial_init();
    
    repeat_timer_t my_timer = {0};

    multicore_launch_core1(core1_entry);

    while (true) {

        process_rx_dma();

        handle_uart_rcv();

        repeat_every(&my_timer, 1000, toggle_led);

        tight_loop_contents();
    }
}