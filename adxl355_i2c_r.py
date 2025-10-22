"""
ADXL355 I2C Interface for Raspberry Pi

This module provides a Python interface for the ADXL355 accelerometer sensor
connected via I2C to a Raspberry Pi. It reads acceleration data and sends it
to an InfluxDB server.
"""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import smbus2 as smbus
from influxdb import InfluxDBClient
from retry import retry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Physical constants
GRAVITY = 9.80665  # m/s^2

# Register addresses
POWER_CTL = 0x2D
RANGE = 0x2C
LOWPASS_FILTER = 0x28
XDATA3 = 0x08
XDATA2 = 0x09
XDATA1 = 0x0A
YDATA3 = 0x0B
YDATA2 = 0x0C
YDATA1 = 0x0D
ZDATA1 = 0x0E
ZDATA2 = 0x0F
ZDATA3 = 0x10
TEMP2 = 0x06
TEMP1 = 0x07
STATUS = 0x04

# Power control bits
POWER_CTL_OFF = 0x01
POWER_CTL_ON = ~POWER_CTL_OFF
POWER_CTL_DRDY_OFF = 0x04
POWER_CTL_DRDY_ON = ~POWER_CTL_DRDY_OFF
POWER_CTL_TEMP_OFF = 0x02
POWER_CTL_TEMP_ON = ~POWER_CTL_TEMP_OFF

# Range settings
RANGE_MASK = 0x03
RANGE_2G = 0b01
RANGE_4G = 0b10
RANGE_8G = 0b11

# Lowpass filter settings
LOWPASS_FILTER_MASK = 0x0F
LOWPASS_FILTER_4000 = 0x0000
LOWPASS_FILTER_2000 = 0x0001
LOWPASS_FILTER_1000 = 0x0010
LOWPASS_FILTER_500 = 0x0011
LOWPASS_FILTER_250 = 0x0100
LOWPASS_FILTER_125 = 0x0101
LOWPASS_FILTER_62_5 = 0x0110
LOWPASS_FILTER_31_25 = 0x0111
LOWPASS_FILTER_15_625 = 0x1000
LOWPASS_FILTER_7_813 = 0x1001
LOWPASS_FILTER_3_906 = 0x1010

# Data reading settings
TEMP_START = TEMP2
TEMP_LENGTH = 2
AXIS_START = XDATA3
AXIS_LENGTH = 9

# Status masks
STATUS_MASK_DATARDY = 0x01
STATUS_MASK_NVMBUSY = 0x10

# Temperature conversion constants
TEMP_BIAS = 1852
TEMP_SLOPE = 9.05
TEMP_OFFSET = 19.21

# Conversion factors for different ranges (LSB/g)
CONVERSION_FACTORS = {
    RANGE_2G: 256000.0,
    RANGE_4G: 128000.0,
    RANGE_8G: 64000.0
}

# Default sampling interval (seconds)
DEFAULT_SAMPLE_INTERVAL = 0.08


@dataclass
class SensorConfig:
    """Configuration for ADXL355 sensor and data collection."""

    # I2C settings
    i2c_bus: int = 1
    device_address: int = 0x1d

    # Sensor settings
    range_setting: int = RANGE_4G
    lowpass_filter: int = LOWPASS_FILTER_62_5

    # Calibration offsets
    x_offset: float = 0.0
    y_offset: float = 0.0
    z_offset: float = 0.0

    # InfluxDB settings
    influxdb_host: str = '192.168.1.180'
    influxdb_port: int = 8086
    influxdb_user: str = 'root'
    influxdb_password: str = ''
    influxdb_database: str = 'sensor'

    # Sampling settings
    sample_interval: float = DEFAULT_SAMPLE_INTERVAL

    @classmethod
    def from_file(cls, config_path: str) -> 'SensorConfig':
        """Load configuration from a JSON file."""
        path = Path(config_path)
        if not path.exists():
            logger.warning(f"Config file {config_path} not found, using defaults")
            return cls()

        with open(path, 'r') as f:
            config_dict = json.load(f)

        return cls(**config_dict)


class ADXL355Range:
    """Convenience class for range settings."""

    range2G = RANGE_2G
    range4G = RANGE_4G
    range8G = RANGE_8G


class ADXL355LowpassFilter:
    """Convenience class for lowpass filter settings."""

    lowpassFilter_4000 = LOWPASS_FILTER_4000
    lowpassFilter_2000 = LOWPASS_FILTER_2000
    lowpassFilter_1000 = LOWPASS_FILTER_1000
    lowpassFilter_500 = LOWPASS_FILTER_500
    lowpassFilter_250 = LOWPASS_FILTER_250
    lowpassFilter_125 = LOWPASS_FILTER_125
    lowpassFilter_62_5 = LOWPASS_FILTER_62_5
    lowpassFilter_31_25 = LOWPASS_FILTER_31_25
    lowpassFilter_15_625 = LOWPASS_FILTER_15_625
    lowpassFilter_7_813 = LOWPASS_FILTER_7_813
    lowpassFilter_3_906 = LOWPASS_FILTER_3_906

    lowpassFilterValue = {
        lowpassFilter_4000: '4000',
        lowpassFilter_2000: '2000',
        lowpassFilter_1000: '1000',
        lowpassFilter_500: '500',
        lowpassFilter_250: '250',
        lowpassFilter_125: '125',
        lowpassFilter_62_5: '62.5',
        lowpassFilter_31_25: '31.25',
        lowpassFilter_15_625: '15.625',
        lowpassFilter_7_813: '7.813',
        lowpassFilter_3_906: '3.906'
    }


