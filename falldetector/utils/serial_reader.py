"""
Serial Communication Module for ESP32 CSI Data

Handles reading and parsing binary CSI packets from ESP32.
"""

import serial
import struct
import time
import threading
import queue
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
import numpy as np
import logging

from .config import SerialConfig, CSIConfig

logger = logging.getLogger(__name__)


@dataclass
class CSIPacket:
    """Parsed CSI packet from ESP32"""
    seq: int
    timestamp: int
    rssi: int
    channel: int
    amplitude: np.ndarray  # Shape: (104,)
    phase: np.ndarray      # Shape: (104,)
    valid: bool = True


class ESP32Reader:
    """
    Reads CSI data from ESP32 via USB serial.
    
    Binary packet format:
    [0xAA][0x55][TYPE][SEQ(4)][TIMESTAMP(4)][RSSI][CH][AMP(208)][PHASE(208)][CHECKSUM]
    """
    
    HEADER = bytes([0xAA, 0x55])
    PKT_TYPE_CSI = 0x01
    PKT_TYPE_STATUS = 0x02
    PKT_TYPE_HEARTBEAT = 0x03
    
    def __init__(self, config: SerialConfig = None, csi_config: CSIConfig = None):
        self.config = config or SerialConfig()
        self.csi_config = csi_config or CSIConfig()
        
        self.serial: Optional[serial.Serial] = None
        self.is_connected = False
        
        # Threading
        self._read_thread: Optional[threading.Thread] = None
        self._running = False
        self._packet_queue = queue.Queue(maxsize=1000)
        
        # Statistics
        self.stats = {
            "total_packets": 0,
            "valid_packets": 0,
            "csi_packets": 0,
            "bytes_read": 0,
            "errors": 0
        }
    
    def connect(self) -> bool:
        """Connect to ESP32"""
        try:
            self.serial = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baudrate,
                timeout=self.config.timeout
            )
            time.sleep(0.5)  # Wait for connection
            
            # Flush any existing data
            self.serial.reset_input_buffer()
            
            self.is_connected = True
            logger.info(f"Connected to ESP32 on {self.config.port} @ {self.config.baudrate}")
            return True
            
        except serial.SerialException as e:
            logger.error(f"Failed to connect: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """Disconnect from ESP32"""
        self.stop_reading()
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.is_connected = False
        logger.info("Disconnected from ESP32")
    
    def start_reading(self):
        """Start background reading thread"""
        if self._running:
            return
        
        self._running = True
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()
        logger.info("Started CSI reading thread")
    
    def stop_reading(self):
        """Stop background reading thread"""
        self._running = False
        if self._read_thread:
            self._read_thread.join(timeout=2)
            self._read_thread = None
    
    def _read_loop(self):
        """Background thread for continuous reading"""
        while self._running and self.is_connected:
            packet = self._read_packet()
            if packet and packet.valid:
                try:
                    self._packet_queue.put_nowait(packet)
                except queue.Full:
                    pass  # Drop oldest if queue is full
    
    def _read_packet(self) -> Optional[CSIPacket]:
        """Read and parse a single packet"""
        if not self.serial or not self.serial.is_open:
            return None
        
        try:
            # Find header
            while True:
                byte = self.serial.read(1)
                if not byte:
                    return None
                
                self.stats["bytes_read"] += 1
                
                if byte == bytes([0xAA]):
                    byte2 = self.serial.read(1)
                    self.stats["bytes_read"] += 1
                    
                    if byte2 == bytes([0x55]):
                        break
            
            # Read packet type
            pkt_type_byte = self.serial.read(1)
            if not pkt_type_byte:
                return None
            pkt_type = pkt_type_byte[0]
            self.stats["bytes_read"] += 1
            self.stats["total_packets"] += 1
            
            # Handle different packet types
            if pkt_type == self.PKT_TYPE_CSI:
                return self._parse_csi_packet()
            elif pkt_type == self.PKT_TYPE_STATUS:
                self._parse_status_packet()
                return None
            elif pkt_type == self.PKT_TYPE_HEARTBEAT:
                self._parse_heartbeat_packet()
                return None
            else:
                logger.warning(f"Unknown packet type: {pkt_type}")
                return None
                
        except Exception as e:
            self.stats["errors"] += 1
            logger.debug(f"Read error: {e}")
            return None
    
    def _parse_csi_packet(self) -> Optional[CSIPacket]:
        """Parse CSI data packet"""
        try:
            # Read fixed-size fields
            # SEQ (4) + TIMESTAMP (4) + RSSI (1) + CH (1) = 10 bytes
            header_bytes = self.serial.read(10)
            if len(header_bytes) < 10:
                return None
            
            self.stats["bytes_read"] += 10
            
            seq, timestamp, rssi, channel = struct.unpack('<IIbB', header_bytes)
            
            # Read amplitude (104 * 2 = 208 bytes)
            amp_bytes = self.serial.read(208)
            if len(amp_bytes) < 208:
                return None
            
            self.stats["bytes_read"] += 208
            amplitude = np.array(struct.unpack('<104h', amp_bytes), dtype=np.float32)
            
            # Read phase (104 * 2 = 208 bytes)
            phase_bytes = self.serial.read(208)
            if len(phase_bytes) < 208:
                return None
            
            self.stats["bytes_read"] += 208
            phase = np.array(struct.unpack('<104h', phase_bytes), dtype=np.float32)
            
            # Read checksum
            checksum_byte = self.serial.read(1)
            self.stats["bytes_read"] += 1
            
            self.stats["csi_packets"] += 1
            self.stats["valid_packets"] += 1
            
            return CSIPacket(
                seq=seq,
                timestamp=timestamp,
                rssi=rssi,
                channel=channel,
                amplitude=amplitude,
                phase=phase,
                valid=True
            )
            
        except Exception as e:
            self.stats["errors"] += 1
            logger.debug(f"CSI parse error: {e}")
            return CSIPacket(0, 0, 0, 0, np.zeros(104), np.zeros(104), valid=False)
    
    def _parse_status_packet(self):
        """Parse status packet"""
        try:
            data = self.serial.read(2)
            self.stats["bytes_read"] += 2
            connected = data[0] == 0x01
            channel = data[1]
            logger.debug(f"Status: connected={connected}, channel={channel}")
        except:
            pass
    
    def _parse_heartbeat_packet(self):
        """Parse heartbeat packet"""
        try:
            data = self.serial.read(5)
            self.stats["bytes_read"] += 5
            csi_count = struct.unpack('<I', data[:4])[0]
            connected = data[4] == 0x01
            logger.debug(f"Heartbeat: csi_count={csi_count}, connected={connected}")
        except:
            pass
    
    def get_packet(self, timeout: float = 0.1) -> Optional[CSIPacket]:
        """Get next packet from queue"""
        try:
            return self._packet_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_packets_batch(self, count: int, timeout: float = 30.0) -> list:
        """Collect a batch of packets"""
        packets = []
        start_time = time.time()
        
        while len(packets) < count:
            if time.time() - start_time > timeout:
                logger.warning(f"Timeout collecting packets: {len(packets)}/{count}")
                break
            
            packet = self.get_packet(timeout=1.0)
            if packet and packet.valid:
                packets.append(packet)
        
        return packets
    
    def get_statistics(self) -> Dict:
        """Get reader statistics"""
        return self.stats.copy()


class CSIWindowBuffer:
    """
    Manages sliding window of CSI data for inference.
    """
    
    def __init__(self, window_size: int = 100, hop_size: int = 50):
        self.window_size = window_size
        self.hop_size = hop_size
        self.buffer: list = []
        self._window_count = 0
    
    def add_packet(self, packet: CSIPacket):
        """Add packet to buffer"""
        if packet and packet.valid:
            self.buffer.append(packet.amplitude.copy())
    
    def add_amplitude(self, amplitude: np.ndarray):
        """Add amplitude array directly"""
        self.buffer.append(amplitude.copy())
    
    def is_ready(self) -> bool:
        """Check if enough data for a window"""
        return len(self.buffer) >= self.window_size
    
    def get_window(self) -> Optional[np.ndarray]:
        """Get current window and advance buffer"""
        if not self.is_ready():
            return None
        
        window = np.array(self.buffer[:self.window_size])
        
        # Slide buffer
        self.buffer = self.buffer[self.hop_size:]
        self._window_count += 1
        
        return window
    
    def clear(self):
        """Clear buffer"""
        self.buffer.clear()
    
    def __len__(self) -> int:
        return len(self.buffer)
