"""IMU telemetry acquisition module for MPU6050 over I2C on Raspberry Pi 3.

Reads 3-axis accelerometer and gyroscope registers via smbus2, computes
instantaneous pitch and roll attitude angles, and handles hardware errors gracefully.
"""

import math
import logging
from typing import Tuple, Optional

logger = logging.getLogger("pi_capture_agent.imu")

# MPU6050 Register Map
REG_SMPLRT_DIV = 0x19
REG_CONFIG = 0x1A
REG_GYRO_CONFIG = 0x1B
REG_ACCEL_CONFIG = 0x1C
REG_INT_ENABLE = 0x38
REG_ACCEL_XOUT_H = 0x3B
REG_TEMP_OUT_H = 0x41
REG_GYRO_XOUT_H = 0x43
REG_PWR_MGMT_1 = 0x6B
REG_WHO_AM_I = 0x75

# Scaling factors (Default ±2g for Accel, ±250 deg/s for Gyro)
ACCEL_SCALE_2G = 16384.0  # LSB / g
GYRO_SCALE_250DPS = 131.0  # LSB / (deg/s)


class IMUReader:
    """I2C interface for MPU6050 6-DOF IMU on Raspberry Pi 3."""

    def __init__(self, bus_id: int = 1, address: int = 0x68, mock_mode: bool = False):
        self.bus_id = bus_id
        self.address = address
        self.mock_mode = mock_mode
        self._bus = None
        self._is_initialized = False
        self._last_pitch: float = 12.5  # Nominal pitch default
        self._last_roll: float = 0.0
        self._last_accel: Tuple[float, float, float] = (0.0, 0.216, 0.976)

    def initialize(self) -> bool:
        """Initializes I2C bus and wakes up sensor."""
        if self.mock_mode:
            logger.info("IMUReader initialized in MOCK mode.")
            self._is_initialized = True
            return True

        try:
            import smbus2

            self._bus = smbus2.SMBus(self.bus_id)
            
            # Check WHO_AM_I register (0x75)
            who_am_i = self._bus.read_byte_data(self.address, REG_WHO_AM_I)
            if who_am_i not in (0x68, 0x69):
                logger.warning(
                    "Unexpected WHO_AM_I byte 0x%02X at address 0x%02X (expected 0x68)",
                    who_am_i,
                    self.address,
                )

            # Wake up MPU6050: write 0 to PWR_MGMT_1 (0x6B)
            self._bus.write_byte_data(self.address, REG_PWR_MGMT_1, 0x00)

            # Set sample rate divider (SMPLRT_DIV = 7 -> 1kHz / (1 + 7) = 125 Hz)
            self._bus.write_byte_data(self.address, REG_SMPLRT_DIV, 0x07)

            # Set DLPF (Digital Low Pass Filter) to ~44Hz (helps reduce robot motor vibration)
            self._bus.write_byte_data(self.address, REG_CONFIG, 0x03)

            # Set Gyro to ±250 dps
            self._bus.write_byte_data(self.address, REG_GYRO_CONFIG, 0x00)

            # Set Accel to ±2g
            self._bus.write_byte_data(self.address, REG_ACCEL_CONFIG, 0x00)

            self._is_initialized = True
            logger.info(
                "MPU6050 successfully initialized on I2C bus %d at 0x%02X (WHO_AM_I: 0x%02X)",
                self.bus_id,
                self.address,
                who_am_i,
            )
            return True

        except ImportError:
            logger.warning("smbus2 library not available. Falling back to mock IMU mode.")
            self.mock_mode = True
            self._is_initialized = True
            return True
        except (IOError, OSError) as e:
            logger.error("Failed to communicate with MPU6050 at 0x%02X: %s", self.address, e)
            self._is_initialized = False
            return False

    @staticmethod
    def _read_word_2c(high: int, low: int) -> int:
        """Converts two unsigned 8-bit registers to a signed 16-bit integer."""
        val = (high << 8) | low
        if val >= 0x8000:
            val -= 0x10000
        return val

    def read_attitude(self) -> Tuple[float, float, Tuple[float, float, float]]:
        """Reads acceleration and computes pitch and roll angles.

        Returns:
            Tuple[float, float, Tuple[float, float, float]]:
                - pitch_deg: Estimated camera pitch angle downwards (degrees)
                - roll_deg: Estimated camera roll angle (degrees)
                - accel_xyz: Acceleration (ax, ay, az) in gravitational units (g)
        """
        if self.mock_mode or not self._is_initialized or self._bus is None:
            return self._last_pitch, self._last_roll, self._last_accel

        try:
            # Burst read 6 consecutive bytes: ACCEL_XOUT_H (0x3B) to ACCEL_ZOUT_L (0x40)
            data = self._bus.read_i2c_block_data(self.address, REG_ACCEL_XOUT_H, 6)
            raw_x = self._read_word_2c(data[0], data[1])
            raw_y = self._read_word_2c(data[2], data[3])
            raw_z = self._read_word_2c(data[4], data[5])

            ax = raw_x / ACCEL_SCALE_2G
            ay = raw_y / ACCEL_SCALE_2G
            az = raw_z / ACCEL_SCALE_2G

            # Attitude computation:
            # In camera rig convention:
            # Pitch is tilt down/up around X-axis.
            # Roll is tilt left/right around Z-axis.
            # Avoid division by zero with small epsilon
            denom_pitch = math.sqrt(ax * ax + az * az) + 1e-6
            pitch_rad = math.atan2(ay, denom_pitch)
            pitch_deg = math.degrees(pitch_rad)

            denom_roll = math.sqrt(ay * ay + az * az) + 1e-6
            roll_rad = math.atan2(-ax, denom_roll)
            roll_deg = math.degrees(roll_rad)

            self._last_pitch = pitch_deg
            self._last_roll = roll_deg
            self._last_accel = (ax, ay, az)

            return pitch_deg, roll_deg, (ax, ay, az)

        except (IOError, OSError) as e:
            logger.warning("I2C read glitch on MPU6050: %s. Returning previous attitude.", e)
            return self._last_pitch, self._last_roll, self._last_accel

    def close(self) -> None:
        """Closes the I2C bus."""
        if self._bus is not None:
            try:
                self._bus.close()
            except Exception:
                pass
            self._bus = None
        self._is_initialized = False
