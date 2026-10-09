"""Unit tests for CameraDriver interface and encoding logic."""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from pi_capture_agent.camera import CameraDriver


def test_camera_driver_properties():
    """Validates parameter assignment in CameraDriver."""
    cam = CameraDriver(device="/dev/video0", width=1280, height=720, fps=30, pixel_format="MJPG")
    assert cam.device == "/dev/video0"
    assert cam.width == 1280
    assert cam.height == 720
    assert cam.fps == 30
    assert cam.pixel_format == "MJPG"
    assert cam._is_opened is False


def test_camera_driver_mocked_capture():
    """Tests read_frame and JPEG encoding with mocked OpenCV VideoCapture."""
    mock_cv2 = MagicMock()
    mock_cv2.IMWRITE_JPEG_QUALITY = 1
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True

    # Dummy 720x1280 BGR test frame
    dummy_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, dummy_frame)
    mock_cv2.imencode.return_value = (True, np.array([0xFF, 0xD8, 0xFF, 0xE0], dtype=np.uint8))

    with patch.dict("sys.modules", {"cv2": mock_cv2}):
        cam = CameraDriver(device=0)
        cam._cap = mock_cap
        cam._is_opened = True

        ts_ns, frame, jpeg_bytes = cam.read_frame(encode_jpeg=True, jpeg_quality=80)

        assert ts_ns > 0
        assert frame is not None
        assert frame.shape == (720, 1280, 3)
        assert jpeg_bytes == bytes([0xFF, 0xD8, 0xFF, 0xE0])

        cam.release()
        assert cam._is_opened is False
        assert cam._cap is None


def test_camera_driver_rotate_180():
    """Validates that cv2.flip is called when rotate_180=True."""
    mock_cv2 = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True

    dummy_frame = np.ones((720, 1280, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, dummy_frame)
    mock_cv2.flip.return_value = dummy_frame

    with patch.dict("sys.modules", {"cv2": mock_cv2}):
        cam = CameraDriver(device=0, rotate_180=True)
        cam._cap = mock_cap
        cam._is_opened = True

        cam.read_frame(encode_jpeg=False)
        mock_cv2.flip.assert_called_once_with(dummy_frame, -1)


