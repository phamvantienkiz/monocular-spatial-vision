"""IMU telemetry acquisition module for MPU6050 over I2C on Raspberry Pi 3.

TODO for Students:
- Initialize smbus2 connection to I2C bus 1 at address 0x68.
- Wake up MPU6050 by writing 0 to PWR_MGMT_1 register (0x6B).
- Read raw accelerometer registers (ACCEL_XOUT_H 0x3B to 0x40).
- Convert raw 16-bit signed integers to gravitational units (g).
- Compute instantaneous pitch (theta) and roll (phi) angles in degrees.
"""

from typing import Tuple


class IMUReader:
    """I2C interface for MPU6050 6-DOF IMU."""

    def __init__(self, bus_id: int = 1, address: int = 0x68):
        self.bus_id = bus_id
        self.address = address
        self._bus = None

    def initialize(self) -> None:
        """Initializes I2C bus and wakes up sensor."""
        # TODO: Implement I2C initialization using smbus2
        pass

    def read_attitude(self) -> Tuple[float, float, Tuple[float, float, float]]:
        """Reads acceleration and computes pitch and roll angles.

        Returns:
            Tuple[float, float, Tuple[float, float, float]]:
                - pitch_deg: Estimated camera pitch angle downwards (degrees)
                - roll_deg: Estimated camera roll angle (degrees)
                - accel_xyz: Raw acceleration (ax, ay, az) in g
        """
        # TODO: Implement attitude estimation
        raise NotImplementedError("Student implementation required: IMUReader.read_attitude()")

    def close(self) -> None:
        """Closes the I2C bus."""
        pass
