import serial.tools.list_ports
import platform
import os
from typing import List, Dict, Optional


def get_serial_devices() -> List[Dict[str, str]]:
    """
    Get a list of available serial devices on the current platform.

    Returns:
        List of dicts with 'name' and 'port' keys.
    """
    devices = []
    system = platform.system().lower()

    if system == "windows":
        ports = serial.tools.list_ports.comports()
        for port in ports:
            product      = port.product or port.description or port.device
            manufacturer = port.manufacturer or ""
            friendly     = f"{product} · {manufacturer}" if manufacturer else product
            devices.append({'name': friendly, 'port': port.device})

    elif system == "linux":
        dev_dir = '/dev/'
        port_info = {p.device: p for p in serial.tools.list_ports.comports()}

        if os.path.exists(dev_dir):
            for device in os.listdir(dev_dir):
                if device.startswith('tty') and not device.startswith('tty0'):
                    port_path = os.path.join(dev_dir, device)
                    try:
                        info = port_info.get(port_path)
                        if info:
                            product      = info.product or info.description or device
                            manufacturer = info.manufacturer or ""
                            friendly     = f"{product} · {manufacturer}" if manufacturer else product
                        else:
                            if os.path.islink(port_path):
                                real_path = os.path.realpath(port_path)
                                if 'usb' in real_path.lower():
                                    friendly = f"USB Serial ({device})"
                                elif 'bluetooth' in real_path.lower():
                                    friendly = f"Bluetooth ({device})"
                                else:
                                    friendly = device
                            else:
                                friendly = device

                        devices.append({'name': friendly, 'port': port_path})
                    except Exception:
                        continue

    elif system == "darwin":  # macOS
        dev_dir = '/dev/'
        # pyserial on macOS registers devices under their cu. path, not tty.
        # Build lookup by cu. path so we can enrich our tty. entries.
        port_info = {p.device: p for p in serial.tools.list_ports.comports()}

        if os.path.exists(dev_dir):
            for device in os.listdir(dev_dir):
                # Only tty. — skip cu. duplicates
                if not device.startswith('tty.'):
                    continue
                if device in ('tty0', 'console'):
                    continue

                port_path = os.path.join(dev_dir, device)
                try:
                    # pyserial stores metadata under the cu. counterpart
                    cu_path = port_path.replace('/tty.', '/cu.')
                    info = port_info.get(cu_path) or port_info.get(port_path)

                    if info:
                        product      = info.product or info.description or ""
                        manufacturer = info.manufacturer or ""
                        if product and manufacturer:
                            friendly = f"{product} · {manufacturer}"
                        elif product:
                            friendly = product
                        elif manufacturer:
                            friendly = manufacturer
                        else:
                            friendly = device
                    else:
                        if 'usb' in device.lower():
                            friendly = f"USB Serial ({device})"
                        elif 'bluetooth' in device.lower():
                            friendly = f"Bluetooth ({device})"
                        else:
                            friendly = device

                    devices.append({'name': friendly, 'port': port_path})
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