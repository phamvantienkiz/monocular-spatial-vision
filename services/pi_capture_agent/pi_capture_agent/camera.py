"""Camera driver module for Pcam 5C (OV5640) on Raspberry Pi 3.

Handles video acquisition via OpenCV V4L2 backend, configures resolution and FPS,
and provides raw BGR and compressed JPEG frames with nanosecond timestamps.
"""

import glob
import re
import subprocess
import time
import logging
from typing import Optional, Tuple, Union
import numpy as np

logger = logging.getLogger("pi_capture_agent.camera")


def find_unicam() -> Optional[Tuple[str, str, str]]:
    """Discovers (media_device, video_node, sensor_entity) for Raspberry Pi unicam + ov5640.

    The kernel can assign arbitrary device node numbers across reboots (/dev/video0 vs /dev/video14).
    media-ctl inspects the subdevice media graph to find the active unicam-image video node.

    Returns:
        Optional[Tuple[str, str, str]]:
            - media_dev: e.g. "/dev/media0"
            - video_node: e.g. "/dev/video0" or "/dev/video14"
            - sensor_entity: e.g. "ov5640 10-003c"
    """
    for m in sorted(glob.glob("/dev/media*")):
        try:
            r = subprocess.run(["media-ctl", "-d", m, "-p"], capture_output=True, text=True, timeout=2)
            if r.returncode != 0 or not re.search(r"^driver\s+unicam", r.stdout, re.M):
                continue
            sensor = re.search(r"entity \d+: (ov5640 [\w-]+)", r.stdout)
            video = re.search(r"unicam-image.*?device node name (/dev/video\d+)", r.stdout, re.S)
            if sensor and video:
                return m, video.group(1), sensor.group(1)
        except Exception:
            continue
    return None


