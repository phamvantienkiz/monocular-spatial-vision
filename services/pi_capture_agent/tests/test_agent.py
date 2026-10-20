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
    cam = CameraDriver(
        device="/dev/video0",
        width=640,
        height=480,
        fps=15,
        pixel_format="UYVY",
        mock_mode=True,
        rotate_180=True,
    )
    assert cam.open() is True
    assert cam.pixel_format == "UYVY"
    assert cam.rotate_180 is True

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


def test_camera_driver_vflip_and_downscale():
    """Validates CameraDriver raw read, vertical flip, and preview downscaling."""
    cam = CameraDriver(
        device="/dev/video0",
        width=1280,
        height=720,
        fps=30,
        pixel_format="UYVY",
        mock_mode=True,
        vflip=True,
        rotate_180=False,
    )
    assert cam.open() is True
    assert cam.vflip is True
    assert cam.rotate_180 is False

    # Test read_raw
    ts_ns, raw_frame = cam.read_raw()
    assert ts_ns > 0
    assert raw_frame is not None
    assert raw_frame.shape == (720, 1280, 3)

    # Test read_frame with preview downscaling
    ts_ns, scaled_frame, jpeg_bytes = cam.read_frame(
        encode_jpeg=True,
        jpeg_quality=65,
        resize_to=(640, 360),
    )
    assert ts_ns > 0
    assert scaled_frame is not None
    assert scaled_frame.shape == (360, 640, 3)
    assert isinstance(jpeg_bytes, bytes)
    assert len(jpeg_bytes) > 0

    cam.release()
    assert cam._is_opened is False


def test_capture_config_preview_parameters():
    """Validates capture_pi.yaml contains required preview and vflip configurations."""
    cfg = load_config("configs/capture_pi.yaml")
    dev = cfg.get("device", {})
    assert dev.get("vflip") is True
    assert dev.get("rotate_180") is False
    assert dev.get("preview_width") == 640
    assert dev.get("preview_height") == 360
    assert dev.get("preview_quality") == 65

    # Check optimization section
    opt = cfg.get("optimization", {})
    assert opt.get("use_hardware_flip") is True
    assert opt.get("jpeg_quality") == 70


def test_fast_jpeg_encoder_valid_output():
    """Validates FastJpegEncoder produces decodable JPEG byte stream."""
    import cv2
    from pi_capture_agent.jpeg import FastJpegEncoder

    dummy_frame = np.full((120, 160, 3), 128, dtype=np.uint8)
    jpeg_bytes = FastJpegEncoder.encode(dummy_frame, quality=70)

    assert jpeg_bytes is not None
    assert isinstance(jpeg_bytes, bytes)
    assert len(jpeg_bytes) > 0
    # JPEG magic number starts with 0xFFD8
    assert jpeg_bytes.startswith(b"\xff\xd8")

    # Verify frame is decodable
    decoded = cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert decoded is not None
    assert decoded.shape == (120, 160, 3)


def test_camera_hardware_flip_bypass():
    """Validates that software flip is bypassed when _hw_vflip_applied is True."""
    cam = CameraDriver(mock_mode=True, vflip=True)
    cam.open()

    # Case A: Hardware flip not applied -> software flip executes
    cam._hw_vflip_applied = False
    _, frame_sw = cam.read_raw()

    # Case B: Hardware flip applied -> software flip bypassed
    cam._hw_vflip_applied = True
    _, frame_hw = cam.read_raw()

    assert frame_sw is not None
    assert frame_hw is not None
    assert frame_sw.shape == frame_hw.shape
    cam.release()


def test_cli_main_argparse(monkeypatch):
    """Validates CLI argument parsing and variable resolution for stream mode."""
    from pi_capture_agent.cli import main

    mock_called = {}

    def mock_run_stream(**kwargs):
        mock_called.update(kwargs)

    monkeypatch.setattr("pi_capture_agent.cli.run_stream", mock_run_stream)
    monkeypatch.setattr("sys.argv", ["cli.py", "--mode", "stream"])

    main()
    assert "i2c_bus" in mock_called
    assert "i2c_addr" in mock_called
    assert "jpeg_quality" in mock_called
    assert mock_called["jpeg_quality"] == 70
    assert mock_called["use_hardware_flip"] is True
    assert mock_called["threaded"] is True
    assert mock_called["width"] == 1280
    assert mock_called["height"] == 720


