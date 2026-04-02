#ifndef USB_DESCRIPTORS
#define USB_DESCRIPTORS

#define USB_VID   0x2E8A
#define USB_PID   0x000A  // CDC device

#include "tusb.h"

// ---- Configuration descriptor ----
#define CONFIG_TOTAL_LEN  (TUD_CONFIG_DESC_LEN + TUD_CDC_DESC_LEN)
#define EPNUM_CDC_NOTIF   0x81
#define EPNUM_CDC_OUT     0x02
#define EPNUM_CDC_IN      0x82


uint8_t const* tud_descriptor_device_cb(void);
uint8_t const* tud_descriptor_configuration_cb(uint8_t index);
uint16_t const* tud_descriptor_string_cb(uint8_t index, uint16_t langid);

#endif