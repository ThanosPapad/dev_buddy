/** @file in_out_ctrl.h
 * 
 * @brief Global information used and visible by all files
 *
 * @par       
 * COPYRIGHT NOTICE: (c) TP Industries Group.  All rights reserved.
 */ 

#ifndef IN_OUT_CTRL
#define IN_OUT_CTRL

#include <stdint.h>
#include <stdio.h>
#include "pico/stdlib.h"
#include "globals.h"


// Digital output channels state
typedef struct __attribute__((packed))
{
    uint8_t channel_0_out;
    uint8_t channel_1_out;
    uint8_t channel_2_out;
    uint8_t channel_3_out;
    uint8_t channel_4_out;
    uint8_t channel_5_out;
    uint8_t channel_6_out;
    uint8_t channel_7_out;
    uint8_t channel_8_out;
    uint8_t channel_9_out;
    uint8_t channel_10_out;

} output_control_t;

// Digital input channels state
typedef struct __attribute__((packed))
{
    uint8_t channel_0_in;
    uint8_t channel_1_in;
    uint8_t channel_2_in;
    uint8_t channel_3_in;
    uint8_t channel_4_in;
    uint8_t channel_5_in;
    uint8_t channel_6_in;
    uint8_t channel_7_in;
    uint8_t channel_8_in;
    uint8_t channel_9_in;
    uint8_t channel_10_in;

} input_read_t;

// ADC measurements struct
typedef struct __attribute__((packed))
{
    float voltage_meas;
    float current_meas;

} channel_adc_meas_t;

// Voltage measurements for all channels
typedef struct __attribute__((packed))
{
    channel_adc_meas_t ch_adc_meas_0;
    channel_adc_meas_t ch_adc_meas_1;
    channel_adc_meas_t ch_adc_meas_2;
    channel_adc_meas_t ch_adc_meas_3;
    channel_adc_meas_t ch_adc_meas_4;
    channel_adc_meas_t ch_adc_meas_5;
    channel_adc_meas_t ch_adc_meas_6;
    channel_adc_meas_t ch_adc_meas_7;

} channel_voltages_t;

//TODO Have to put in here the actual pin numbers
// Digital Output channel pins
typedef enum {
    CHANNEL_OUT_0 = 13,
    CHANNEL_OUT_1 = 14,
    CHANNEL_OUT_2 = 15,
    CHANNEL_OUT_3,
    CHANNEL_OUT_4,
    CHANNEL_OUT_5,
    CHANNEL_OUT_6,
    CHANNEL_OUT_7,
    CHANNEL_OUT_8,
    CHANNEL_OUT_9,
    CHANNEL_OUT_10
} channel_pins_t;

// Digital Input channel pins
typedef enum {
    CHANNEL_READ_0 = 14,
    CHANNEL_READ_1 = 18,
    CHANNEL_READ_2 = 16,
    CHANNEL_READ_3,
    CHANNEL_READ_4,
    CHANNEL_READ_5,
    CHANNEL_READ_6,
    CHANNEL_READ_7,
    CHANNEL_READ_8,
    CHANNEL_READ_9,
    CHANNEL_READ_10
} in_channel_pins_t;

typedef enum {
    V_CHANNELS_ADC_PIN = 26,
    I_CHANNELS_ADC_PIN = 27
} adc_channel_pins_t;

// Variables used inside main
extern output_control_t out_status;
extern input_read_t in_status;
extern channel_voltages_t adc_meas;
extern bool output_set_flag;
extern bool read_ins_flag;

// Function defines
void toggle_led();
void pico_led_init(void);
void pico_set_led(bool led_on);
void update_outputs();
void init_outputs();
void init_inputs();
void read_input_channels (input_read_t *packet);
void adc_init_internal ();
channel_voltages_t read_adc_channels ();
void read_adc_channels_wrapper(void *ctx);

#endif