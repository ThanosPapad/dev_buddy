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

extern output_control_t out_status;
extern bool output_set_flag;

extern input_read_t in_status;

//TODO Have to put in here the actual pin numbers
typedef enum {
    CHANNEL_OUT_0 = 15,
    CHANNEL_OUT_1 = 19,
    CHANNEL_OUT_2 = 17,
    CHANNEL_OUT_3,
    CHANNEL_OUT_4,
    CHANNEL_OUT_5,
    CHANNEL_OUT_6,
    CHANNEL_OUT_7,
    CHANNEL_OUT_8,
    CHANNEL_OUT_9,
    CHANNEL_OUT_10
} channel_pins_t;

typedef enum {
    CHANNEL_ΙΝ_0 = 14,
    CHANNEL_ΙΝ_1 = 18,
    CHANNEL_ΙΝ_2 = 16,
    CHANNEL_ΙΝ_3,
    CHANNEL_ΙΝ_4,
    CHANNEL_ΙΝ_5,
    CHANNEL_ΙΝ_6,
    CHANNEL_ΙΝ_7,
    CHANNEL_ΙΝ_8,
    CHANNEL_ΙΝ_9,
    CHANNEL_ΙΝ_10
} in_channel_pins_t;

void toggle_led();
void pico_led_init(void);
void pico_set_led(bool led_on);
void update_outputs();
void init_outputs();
void init_inputs();

#endif