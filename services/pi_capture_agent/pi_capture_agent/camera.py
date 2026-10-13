"""Camera driver module for Pcam 5C (OV5640) on Raspberry Pi 3.

Handles V4L2 video capture, hardware MJPG format selection, resolution configuration,
and timestamped frame acquisition with fallback to synthetic test patterns if hardware is absent.
"""

import time
import logging
from typing import Optional, Tuple
import numpy as np

logger = logging.getLogger("pi_capture_agent.camera")


class CameraDriver:
    """Wrapper for OV5640 V4L2 video acquisition on Raspberry Pi 3."""

    def __init__(
        self,
        device: str = "/dev/video0",
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        pixel_format: str = "UYVY",
        mock_mode: bool = False,
        rotate_180: bool = False,
    ):
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.pixel_format = pixel_format
        self.mock_mode = mock_mode
        self.rotate_180 = rotate_180
        self._cap = None
        self._is_opened = False
        self._frame_count = 0
        self.is_synthetic_active = mock_mode

    def _negotiate_unicam_pipeline(self) -> None:
        """Configures V4L2 Media Controller subdevice pad format if Unicam is present."""
        import glob
        import re
        import subprocess

        for m in sorted(glob.glob("/dev/media*")):
            try:
                r = subprocess.run(["media-ctl", "-d", m, "-p"], capture_output=True, text=True, timeout=2)
                if r.returncode != 0 or not re.search(r"^driver\s+unicam", r.stdout, re.M):
                    continue
                sensor = re.search(r"entity \d+: (ov5640 [\w-]+)", r.stdout)
                if sensor:
                    sensor_entity = sensor.group(1)
                    fmt_cmd = [
                        "media-ctl",
                        "-d",
                        m,
                        "-V",
                        f"'{sensor_entity}':0 [fmt:UYVY8_1X16/{self.width}x{self.height}]",
                    ]
                    subprocess.run(fmt_cmd, capture_output=True, text=True, timeout=3)
                    logger.info("Negotiated media-ctl pipeline: %s:0 -> %dx%d UYVY", sensor_entity, self.width, self.height)
                    break
            except Exception as e:
                logger.debug("media-ctl negotiation notice: %s", e)

    def open(self) -> bool:
        """Opens camera device and sets resolution and codec."""
        if self.mock_mode:
            logger.info("CameraDriver initialized in MOCK mode.")
            self._is_opened = True
            self.is_synthetic_active = True
            return True

        try:
            import cv2

            # Negotiate subdevice pad resolution via Media Controller (required by Unicam)
            self._negotiate_unicam_pipeline()

            backend = cv2.CAP_V4L2 if hasattr(cv2, "CAP_V4L2") else cv2.CAP_ANY

            # Determine device target (path or index)
            dev_target = self.device
            if isinstance(self.device, str) and self.device.isdigit():
                dev_target = int(self.device)

            self._cap = cv2.VideoCapture(dev_target, backend)

            # Fallback if device string failed to open directly
            if not self._cap.isOpened() and isinstance(dev_target, str) and "/dev/video" in dev_target:
                try:
                    idx = int(dev_target.replace("/dev/video", ""))
                    self._cap = cv2.VideoCapture(idx, backend)
                except ValueError:
                    pass

            if not self._cap.isOpened():
                logger.warning("Could not open V4L2 camera %s. Falling back to synthetic mock.", self.device)
                self.mock_mode = True
                self._is_opened = True
                self.is_synthetic_active = True
                return True

            # Configure pixel format (UYVY native to OV5640 + Unicam, or YUYV / MJPG)
            fmt = self.pixel_format.upper()
            if fmt in ("UYVY", "YUYV", "MJPG"):
                fourcc = cv2.VideoWriter_fourcc(*fmt)
                self._cap.set(cv2.CAP_PROP_FOURCC, float(fourcc))

            # Configure resolution and FPS
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(self.width))
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(self.height))
            self._cap.set(cv2.CAP_PROP_FPS, float(self.fps))

            # Set buffer size to 1 to eliminate frame latency
            if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1.0)

            # Warm-up frames: Unicam CSI receiver needs a few frames to settle DMA buffer
            for _ in range(3):
                self._cap.read()

            actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self._cap.get(cv2.CAP_PROP_FPS)

            logger.info(
                "Camera %s opened: %dx%d @ %.1f FPS (Requested %dx%d @ %d FPS, fmt=%s)",
                self.device,
                actual_w,
                actual_h,
                actual_fps,
                self.width,
                self.height,
                self.fps,
                self.pixel_format,
            )
            self._is_opened = True
            return True

        except Exception as e:
            logger.warning("Error initializing camera hardware (%s). Using mock mode.", e)
            self.mock_mode = True
            self._is_opened = True
            return True

    def _generate_synthetic_frame(self) -> Tuple[int, np.ndarray, bytes]:
        """Generates a synthetic test pattern for headless verification without hardware."""
        import cv2

        self._frame_count += 1
        ts_ns = time.time_ns()

        # Create gradient canvas
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        # Add a subtle grid
        frame[::40, :, :] = 40
        frame[:, ::40, :] = 40

        # Draw moving indicator
        cx = int((self.width / 2) + 200 * np.sin(self._frame_count * 0.05))
        cy = int((self.height / 2) + 100 * np.cos(self._frame_count * 0.05))
        cv2.circle(frame, (cx, cy), 30, (0, 255, 128), -1)

        cv2.putText(
            frame,
            f"SYNTHETIC TEST PATTERN | Frame #{self._frame_count}",
            (40, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 220, 255),
            2,
        )
        cv2.putText(
            frame,
            f"Res: {self.width}x{self.height} | Time: {time.strftime('%H:%M:%S')}",
            (40, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (180, 180, 180),
            2,
        )

        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
        _, jpeg_buf = cv2.imencode(".jpg", frame, encode_param)
        return ts_ns, frame, jpeg_buf.tobytes()

    def read_frame(self) -> Tuple[int, Optional[np.ndarray], Optional[bytes]]:
        """Reads a single frame from the camera.

        Returns:
            Tuple[int, Optional[np.ndarray], Optional[bytes]]:
                - Timestamp in nanoseconds
                - Decoded BGR numpy array
                - Compressed JPEG byte array
        """
        if not self._is_opened:
            raise RuntimeError("CameraDriver is not opened. Call open() first.")

        if self.mock_mode or self._cap is None:
            self.is_synthetic_active = True
            return self._generate_synthetic_frame()

        import cv2

        ts_ns = time.time_ns()
        ret, frame = self._cap.read()
        if not ret or frame is None:
            self.is_synthetic_active = True
            logger.warning("Failed to grab frame from %s. Returning synthetic fallback.", self.device)
            return self._generate_synthetic_frame()

        self.is_synthetic_active = False

        if self.rotate_180:
            frame = cv2.flip(frame, -1)

        # Compress to JPEG
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
        success, jpeg_buf = cv2.imencode(".jpg", frame, encode_param)
        jpeg_bytes = jpeg_buf.tobytes() if success else None

        return ts_ns, frame, jpeg_bytes

    def release(self) -> None:
        """Releases the camera device."""
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None
        self._is_opened = False
        logger.info("Camera device released.")
