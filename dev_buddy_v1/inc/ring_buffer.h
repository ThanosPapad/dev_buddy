#ifndef RING_BUFFER_H
#define RING_BUFFER_H

// ring_buffer.h
#include <stdint.h>
#include <stdbool.h>
#include <string.h>

// Power-of-2 size → allows fast index masking instead of modulo
#define RING_BUFFER_SIZE  256          // must be a power of 2
#define RING_BUFFER_MASK  (RING_BUFFER_SIZE - 1)

typedef struct {
    volatile uint8_t  buf[RING_BUFFER_SIZE];
    volatile uint16_t head;   // IRQ writes here
    volatile uint16_t tail;   // main loop reads here
} ring_buffer_t;

// Called from IRQ — writes one byte, silently drops if full
static inline void rb_push(ring_buffer_t *rb, uint8_t byte) {
    uint16_t next_head = (rb->head + 1) & RING_BUFFER_MASK;
    if (next_head == rb->tail) return;   // full — drop byte (you can count these later)
    rb->buf[rb->head] = byte;
    rb->head = next_head;
}

// Called from main loop — returns true if a byte was available
static inline bool rb_pop(ring_buffer_t *rb, uint8_t *out) {
    if (rb->tail == rb->head) return false;   // empty
    *out = rb->buf[rb->tail];
    rb->tail = (rb->tail + 1) & RING_BUFFER_MASK;
    return true;
}

// How many bytes are currently sitting in the buffer
static inline uint16_t rb_available(ring_buffer_t *rb) {
    return (rb->head - rb->tail) & RING_BUFFER_MASK;
}

// Wipe the buffer (use carefully — not IRQ safe)
static inline void rb_flush(ring_buffer_t *rb) {
    rb->head = rb->tail = 0;
}

#endif