import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
from serial_utils import get_serial_devices, connect_to_serial, close_serial_connection
from packet_handler import create_handshake_packet, create_set_packet, verify_response_packet
from config import DEFAULT_BAUDRATE, RESPONSE_TIMEOUT, WINDOW_WIDTH, WINDOW_HEIGHT

class SerialConnectionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Serial Device Connector")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT + 300}")
        
        # Serial connection state
        self.serial_connection = None
        self.is_connected = False
        self.handshake_active = False  # Flag to track handshake status
        
        # Channel states (0-10)
        self.channel_states = [False] * 11  # All channels initially off
        
        # Global packet struct
        self.global_packet = None
        self.device_id = None
        
        # Create GUI elements
        self.create_widgets()
        
        # Load initial device list
        self.refresh_devices()
        
    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Connection controls (top-left)
        connection_frame = ttk.LabelFrame(main_frame, text="Connection", padding="10")
        connection_frame.grid(row=0, column=0, sticky=(tk.W, tk.N), padx=10, pady=10)
        
        # Device selection
        ttk.Label(connection_frame, text="Select Serial Device:").grid(row=0, column=0, sticky=tk.W, pady=5)
        
        # Device dropdown
        self.device_var = tk.StringVar()
        self.device_dropdown = ttk.Combobox(connection_frame, textvariable=self.device_var, state="readonly")
        self.device_dropdown.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        # Refresh button
        self.refresh_button = ttk.Button(connection_frame, text="Refresh", command=self.refresh_devices)
        self.refresh_button.grid(row=0, column=2, padx=5)
        
        # Connect/Disconnect button
        self.connect_button = ttk.Button(connection_frame, text="Connect", command=self.toggle_connection)
        self.connect_button.grid(row=1, column=1, pady=10)
        
        # Handshake button
        self.handshake_button = ttk.Button(connection_frame, text="Handshake", command=self.perform_handshake, state="disabled")
        self.handshake_button.grid(row=1, column=2, padx=5)
        
        # Set button
        self.set_button = ttk.Button(connection_frame, text="Set", command=self.set_channel_data, state="disabled")
        self.set_button.grid(row=1, column=3, padx=5)
        
        # Connection status indicator
        self.status_frame = ttk.Frame(connection_frame)
        self.status_frame.grid(row=1, column=4, padx=10)
        
        self.status_indicator = tk.Canvas(self.status_frame, width=20, height=20, bg="red")
        self.status_indicator.pack()
        
        self.status_label = ttk.Label(self.status_frame, text="Disconnected")
        self.status_label.pack()
        
        # Configure grid weights for connection frame
        connection_frame.columnconfigure(1, weight=1)
        
        # Main notebook for tabs
        main_notebook = ttk.Notebook(main_frame)
        main_notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        
        # Log tab
        log_frame = ttk.Frame(main_notebook)
        main_notebook.add(log_frame, text="Log")
        
        # Data monitoring frame
        monitor_frame = ttk.LabelFrame(log_frame, text="Data Monitor", padding="10")
        monitor_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        
        # Single text widget for both sent and received data
        self.data_text = tk.Text(monitor_frame, height=15, width=80, wrap=tk.NONE)
        self.data_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Add vertical scrollbar
        data_scrollbar = ttk.Scrollbar(monitor_frame, orient=tk.VERTICAL, command=self.data_text.yview)
        data_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.data_text.config(yscrollcommand=data_scrollbar.set)
        
        # Add horizontal scrollbar
        data_hscrollbar = ttk.Scrollbar(monitor_frame, orient=tk.HORIZONTAL, command=self.data_text.xview)
        data_hscrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.data_text.config(xscrollcommand=data_hscrollbar.set)
        
        # Configure grid weights for monitor frame
        monitor_frame.columnconfigure(0, weight=1)
        monitor_frame.rowconfigure(0, weight=1)
        
        # Outputs tab
        outputs_frame = ttk.Frame(main_notebook)
        main_notebook.add(outputs_frame, text="Outputs")
        
        # Outputs frame with padding
        outputs_content = ttk.Frame(outputs_frame, padding="10")
        outputs_content.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        
        # Channel buttons
        channel_frame = ttk.LabelFrame(outputs_content, text="Channels", padding="10")
        channel_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=10, pady=10)
        
        # Create 11 channel buttons with proper toggle functionality
        self.channel_buttons = []
        for i in range(11):
            button = tk.Button(channel_frame, text=f"Channel {i}", 
                             command=lambda i=i: self.toggle_channel(i),
                             bg="lightgrey", fg="black", relief="raised", width=10, height=2)
            button.grid(row=i // 4, column=i % 4, padx=5, pady=5)
            self.channel_buttons.append(button)
        
        # Configure grid weights
        main_frame.rowconfigure(1, weight=1)
        main_notebook.rowconfigure(0, weight=1)
        main_notebook.columnconfigure(0, weight=1)
        monitor_frame.rowconfigure(0, weight=1)
        monitor_frame.columnconfigure(0, weight=1)
        outputs_content.rowconfigure(0, weight=1)
        outputs_content.columnconfigure(0, weight=1)
        channel_frame.rowconfigure(2, weight=1)
        channel_frame.columnconfigure(3, weight=1)
        
        # Increase window height to accommodate new layout
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT + 300}")
        
    def refresh_devices(self):
        """Refresh the list of available serial devices."""
        devices = get_serial_devices()
        device_names = [f"{device['name']} ({device['port']})" for device in devices]
        
        self.device_dropdown['values'] = device_names
        if device_names:
            self.device_dropdown.current(0)
        
    def toggle_connection(self):
        """Toggle the serial connection state."""
        if not self.is_connected:
            self.connect_to_device()
        else:
            self.disconnect_from_device()
    
    def connect_to_device(self):
        """Connect to the selected serial device."""
        selected_device = self.device_var.get()
        if not selected_device:
            messagebox.showerror("Error", "Please select a device first")
            return
        
        # Extract port from the selection string
        port = selected_device.split('(')[-1].strip(')')
        
        # Connect to the device
        self.serial_connection = connect_to_serial(port, DEFAULT_BAUDRATE)
        
        if self.serial_connection:
            self.is_connected = True
            self.connect_button.config(text="Disconnect")
            self.handshake_button.config(state="normal")
            self.set_button.config(state="disabled")  # Disabled until handshake
            # Keep status indicator red until successful handshake
            self.status_label.config(text="Connected (waiting for handshake)")
        else:
            messagebox.showerror("Error", "Failed to connect to the selected device")
    
    def disconnect_from_device(self):
        """Disconnect from the current serial device."""
        # Cancel any ongoing handshake
        if hasattr(self, 'handshake_active') and self.handshake_active:
            self.handshake_active = False
        
        if self.serial_connection:
            close_serial_connection(self.serial_connection)
            self.serial_connection = None
        
        self.is_connected = False
        self.connect_button.config(text="Connect")
        self.handshake_button.config(state="disabled")
        self.set_button.config(state="disabled")
        self.status_indicator.config(bg="red")
        self.status_label.config(text="Disconnected")
        self.device_id = None
        
        # Clear data monitor
        self.root.after(0, lambda: self._clear_text(self.data_text))
    
    def format_hex_dump(self, data: bytes, title: str = "") -> str:
        """Format binary data as a hex dump string."""
        if not data:
            return f"{title}: No data"
        
        lines = []
        if title:
            lines.append(f"{title}:")
        
        # Process data in 16-byte chunks
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            
            # Hex bytes (formatted as XX XX XX ...)
            hex_str = ' '.join(f'{b:02X}' for b in chunk)
            
            # ASCII representation (replace non-printable with dots)
            ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            
            # Combine with offset
            offset = f'{i:08X}'
            lines.append(f'{offset}  {hex_str:<48} {ascii_str}')
        
        return '\n'.join(lines)
    
    def log_sent_data(self, data: bytes):
        """Log sent data to the monitor."""
        timestamp = time.strftime("%H:%M:%S")
        hex_dump = self.format_hex_dump(data, f"SENT [{timestamp}]")
        self.root.after(0, lambda: self._append_text(self.data_text, hex_dump))
    
    def log_received_data(self, data: bytes):
        """Log received data to the monitor."""
        timestamp = time.strftime("%H:%M:%S")
        hex_dump = self.format_hex_dump(data, f"RECEIVED [{timestamp}]")
        self.root.after(0, lambda: self._append_text(self.data_text, hex_dump))
    
    def _append_text(self, text_widget: tk.Text, text: str):
        """Safely append text to a text widget."""
        text_widget.config(state=tk.NORMAL)
        
        # Add timestamp separator before new entry
        current_content = text_widget.get(1.0, tk.END)
        if current_content.strip():  # If not empty, add separator
            text_widget.insert(tk.END, "\n" + "="*80 + "\n")
        
        text_widget.insert(tk.END, text + "\n\n")
        text_widget.see(tk.END)
        text_widget.config(state=tk.DISABLED)
    
    def _clear_text(self, text_widget: tk.Text):
        """Safely clear text from a text widget."""
        text_widget.config(state=tk.NORMAL)
        text_widget.delete(1.0, tk.END)
        text_widget.config(state=tk.DISABLED)
    
    def toggle_channel(self, channel: int):
        """Toggle the state of a channel button."""
        # Toggle the channel state
        self.channel_states[channel] = not self.channel_states[channel]
        
        # Update button appearance
        button = self.channel_buttons[channel]
        if self.channel_states[channel]:
            button.config(bg="blue", fg="white", relief="sunken")
        else:
            button.config(bg="lightgrey", fg="black", relief="raised")
    
    def set_channel_data(self):
        """Update the packet's data array based on channel states."""
        if not self.is_connected or not self.serial_connection:
            messagebox.showerror("Error", "Not connected to any device")
            return
        
        if self.device_id is None:
            messagebox.showerror("Error", "Please perform handshake first")
            return
        
        try:
            # Create set packet with device ID and channel states
            set_packet = create_set_packet(self.device_id, self.channel_states)
            
            # Send the set packet followed by newline terminator
            self.serial_connection.write(set_packet)
            self.serial_connection.write(b'\x0A')  # Send newline terminator
            
            # Log the complete transmission
            complete_transmission = set_packet + b'\x0A'
            self.log_sent_data(complete_transmission)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send set packet: {str(e)}")
    
    def perform_handshake(self):
        """Perform handshake with the connected device."""
        if not self.is_connected or not self.serial_connection:
            messagebox.showerror("Error", "Not connected to any device")
            return
        
        # Disable buttons during handshake
        self.handshake_button.config(state="disabled")
        self.connect_button.config(state="disabled")
        self.set_button.config(state="disabled")
        
        # Run handshake in a separate thread to avoid blocking the GUI
        handshake_thread = threading.Thread(target=self.handshake_worker)
        handshake_thread.daemon = True
        handshake_thread.start()
    
    def handshake_worker(self):
        """Worker function for performing handshake in a separate thread."""
        self.handshake_active = True
        try:
            # Create and send handshake packet
            handshake_packet = create_handshake_packet()
            
            # Send the packet followed by newline terminator
            self.serial_connection.write(handshake_packet)
            self.serial_connection.write(b'\x0A')  # Send newline terminator
            
            # Log the complete transmission (packet + terminator)
            complete_transmission = handshake_packet + b'\x0A'
            self.log_sent_data(complete_transmission)
            
            self.root.after(0, lambda: self.status_label.config(text="Handshake sent, waiting for response..."))
            
            # Wait for response with timeout
            start_time = time.time()
            response_data = b''
            
            while time.time() - start_time < RESPONSE_TIMEOUT and self.handshake_active:
                if self.serial_connection.in_waiting > 0:
                    new_data = self.serial_connection.read(self.serial_connection.in_waiting)
                    response_data += new_data
                    
                    # Check if we have the terminator (0x0A)
                    if b'\x0A' in response_data:
                        # Split the response at the terminator
                        terminator_pos = response_data.find(b'\x0A')
                        complete_response = response_data[:terminator_pos + 1]  # Include terminator
                        device_data = response_data[:terminator_pos]  # Device data without terminator
                        
                        # Log the complete response (device data + terminator)
                        self.log_received_data(complete_response)
                        
                        # Process only the device data (without terminator)
                        if len(device_data) >= 112:  # Expected packet size
                            is_valid, device_id = verify_response_packet(device_data)
                            
                            if is_valid:
                                # Store device ID for set operations
                                self.device_id = device_id
                                
                                # Update GUI on successful handshake
                                self.root.after(0, lambda: self.status_indicator.config(bg="green"))
                                self.root.after(0, lambda: self.status_label.config(text="Handshake successful"))
                                self.root.after(0, lambda: self.set_button.config(state="normal"))
                            else:
                                # Update GUI on invalid response
                                self.root.after(0, lambda: self.status_indicator.config(bg="red"))
                                self.root.after(0, lambda: self.status_label.config(text="Handshake failed - Invalid response"))
                            break
                    else:
                        # Log partial received data
                        self.log_received_data(new_data)
                
                time.sleep(0.01)  # Small delay to prevent busy waiting
            
            # If we get here without finding terminator, it's a timeout
            if self.handshake_active and b'\x0A' not in response_data:
                # Update GUI on timeout
                self.root.after(0, lambda: self.status_indicator.config(bg="red"))
                self.root.after(0, lambda: self.status_label.config(text="Handshake failed - Timeout"))
        
        except Exception as e:
            # Update GUI on error
            self.root.after(0, lambda: self.status_indicator.config(bg="red"))
            self.root.after(0, lambda: self.status_label.config(text="Handshake failed - Error"))
        
        finally:
            # Reset handshake flag and re-enable buttons
            self.handshake_active = False
            self.root.after(0, lambda: self.handshake_button.config(state="normal"))
            self.root.after(0, lambda: self.connect_button.config(state="normal"))

def main():
    # Create the main application window
    root = tk.Tk()
    
    # Configure styles for channel buttons
    style = ttk.Style()
    style.configure("On.TButton", background="blue", foreground="white")
    style.configure("Off.TButton", background="lightgrey", foreground="black")
    
    app = SerialConnectionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()