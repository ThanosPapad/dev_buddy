#include "timer_handler.h"

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
        timer->enabled = true;
        return;
    }

    // Check if time reached
    if (timer->enabled && time_reached(timer->next_time))
    {
        timer->callback();

        // Schedule next execution WITHOUT drift
        timer->next_time = delayed_by_ms(timer->next_time,
                                         timer->interval_ms);
    }
}

void repeat_every_ex(repeat_timer_ex_t *timer,
                     uint32_t interval_ms,
                     void (*callback)(void *),
                     void *context)
{
    // First time setup
    if (!timer->initialized)
    {
        timer->interval_ms = interval_ms;
        timer->callback = callback;
        timer->context = context;
        timer->next_time = make_timeout_time_ms(interval_ms);
        timer->initialized = true;
        timer->enabled = true; 
        return;
    }

    // Only run if enabled and time reached
    if (timer->enabled && time_reached(timer->next_time))
    {
        timer->callback(timer->context);
        timer->next_time = delayed_by_ms(timer->next_time,
                                         timer->interval_ms);
    }
}

void timer_enable_ex(repeat_timer_ex_t *timer)
{
    timer->enabled = true;
}

void timer_disable_ex(repeat_timer_ex_t *timer)
{
    timer->enabled = false;
}

void timer_enable(repeat_timer_t *timer)
{
    timer->enabled = true;
}

void timer_disable(repeat_timer_t *timer)
{
    timer->enabled = false;
}

bool change_timer_period_ex(repeat_timer_ex_t *timer, uint32_t new_period_ms)
{
    if (new_period_ms < 50)
    {
        new_period_ms = 50;
        timer->interval_ms = new_period_ms;
        return true;
    }
    else if (new_period_ms > 10000)
    {
        new_period_ms = 10000;
        timer->interval_ms = new_period_ms;
        return true;
    }
    timer->interval_ms = new_period_ms;
    return false;
}

bool change_timer_period(repeat_timer_t *timer, uint32_t new_period_ms)
{
    if (new_period_ms < 100)
    {
        new_period_ms = 100;
        timer->interval_ms = new_period_ms;
        return true;
    }
    else if (new_period_ms > 2000)
    {
        new_period_ms = 2000;
        timer->interval_ms = new_period_ms;
        return true;
    }
    timer->interval_ms = new_period_ms;
    return false;
}