import struct
from typing import Tuple, Optional, List
from config import (HANDSHAKE_VALUE, SET_HANDSHAKE_VALUE,
                    INPUTS_HANDSHAKE_VALUE, INPUTS_RESPONSE_HANDSHAKE_VALUE,
                    DEVICE_NUMBER, PAYLOAD_LENGTH, RESPONSE_HANDSHAKE_VALUE,
                    CHIP_ID_SIZE,
                    SET_ADC_INTERVAL_REQ, SET_ADC_INTERVAL_RESP,
                    SET_ADC_INTERVAL_STATE_REQ, SET_ADC_INTERVAL_STATE_RESP,
                    ADC_TELEMETRY_TRANS, ADC_CHANNEL_COUNT)


# ─────────────────────────────────────────────────────────────────────────────
# Existing packet builders
# ─────────────────────────────────────────────────────────────────────────────

def create_handshake_packet() -> bytes:
    """
    Create a handshake packet with the specified format.

    Packet structure (112 bytes, little-endian):
      [0:8]   chip_id        – 8 bytes, zeros (host doesn't know its own id)
      [8]     handshake_value – 111  (INCOMING_HANDSHKE_REQ)
      [9]     device_number  – 99
      [10:110] data_incoming  – 100 bytes zeros
      [110:112] payload_length – 112 (uint16 LE)
    """
    chip_id      = b'\x00' * 8
    data_incoming = b'\x00' * 100
    packet = struct.pack('<8B B B 100B H',
                         *chip_id,
                         HANDSHAKE_VALUE,
                         DEVICE_NUMBER,
                         *data_incoming,
                         PAYLOAD_LENGTH)
    return packet


def create_set_packet(device_id: bytes, channel_data: List[int]) -> bytes:
    """
    Create a SET_DEVICE_OUTPUTS packet (handshake_value = 21).

    First 11 bytes of the data field carry output channel states (0 or 1).
    """
    if len(device_id) != CHIP_ID_SIZE:
        raise ValueError(f"device_id must be {CHIP_ID_SIZE} bytes long")

    data_array = bytearray(100)
    for i in range(min(11, len(channel_data))):
        data_array[i] = 1 if channel_data[i] else 0

    packet = struct.pack('<8B B B 100B H',
                         *device_id,
                         SET_HANDSHAKE_VALUE,
                         DEVICE_NUMBER,
                         *data_array,
                         PAYLOAD_LENGTH)
    return packet


def create_inputs_packet(device_id: bytes) -> bytes:
    """
    Create a GET_DEVICE_OUTPUTS_REQ packet (handshake_value = 22).
    """
    if len(device_id) != CHIP_ID_SIZE:
        raise ValueError(f"device_id must be {CHIP_ID_SIZE} bytes long")

    data_array = b'\x00' * 100
    packet = struct.pack('<8B B B 100B H',
                         *device_id,
                         INPUTS_HANDSHAKE_VALUE,
                         DEVICE_NUMBER,
                         *data_array,
                         PAYLOAD_LENGTH)
    return packet


# ─────────────────────────────────────────────────────────────────────────────
# NEW — ADC interval control packets
# ─────────────────────────────────────────────────────────────────────────────

def create_set_adc_interval_packet(device_id: bytes, interval_ms: int) -> bytes:
    """
    Build a SET_ADC_INTERVAL_REQ packet (handshake_value = 11).

    The firmware expects the new timer period as a uint32_t in the first
    4 bytes of the data field, little-endian:

        pack.data[0..3] = new_adc_interval (uint32_t LE)

    Args:
        device_id:   8-byte chip ID from the handshake response.
        interval_ms: New ADC timer period in milliseconds (uint32).

    Returns:
        112-byte packet ready to write to the serial port (append \\x0A).
    """
    if len(device_id) != CHIP_ID_SIZE:
        raise ValueError(f"device_id must be {CHIP_ID_SIZE} bytes long")

    data_array = bytearray(100)
    # Pack interval as uint32 little-endian into bytes 0-3 of the data field.
    # This matches the firmware decode:
    #   new_adc_interval = data[0] | (data[1]<<8) | (data[2]<<16) | (data[3]<<24)
    struct.pack_into('<I', data_array, 0, interval_ms)

    packet = struct.pack('<8B B B 100B H',
                         *device_id,
                         SET_ADC_INTERVAL_REQ,
                         DEVICE_NUMBER,
                         *data_array,
                         PAYLOAD_LENGTH)
    return packet


