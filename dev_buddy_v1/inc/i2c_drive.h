/** @file i2c_drive.h
 * 
 * @brief Global information used and visible by all files
 *
 * @par       
 * COPYRIGHT NOTICE: (c) TP Industries Group.  All rights reserved.
 */ 

#ifndef I2C_DRIVE
#define I2C_DRIVE

#include <stdint.h>
#include <stdio.h>
#include "pico/stdlib.h"
#include <stdbool.h>
#include "globals.h"
#include "hardware/i2c.h"

#define I2C_PORT   i2c0
#define I2C_SDA    4
#define I2C_SCL    5
#define I2C_SPEED  100000

#define MCP4725_ADDR_DEFAULT  0x60
#define MCP4725_ADDR_SECOND   0x61

#define MCP4725_CMD_WRITE_DAC         0x40  // Write DAC register only
#define MCP4725_CMD_WRITE_DAC_EEPROM  0x60  // Write DAC register AND EEPROM

#define MCP4725_PD_NORMAL    0x00
#define MCP4725_PD_1K        0x02
#define MCP4725_PD_100K      0x04
#define MCP4725_PD_500K      0x06

typedef struct {
    i2c_inst_t *i2c;
    uint8_t     addr;
} mcp4725_t;

void mcp4725_init(mcp4725_t *dev);
void mcp4725_fill(mcp4725_t *dev, i2c_inst_t *i2c, uint8_t addr);
int mcp4725_write_fast(mcp4725_t *dev, uint16_t value);
int mcp4725_write(mcp4725_t *dev, uint16_t value, bool write_eeprom);
bool mcp4725_read(mcp4725_t *dev, uint16_t *out_dac_value, uint16_t *out_eeprom_value, bool *out_ready);

#endif