#include "in_out_ctrl.h"
#include "hardware/adc.h"
#include "uart_coms.h"

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
    gpio_put((uint)CHANNEL_OUT_0, out_status.channel_0_out);
    gpio_put((uint)CHANNEL_OUT_1, out_status.channel_1_out);
    gpio_put((uint)CHANNEL_OUT_2, out_status.channel_2_out);
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
output_set_flag = false;
}

void init_outputs()
{
    gpio_init((uint)CHANNEL_OUT_0);
    gpio_set_dir((uint)CHANNEL_OUT_0, GPIO_OUT);
    gpio_init((uint)CHANNEL_OUT_1);
    gpio_set_dir((uint)CHANNEL_OUT_1, GPIO_OUT);
    gpio_init((uint)CHANNEL_OUT_2);
    gpio_set_dir((uint)CHANNEL_OUT_2, GPIO_OUT);
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
void init_inputs()
{
#ifdef OUTPUTS_READY   
    gpio_init((uint)CHANNEL_READ_0);
    gpio_set_dir((uint)CHANNEL_READ_0, GPIO_IN);
    gpio_pull_down((uint)CHANNEL_READ_0);
    gpio_init((uint)CHANNEL_READ_1);
    gpio_set_dir((uint)CHANNEL_READ_1, GPIO_IN);
    gpio_pull_down((uint)CHANNEL_READ_1);
    gpio_init((uint)CHANNEL_READ_2);
    gpio_set_dir((uint)CHANNEL_READ_2, GPIO_IN);
    gpio_pull_down((uint)CHANNEL_READ_2);
    gpio_init((uint)CHANNEL_READ_3);
    gpio_set_dir((uint)CHANNEL_READ_3, GPIO_IN);
    gpio_pull_down((uint)CHANNEL_READ_3);
    gpio_init((uint)CHANNEL_READ_4);
    gpio_set_dir((uint)CHANNEL_READ_4, GPIO_IN);
    gpio_pull_down((uint)CHANNEL_READ_4);
    gpio_init((uint)CHANNEL_READ_5);
    gpio_set_dir((uint)CHANNEL_READ_5, GPIO_IN);
    gpio_pull_down((uint)CHANNEL_READ_5);
    gpio_init((uint)CHANNEL_READ_6);
    gpio_set_dir((uint)CHANNEL_READ_6, GPIO_IN);
    gpio_pull_down((uint)CHANNEL_READ_6);
    gpio_init((uint)CHANNEL_READ_7);
    gpio_set_dir((uint)CHANNEL_READ_7, GPIO_IN);
    gpio_pull_down((uint)CHANNEL_READ_7);
    gpio_init((uint)CHANNEL_READ_8);
    gpio_set_dir((uint)CHANNEL_READ_8, GPIO_IN);
    gpio_pull_down((uint)CHANNEL_READ_8);
    gpio_init((uint)CHANNEL_READ_9);
    gpio_set_dir((uint)CHANNEL_READ_9, GPIO_IN);
    gpio_pull_down((uint)CHANNEL_READ_9);
    gpio_init((uint)CHANNEL_READ_10);
    gpio_set_dir((uint)CHANNEL_READ_10, GPIO_IN);
    gpio_pull_down((uint)CHANNEL_READ_10);
#endif
}

void read_input_channels (input_read_t *packet)
{
#ifdef OUTPUTS_READY
    packet->channel_0_in = gpio_get((uint)CHANNEL_READ_0);
    packet->channel_0_in = gpio_get((uint)CHANNEL_READ_1);
    packet->channel_0_in = gpio_get((uint)CHANNEL_READ_2);
    packet->channel_0_in = gpio_get((uint)CHANNEL_READ_3);
    packet->channel_0_in = gpio_get((uint)CHANNEL_READ_4);
    packet->channel_0_in = gpio_get((uint)CHANNEL_READ_5);
    packet->channel_0_in = gpio_get((uint)CHANNEL_READ_6);
    packet->channel_0_in = gpio_get((uint)CHANNEL_READ_7);
    packet->channel_0_in = gpio_get((uint)CHANNEL_READ_8);
    packet->channel_0_in = gpio_get((uint)CHANNEL_READ_9);
    packet->channel_0_in = gpio_get((uint)CHANNEL_READ_10);
#else
    packet->channel_0_in = 1;
    packet->channel_1_in = 0;
    packet->channel_2_in = 1;
    packet->channel_3_in = 0;
    packet->channel_4_in = 1;
    packet->channel_5_in = 0;
    packet->channel_6_in = 1;
    packet->channel_7_in = 0;
    packet->channel_8_in = 1;
    packet->channel_9_in = 0;
    packet->channel_10_in = 1;
#endif
    read_ins_flag = false;
}

void adc_init_internal ()
{
    adc_init();
    adc_gpio_init(V_CHANNELS_ADC_PIN);
    adc_gpio_init(I_CHANNELS_ADC_PIN);

}

// Read all the channels
channel_voltages_t read_adc_channels ()
{
    channel_voltages_t res = {0};
    uint16_t raw = 0;
    const float conversion_factor = 3.3f / (1 << 12);  // 3.3V / 4096
    // TODO; Add more measurements for each reading to achieve better accuracy
    // TODO; Set MUX channel 0
    adc_select_input(0); // ADC0 - (GPIO26)
    raw = adc_read();    // (0-4095)
    res.ch_adc_meas_0.voltage_meas = raw * conversion_factor;
    adc_select_input(1);
    raw = adc_read();
    res.ch_adc_meas_0.current_meas = raw * conversion_factor;

    // TODO; Set MUX channel 1
    adc_select_input(0); // ADC0 - (GPIO26)
    raw = adc_read();    // (0-4095)
    res.ch_adc_meas_1.voltage_meas = raw * conversion_factor;
    adc_select_input(1);
    raw = adc_read();
    res.ch_adc_meas_1.current_meas = raw * conversion_factor;

    // TODO; Set MUX channel 2
    adc_select_input(0); // ADC0 - (GPIO26)
    raw = adc_read();    // (0-4095)
    res.ch_adc_meas_2.voltage_meas = raw * conversion_factor;
    adc_select_input(1);
    raw = adc_read();
    res.ch_adc_meas_2.current_meas = raw * conversion_factor;

    // TODO; Set MUX channel 3
    adc_select_input(0); // ADC0 - (GPIO26)
    raw = adc_read();    // (0-4095)
    res.ch_adc_meas_3.voltage_meas = raw * conversion_factor;
    adc_select_input(1);
    raw = adc_read();
    res.ch_adc_meas_3.current_meas = raw * conversion_factor;

    // TODO; Set MUX channel 4
    adc_select_input(0); // ADC0 - (GPIO26)
    raw = adc_read();    // (0-4095)
    res.ch_adc_meas_4.voltage_meas = raw * conversion_factor;
    adc_select_input(1);
    raw = adc_read();
    res.ch_adc_meas_4.current_meas = raw * conversion_factor;

    // TODO; Set MUX channel 5
    adc_select_input(0); // ADC0 - (GPIO26)
    raw = adc_read();    // (0-4095)
    res.ch_adc_meas_5.voltage_meas = raw * conversion_factor;
    adc_select_input(1);
    raw = adc_read();
    res.ch_adc_meas_5.current_meas = raw * conversion_factor;

    // TODO; Set MUX channel 6
    adc_select_input(0); // ADC0 - (GPIO26)
    raw = adc_read();    // (0-4095)
    res.ch_adc_meas_6.voltage_meas = raw * conversion_factor;
    adc_select_input(1);
    raw = adc_read();
    res.ch_adc_meas_6.current_meas = raw * conversion_factor;

    // TODO; Set MUX channel 7
    adc_select_input(0); // ADC0 - (GPIO26)
    raw = adc_read();    // (0-4095)
    res.ch_adc_meas_7.voltage_meas = raw * conversion_factor;
    adc_select_input(1);
    raw = adc_read();
    res.ch_adc_meas_7.current_meas = raw * conversion_factor;

    return res;
}
// Wrapper function in case it's needed for periodic run
void read_adc_channels_wrapper(void *ctx) 
{
    channel_voltages_t *dest = (channel_voltages_t*)ctx;
    *dest = read_adc_channels();
}