def create_set_adc_interval_state_packet(device_id: bytes, enable: bool) -> bytes:
    """
    Build a SET_ADC_INTERVAL_STATE_REQ packet (handshake_value = 13).

    The firmware checks data[0]:
        1  → timer_enable()
        0  → timer_disable()

    Args:
        device_id: 8-byte chip ID from the handshake response.
        enable:    True to start the ADC timer, False to stop it.

    Returns:
        112-byte packet ready to write to the serial port (append \\x0A).
    """
    if len(device_id) != CHIP_ID_SIZE:
        raise ValueError(f"device_id must be {CHIP_ID_SIZE} bytes long")

    data_array = bytearray(100)
    data_array[0] = 1 if enable else 0

    packet = struct.pack('<8B B B 100B H',
                         *device_id,
                         SET_ADC_INTERVAL_STATE_REQ,
                         DEVICE_NUMBER,
                         *data_array,
                         PAYLOAD_LENGTH)
    return packet


# ─────────────────────────────────────────────────────────────────────────────
# NEW — ADC response / telemetry parsers
# ─────────────────────────────────────────────────────────────────────────────

def verify_adc_interval_response(response_data: bytes) -> Tuple[bool, Optional[int], Optional[bool]]:
    """
    Parse a SET_ADC_INTERVAL_RESP packet (handshake_value = 12).

    The firmware sends back:
        data[0]    = (uint8_t) success flag  (1 = ok, 0 = fail)
        data[1..4] = new_adc_interval echoed back as uint32 LE

    Returns:
        (is_valid, new_interval_ms, success)
        All None / False on parse failure.
    """
    packet_data = _strip_terminator(response_data)
    if len(packet_data) < 112:
        return False, None, None
    if packet_data[8] != SET_ADC_INTERVAL_RESP:
        return False, None, None

    # data field starts at byte 10
    success      = packet_data[10] != 0
    new_interval = struct.unpack_from('<I', packet_data, 11)[0]
    return True, new_interval, success


def verify_adc_state_response(response_data: bytes) -> Tuple[bool, Optional[bool]]:
    """
    Parse a SET_ADC_INTERVAL_STATE_RESP packet (handshake_value = 14).

    The firmware just echoes the packet back with the updated handshake_value;
    we treat reception of a valid packet as confirmation.

    Returns:
        (is_valid, acknowledged)
    """
    packet_data = _strip_terminator(response_data)
    if len(packet_data) < 112:
        return False, None
    if packet_data[8] != SET_ADC_INTERVAL_STATE_RESP:
        return False, None
    return True, True


def parse_adc_telemetry_packet(response_data: bytes) -> Tuple[bool, Optional[List[Tuple[float, float]]]]:
    """
    Parse an ADC_TELEMETRY_TRANS packet (handshake_value = 102).

    The firmware packs a channel_voltages_t into pack.data, which is a
    sequence of 8 × channel_adc_meas_t structs, each containing two
    IEEE-754 single-precision floats (voltage_meas, current_meas).

    Layout inside data field (bytes 0..63):
        [0..3]   ch0 voltage   (float32 LE)
        [4..7]   ch0 current   (float32 LE)
        [8..11]  ch1 voltage
        [12..15] ch1 current
        ...

    Returns:
        (is_valid, [(voltage, current), ...])   — list of 8 tuples, or None.
    """
    packet_data = _strip_terminator(response_data)
    if len(packet_data) < 112:
        return False, None
    if packet_data[8] != ADC_TELEMETRY_TRANS:
        return False, None

    # data field starts at byte 10; each channel = 2 × float32 = 8 bytes
    # 8 channels × 8 bytes = 64 bytes — well within the 100-byte data field
    channels = []
    offset = 10  # start of data field in the flat packet
    for _ in range(ADC_CHANNEL_COUNT):
        voltage, current = struct.unpack_from('<ff', packet_data, offset)
        channels.append((voltage, current))
        offset += 8  # sizeof(channel_adc_meas_t)

    return True, channels


# ─────────────────────────────────────────────────────────────────────────────
# Existing response verifiers (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def verify_response_packet(response_data: bytes) -> Tuple[bool, Optional[bytes]]:
    """
    Verify the initial handshake response (handshake_value 111 → 112).

    Returns (is_valid, device_id_bytes).
    """
    packet_data = _strip_terminator(response_data)
    if len(packet_data) < CHIP_ID_SIZE + 1:
        return False, None
    if packet_data[8] != RESPONSE_HANDSHAKE_VALUE:
        return False, None
    return True, packet_data[:CHIP_ID_SIZE]


def verify_inputs_response_packet(response_data: bytes) -> Tuple[bool, Optional[List[int]]]:
    """
    Verify a GET_DEVICE_OUTPUTS_RESP packet (handshake_value = 23).

    Returns (is_valid, [11 channel states]).
    """
    packet_data = _strip_terminator(response_data)
    if len(packet_data) < 112:
        return False, None
    if packet_data[8] != INPUTS_RESPONSE_HANDSHAKE_VALUE:
        return False, None

    channel_states = []
    for i in range(11):
        channel_states.append(1 if packet_data[10 + i] > 0 else 0)
    return True, channel_states


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _strip_terminator(data: bytes) -> bytes:
    """Remove trailing 0x0A terminator if present."""
    if data and data[-1] == 0x0A:
        return data[:-1]
    return data