"""Camera driver module for Pcam 5C (OV5640) on Raspberry Pi 3.

Handles V4L2 video capture, hardware MJPG format selection, resolution configuration,
and timestamped frame acquisition with fallback to synthetic test patterns if hardware is absent.
"""

import time
import logging
from typing import Optional, Tuple
import numpy as np

from pi_capture_agent.jpeg import FastJpegEncoder

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
        vflip: bool = True,
        rotate_180: bool = False,
        use_hardware_flip: bool = True,
    ):
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.pixel_format = pixel_format
        self.mock_mode = mock_mode
        self.vflip = vflip
        self.rotate_180 = rotate_180
        self.use_hardware_flip = use_hardware_flip
        self._hw_vflip_applied = False
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
                    # Hardware constraint: OV5640 CSI-2 sensor hardware timing supports native 1280x720 @ 30 FPS.
                    # Setting non-standard sensor modes (like 640x360) directly in media-ctl breaks sensor PLL clock.
                    # Therefore, sensor pad is locked to native 1280x720, and CameraDriver handles 640x360 scaling.
                    sensor_w, sensor_h = (1280, 720) if (self.width, self.height) == (640, 360) else (self.width, self.height)
                    fmt_cmd_fps = [
                        "media-ctl",
                        "-d",
                        m,
                        "-V",
                        f"'{sensor_entity}':0 [fmt:UYVY8_1X16/{sensor_w}x{sensor_h}@1/{self.fps}]",
                    ]
                    res = subprocess.run(fmt_cmd_fps, capture_output=True, text=True, timeout=3)
                    if res.returncode != 0:
                        fmt_cmd = [
                            "media-ctl",
                            "-d",
                            m,
                            "-V",
                            f"'{sensor_entity}':0 [fmt:UYVY8_1X16/{sensor_w}x{sensor_h}]",
                        ]
                        subprocess.run(fmt_cmd, capture_output=True, text=True, timeout=3)

                    # Explicitly set sensor frame rate on V4L2 subdevices
                    for subdev in sorted(glob.glob("/dev/v4l-subdev*")):
                        subprocess.run(
                            ["v4l2-ctl", "-d", subdev, f"--set-subdev-fps=pad=0,fps={self.fps}"],
                            capture_output=True,
                            text=True,
                            timeout=1,
                        )
                    # And try configuring capture node frame rate
                    subprocess.run(
                        ["v4l2-ctl", "-d", str(self.device), "-p", str(self.fps)],
                        capture_output=True,
                        text=True,
                        timeout=1,
                    )

                    logger.info("Negotiated media-ctl pipeline: %s:0 -> %dx%d @ %d FPS UYVY", sensor_entity, self.width, self.height, self.fps)
                    break
            except Exception as e:
                logger.debug("media-ctl negotiation notice: %s", e)

    def _apply_hardware_flip(self) -> bool:
        """Configures vertical flip directly on OV5640 sensor hardware via V4L2 controls."""
        if not self.vflip or not self.use_hardware_flip or self.mock_mode:
            self._hw_vflip_applied = False
            return False

        import glob
        import subprocess

        # Target subdevices and camera video node
        targets = sorted(glob.glob("/dev/v4l-subdev*"))
        if self.device not in targets:
            targets.append(self.device)

        for dev_path in targets:
            try:
                res = subprocess.run(
                    ["v4l2-ctl", "-d", str(dev_path), "--set-ctrl=vertical_flip=1"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                if res.returncode == 0:
                    logger.info("Hardware vertical flip enabled successfully on %s", dev_path)
                    self._hw_vflip_applied = True
                    return True
            except Exception as e:
                logger.debug("Hardware flip attempt on %s failed: %s", dev_path, e)

        logger.info("V4L2 hardware flip not supported on current device; using software flip fallback.")
        self._hw_vflip_applied = False
        return False

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
            # Hardware constraint: OV5640 16:9 mode requires native 1280x720 sensor timing.
            # If 640x360 is requested, capture at 1280x720 and let read_raw() scale cleanly to 640x360.
            v4l_w = 1280 if (self.width, self.height) == (640, 360) else self.width
            v4l_h = 720 if (self.width, self.height) == (640, 360) else self.height
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(v4l_w))
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(v4l_h))
            self._cap.set(cv2.CAP_PROP_FPS, float(self.fps))

            # Set buffer size to 1 to eliminate frame latency
            if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1.0)

            # Attempt to apply hardware vertical flip on OV5640 sensor
            self._apply_hardware_flip()

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

        jpeg_bytes = FastJpegEncoder.encode(frame, quality=80) or b""
        return ts_ns, frame, jpeg_bytes

    def read_raw(self) -> Tuple[int, Optional[np.ndarray]]:
        """Reads a single decoded BGR frame from the camera without JPEG compression.

        Returns:
            Tuple[int, Optional[np.ndarray]]:
                - Timestamp in nanoseconds
                - Decoded BGR numpy array
        """
        if not self._is_opened:
            raise RuntimeError("CameraDriver is not opened. Call open() first.")

        import cv2

        if self.mock_mode or self._cap is None:
            self.is_synthetic_active = True
            ts_ns, frame, _ = self._generate_synthetic_frame()
        else:
            ts_ns = time.time_ns()
            ret, frame = self._cap.read()
            if not ret or frame is None:
                self.is_synthetic_active = True
                logger.warning("Failed to grab frame from %s. Returning synthetic fallback.", self.device)
                ts_ns, frame, _ = self._generate_synthetic_frame()
            else:
                self.is_synthetic_active = False

        if frame is not None:
            # If sensor delivered a different resolution from requested dimensions, scale cleanly
            if (frame.shape[1], frame.shape[0]) != (self.width, self.height):
                frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_LINEAR)

            # Apply orientation correction:
            # Only perform software CPU flip if hardware flip was not applied on sensor
            if self.vflip and not self._hw_vflip_applied:
                frame = cv2.flip(frame, 0)
            if self.rotate_180:
                frame = cv2.flip(frame, -1)

        return ts_ns, frame

    def read_frame(
        self,
        encode_jpeg: bool = True,
        jpeg_quality: int = 70,
        resize_to: Optional[Tuple[int, int]] = None,
    ) -> Tuple[int, Optional[np.ndarray], Optional[bytes]]:
        """Reads a single frame from the camera, with optional resize and JPEG compression.

        Args:
            encode_jpeg: Whether to compress to JPEG.
            jpeg_quality: JPEG compression quality (1-100, default: 70).
            resize_to: Optional (width, height) tuple to downscale frame before encoding.

        Returns:
            Tuple[int, Optional[np.ndarray], Optional[bytes]]:
                - Timestamp in nanoseconds
                - Decoded BGR numpy array
                - Compressed JPEG byte array (or None if encode_jpeg=False)
        """
        ts_ns, frame = self.read_raw()
        if frame is None:
            return ts_ns, None, None

        import cv2

        if resize_to is not None:
            frame = cv2.resize(frame, resize_to, interpolation=cv2.INTER_LINEAR)

        jpeg_bytes: Optional[bytes] = None
        if encode_jpeg:
            jpeg_bytes = FastJpegEncoder.encode(frame, quality=jpeg_quality)

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
