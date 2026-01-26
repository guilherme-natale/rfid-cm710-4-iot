#!/usr/bin/env python3
"""
RFID Reader Script for CM710-4 Module
Runs on Raspberry Pi - reads tags and writes to log file
"""
import serial
import time
import glob
import sys
import signal
from datetime import datetime
import uuid
import logging

# Try to import GPIO, fallback for development
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("Warning: RPi.GPIO not available, running in simulation mode")

# ==================== CONFIGURATION ====================
EN_PIN = 18          # GPIO pin for module enable
BUZZER_PIN = 17      # GPIO pin for buzzer
LOG_FILE = "/var/log/rfid/cm710-4.log"
BAUD_RATE = 115200

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== GLOBALS ====================
running = True
serial_port = None


def get_mac_address():
    """Get device MAC address"""
    try:
        # Try network interfaces
        for iface in ['eth0', 'wlan0', 'enp0s3']:
            path = f'/sys/class/net/{iface}/address'
            try:
                with open(path, 'r') as f:
                    return f.read().strip().upper()
            except FileNotFoundError:
                continue
        
        # Fallback to uuid method
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff) 
                       for i in range(0, 48, 8)][::-1]).upper()
        return mac
    except Exception as e:
        logger.error(f"Failed to get MAC address: {e}")
        return "00:00:00:00:00:00"


MAC_ADDRESS = get_mac_address()


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global running
    logger.info("Shutdown signal received")
    running = False


def setup_gpio():
    """Initialize GPIO pins"""
    if not GPIO_AVAILABLE:
        logger.warning("GPIO not available, skipping setup")
        return
    
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(EN_PIN, GPIO.OUT)
    GPIO.setup(BUZZER_PIN, GPIO.OUT)
    
    # Enable module
    GPIO.output(EN_PIN, GPIO.HIGH)
    GPIO.output(BUZZER_PIN, GPIO.LOW)
    
    logger.info("GPIO initialized")


def cleanup_gpio():
    """Cleanup GPIO resources"""
    if not GPIO_AVAILABLE:
        return
    
    try:
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        GPIO.output(EN_PIN, GPIO.LOW)
        GPIO.cleanup()
    except Exception as e:
        logger.error(f"GPIO cleanup error: {e}")


def find_serial_port():
    """Find available serial port"""
    ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
    
    if not ports:
        logger.error("No serial port found!")
        return None
    
    logger.info(f"Found serial ports: {ports}")
    return ports[0]


def open_serial(port):
    """Open serial connection"""
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=1.0)
        ser.reset_input_buffer()
        logger.info(f"Serial port opened: {port}")
        return ser
    except Exception as e:
        logger.error(f"Failed to open serial port: {e}")
        return None


def start_continuous_inventory(ser):
    """Send command to start continuous inventory"""
    # Continuous Inventory Label Command (0x82)
    # Frame: C8 8C 00 0A 82 00 00 88 0D 0A
    cmd = bytes.fromhex("C88C000A820000880D0A")
    ser.write(cmd)
    logger.info("Started continuous inventory")


def stop_continuous_inventory(ser):
    """Send command to stop continuous inventory"""
    # Stop Continuous Inventory Tag (CMD 0x8C)
    # Frame: C8 8C 00 08 8C 84 0D 0A
    cmd = bytes.fromhex("C88C00088C840D0A")
    ser.write(cmd)
    logger.info("Stopped continuous inventory")


def beep():
    """Sound buzzer briefly"""
    if not GPIO_AVAILABLE:
        return
    
    try:
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        time.sleep(0.01)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
    except Exception:
        pass


def log_reading(epc, antenna, rssi):
    """Write reading to log file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"{timestamp} {MAC_ADDRESS} {epc} {antenna} {rssi:6.1f}"
    
    # Print to console
    print(line)
    
    # Write to log file
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception as e:
        logger.error(f"Failed to write to log: {e}")
    
    # Beep
    beep()


def parse_frame(frame):
    """Parse RFID response frame"""
    try:
        # Validate frame structure
        if len(frame) < 12:
            return None
        if frame[:2] != b'\xC8\x8C':
            return None
        if frame[4] != 0x83:  # Inventory response
            return None
        
        i = 5
        
        # Parse PC (Protocol Control)
        pc = (frame[i] << 8) | frame[i + 1]
        epc_len = ((pc >> 11) & 0x1F) * 2
        i += 2
        
        # Parse EPC
        epc = frame[i:i + epc_len].hex().upper()
        i += epc_len
        
        # Parse RSSI
        rssi_raw = (frame[i] << 8) | frame[i + 1]
        rssi = (rssi_raw - 65536) / 10.0 if rssi_raw > 32767 else rssi_raw / 10.0
        i += 2
        
        # Parse antenna
        antenna = ((frame[i] - 1) % 4) + 1
        
        return {
            'epc': epc,
            'antenna': antenna,
            'rssi': rssi
        }
        
    except Exception as e:
        logger.debug(f"Frame parse error: {e}")
        return None


def main():
    global running, serial_port
    
    logger.info("=" * 50)
    logger.info("RFID CM710-4 Reader Starting")
    logger.info(f"MAC Address: {MAC_ADDRESS}")
    logger.info(f"Log File: {LOG_FILE}")
    logger.info("=" * 50)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Setup GPIO
    setup_gpio()
    time.sleep(2.0)  # Wait for module to initialize
    
    # Find and open serial port
    port = find_serial_port()
    if not port:
        logger.error("No serial port available")
        sys.exit(1)
    
    serial_port = open_serial(port)
    if not serial_port:
        logger.error("Failed to open serial port")
        cleanup_gpio()
        sys.exit(1)
    
    # Start continuous inventory
    start_continuous_inventory(serial_port)
    time.sleep(0.5)
    
    # Main reading loop
    buffer = b""
    
    logger.info("Reading active - Press Ctrl+C to stop")
    
    try:
        while running:
            # Read available data
            if serial_port.in_waiting:
                buffer += serial_port.read(serial_port.in_waiting)
            
            # Process complete frames
            while b'\x0D\x0A' in buffer:
                pos = buffer.find(b'\x0D\x0A')
                
                if pos < 10:
                    buffer = buffer[pos + 2:]
                    continue
                
                frame = buffer[:pos + 2]
                buffer = buffer[pos + 2:]
                
                # Parse and log reading
                reading = parse_frame(frame)
                if reading:
                    # Filter: only log EPCs of expected length (adjust as needed)
                    if len(reading['epc']) >= 8:
                        log_reading(
                            reading['epc'],
                            reading['antenna'],
                            reading['rssi']
                        )
            
            # Small delay to prevent busy loop
            time.sleep(0.01)
            
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    
    finally:
        # Cleanup
        logger.info("Shutting down...")
        
        if serial_port:
            try:
                stop_continuous_inventory(serial_port)
                time.sleep(0.1)
                serial_port.close()
            except Exception:
                pass
        
        cleanup_gpio()
        logger.info("Reader stopped")


if __name__ == "__main__":
    main()
