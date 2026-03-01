#!/usr/bin/env python3
"""
CSI Data Receiver for Jetson Nano
Receives CSI data from ESP32 via USB serial and processes it for fall detection.

Based on research paper:
"Deep Learning-Based Fall Detection Using WiFi Channel State Information"
by Chu et al., IEEE Access 2023
"""

import serial
import serial.tools.list_ports
import numpy as np
import threading
import queue
import time
from dataclasses import dataclass
from typing import Optional, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class CSIDataPacket:
    """CSI Data packet structure"""
    timestamp: int
    rssi: int
    channel: int
    amplitude: np.ndarray  # Shape: (num_subcarriers,)
    phase: np.ndarray      # Shape: (num_subcarriers,)
    valid: bool = True


class CSIReceiver:
    """
    Receives and parses CSI data from ESP32 via USB serial.
    
    Packet Format:
    [0xAA][0x55][TYPE][DATA...][CHECKSUM]
    
    Type 0x01: CSI Data
    Type 0x02: System Status  
    Type 0x03: Heartbeat
    """
    
    HEADER = bytes([0xAA, 0x55])
    NUM_SUBCARRIERS = 64
    CSI_PACKET_SIZE = 4 + 1 + 1 + (64 * 2) + (64 * 2) + 1  # timestamp + rssi + channel + amp + phase + checksum
    
    def __init__(self, port: str = None, baudrate: int = 921600):
        """
        Initialize CSI receiver.
        
        Args:
            port: Serial port (e.g., '/dev/ttyUSB0'). If None, auto-detect.
            baudrate: Serial baud rate (default: 921600)
        """
        self.port = port or self._auto_detect_port()
        self.baudrate = baudrate
        self.serial_conn: Optional[serial.Serial] = None
        self.is_running = False
        self.data_queue = queue.Queue(maxsize=1000)
        self.receive_thread: Optional[threading.Thread] = None
        
        # Statistics
        self.packets_received = 0
        self.packets_valid = 0
        self.packets_invalid = 0
        
    def _auto_detect_port(self) -> str:
        """Auto-detect ESP32 serial port"""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            # Common ESP32 identifiers
            if any(id in port.description.lower() for id in ['esp32', 'cp210', 'ch340', 'usb-serial']):
                logger.info(f"Auto-detected ESP32 on port: {port.device}")
                return port.device
        
        # Default for Jetson Nano
        if len(ports) > 0:
            logger.info(f"Using first available port: {ports[0].device}")
            return ports[0].device
        
        raise RuntimeError("No serial port found. Please specify port manually.")
    
    def connect(self) -> bool:
        """Connect to ESP32 serial port"""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.1,
                write_timeout=0.1
            )
            time.sleep(1)  # Wait for connection to stabilize
            logger.info(f"Connected to ESP32 on {self.port} at {self.baudrate} baud")
            return True
        except serial.SerialException as e:
            logger.error(f"Failed to connect to ESP32: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from ESP32"""
        self.stop_receiving()
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logger.info("Disconnected from ESP32")
    
    def _parse_csi_packet(self, data: bytes) -> CSIDataPacket:
        """Parse CSI data packet"""
        try:
            idx = 0
            
            # Timestamp (4 bytes, little-endian)
            timestamp = int.from_bytes(data[idx:idx+4], 'little')
            idx += 4
            
            # RSSI (1 byte)
            rssi = int.from_bytes(data[idx:idx+1], 'little', signed=True)
            idx += 1
            
            # Channel (1 byte)
            channel = data[idx]
            idx += 1
            
            # Amplitude (64 x 2 bytes)
            amplitude = np.frombuffer(data[idx:idx+128], dtype=np.int16)
            idx += 128
            
            # Phase (64 x 2 bytes)
            phase = np.frombuffer(data[idx:idx+128], dtype=np.int16)
            idx += 128
            
            # Validate checksum
            checksum = data[idx]
            calc_checksum = 0x01  # Packet type
            calc_checksum ^= (timestamp & 0xFF) ^ ((timestamp >> 8) & 0xFF)
            calc_checksum ^= ((timestamp >> 16) & 0xFF) ^ ((timestamp >> 24) & 0xFF)
            calc_checksum ^= (rssi & 0xFF)
            calc_checksum ^= channel
            for b in data[6:idx]:
                calc_checksum ^= b
            
            valid = (checksum == calc_checksum)
            
            return CSIDataPacket(
                timestamp=timestamp,
                rssi=rssi,
                channel=channel,
                amplitude=amplitude,
                phase=phase,
                valid=valid
            )
        except Exception as e:
            logger.error(f"Error parsing CSI packet: {e}")
            return CSIDataPacket(0, 0, 0, np.zeros(64), np.zeros(64), False)
    
    def _receive_loop(self):
        """Main receive loop running in separate thread"""
        buffer = bytearray()
        
        while self.is_running:
            try:
                # Read available data
                if self.serial_conn and self.serial_conn.in_waiting > 0:
                    data = self.serial_conn.read(self.serial_conn.in_waiting)
                    buffer.extend(data)
                
                # Look for header
                while len(buffer) >= 3:
                    # Find header
                    header_idx = -1
                    for i in range(len(buffer) - 1):
                        if buffer[i] == 0xAA and buffer[i+1] == 0x55:
                            header_idx = i
                            break
                    
                    if header_idx == -1:
                        # No header found, clear buffer except last byte
                        buffer = bytearray([buffer[-1]]) if buffer else bytearray()
                        break
                    
                    if header_idx > 0:
                        # Remove data before header
                        buffer = buffer[header_idx:]
                    
                    if len(buffer) < 3:
                        break
                    
                    packet_type = buffer[2]
                    self.packets_received += 1
                    
                    if packet_type == 0x01:  # CSI Data
                        if len(buffer) >= 3 + self.CSI_PACKET_SIZE:
                            packet_data = bytes(buffer[3:3+self.CSI_PACKET_SIZE])
                            buffer = buffer[3+self.CSI_PACKET_SIZE:]
                            
                            csi_packet = self._parse_csi_packet(packet_data)
                            
                            if csi_packet.valid:
                                self.packets_valid += 1
                                try:
                                    self.data_queue.put_nowait(csi_packet)
                                except queue.Full:
                                    # Drop oldest packet
                                    try:
                                        self.data_queue.get_nowait()
                                        self.data_queue.put_nowait(csi_packet)
                                    except queue.Empty:
                                        pass
                            else:
                                self.packets_invalid += 1
                        else:
                            break  # Wait for more data
                    
                    elif packet_type == 0x02:  # System Status
                        if len(buffer) >= 5:
                            connected = buffer[3]
                            channel = buffer[4]
                            logger.debug(f"System status: connected={connected}, channel={channel}")
                            buffer = buffer[5:]
                        else:
                            break
                    
                    elif packet_type == 0x03:  # Heartbeat
                        if len(buffer) >= 8:
                            count = int.from_bytes(bytes(buffer[3:7]), 'little')
                            connected = buffer[7]
                            logger.debug(f"Heartbeat: packets={count}, connected={connected}")
                            buffer = buffer[8:]
                        else:
                            break
                    
                    else:
                        # Unknown packet type, skip header
                        buffer = buffer[2:]
                
                time.sleep(0.001)  # Small sleep to prevent busy waiting
                
            except Exception as e:
                logger.error(f"Error in receive loop: {e}")
                time.sleep(0.1)
    
    def start_receiving(self):
        """Start receiving CSI data in background thread"""
        if not self.serial_conn or not self.serial_conn.is_open:
            if not self.connect():
                return False
        
        self.is_running = True
        self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receive_thread.start()
        logger.info("Started CSI data reception")
        return True
    
    def stop_receiving(self):
        """Stop receiving CSI data"""
        self.is_running = False
        if self.receive_thread:
            self.receive_thread.join(timeout=2)
            self.receive_thread = None
        logger.info("Stopped CSI data reception")
    
    def get_csi_data(self, timeout: float = 0.1) -> Optional[CSIDataPacket]:
        """Get next CSI data packet from queue"""
        try:
            return self.data_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_statistics(self) -> dict:
        """Get receiver statistics"""
        return {
            'packets_received': self.packets_received,
            'packets_valid': self.packets_valid,
            'packets_invalid': self.packets_invalid,
            'queue_size': self.data_queue.qsize(),
            'valid_rate': self.packets_valid / max(self.packets_received, 1)
        }
    
    def send_command(self, command: str):
        """Send command to ESP32"""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.write(command.encode())
            logger.debug(f"Sent command: {command}")


class CSIBuffer:
    """
    Buffer for accumulating CSI data into time windows for model inference.
    
    Based on the paper methodology, we use sliding windows of CSI data
    to detect falls based on temporal patterns.
    """
    
    def __init__(self, window_size: int = 100, hop_size: int = 10, num_subcarriers: int = 64):
        """
        Initialize CSI buffer.
        
        Args:
            window_size: Number of CSI samples per window
            hop_size: Number of samples to slide window
            num_subcarriers: Number of CSI subcarriers
        """
        self.window_size = window_size
        self.hop_size = hop_size
        self.num_subcarriers = num_subcarriers
        
        self.amplitude_buffer = np.zeros((window_size * 2, num_subcarriers), dtype=np.float32)
        self.phase_buffer = np.zeros((window_size * 2, num_subcarriers), dtype=np.float32)
        self.buffer_idx = 0
        self.lock = threading.Lock()
    
    def add_packet(self, packet: CSIDataPacket):
        """Add CSI packet to buffer"""
        with self.lock:
            idx = self.buffer_idx % (self.window_size * 2)
            self.amplitude_buffer[idx] = packet.amplitude
            self.phase_buffer[idx] = packet.phase
            self.buffer_idx += 1
    
    def get_window(self) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """
        Get current window of CSI data.
        
        Returns:
            Tuple of (amplitude_window, phase_window) or None if not enough data
        """
        with self.lock:
            if self.buffer_idx < self.window_size:
                return None
            
            # Get the most recent window_size samples
            end_idx = self.buffer_idx % (self.window_size * 2)
            if end_idx >= self.window_size:
                amp_window = self.amplitude_buffer[end_idx - self.window_size:end_idx].copy()
                phase_window = self.phase_buffer[end_idx - self.window_size:end_idx].copy()
            else:
                # Handle circular buffer wrap-around
                amp_window = np.vstack([
                    self.amplitude_buffer[-(self.window_size - end_idx):],
                    self.amplitude_buffer[:end_idx]
                ])
                phase_window = np.vstack([
                    self.phase_buffer[-(self.window_size - end_idx):],
                    self.phase_buffer[:end_idx]
                ])
            
            return amp_window, phase_window
    
    def is_ready(self) -> bool:
        """Check if buffer has enough data for a window"""
        return self.buffer_idx >= self.window_size


if __name__ == "__main__":
    # Test the receiver
    receiver = CSIReceiver()
    
    if receiver.connect():
        receiver.start_receiving()
        
        try:
            print("Receiving CSI data... Press Ctrl+C to stop")
            while True:
                packet = receiver.get_csi_data(timeout=1.0)
                if packet:
                    print(f"CSI Packet: timestamp={packet.timestamp}, rssi={packet.rssi}, "
                          f"amp_mean={np.mean(packet.amplitude):.2f}, valid={packet.valid}")
                
                stats = receiver.get_statistics()
                print(f"Stats: received={stats['packets_received']}, "
                      f"valid_rate={stats['valid_rate']:.2%}")
                
        except KeyboardInterrupt:
            print("\nStopping...")
        finally:
            receiver.disconnect()
