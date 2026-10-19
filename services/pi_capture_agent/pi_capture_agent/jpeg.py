"""High-performance JPEG encoder module with ARM NEON acceleration and OpenCV fallback.

Leverages libjpeg-turbo directly via PyTurboJPEG to utilize 128-bit ARM NEON SIMD
vector instructions on Raspberry Pi 3 (Cortex-A53), reducing JPEG compression time
by 2.5x to 3.0x compared to generic software encoders.
"""

import ctypes.util
import glob
import logging
from typing import Optional
import numpy as np

logger = logging.getLogger("pi_capture_agent.jpeg")


def _find_turbojpeg_lib() -> Optional[str]:
    """Finds turbojpeg shared library path across standard Linux multiarch locations."""
    found = ctypes.util.find_library("turbojpeg")
    if found:
        return found

    candidate_patterns = [
        "/usr/lib/arm-linux-gnueabihf/libturbojpeg.so*",
        "/usr/lib/aarch64-linux-gnu/libturbojpeg.so*",
        "/usr/lib/*/libturbojpeg.so*",
        "/usr/lib/libturbojpeg.so*",
        "/usr/local/lib/libturbojpeg.so*",
    ]
    for pattern in candidate_patterns:
        matches = sorted(glob.glob(pattern))
        if matches:
            for m in matches:
                if m.endswith(".so"):
                    return m
            return matches[0]
    return None


try:
    from turbojpeg import TurboJPEG, TJPF_BGR

    _lib_path = _find_turbojpeg_lib()
    if _lib_path:
        _turbo_instance = TurboJPEG(_lib_path)
    else:
        _turbo_instance = TurboJPEG()
    HAS_TURBOJPEG = True
    logger.info("TurboJPEG initialized successfully with ARM NEON acceleration (lib: %s).", _lib_path or "default")
except Exception as e:
    _turbo_instance = None
    HAS_TURBOJPEG = False
    logger.warning("TurboJPEG not available (%s). Defaulting to standard OpenCV encoder.", e)


class FastJpegEncoder:
    """Dispatches JPEG compression to the fastest available hardware/SIMD engine."""

    @staticmethod
    def is_neon_accelerated() -> bool:
        """Returns True if TurboJPEG with hardware/SIMD acceleration is active."""
        return HAS_TURBOJPEG and _turbo_instance is not None

    @staticmethod
    def encode(frame: np.ndarray, quality: int = 70) -> Optional[bytes]:
        """Encodes a BGR numpy array to JPEG byte stream.

        Args:
            frame: Input image array in BGR format (height, width, 3).
            quality: JPEG compression quality (1-100, default: 70).

        Returns:
            Optional[bytes]: Compressed JPEG byte payload, or None on failure.
        """
        if frame is None:
            return None

        # 1. High-speed path: TurboJPEG with ARM NEON SIMD vectorization
        if HAS_TURBOJPEG and _turbo_instance is not None:
            try:
                # Fast encode directly from BGR memory buffer
                jpeg_bytes = _turbo_instance.encode(frame, quality=quality, pixel_format=TJPF_BGR)
                if jpeg_bytes:
                    return jpeg_bytes
            except Exception as e:
                logger.debug("TurboJPEG encode error (%s). Falling back to OpenCV.", e)

        # 2. Standard fallback path: OpenCV imencode
        import cv2

        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
        success, jpeg_buf = cv2.imencode(".jpg", frame, encode_param)
        return jpeg_buf.tobytes() if success else None