class CameraDriver:
    """Wrapper for OV5640 V4L2 video acquisition on Raspberry Pi."""

    def __init__(
        self,
        device: Union[str, int] = "/dev/video0",
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        pixel_format: str = "MJPG",
        buffer_size: int = 1,
        rotate_180: bool = False,
    ):
        """Initializes CameraDriver configuration.

        Args:
            device: V4L2 device path (e.g. '/dev/video0') or device index.
            width: Desired image width (default: 1280).
            height: Desired image height (default: 720).
            fps: Desired capture frame rate (default: 30).
            pixel_format: Camera pixel format ("MJPG", "UYVY", or "YUYV").
            buffer_size: OpenCV internal V4L2 buffer size (1 minimizes latency).
            rotate_180: Rotate frames by 180 degrees (for inverted Pcam 5C mounting).
        """
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.pixel_format = pixel_format.upper()
        self.buffer_size = buffer_size
        self.rotate_180 = rotate_180


        self.media_device: Optional[str] = None
        self.sensor_entity: Optional[str] = None
        self._cap = None
        self._is_opened = False

    def open(self) -> bool:
        """Opens camera device and sets resolution and FPS."""
        try:
            import cv2
        except ImportError as exc:
            raise ImportError(
                "opencv-python-headless is required for CameraDriver. Install it with: pip install opencv-python-headless"
            ) from exc

        dev_target: Union[int, str] = self.device

        # 1. Probe for dynamic Raspberry Pi Unicam + OV5640 subdevice graph
        unicam_info = find_unicam()
        if unicam_info:
            media_dev, video_dev, sensor_entity = unicam_info
            self.media_device = media_dev
            self.sensor_entity = sensor_entity
            dev_target = video_dev
            self.pixel_format = "UYVY"
            logger.info(
                "Detected active unicam pipeline: media=%s, video=%s, sensor=%s",
                media_dev,
                video_dev,
                sensor_entity,
            )

            # Negotiate subdevice pad format via media-ctl
            try:
                cmd = [
                    "media-ctl",
                    "-d",
                    media_dev,
                    "-V",
                    f"'{sensor_entity}':0 [fmt:UYVY8_1X16/{self.width}x{self.height}]",
                ]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                if r.returncode == 0:
                    logger.info("Successfully set media-ctl format UYVY8_1X16/%dx%d", self.width, self.height)
                else:
                    logger.warning("media-ctl configuration notice: %s %s", r.stdout, r.stderr)
            except Exception as e:
                logger.warning("Could not execute media-ctl: %s", e)

        elif isinstance(self.device, str) and self.device.isdigit():
            dev_target = int(self.device)

        logger.info("Opening camera device %s (target %dx%d @ %d fps, fmt: %s)...", dev_target, self.width, self.height, self.fps, self.pixel_format)

        # Try opening with V4L2 API first (standard for Linux/Raspberry Pi)
        if hasattr(cv2, "CAP_V4L2"):
            self._cap = cv2.VideoCapture(dev_target, cv2.CAP_V4L2)
        else:
            self._cap = cv2.VideoCapture(dev_target)

        if not self._cap or not self._cap.isOpened():
            # Fallback if path string failed on some systems
            if isinstance(dev_target, str) and dev_target.startswith("/dev/video"):
                try:
                    idx = int(dev_target.replace("/dev/video", ""))
                    self._cap = cv2.VideoCapture(idx)
                except ValueError:
                    pass

        if not self._cap or not self._cap.isOpened():
            logger.error("Failed to open camera device %s", dev_target)
            self._is_opened = False
            return False

        # Configure fourcc
        if self.pixel_format == "MJPG":
            fourcc = cv2.VideoWriter_fourcc(*"MJPG")
            self._cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        elif self.pixel_format == "UYVY":
            fourcc = cv2.VideoWriter_fourcc(*"UYVY")
            self._cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        elif self.pixel_format == "YUYV":
            fourcc = cv2.VideoWriter_fourcc(*"YUYV")
            self._cap.set(cv2.CAP_PROP_FOURCC, fourcc)

        # Configure resolution and frame rate
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)

        actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = self._cap.get(cv2.CAP_PROP_FPS)

        logger.info(
            "Camera opened successfully: actual resolution %dx%d @ %.1f FPS",
            actual_w,
            actual_h,
            actual_fps,
        )

        # Warm-up frames to allow auto-exposure/white balance to settle
        for _ in range(5):
            self._cap.read()

        self._is_opened = True
        return True


    def read_frame(
        self,
        encode_jpeg: bool = True,
        jpeg_quality: int = 80,
    ) -> Tuple[int, Optional[np.ndarray], Optional[bytes]]:
        """Reads a single frame from the camera.

        Args:
            encode_jpeg: If True, encodes frame to compressed JPEG bytes.
            jpeg_quality: JPEG compression quality (1-100, default: 80).

        Returns:
            Tuple[int, Optional[np.ndarray], Optional[bytes]]:
                - Timestamp in nanoseconds (time.time_ns())
                - Decoded BGR numpy array
                - Compressed JPEG byte array (if encode_jpeg=True)
        """
        if not self._is_opened or self._cap is None:
            raise RuntimeError("CameraDriver is not opened. Call open() first.")

        import cv2

        timestamp_ns = time.time_ns()
        ret, frame = self._cap.read()

        if not ret or frame is None:
            logger.warning("Failed to grab frame from camera.")
            return timestamp_ns, None, None

        if self.rotate_180:
            # -1 flips around both X and Y axes, rotating frame by 180 degrees
            frame = cv2.flip(frame, -1)

        jpeg_bytes: Optional[bytes] = None

        if encode_jpeg:
            encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)]
            success, enc_buf = cv2.imencode(".jpg", frame, encode_params)
            if success:
                jpeg_bytes = enc_buf.tobytes()
            else:
                logger.warning("Failed to encode frame to JPEG.")

        return timestamp_ns, frame, jpeg_bytes

    def release(self) -> None:
        """Releases the camera device."""
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception as e:
                logger.debug("Error releasing camera: %s", e)
            finally:
                self._cap = None
        self._is_opened = False
        logger.info("Camera device released.")

    def __enter__(self) -> "CameraDriver":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()

