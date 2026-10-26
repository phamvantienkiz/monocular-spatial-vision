"""Camera driver module for Pcam 5C (OV5640) on Raspberry Pi 3.

Handles V4L2 Media Controller negotiation (bcm2835-unicam), hardware vertical flip,
anti-motion-blur sensor controls, 4-buffer MMAP ring configuration (preventing
Unicam dummy-buffer frame drops), and fast strided decimation for preview.
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
        buffer_size: int = 4,
        exposure: Optional[int] = None,
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
        # IMPORTANT: bcm2835-unicam requires >= 2 queued DMA buffers at all times;
        # setting BUFFERSIZE=1 forces Unicam into dummy_buf drops (cutting FPS to 9.8 FPS).
        self.buffer_size = max(2, int(buffer_size))
        self.exposure = exposure
        self._hw_vflip_applied = False
        self._unicam_active = False
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
                    self._unicam_active = True
                    sensor_entity = sensor.group(1)
                    # Hardware constraint: OV5640 CSI-2 sensor hardware timing supports native 1280x720 @ 30 FPS.
                    # Setting non-standard sensor modes (e.g. 640x360) breaks sensor PLL clock and causes CSI desync.
                    sensor_w, sensor_h = (1280, 720) if (self.width <= 1280 and self.height <= 720) else (self.width, self.height)
                    fmt_candidates = [
                        f"'{sensor_entity}':0 [fmt:UYVY8_1X16/{sensor_w}x{sensor_h}@1/{self.fps} field:none]",
                        f"'{sensor_entity}':0 [fmt:UYVY8_1X16/{sensor_w}x{sensor_h}@1/{self.fps}]",
                        f"'{sensor_entity}':0 [fmt:UYVY8_1X16/{sensor_w}x{sensor_h}]",
                    ]
                    for fmt_str in fmt_candidates:
                        res = subprocess.run(
                            ["media-ctl", "-d", m, "-V", fmt_str],
                            capture_output=True,
                            text=True,
                            timeout=3,
                        )
                        if res.returncode == 0:
                            break

                    logger.info(
                        "Negotiated media-ctl pipeline: %s:0 -> %dx%d @ %d FPS UYVY",
                        sensor_entity,
                        sensor_w,
                        sensor_h,
                        self.fps,
                    )
                    break
            except Exception as e:
                logger.debug("media-ctl negotiation notice: %s", e)

    def _apply_hardware_flip(self) -> bool:
        """Configures vertical flip and anti-blur controls directly on OV5640 sensor hardware via V4L2 subdev."""
        if self.mock_mode:
            self._hw_vflip_applied = False
            return False

        import glob
        import subprocess

        targets = sorted(glob.glob("/dev/v4l-subdev*"))
        if self.device not in targets:
            targets.append(self.device)

        # 1. Configure anti-flicker (50Hz) and automatic gain on sensor subdevice
        #    If self.exposure is specified, cap shutter exposure time to eliminate motion blur in indoor light.
        for dev_path in targets:
            try:
                ctrl_list = ["power_line_frequency=1", "gain_automatic=1"]
                for ctrl in ctrl_list:
                    subprocess.run(
                        ["v4l2-ctl", "-d", str(dev_path), f"--set-ctrl={ctrl}"],
                        capture_output=True,
                        text=True,
                        timeout=1,
                    )
                if self.exposure is not None and self.exposure > 0:
                    subprocess.run(
                        ["v4l2-ctl", "-d", str(dev_path), f"--set-ctrl=auto_exposure=1,exposure={int(self.exposure)}"],
                        capture_output=True,
                        text=True,
                        timeout=1,
                    )
            except Exception:
                pass

        # 2. Apply Hardware Vertical Flip (V4L2_CID_VFLIP)
        if not self.vflip or not self.use_hardware_flip:
            self._hw_vflip_applied = False
            return False

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
        """Opens camera device and sets resolution, 4-buffer DMA ring, and sensor controls."""
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

            dev_target = self.device
            if isinstance(self.device, str) and self.device.isdigit():
                dev_target = int(self.device)

            self._cap = cv2.VideoCapture(dev_target, backend)

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

            # Hardware constraint: OV5640 requires native 1280x720 sensor timing on Unicam.
            v4l_w = 1280 if (self.width <= 1280 and self.height <= 720) else self.width
            v4l_h = 720 if (self.width <= 1280 and self.height <= 720) else self.height
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(v4l_w))
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(v4l_h))

            # Only call CAP_PROP_FPS on monolithic V4L2 drivers; Unicam sets FPS on /dev/v4l-subdev0 via media-ctl
            if not self._unicam_active:
                self._cap.set(cv2.CAP_PROP_FPS, float(self.fps))

            # Allocate 4 V4L2 MMAP buffers so bcm2835-unicam DMA never starves into dummy_buf
            if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, float(self.buffer_size))

            # Apply hardware vertical flip and exposure controls on OV5640 subdevice
            self._apply_hardware_flip()

            # Warm-up frames: Unicam CSI receiver needs a few frames to settle DMA buffer
            for _ in range(3):
                self._cap.read()

            # Re-verify hardware flip after OpenCV stream initialization
            if self.vflip and self.use_hardware_flip and not self._hw_vflip_applied:
                self._apply_hardware_flip()

            actual_w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = self._cap.get(cv2.CAP_PROP_FPS)
            reported_fps = actual_fps if actual_fps and actual_fps > 0 else float(self.fps)

            logger.info(
                "Camera %s opened: %dx%d @ %.1f FPS (Requested %dx%d @ %d FPS, fmt=%s, buffers=%d)",
                self.device,
                actual_w,
                actual_h,
                reported_fps,
                self.width,
                self.height,
                self.fps,
                self.pixel_format,
                self.buffer_size,
            )
            self._is_opened = True
            return True

        except Exception as e:
            logger.warning("Error initializing camera hardware (%s). Using mock mode.", e)
            self.mock_mode = True
            self._is_opened = True
            self.is_synthetic_active = True
            return True

    @staticmethod
    def fast_downscale(frame: np.ndarray, target_size: Tuple[int, int]) -> np.ndarray:
        """Downscales a BGR frame to target_size (width, height) using zero-overhead 2x2 strided decimation when possible."""
        target_w, target_h = target_size
        src_h, src_w = frame.shape[:2]
        if (src_w, src_h) == (target_w, target_h):
            return frame
        # Fast path: exact 2x2 decimation (1280x720 -> 640x360) takes ~0.8ms vs ~3.8ms for cv2.resize
        if src_w == target_w * 2 and src_h == target_h * 2:
            return np.ascontiguousarray(frame[::2, ::2])
        import cv2

        return cv2.resize(frame, (target_w, target_h), interpolation=cv2.INTER_NEAREST)

    def _generate_synthetic_frame(self) -> Tuple[int, np.ndarray, bytes]:
        """Generates a synthetic test pattern for headless verification without hardware."""
        import cv2

        self._frame_count += 1
        ts_ns = time.time_ns()

        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame[::40, :, :] = 40
        frame[:, ::40, :] = 40

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
        """Reads a single decoded BGR frame from the camera without JPEG compression."""
        if not self._is_opened:
            raise RuntimeError("CameraDriver is not opened. Call open() first.")

        import cv2

        if self.mock_mode or self._cap is None:
            self.is_synthetic_active = True
            ts_ns, frame, _ = self._generate_synthetic_frame()
        else:
            ret, frame = self._cap.read()
            ts_ns = time.time_ns()
            if not ret or frame is None:
                self.is_synthetic_active = True
                logger.warning("Failed to grab frame from %s. Returning synthetic fallback.", self.device)
                ts_ns, frame, _ = self._generate_synthetic_frame()
            else:
                self.is_synthetic_active = False

        if frame is not None:
            if (frame.shape[1], frame.shape[0]) != (self.width, self.height):
                frame = self.fast_downscale(frame, (self.width, self.height))

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
        """Reads a single frame from the camera, with optional fast resize and JPEG compression."""
        ts_ns, frame = self.read_raw()
        if frame is None:
            return ts_ns, None, None

        if resize_to is not None:
            frame = self.fast_downscale(frame, resize_to)

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
