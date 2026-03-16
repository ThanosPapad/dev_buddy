# Configuration constants for the serial communication tool

# Handshake packet configuration
HANDSHAKE_VALUE = 111  # 0x6F in decimal
SET_HANDSHAKE_VALUE = 21  # 0x15 in decimal for set operations
INPUTS_HANDSHAKE_VALUE = 22  # 0x16 in decimal for inputs operations
INPUTS_RESPONSE_HANDSHAKE_VALUE = 23  # 0x17 in decimal for inputs response
DEVICE_NUMBER = 99     # 0x63 in decimal
PAYLOAD_LENGTH = 112   # 0x70 in decimal (updated from 12 to 112)
RESPONSE_HANDSHAKE_VALUE = 112  # Expected response value (0x70)

# ADC interval / state packet types (matches packet_type_t enum in firmware)
SET_ADC_INTERVAL_REQ         = 11   # 0x0B — request to change ADC timer period
SET_ADC_INTERVAL_RESP        = 12   # 0x0C — device confirms new period
SET_ADC_INTERVAL_STATE_REQ   = 13   # 0x0D — enable / disable ADC timer
SET_ADC_INTERVAL_STATE_RESP  = 14   # 0x0E — device confirms state change
ADC_TELEMETRY_TRANS          = 102  # 0x66 — unsolicited ADC telemetry frame

# DAC control packet types
SET_DAC_VALUE_REQ            = 31   # 0x1F — set DAC1 and DAC2 output values
SET_DAC_VALUE_RESP           = 32   # 0x20 — device confirms new DAC values

# Number of ADC channels exposed by channel_voltages_t
ADC_CHANNEL_COUNT = 8

# Timeout settings
RESPONSE_TIMEOUT = 5  # seconds (reduced from 30 to 5)

# Serial port settings
DEFAULT_BAUDRATE = 250000
BYTESIZE = 8
PARITY = 'N'
STOPBITS = 1

# Packet structure sizes
CHIP_ID_SIZE = 8  # bytes for pico_unique_board_id_t
HANDSHAKE_PACKET_SIZE = CHIP_ID_SIZE + 1 + 1 + 100 + 2  # 112 bytes total (updated)

# GUI settings
WINDOW_WIDTH = 600
WINDOW_HEIGHT = 200

# Input status update settings
INPUT_UPDATE_INTERVAL = 2  # seconds between automatic input status updates