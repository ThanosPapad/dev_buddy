/** @file tinmer_handler.h
 * 
 * @brief Global information used and visible by all files
 *
 * @par       
 * COPYRIGHT NOTICE: (c) TP Industries Group.  All rights reserved.
 */ 

#ifndef TIMER_HANDLER
#define TIMER_HANDLER

#include <stdint.h>
#include <stdio.h>
#include "pico/stdlib.h"
#include "globals.h"

typedef struct
{
    uint32_t interval_ms;
    absolute_time_t next_time;
    void (*callback)(void);
    bool initialized;
    bool enabled;
} repeat_timer_t;

typedef struct {
    uint32_t interval_ms;
    absolute_time_t next_time;
    bool initialized;
    void (*callback)(void*);
    void *context;
    bool enabled;
} repeat_timer_ex_t;

extern repeat_timer_t led_timer;
extern repeat_timer_t adc_tlm_timer;
extern repeat_timer_ex_t adc_timer;

void repeat_every(repeat_timer_t *timer,
                  uint32_t interval_ms,
                  void (*callback)(void));
void repeat_every_ex(repeat_timer_ex_t *timer,
                     uint32_t interval_ms,
                     void (*callback)(void*),
                     void *context);
void timer_enable_ex(repeat_timer_ex_t *timer);
void timer_disable_ex(repeat_timer_ex_t *timer);
void timer_enable(repeat_timer_t *timer);
void timer_disable(repeat_timer_t *timer);
bool change_timer_period_ex(repeat_timer_ex_t *timer, uint32_t new_period_ms);
bool change_timer_period(repeat_timer_t *timer, uint32_t new_period_ms);

#endif