"""Camera driver module for Pcam 5C (OV5640) on Raspberry Pi 3.

TODO for Students:
- Initialize V4L2 device (/dev/video0) with OpenCV VideoCapture or native v4l2.
- Configure resolution (1280x720) and format (MJPG or YUYV).
- Implement read_frame() returning (timestamp_ns, image_bytes_or_numpy).
- Implement release() to cleanly close device.
"""

from typing import Optional, Tuple
import numpy as np


class CameraDriver:
    """Wrapper for OV5640 V4L2 video acquisition."""

    def __init__(self, device: str = "/dev/video0", width: int = 1280, height: int = 720, fps: int = 30):
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self._is_opened = False

    def open(self) -> bool:
        """Opens camera device and sets resolution."""
        # TODO: Implement opening video capture
        self._is_opened = True
        return True

    def read_frame(self) -> Tuple[int, Optional[np.ndarray], Optional[bytes]]:
        """Reads a single frame from the camera.

        Returns:
            Tuple[int, Optional[np.ndarray], Optional[bytes]]:
                - Timestamp in nanoseconds
                - Decoded BGR numpy array (optional)
                - Compressed JPEG byte array (optional)
        """
        # TODO: Implement capture logic
        raise NotImplementedError("Student implementation required: CameraDriver.read_frame()")

    def release(self) -> None:
        """Releases the camera device."""
        self._is_opened = False
