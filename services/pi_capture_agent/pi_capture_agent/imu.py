"""IMU telemetry acquisition module for MPU6050 over I2C on Raspberry Pi 3.

Reads 3-axis accelerometer and 3-axis gyroscope data, applies sensor scaling,
and computes instantaneous camera pitch and roll angles with optional complementary filtering.
"""

import math
import struct
import time
import logging
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger("pi_capture_agent.imu")

# MPU-6050 Register Map
REG_SMPLRT_DIV = 0x19
REG_CONFIG = 0x1A
REG_GYRO_CONFIG = 0x1B
REG_ACCEL_CONFIG = 0x1C
REG_ACCEL_XOUT_H = 0x3B
REG_TEMP_OUT_H = 0x41
REG_GYRO_XOUT_H = 0x43
REG_PWR_MGMT_1 = 0x6B
REG_WHO_AM_I = 0x75

# Scaling factors (for ±2g and ±250 deg/s default configs)
ACCEL_SCALE_2G = 16384.0  # LSB / g
GYRO_SCALE_250 = 131.0    # LSB / (deg/s)


class IMUReader:
    """I2C interface for MPU6050 6-DOF IMU."""

    def __init__(
        self,
        bus_id: int = 1,
        address: int = 0x68,
        alpha_filter: float = 0.98,
        use_filter: bool = True,
    ):
        """Initializes reader configuration.

        Args:
            bus_id: I2C bus ID (default 1 for Raspberry Pi /dev/i2c-1).
            address: MPU6050 I2C address (0x68 if AD0=GND, 0x69 if AD0=VCC).
            alpha_filter: Complementary filter weighting factor (0.0 to 1.0).
            use_filter: Whether to apply complementary filter with gyro integration.
        """
        self.bus_id = bus_id
        self.address = address
        self.alpha_filter = alpha_filter
        self.use_filter = use_filter

        self._bus: Any = None
        self._is_initialized = False

        # Filter state
        self._last_pitch: Optional[float] = None
        self._last_roll: Optional[float] = None
        self._last_time: Optional[float] = None

    def initialize(self) -> None:
        """Initializes I2C bus and wakes up MPU-6050 sensor."""
        try:
            import smbus2
        except ImportError as exc:
            raise ImportError(
                "smbus2 is required for IMU communication. Install it with: pip install smbus2"
            ) from exc

        try:
            self._bus = smbus2.SMBus(self.bus_id)

            # Wake up MPU6050 (clear sleep bit in PWR_MGMT_1)
            # Setting clock source to 1 (PLL with X axis gyroscope reference) for improved stability
            self._bus.write_byte_data(self.address, REG_PWR_MGMT_1, 0x01)
            time.sleep(0.01)

            # Set sample rate divider (1kHz / (1 + 7) = 125Hz)
            self._bus.write_byte_data(self.address, REG_SMPLRT_DIV, 0x07)

            # DLPF configuration (DLPF_CFG = 3 -> Accel BW ~44Hz, Gyro BW ~42Hz)
            self._bus.write_byte_data(self.address, REG_CONFIG, 0x03)

            # Gyro full scale range ±250 deg/s
            self._bus.write_byte_data(self.address, REG_GYRO_CONFIG, 0x00)

            # Accelerometer full scale range ±2g
            self._bus.write_byte_data(self.address, REG_ACCEL_CONFIG, 0x00)

            # Validate WHO_AM_I register (expected 0x68)
            try:
                who_am_i = self._bus.read_byte_data(self.address, REG_WHO_AM_I)
                logger.info(
                    "MPU6050 detected at I2C bus %d, addr 0x%02X (WHO_AM_I: 0x%02X)",
                    self.bus_id,
                    self.address,
                    who_am_i,
                )
            except Exception as e:
                logger.warning("Could not read WHO_AM_I from 0x%02X: %s", self.address, e)

            self._is_initialized = True
            logger.info("MPU6050 initialized successfully.")

        except Exception as e:
            self._is_initialized = False
            logger.error("Failed to initialize MPU6050 on bus %d, addr 0x%02X: %s", self.bus_id, self.address, e)
            raise

    def read_raw_sensors(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], float]:
        """Reads 14 bytes in a single burst: Accel (6B), Temp (2B), Gyro (6B).

        Returns:
            Tuple:
                - accel_g: (ax, ay, az) in gravitational units (g)
                - gyro_dps: (gx, gy, gz) in degrees per second (deg/s)
                - temp_c: Internal die temperature in Celsius
        """
        if not self._is_initialized or self._bus is None:
            raise RuntimeError("IMUReader is not initialized. Call initialize() first.")

        # Burst read 14 bytes starting at REG_ACCEL_XOUT_H (0x3B)
        data = self._bus.read_i2c_block_data(self.address, REG_ACCEL_XOUT_H, 14)
        raw_vals = struct.unpack(">hhhhhhh", bytes(data))

        ax_raw, ay_raw, az_raw, temp_raw, gx_raw, gy_raw, gz_raw = raw_vals

        ax = ax_raw / ACCEL_SCALE_2G
        ay = ay_raw / ACCEL_SCALE_2G
        az = az_raw / ACCEL_SCALE_2G

        temp_c = (temp_raw / 340.0) + 36.53

        gx = gx_raw / GYRO_SCALE_250
        gy = gy_raw / GYRO_SCALE_250
        gz = gz_raw / GYRO_SCALE_250

        return (ax, ay, az), (gx, gy, gz), temp_c

    def read_attitude(self) -> Tuple[float, float, Tuple[float, float, float]]:
        """Reads acceleration and computes pitch and roll angles in degrees.

        Coordinates convention:
            - IMU X: forward along camera optical axis
            - IMU Y: left/right lateral axis
            - IMU Z: upward normal axis

        Formulas:
            pitch_acc = atan2(-ax, sqrt(ay^2 + az^2)) in degrees (positive when tilted downwards)
            roll_acc  = atan2(ay, az) in degrees

        Returns:
            Tuple[float, float, Tuple[float, float, float]]:
                - pitch_deg: Estimated camera pitch angle downwards (degrees)
                - roll_deg: Estimated camera roll angle (degrees)
                - accel_xyz: Raw acceleration (ax, ay, az) in g
        """
        now = time.time()
        accel_xyz, gyro_dps, _ = self.read_raw_sensors()
        ax, ay, az = accel_xyz
        gx, gy, gz = gyro_dps

        # Accelerometer static angles
        norm_yz = math.sqrt(ay * ay + az * az)
        pitch_acc = math.degrees(math.atan2(-ax, norm_yz if norm_yz > 1e-6 else 1e-6))
        roll_acc = math.degrees(math.atan2(ay, az if abs(az) > 1e-6 else 1e-6))

        if not self.use_filter or self._last_time is None or self._last_pitch is None or self._last_roll is None:
            # First reading or filter disabled: initialize with accelerometer static pose
            pitch_deg = pitch_acc
            roll_deg = roll_acc
        else:
            dt = now - self._last_time
            if 0.0005 < dt < 0.5:
                # Complementary filter: combine high-pass gyro integration with low-pass accel
                # Pitch rotation rate is gy, Roll rotation rate is gx
                pitch_gyro = self._last_pitch + gy * dt
                roll_gyro = self._last_roll + gx * dt

                pitch_deg = self.alpha_filter * pitch_gyro + (1.0 - self.alpha_filter) * pitch_acc
                roll_deg = self.alpha_filter * roll_gyro + (1.0 - self.alpha_filter) * roll_acc
            else:
                # Delta t out of bounds (pause/stall), fallback to accel
                pitch_deg = pitch_acc
                roll_deg = roll_acc

        self._last_pitch = pitch_deg
        self._last_roll = roll_deg
        self._last_time = now

        return pitch_deg, roll_deg, accel_xyz

    def read_telemetry(self) -> Dict[str, Any]:
        """Returns comprehensive telemetry dictionary for diagnostics and logging."""
        pitch_deg, roll_deg, accel = self.read_attitude()
        return {
            "timestamp_ns": time.time_ns(),
            "pitch_deg": pitch_deg,
            "roll_deg": roll_deg,
            "accel_x_g": accel[0],
            "accel_y_g": accel[1],
            "accel_z_g": accel[2],
        }

    def close(self) -> None:
        """Closes the I2C bus cleanly."""
        if self._bus is not None:
            try:
                self._bus.close()
            except Exception as e:
                logger.debug("Error closing I2C bus: %s", e)
            finally:
                self._bus = None
                self._is_initialized = False

    def __enter__(self) -> "IMUReader":
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

