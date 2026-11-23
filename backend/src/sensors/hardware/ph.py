"""
Real pH sensor implementation for Raspberry Pi
Atlas Scientific pH sensor via I2C
"""
import asyncio
import time
from datetime import datetime
from typing import Dict, Any
from ..base_sensor import BaseSensor
from ...utils.logger import logger

try:
    import smbus2
    SMBUS_AVAILABLE = True
except ImportError:
    SMBUS_AVAILABLE = False
    logger.warning("smbus2 not available - install with: pip install smbus2")


class PHReal(BaseSensor):
    """Real Atlas Scientific pH sensor via I2C"""
    
    def __init__(self, i2c_address=0x63):
        """
        Initialize pH sensor
        
        Args:
            i2c_address: I2C address (default: 0x63 for Atlas Scientific)
        """
        super().__init__("ph", "Atlas Scientific pH Sensor")
        
        if not SMBUS_AVAILABLE:
            logger.error("smbus2 not installed")
            self.sensor = None
            self.is_initialized = False
            return
        
        try:
            self.bus = smbus2.SMBus(1)  # I2C bus 1 on Raspberry Pi
            self.address = i2c_address
            
            # Test connection: "i" must get a success reply
            self._send_command("i")
            self._read_response(wait=0.3)
            
            self.is_initialized = True
            logger.info(f"pH sensor initialized at address 0x{i2c_address:02x}")
            
        except Exception as e:
            logger.error(f"Failed to initialize pH sensor: {e}")
            self.sensor = None
            self.is_initialized = False
    
    def _send_command(self, command: str):
        """Send command to pH sensor (raw write, no register byte)"""
        self.bus.i2c_rdwr(smbus2.i2c_msg.write(self.address, command.encode("ascii")))
    
    def _read_response(self, wait: float = 0.9) -> str:
        """Read response; first byte is a status code (1 = success)"""
        time.sleep(wait)  # Wait for sensor to process
        
        msg = smbus2.i2c_msg.read(self.address, 31)
        self.bus.i2c_rdwr(msg)
        data = bytes(list(msg))
        
        if data[0] != 1:
            errors = {2: "command failed", 254: "still processing", 255: "no data"}
            raise RuntimeError(f"pH sensor: {errors.get(data[0], f'status {data[0]}')}")
        
        return data[1:].split(b"\x00", 1)[0].decode("ascii").strip()
    
    def _blocking_i2c_read(self) -> Dict[str, Any]:
        """
        Synchronous I2C read (runs in thread pool)
        
        Returns:
            Dictionary with pH value and status
        """
        if not self.is_initialized:
            raise RuntimeError("pH sensor not initialized")
        
        # Send read command
        self._send_command("R")
        
        # Get response
        response = self._read_response()
        logger.debug(f"Raw pH sensor response: {response}")
        
        # Parse pH value
        try:
            ph_value = float(response)
            logger.debug(f"Parsed pH value: {ph_value}")
        except ValueError:
            logger.error(f"Invalid pH reading: {response}")
            raise RuntimeError(f"Invalid pH reading: {response}")
        
        # Determine status based on typical hydroponic ranges
        if 5.5 <= ph_value <= 6.5:
            status = "optimal"
            status_message = "pH is in optimal range"
        elif 5.0 <= ph_value < 5.5 or 6.5 < ph_value <= 7.0:
            status = "acceptable"
            status_message = "pH is acceptable but not optimal"
        elif ph_value < 5.0:
            status = "low"
            status_message = "pH is too low (acidic)"
        else:
            status = "high"
            status_message = "pH is too high (alkaline)"
        
        logger.info(f"pH reading: {ph_value} ({status})")
        
        return {
            "ph": round(ph_value, 2),
            "status": status,
            "status_message": status_message,
            "temperature_compensated": False  # Add temp compensation if needed
        }
    
    async def read(self) -> Dict[str, Any]:
        """
        Async wrapper for I2C read
        
        Returns:
            Sensor reading dictionary with graceful fallback for unavailable hardware
        """
        if not self.is_initialized:
            # Return safe placeholder values instead of crashing
            logger.warning("pH sensor not initialized, returning placeholder values")
            self.last_reading = {
                "ph": 7.0,
                "status": "hardware_not_connected",
                "status_message": "pH sensor hardware not available",
                "temperature_compensated": False
            }
            self.last_reading_time = datetime.now().isoformat()
            return self.last_reading
        
        # Get event loop
        loop = asyncio.get_event_loop()
        
        # Run blocking I2C read in thread pool
        data = await loop.run_in_executor(None, self._blocking_i2c_read)
        
        # Store reading
        self.last_reading = data
        self.last_reading_time = datetime.now().isoformat()
        
        return self.last_reading


# Test function
if __name__ == "__main__":
    async def test():
        sensor = PHReal()
        reading = await sensor.read()
        print(f"pH Reading: {reading}")
    
    asyncio.run(test())
