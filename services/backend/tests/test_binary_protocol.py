"""Unit tests for the 36-byte binary protocol, IMU telemetry, and Ingest Service ring buffer."""

import struct
import time
import numpy as np
import pytest

from pi_capture_agent.packer import BinaryFramePacker, HEADER_SIZE, MAGIC_NUMBER, PROTOCOL_VERSION
from pi_capture_agent.imu import IMUReader
from app.services.ingest_service import IngestService, HEADER_FORMAT
from app.services.geometry_service import GeometryService


def test_header_size_and_format():
    """Validates that the frame header adheres strictly to the binary contract (>HHIQffIIII)."""
    assert HEADER_SIZE == struct.calcsize(HEADER_FORMAT)
    assert HEADER_SIZE == 40


def test_packer_and_unpack_roundtrip():
    """Validates full pack-unpack roundtrip for telemetry and payload."""
    frame_id = 42
    timestamp_ns = 1775460000000000
    pitch_deg = 12.50
    roll_deg = -0.15
    dummy_payload = b"\xFF\xD8\xFF\xE0" + b"\x00" * 200 + b"\xFF\xD9"  # Dummy JPEG bytes
    width = 1280
    height = 720

    packet = BinaryFramePacker.pack(
        frame_id=frame_id,
        timestamp_ns=timestamp_ns,
        pitch_deg=pitch_deg,
        roll_deg=roll_deg,
        image_bytes=dummy_payload,
        width=width,
        height=height,
    )

    # Check total packet length
    assert len(packet) == HEADER_SIZE + len(dummy_payload)

    # Unpack header
    header_bytes = packet[:HEADER_SIZE]
    magic, ver, f_id, ts, pitch, roll, p_len, w, h, reserved = struct.unpack(HEADER_FORMAT, header_bytes)

    assert magic == MAGIC_NUMBER == 0x5043
    assert ver == PROTOCOL_VERSION == 1
    assert f_id == frame_id
    assert ts == timestamp_ns
    assert pytest.approx(pitch, 0.01) == pitch_deg
    assert pytest.approx(roll, 0.01) == roll_deg
    assert p_len == len(dummy_payload)
    assert w == width
    assert h == height
    assert reserved == 0

    # Payload slice matches exactly
    assert packet[HEADER_SIZE:] == dummy_payload


def test_imu_mock_attitude():
    """Validates IMUReader attitude math in mock mode."""
    imu = IMUReader(mock_mode=True)
    assert imu.initialize() is True

    pitch, roll, (ax, ay, az) = imu.read_attitude()
    assert isinstance(pitch, float)
    assert isinstance(roll, float)
    assert isinstance(ax, float)
    assert isinstance(ay, float)
    assert isinstance(az, float)
    imu.close()


def test_ingest_service_standby_frame():
    """Validates IngestService generates aesthetic standby frames before clients connect."""
    service = IngestService(port=19876, buffer_size=3)
    telem, frame, jpeg_bytes = service.get_latest_frame()

    assert telem["is_streaming"] is False
    assert telem["frame_id"] == 0
    assert frame is not None
    assert frame.shape == (720, 1280, 3)
    assert len(jpeg_bytes) > 0


def test_geometry_ipm_tilt_compensation():
    """Validates IPM ground distance computation with dynamic IMU tilt compensation."""
    geom = GeometryService(fx=920.0, fy=920.0, cx=640.0, cy=360.0, h_c=0.285)

    # Nominal pitch 12.5 deg (0.218 rad), contact point at row v=520
    nominal_pitch_rad = np.radians(12.5)
    dist_nominal = geom.compute_ipm_distance(v_contact=520, pitch_rad=nominal_pitch_rad)
    assert dist_nominal is not None
    assert 0.5 < dist_nominal < 3.0

    # If rig tilts downwards by +3 deg (IMU total pitch = 15.5 deg), IPM distance must adjust
    tilted_pitch_rad = np.radians(15.5)
    dist_tilted = geom.compute_ipm_distance(v_contact=520, pitch_rad=tilted_pitch_rad)
    assert dist_tilted is not None
    assert dist_tilted < dist_nominal  # Steeper downward pitch means object is closer for the same pixel row

    # Horizon boundary: pixel above horizon should return None (no crash)
    dist_invalid = geom.compute_ipm_distance(v_contact=100, pitch_rad=np.radians(2.0))
    # total angle <= 0
    assert dist_invalid is None