class ADXL355:
    """Interface for ADXL355 accelerometer sensor."""

    def __init__(self, bus: smbus.SMBus, addr: int = 0x1d):
        """
        Initialize ADXL355 sensor.

        Args:
            bus: SMBus instance for I2C communication
            addr: I2C device address (default: 0x1d)
        """
        self._bus = bus
        self._devAddr = addr
        self._range = RANGE_2G
        logger.info(f"Initialized ADXL355 at address 0x{addr:02x}")

    def begin(self) -> None:
        """Start the sensor by turning off standby mode."""
        try:
            power_ctl = self._bus.read_byte_data(self._devAddr, POWER_CTL)

            if (power_ctl & POWER_CTL_OFF) == POWER_CTL_OFF:
                self._bus.write_byte_data(
                    self._devAddr,
                    POWER_CTL,
                    power_ctl & POWER_CTL_ON
                )
                logger.info("Sensor started")
        except OSError as e:
            logger.error(f"Error starting sensor: {e}")
            raise

    def end(self) -> None:
        """Stop the sensor by entering standby mode."""
        try:
            power_ctl = self._bus.read_byte_data(self._devAddr, POWER_CTL)

            if (power_ctl & POWER_CTL_OFF) != POWER_CTL_OFF:
                self._bus.write_byte_data(
                    self._devAddr,
                    POWER_CTL,
                    power_ctl | POWER_CTL_OFF
                )
                logger.info("Sensor stopped")
        except OSError as e:
            logger.error(f"Error stopping sensor: {e}")
            raise

    def get_lowpass_filter(self) -> int:
        """Get current lowpass filter setting."""
        return (self._bus.read_byte_data(self._devAddr, LOWPASS_FILTER)
                & LOWPASS_FILTER_MASK)

    def set_lowpass_filter(self, new_lowpass_filter: int) -> None:
        """
        Set lowpass filter setting.

        Args:
            new_lowpass_filter: Filter setting value

        Raises:
            ValueError: If filter value is invalid
        """
        if not isinstance(new_lowpass_filter, int):
            raise ValueError('newLowpassFilter must be an integer')

        if new_lowpass_filter < LOWPASS_FILTER_3_906 or \
           new_lowpass_filter > LOWPASS_FILTER_4000:
            raise ValueError('newLowpassFilter is out of range')

        lowpass_filter = self._bus.read_byte_data(self._devAddr, LOWPASS_FILTER)
        lowpass_filter = (lowpass_filter & ~LOWPASS_FILTER_MASK) | new_lowpass_filter
        self._bus.write_byte_data(self._devAddr, LOWPASS_FILTER, lowpass_filter)
        logger.info(f"Lowpass filter set to {new_lowpass_filter}")

    def get_range(self) -> int:
        """Get current range setting."""
        return (self._bus.read_byte_data(self._devAddr, RANGE)) & RANGE_MASK

    def set_range(self, new_range: int) -> None:
        """
        Set measurement range.

        Args:
            new_range: Range setting (RANGE_2G, RANGE_4G, or RANGE_8G)

        Raises:
            ValueError: If range value is invalid
        """
        if not isinstance(new_range, int):
            raise ValueError('newRange must be an integer')

        if new_range < RANGE_2G or new_range > RANGE_8G:
            raise ValueError('newRange is out of range')

        range_val = self._bus.read_byte_data(self._devAddr, RANGE)
        range_val = (range_val & ~RANGE_MASK) | new_range
        self._bus.write_byte_data(self._devAddr, RANGE, range_val)
        self._range = new_range
        logger.info(f"Range set to {new_range}")

    range = property(get_range, set_range)
    lowpass_filter = property(get_lowpass_filter, set_lowpass_filter)

    def is_running(self) -> bool:
        """Check if sensor is running (not in standby mode)."""
        power_ctl = self._bus.read_byte_data(self._devAddr, POWER_CTL)
        return (power_ctl & POWER_CTL_OFF) != POWER_CTL_OFF

    def get_status(self) -> int:
        """Get data ready status."""
        status = self._bus.read_byte_data(self._devAddr, STATUS)
        return status & STATUS_MASK_DATARDY

    status = property(get_status)

    def get_temperature(self) -> float:
        """
        Read temperature from sensor.

        Returns:
            Temperature in degrees Celsius
        """
        temp_bytes = self._bus.read_i2c_block_data(
            self._devAddr,
            TEMP_START,
            TEMP_LENGTH
        )
        temp = temp_bytes[0] << 8 | temp_bytes[1]
        temp = (TEMP_BIAS - temp) / TEMP_SLOPE + TEMP_OFFSET
        return temp

    temperature = property(get_temperature)

    def get_axes(self) -> Dict[str, int]:
        """
        Read raw acceleration data from all axes.

        Returns:
            Dictionary with 'x', 'y', 'z' raw values
        """
        axis_bytes = self._bus.read_i2c_block_data(
            self._devAddr,
            AXIS_START,
            AXIS_LENGTH
        )

        # Extract 20-bit values
        axis_x = (axis_bytes[0] << 16 | axis_bytes[1] << 8 | axis_bytes[2]) >> 4
        axis_y = (axis_bytes[3] << 16 | axis_bytes[4] << 8 | axis_bytes[5]) >> 4
        axis_z = (axis_bytes[6] << 16 | axis_bytes[7] << 8 | axis_bytes[8]) >> 4

        # Convert to signed values
        if axis_x & (1 << 19):
            axis_x = axis_x - (1 << 20)

        if axis_y & (1 << 19):
            axis_y = axis_y - (1 << 20)

        if axis_z & (1 << 19):
            axis_z = axis_z - (1 << 20)

        return {'x': axis_x, 'y': axis_y, 'z': axis_z}

    def get_axes_g(self, offsets: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        """
        Read acceleration data in m/s^2.

        Args:
            offsets: Optional dictionary with 'x', 'y', 'z' offset values

        Returns:
            Dictionary with 'x', 'y', 'z' values in m/s^2
        """
        raw_axes = self.get_axes()
        conversion_factor = CONVERSION_FACTORS.get(self._range, CONVERSION_FACTORS[RANGE_2G])

        if offsets is None:
            offsets = {'x': 0.0, 'y': 0.0, 'z': 0.0}

        return {
            'x': raw_axes['x'] * GRAVITY / conversion_factor + offsets.get('x', 0.0),
            'y': raw_axes['y'] * GRAVITY / conversion_factor + offsets.get('y', 0.0),
            'z': raw_axes['z'] * GRAVITY / conversion_factor + offsets.get('z', 0.0)
        }

    axes = property(get_axes)

    def get_axis_x(self) -> int:
        """Get raw X-axis value."""
        return self.axes['x']

    def get_axis_y(self) -> int:
        """Get raw Y-axis value."""
        return self.axes['y']

    def get_axis_z(self) -> int:
        """Get raw Z-axis value."""
        return self.axes['z']

    axisX = property(get_axis_x)
    axisY = property(get_axis_y)
    axisZ = property(get_axis_z)


class SensorDataCollector:
    """Handles sensor data collection and InfluxDB writing."""

    def __init__(self, config: SensorConfig):
        """
        Initialize data collector.

        Args:
            config: Sensor configuration
        """
        self.config = config
        self.bus = smbus.SMBus(config.i2c_bus)
        self.sensor = ADXL355(self.bus, config.device_address)

        # Initialize InfluxDB client
        self.influx_client = InfluxDBClient(
            host=config.influxdb_host,
            port=config.influxdb_port,
            username=config.influxdb_user,
            password=config.influxdb_password,
            database=config.influxdb_database
        )

        logger.info("Data collector initialized")

    def setup_sensor(self) -> None:
        """Configure and start the sensor."""
        self.sensor.range = self.config.range_setting
        self.sensor.lowpass_filter = self.config.lowpass_filter
        self.sensor.begin()
        logger.info("Sensor configured and started")

    def collect_and_send(self) -> None:
        """Collect sensor data and send to InfluxDB."""
        offsets = {
            'x': self.config.x_offset,
            'y': self.config.y_offset,
            'z': self.config.z_offset
        }

        axes_data = self.sensor.get_axes_g(offsets)

        # Prepare InfluxDB data point
        data_point = [{
            "measurement": "adxl355_measure",
            "fields": {
                "x-axis": axes_data['x'],
                "y-axis": axes_data['y'],
                "z-axis": axes_data['z']
            }
        }]

        try:
            self.influx_client.write_points(data_point)
            logger.debug(f"Data sent: X={axes_data['x']:.6f}, "
                        f"Y={axes_data['y']:.6f}, Z={axes_data['z']:.6f}")
        except Exception as e:
            logger.error(f"Error writing to InfluxDB: {e}")
            raise

    def run(self) -> None:
        """Main data collection loop."""
        self.setup_sensor()

        logger.info("Starting data collection loop")
        try:
            while True:
                self.collect_and_send()
                time.sleep(self.config.sample_interval)
        except KeyboardInterrupt:
            logger.info("Data collection stopped by user")
        except Exception as e:
            logger.error(f"Error in data collection loop: {e}")
            raise
        finally:
            self.sensor.end()
            logger.info("Sensor stopped")


@retry(exceptions=OSError, delay=5)
def run(config_path: Optional[str] = None) -> None:
    """
    Run the sensor data collection with retry on OSError.

    Args:
        config_path: Optional path to configuration file
    """
    if config_path:
        config = SensorConfig.from_file(config_path)
    else:
        config = SensorConfig()

    collector = SensorDataCollector(config)
    collector.run()


if __name__ == "__main__":
    run()