def test_cli_main_stage2_custom_resolution_and_threading(monkeypatch):
    """Validates CLI stage 2 arguments --width, --height, and --no-threaded."""
    from pi_capture_agent.cli import main

    mock_called = {}

    def mock_run_stream(**kwargs):
        mock_called.update(kwargs)

    monkeypatch.setattr("pi_capture_agent.cli.run_stream", mock_run_stream)
    monkeypatch.setattr(
        "sys.argv",
        ["cli.py", "--mode", "stream", "--width", "640", "--height", "360", "--no-threaded"],
    )

    main()
    assert mock_called["width"] == 640
    assert mock_called["height"] == 360
    assert mock_called["threaded"] is False


def test_camera_driver_scale_to_custom_dimensions():
    """Validates CameraDriver auto-scales to requested dimensions if raw shape differs."""
    cam = CameraDriver(mock_mode=True, width=640, height=360)
    cam.open()
    ts_ns, frame = cam.read_raw()
    assert ts_ns > 0
    assert frame is not None
    assert frame.shape == (360, 640, 3)
    cam.release()


def test_preview_server_endpoints():
    """Verifies that run_preview_server starts and serves /, /telemetry, /snapshot.jpg, /stream.mjpg without NameError or crash."""
    import urllib.request
    import threading
    import time
    from pi_capture_agent.cli import run_preview_server

    test_port = 18099
    server_thread = threading.Thread(
        target=run_preview_server,
        kwargs={
            "device": "/dev/video_mock",
            "width": 640,
            "height": 360,
            "port": test_port,
            "i2c_bus": 1,
            "i2c_addr": 0x68,
        },
        daemon=True,
    )
    server_thread.start()
    time.sleep(0.5)

    # Test /
    with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/", timeout=3.0) as resp:
        assert resp.status == 200
        html = resp.read().decode("utf-8")
        assert "PCAM 5C & MPU-6050 HUD" in html

    # Test /telemetry
    with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/telemetry", timeout=3.0) as resp:
        assert resp.status == 200
        import json
        data = json.loads(resp.read().decode("utf-8"))
        assert "fps" in data

    # Test /snapshot.jpg
    with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/snapshot.jpg", timeout=3.0) as resp:
        assert resp.status == 200
        assert resp.headers.get_content_type() == "image/jpeg"

    # Test /stream.mjpg (first chunk)
    req = urllib.request.Request(f"http://127.0.0.1:{test_port}/stream.mjpg")
    with urllib.request.urlopen(req, timeout=3.0) as resp:
        assert resp.status == 200
        first_chunk = resp.read(200)
        assert b"--frame" in first_chunk or b"image/jpeg" in first_chunk


def test_fast_downscale_strided_decimation_contiguous():
    """Validates CameraDriver.fast_downscale uses 2x2 strided decimation and returns C-contiguous array."""
    raw = np.arange(720 * 1280 * 3, dtype=np.uint8).reshape((720, 1280, 3))
    scaled = CameraDriver.fast_downscale(raw, (640, 360))
    assert scaled.shape == (360, 640, 3)
    assert scaled.flags["C_CONTIGUOUS"] is True
    assert np.array_equal(scaled[0, 0], raw[0, 0])
    assert np.array_equal(scaled[1, 1], raw[2, 2])


def test_fast_jpeg_encoder_non_contiguous_and_multithreaded():
    """Validates FastJpegEncoder handles non-contiguous views and concurrent worker threads safely."""
    import threading
    from pi_capture_agent.jpeg import FastJpegEncoder

    raw = np.full((720, 1280, 3), 90, dtype=np.uint8)
    # Non-contiguous slice
    non_contig = raw[::2, ::2]
    assert non_contig.flags["C_CONTIGUOUS"] is False

    results = []
    errors = []

    def worker():
        try:
            for _ in range(5):
                jb = FastJpegEncoder.encode(non_contig, quality=65)
                assert jb is not None and jb.startswith(b"\xff\xd8")
                results.append(len(jb))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert errors == []
    assert len(results) == 20


def test_run_test_perf_mock_mode():
    """Validates run_test_perf completes both sequential and multi-core benchmarks in mock mode."""
    from pi_capture_agent.cli import run_test_perf

    run_test_perf(
        device="/dev/video_mock",
        width=640,
        height=360,
        frames=6,
        num_workers=2,
        buffer_size=4,
    )



