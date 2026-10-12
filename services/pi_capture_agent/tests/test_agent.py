"""Unit tests for Raspberry Pi 3 capture agent components."""

import struct
import numpy as np
import pytest

from pi_capture_agent.camera import CameraDriver
from pi_capture_agent.imu import IMUReader
from pi_capture_agent.packer import BinaryFramePacker, HEADER_SIZE, MAGIC_NUMBER, PROTOCOL_VERSION
from pi_capture_agent.streamer import SocketStreamer
from pi_capture_agent.cli import load_config


def test_camera_driver_mock():
    """Validates CameraDriver in synthetic mock mode."""
    cam = CameraDriver(device="/dev/video0", width=640, height=480, fps=15, mock_mode=True)
    assert cam.open() is True

    ts_ns, frame, jpeg_bytes = cam.read_frame()
    assert ts_ns > 0
    assert frame is not None
    assert frame.shape == (480, 640, 3)
    assert isinstance(jpeg_bytes, bytes)
    assert len(jpeg_bytes) > 0

    cam.release()
    assert cam._is_opened is False


def test_imu_reader_mock_and_math():
    """Validates IMUReader attitude math."""
    imu = IMUReader(bus_id=1, address=0x68, mock_mode=True)
    assert imu.initialize() is True

    pitch, roll, (ax, ay, az) = imu.read_attitude()
    assert isinstance(pitch, float)
    assert isinstance(roll, float)
    assert isinstance(ax, float)
    assert isinstance(ay, float)
    assert isinstance(az, float)

    # Test word 2s complement helper
    assert IMUReader._read_word_2c(0x00, 0x10) == 16
    assert IMUReader._read_word_2c(0xFF, 0xF0) == -16

    imu.close()


def test_binary_frame_packer():
    """Validates binary frame packer adheres to protocol specifications."""
    dummy_img = b"fake_jpeg_data_bytes_12345"
    packet = BinaryFramePacker.pack(
        frame_id=10,
        timestamp_ns=100020003000,
        pitch_deg=12.5,
        roll_deg=-0.5,
        image_bytes=dummy_img,
        width=1280,
        height=720,
    )

    assert len(packet) == HEADER_SIZE + len(dummy_img)

    magic, ver, f_id, ts, pitch, roll, p_len, w, h, _ = struct.unpack(">HHIQffIIII", packet[:HEADER_SIZE])
    assert magic == MAGIC_NUMBER == 0x5043
    assert ver == PROTOCOL_VERSION == 1
    assert f_id == 10
    assert ts == 100020003000
    assert pytest.approx(pitch, 0.01) == 12.5
    assert pytest.approx(roll, 0.01) == -0.5
    assert p_len == len(dummy_img)
    assert w == 1280
    assert h == 720


def test_socket_streamer_unreachable_target():
    """Validates SocketStreamer handles connection errors cleanly without crash."""
    # Attempt connecting to invalid host/port
    streamer = SocketStreamer(host="127.0.0.1", port=59999, retry_delay=0.1, max_retry_delay=0.2)
    assert streamer.is_connected is False

    # connect() should fail gracefully and return False
    assert streamer.connect() is False
    assert streamer.is_connected is False

    # send_frame_packet should fail gracefully and return False
    assert streamer.send_frame_packet(b"test_payload") is False

    streamer.close()


def test_load_config_missing_and_existing():
    """Validates configuration loader with missing and existing files."""
    # Missing file returns empty dict
    cfg = load_config("configs/non_existent_file.yaml")
    assert cfg == {}

    # Existing file returns dict
    cfg = load_config("configs/capture_pi.yaml")
    assert isinstance(cfg, dict)
    assert "device" in cfg
    assert "imu" in cfg
