"""Unit tests for MPU6050 IMU attitude calculations and driver logic."""

import math
import struct
from unittest.mock import MagicMock, patch
import pytest

from pi_capture_agent.imu import (
    IMUReader,
    ACCEL_SCALE_2G,
    GYRO_SCALE_250,
)


def test_attitude_math_level_orientation():
    """When camera is level, ax=0, ay=0, az=1.0g -> pitch=0, roll=0."""
    reader = IMUReader(use_filter=False)
    reader._is_initialized = True

    # Mock read_raw_sensors returning (0, 0, 1.0)g
    with patch.object(
        reader,
        "read_raw_sensors",
        return_value=((0.0, 0.0, 1.0), (0.0, 0.0, 0.0), 25.0),
    ):
        pitch, roll, accel = reader.read_attitude()
        assert pytest.approx(pitch, abs=0.01) == 0.0
        assert pytest.approx(roll, abs=0.01) == 0.0
        assert accel == (0.0, 0.0, 1.0)


def test_attitude_math_nominal_pitch():
    """When camera is pitched downwards by 12.5 degrees (nominal mount)."""
    nominal_pitch_deg = 12.5
    pitch_rad = math.radians(nominal_pitch_deg)

    # In our coordinate system:
    # ax = -sin(pitch)
    # ay = 0
    # az = cos(pitch)
    ax = -math.sin(pitch_rad)
    ay = 0.0
    az = math.cos(pitch_rad)

    reader = IMUReader(use_filter=False)
    reader._is_initialized = True

    with patch.object(
        reader,
        "read_raw_sensors",
        return_value=((ax, ay, az), (0.0, 0.0, 0.0), 25.0),
    ):
        pitch, roll, _ = reader.read_attitude()
        assert pytest.approx(pitch, abs=0.01) == nominal_pitch_deg
        assert pytest.approx(roll, abs=0.01) == 0.0


def test_attitude_math_roll_tilt():
    """When camera is rolled laterally by +15 degrees."""
    roll_deg_target = 15.0
    roll_rad = math.radians(roll_deg_target)

    ax = 0.0
    ay = math.sin(roll_rad)
    az = math.cos(roll_rad)

    reader = IMUReader(use_filter=False)
    reader._is_initialized = True

    with patch.object(
        reader,
        "read_raw_sensors",
        return_value=((ax, ay, az), (0.0, 0.0, 0.0), 25.0),
    ):
        pitch, roll, _ = reader.read_attitude()
        assert pytest.approx(pitch, abs=0.01) == 0.0
        assert pytest.approx(roll, abs=0.01) == roll_deg_target


def test_read_raw_sensors_i2c_unpack():
    """Tests byte unpacking of 14-byte I2C block read."""
    reader = IMUReader()
    reader._is_initialized = True
    mock_bus = MagicMock()
    reader._bus = mock_bus

    # Pack 7 signed 16-bit integers
    # ax = 16384 (1.0g), ay = 0, az = 0, temp = 0 (~36.53C), gx = 131 (1.0 dps), gy = 0, gz = 0
    raw_bytes = struct.pack(">hhhhhhh", 16384, 0, 0, 0, 131, 0, 0)
    mock_bus.read_i2c_block_data.return_value = list(raw_bytes)

    accel, gyro, temp = reader.read_raw_sensors()

    assert pytest.approx(accel[0], 0.001) == 1.0
    assert pytest.approx(accel[1], 0.001) == 0.0
    assert pytest.approx(accel[2], 0.001) == 0.0
    assert pytest.approx(gyro[0], 0.001) == 1.0
    assert pytest.approx(temp, 0.1) == 36.53
