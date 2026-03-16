#include "i2c_drive.h"
#include "pico/binary_info.h"

// Initializes both I2C and fills the MCP4725
void mcp4725_init(mcp4725_t *dev)
{
    i2c_init(I2C_PORT, I2C_SPEED);
    gpio_set_function(I2C_SDA, GPIO_FUNC_I2C);
    gpio_set_function(I2C_SCL, GPIO_FUNC_I2C);
    gpio_pull_up(I2C_SDA);
    gpio_pull_up(I2C_SCL);
    bi_decl(bi_2pins_with_func(I2C_SDA, I2C_SCL, GPIO_FUNC_I2C));
    // mcp4725_fill(dev, I2C_PORT, MCP4725_ADDR_DEFAULT);
}

// Fills the mcp4725 struct
void mcp4725_fill(mcp4725_t *dev, i2c_inst_t *i2c, uint8_t addr) 
{
    dev->i2c  = i2c;
    dev->addr = addr;
}

// Fast write — 2 bytes, updates VOUT immediately, does NOT touch EEPROM.
// value: 12-bit DAC code, 0x000–0xFFF
// Returns number of bytes written should be 2
int mcp4725_write_fast(mcp4725_t *dev, uint16_t value) 
{
    if (value > 0xFFF) value = 0xFFF;

    // datasheet Figure 6-1:
    //   Byte 0: [0 0 | PD1 PD0 | D11 D10 D9 D8]
    //   Byte 1: [D7  D6  D5  D4  D3  D2  D1  D0]
    uint8_t buf[2];
    buf[0] = (uint8_t)((value >> 8) & 0x0F);  // top 4 bits of value; cmd bits 00 already zero
    buf[1] = (uint8_t)(value & 0xFF);          // bottom 8 bits

    return i2c_write_blocking(dev->i2c, dev->addr, buf, 2, false);
}

// Normal write — 3 bytes. Updates DAC register.
// Set write_eeprom=true to also persist the value to EEPROM (slower, ~25ms).
// value: 12-bit DAC code, 0x000–0xFFF
int mcp4725_write(mcp4725_t *dev, uint16_t value, bool write_eeprom)
{
    if (value > 0xFFF) value = 0xFFF;

    // datasheet Figure 6-2:
    //   Byte 0: command byte  [C2 C1 C0 | x | PD1 PD0 | x x]
    //   Byte 1: upper data    [D11 D10 D9 D8 D7 D6 D5 D4]
    //   Byte 2: lower data    [D3  D2  D1  D0  0  0  0  0]  (left-aligned)
    uint8_t buf[3];
    buf[0] = write_eeprom ? MCP4725_CMD_WRITE_DAC_EEPROM : MCP4725_CMD_WRITE_DAC;
    buf[1] = (uint8_t)(value >> 4);          // upper 8 bits  (D11..D4)
    buf[2] = (uint8_t)((value & 0xF) << 4); // lower 4 bits left-shifted into top nibble

    int ret = i2c_write_blocking(dev->i2c, dev->addr, buf, 3, false);

    if (write_eeprom) {
        // EEPROM write takes up to ~25ms
        sleep_ms(30);
    }

    return ret;
}

// Read back device status + current DAC and EEPROM values.
// Returns true on success.
// out_dac_value:    current DAC register value (12-bit)
// out_eeprom_value: value stored in EEPROM (12-bit)
// out_ready:        true if device is idle (EEPROM write not in progress)
bool mcp4725_read(mcp4725_t *dev,
                    uint16_t *out_dac_value,
                    uint16_t *out_eeprom_value,
                    bool     *out_ready) 
{
    // Datasheet Figure 6-3 - 5 bytes
    //   Byte 0: [RDY | POR | x | x | PD1 | PD0 | x | x]
    //   Byte 1: [D11 D10 D9 D8 D7 D6 D5 D4]    (DAC register upper)
    //   Byte 2: [D3  D2  D1  D0  x  x  x  x]   (DAC register lower)
    //   Byte 3: [x | PD1 | PD0 | x | E11..E8]  (EEPROM upper)
    //   Byte 4: [E7 E6 E5 E4 E3 E2 E1 E0]       (EEPROM lower)
    uint8_t buf[5];
    int ret = i2c_read_blocking(dev->i2c, dev->addr, buf, 5, false);
    if (ret != 5) return false;

    if (out_ready)        *out_ready        = (buf[0] & 0x80) != 0;
    if (out_dac_value)
        *out_dac_value = (((uint16_t)buf[1] << 4) | (buf[2] >> 4)) & 0x0FFF;
    if (out_eeprom_value)
        *out_eeprom_value = (((uint16_t)(buf[3] & 0x0F) << 8) | buf[4]) & 0x0FFF;

    return true;
}