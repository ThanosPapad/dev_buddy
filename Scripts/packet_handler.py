import struct
from typing import Tuple, Optional, List
from config import HANDSHAKE_VALUE, SET_HANDSHAKE_VALUE, DEVICE_NUMBER, PAYLOAD_LENGTH, RESPONSE_HANDSHAKE_VALUE, CHIP_ID_SIZE

def create_handshake_packet() -> bytes:
    """
    Create a handshake packet with the specified format.
    
    Returns:
        bytes: Packed handshake packet in little endian format (112 bytes)
        
    Packet structure:
    - First 8 bytes: chip_id (empty)
    - 9th byte: handshake_value (111)
    - 10th byte: device_number (99)
    - Next 100 bytes: data_incoming (filled with zeros)
    - Final 2 bytes: payload_length (112)
    """
    # Create empty chip ID (8 bytes)
    chip_id = b'\x00\x00\x00\x00\x00\x00\x00\x00'
    
    # Create data_incoming field (100 bytes of zeros)
    data_incoming = b'\x00' * 100
    
    # Pack the entire structure in little endian format
    # Format: <8B B B 100B H (8 bytes + 1 byte + 1 byte + 100 bytes + 2 bytes = 112 bytes)
    packet = struct.pack('<8B B B 100B H', 
                        *chip_id, 
                        HANDSHAKE_VALUE, 
                        DEVICE_NUMBER, 
                        *data_incoming, 
                        PAYLOAD_LENGTH)
    
    return packet

def create_set_packet(device_id: bytes, channel_data: List[int]) -> bytes:
    """
    Create a set packet with the specified format.
    
    Args:
        device_id: 8 bytes representing the device ID from handshake response
        channel_data: List of channel states (first 11 bytes of data array)
        
    Returns:
        bytes: Packed set packet in little endian format (112 bytes)
        
    Packet structure:
    - First 8 bytes: chip_id (from handshake response)
    - 9th byte: handshake_value (21 for set operations)
    - 10th byte: device_number (99)
    - Next 100 bytes: data array (first 11 bytes from channel_data, rest zeros)
    - Final 2 bytes: payload_length (112)
    """
    # Validate device_id length
    if len(device_id) != CHIP_ID_SIZE:
        raise ValueError(f"device_id must be {CHIP_ID_SIZE} bytes long")
    
    # Create data array with channel states and zeros
    data_array = bytearray(100)
    
    # Fill first 11 bytes with channel states
    for i in range(min(11, len(channel_data))):
        data_array[i] = 1 if channel_data[i] else 0
    
    # Pack the entire structure in little endian format
    # Format: <8B B B 100B H (8 bytes + 1 byte + 1 byte + 100 bytes + 2 bytes = 112 bytes)
    packet = struct.pack('<8B B B 100B H', 
                        *device_id, 
                        SET_HANDSHAKE_VALUE, 
                        DEVICE_NUMBER, 
                        *data_array, 
                        PAYLOAD_LENGTH)
    
    return packet

def verify_response_packet(response_data: bytes) -> Tuple[bool, Optional[bytes]]:
    """
    Verify a response packet received from the device.
    
    Args:
        response_data: Raw bytes received from the serial port (should be 112 bytes + 0x0A terminator)
        
    Returns:
        Tuple of (is_valid, device_id)
        - is_valid: True if packet is valid, False otherwise
        - device_id: The first 8 bytes (chip_id) if valid, None otherwise
    """
    # Extract the actual packet data (remove terminator if present)
    if len(response_data) > 0 and response_data[-1] == 0x0A:
        # Remove the newline terminator
        packet_data = response_data[:-1]
    else:
        packet_data = response_data
    
    # Only check the handshake value change (111 → 112)
    # The 9th byte (index 8) should be 112 (0x70)
    if packet_data[8] != RESPONSE_HANDSHAKE_VALUE:
        return False, None
    
    # Return chip ID regardless of packet size
    return True, packet_data[:CHIP_ID_SIZE]