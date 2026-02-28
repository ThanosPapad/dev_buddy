import serial.tools.list_ports
import platform
import os
from typing import List, Dict, Optional

def get_serial_devices() -> List[Dict[str, str]]:
    """
    Get a list of available serial devices on the current platform.
    
    Returns:
        List of dictionaries containing device information with 'name' and 'port' keys.
    """
    devices = []
    system = platform.system().lower()
    
    if system == "windows":
        # Use pyserial for Windows
        ports = serial.tools.list_ports.comports()
        for port in ports:
            device_info = {
                'name': port.description,
                'port': port.device
            }
            devices.append(device_info)
    
    elif system == "linux":
        # List devices in /dev/ that match typical serial patterns
        dev_dir = '/dev/'
        if os.path.exists(dev_dir):
            for device in os.listdir(dev_dir):
                if device.startswith('tty') and not device.startswith('tty0'):
                    port_path = os.path.join(dev_dir, device)
                    try:
                        # Get device description if available
                        description = device
                        if os.path.islink(port_path):
                            # Get the actual device file
                            real_path = os.path.realpath(port_path)
                            if 'usb' in real_path.lower():
                                description = f"USB Serial: {device}"
                            elif 'bluetooth' in real_path.lower():
                                description = f"Bluetooth: {device}"
                        
                        device_info = {
                            'name': description,
                            'port': port_path
                        }
                        devices.append(device_info)
                    except Exception:
                        continue
    
    elif system == "darwin":  # macOS
        # List devices in /dev/ that match typical serial patterns
        dev_dir = '/dev/'
        if os.path.exists(dev_dir):
            for device in os.listdir(dev_dir):
                if (device.startswith('tty.') or device.startswith('cu.')) and device not in ['tty0', 'console']:
                    port_path = os.path.join(dev_dir, device)
                    try:
                        # Get device description based on name
                        description = device
                        if 'usb' in device.lower():
                            description = f"USB Serial: {device}"
                        elif 'bluetooth' in device.lower():
                            description = f"Bluetooth: {device}"
                        
                        device_info = {
                            'name': description,
                            'port': port_path
                        }
                        devices.append(device_info)
                    except Exception:
                        continue
    
    return devices

def connect_to_serial(port: str, baudrate: int = 115200) -> Optional[serial.Serial]:
    """
    Connect to a serial port.
    
    Args:
        port: Serial port path
        baudrate: Baud rate for the connection
        
    Returns:
        Serial connection object if successful, None otherwise
    """
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1
        )
        return ser
    except Exception as e:
        print(f"Error connecting to {port}: {e}")
        return None

def close_serial_connection(ser: serial.Serial) -> None:
    """
    Close a serial connection.
    
    Args:
        ser: Serial connection object to close
    """
    if ser and ser.is_open:
        ser.close()