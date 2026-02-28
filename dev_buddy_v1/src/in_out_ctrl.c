#include "in_out_ctrl.h"

void toggle_led()
{
    static bool led_status = 0;
    if (led_status == true){
        pico_set_led(false);
        led_status = false;
    }
    else if (led_status == false){
        pico_set_led(true);
        led_status = true;
    }
}

void pico_led_init(void)
{
    gpio_init(PICO_DEFAULT_LED_PIN);
    gpio_set_dir(PICO_DEFAULT_LED_PIN, GPIO_OUT);
}

// Turn the LED on or off
void pico_set_led(bool led_on)
{
    // Just set the GPIO on or off
    gpio_put(PICO_DEFAULT_LED_PIN, led_on);
}

void update_outputs()
{
#ifdef OUTPUTS_READY
    gpio_put((uint)CHANNEL_OUT_0, out_status.channel_0_out);
    gpio_put((uint)CHANNEL_OUT_1, out_status.channel_1_out);
    gpio_put((uint)CHANNEL_OUT_2, out_status.channel_2_out);
    gpio_put((uint)CHANNEL_OUT_3, out_status.channel_3_out);
    gpio_put((uint)CHANNEL_OUT_4, out_status.channel_4_out);
    gpio_put((uint)CHANNEL_OUT_5, out_status.channel_5_out);
    gpio_put((uint)CHANNEL_OUT_6, out_status.channel_6_out);
    gpio_put((uint)CHANNEL_OUT_7, out_status.channel_7_out);
    gpio_put((uint)CHANNEL_OUT_8, out_status.channel_8_out);
    gpio_put((uint)CHANNEL_OUT_9, out_status.channel_9_out);
    gpio_put((uint)CHANNEL_OUT_10, out_status.channel_10_out);
#endif
}

void init_outputs(){
#ifdef OUTPUTS_READY   
    gpio_init((uint)CHANNEL_OUT_0);
    gpio_set_dir((uint)CHANNEL_OUT_0, GPIO_OUT);
    gpio_init((uint)CHANNEL_OUT_1);
    gpio_set_dir((uint)CHANNEL_OUT_1, GPIO_OUT);
    gpio_init((uint)CHANNEL_OUT_2);
    gpio_set_dir((uint)CHANNEL_OUT_2, GPIO_OUT);
    gpio_init((uint)CHANNEL_OUT_3);
    gpio_set_dir((uint)CHANNEL_OUT_3, GPIO_OUT);
    gpio_init((uint)CHANNEL_OUT_4);
    gpio_set_dir((uint)CHANNEL_OUT_4, GPIO_OUT);
    gpio_init((uint)CHANNEL_OUT_5);
    gpio_set_dir((uint)CHANNEL_OUT_5, GPIO_OUT);
    gpio_init((uint)CHANNEL_OUT_6);
    gpio_set_dir((uint)CHANNEL_OUT_6, GPIO_OUT);
    gpio_init((uint)CHANNEL_OUT_7);
    gpio_set_dir((uint)CHANNEL_OUT_7, GPIO_OUT);
    gpio_init((uint)CHANNEL_OUT_8);
    gpio_set_dir((uint)CHANNEL_OUT_8, GPIO_OUT);
    gpio_init((uint)CHANNEL_OUT_9);
    gpio_set_dir((uint)CHANNEL_OUT_9, GPIO_OUT);
    gpio_init((uint)CHANNEL_OUT_10);
    gpio_set_dir((uint)CHANNEL_OUT_10, GPIO_OUT);
#endif
}
void init_inputs(){
#ifdef OUTPUTS_READY   
    gpio_init((uint)CHANNEL_IN_0);
    gpio_set_dir((uint)CHANNEL_IN_0, GPIO_IN);
    gpio_init((uint)CHANNEL_IN_1);
    gpio_set_dir((uint)CHANNEL_IN_1, GPIO_IN);
    gpio_init((uint)CHANNEL_IN_2);
    gpio_set_dir((uint)CHANNEL_IN_2, GPIO_IN);
    gpio_init((uint)CHANNEL_IN_3);
    gpio_set_dir((uint)CHANNEL_IN_3, GPIO_IN);
    gpio_init((uint)CHANNEL_IN_4);
    gpio_set_dir((uint)CHANNEL_IN_4, GPIO_IN);
    gpio_init((uint)CHANNEL_IN_5);
    gpio_set_dir((uint)CHANNEL_IN_5, GPIO_IN);
    gpio_init((uint)CHANNEL_IN_6);
    gpio_set_dir((uint)CHANNEL_IN_6, GPIO_IN);
    gpio_init((uint)CHANNEL_IN_7);
    gpio_set_dir((uint)CHANNEL_IN_7, GPIO_IN);
    gpio_init((uint)CHANNEL_IN_8);
    gpio_set_dir((uint)CHANNEL_IN_8, GPIO_IN);
    gpio_init((uint)CHANNEL_IN_9);
    gpio_set_dir((uint)CHANNEL_IN_9, GPIO_IN);
    gpio_init((uint)CHANNEL_IN_10);
    gpio_set_dir((uint)CHANNEL_IN_10, GPIO_IN);
#endif
}