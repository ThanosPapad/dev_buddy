/** @file globals.h
 * 
 * @brief Global information used and visible by all files
 *
 * @par       
 * COPYRIGHT NOTICE: (c) TP Industries Group.  All rights reserved.
 */ 

#ifndef MODULE_H
#define MODULE_H

#include "pico/stdlib.h"


//------ DEFINES START--------

// Uncomment this when ready to test outputs.
// #define OUTPUTS_READY

//------ DEFINES END--------


typedef struct
{
    uint32_t interval_ms;
    absolute_time_t next_time;
    void (*callback)(void);
    bool initialized;
} repeat_timer_t;

#endif /* MODULE_H */