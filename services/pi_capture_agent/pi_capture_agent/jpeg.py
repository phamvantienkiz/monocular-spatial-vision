"""High-performance thread-safe JPEG encoder module with ARM NEON acceleration and OpenCV fallback.

Leverages libjpeg-turbo directly via PyTurboJPEG to utilize 128-bit ARM NEON SIMD
vector instructions on Raspberry Pi 3 (Cortex-A53). Uses thread-local TurboJPEG
handles so multiple encoder worker threads can compress frames concurrently across
all 4 Cortex-A53 cores while releasing the Python GIL.
"""

import ctypes.util
import glob
import logging
import threading
from typing import Optional
import numpy as np

logger = logging.getLogger("pi_capture_agent.jpeg")


def _find_turbojpeg_lib() -> Optional[str]:
    """Finds turbojpeg shared library path across standard Linux multiarch locations."""
    found = ctypes.util.find_library("turbojpeg")
    if found:
        return found

    candidate_patterns = [
        "/usr/lib/aarch64-linux-gnu/libturbojpeg.so*",
        "/usr/lib/arm-linux-gnueabihf/libturbojpeg.so*",
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
    from turbojpeg import TurboJPEG, TJPF_BGR, TJSAMP_420, TJSAMP_422, TJFLAG_FASTDCT

    _lib_path = _find_turbojpeg_lib()
    # Probe primary instance at import time to verify shared library availability
    _probe_instance = TurboJPEG(_lib_path) if _lib_path else TurboJPEG()
    HAS_TURBOJPEG = True
    logger.info("TurboJPEG initialized successfully with ARM NEON acceleration (lib: %s).", _lib_path or "default")
except Exception as e:
    _lib_path = None
    _probe_instance = None
    HAS_TURBOJPEG = False
    TJSAMP_420 = 2
    TJSAMP_422 = 1
    logger.warning("TurboJPEG not available (%s). Defaulting to standard OpenCV encoder.", e)

_tls = threading.local()
_warned_fallback = False


def _get_thread_encoder():
    """Returns a thread-local TurboJPEG instance (tjhandle is not thread-safe across threads)."""
    if not HAS_TURBOJPEG:
        return None
    enc = getattr(_tls, "encoder", None)
    if enc is None:
        enc = TurboJPEG(_lib_path) if _lib_path else TurboJPEG()
        _tls.encoder = enc
    return enc


class FastJpegEncoder:
    """Dispatches JPEG compression to thread-local ARM NEON TurboJPEG or OpenCV fallback."""

    @staticmethod
    def is_neon_accelerated() -> bool:
        """Returns True if TurboJPEG with hardware/SIMD acceleration is active."""
        return HAS_TURBOJPEG and _probe_instance is not None

    @staticmethod
    def encode(frame: np.ndarray, quality: int = 70, subsample_422: bool = True) -> Optional[bytes]:
        """Encodes a BGR numpy array to JPEG byte stream.

        Args:
            frame: Input image array in BGR format (height, width, 3).
            quality: JPEG compression quality (1-100, default: 70).
            subsample_422: Use 4:2:2 chroma subsampling (faster on Cortex-A53, preserves edges).

        Returns:
            Optional[bytes]: Compressed JPEG byte payload, or None on failure.
        """
        global _warned_fallback
        if frame is None:
            return None

        # Ensure C-contiguous memory layout (required by ctypes/TurboJPEG after strided slicing)
        if not frame.flags["C_CONTIGUOUS"]:
            frame = np.ascontiguousarray(frame)

        # 1. High-speed path: Thread-local TurboJPEG with ARM NEON SIMD vectorization (releases GIL)
        if HAS_TURBOJPEG:
            try:
                enc = _get_thread_encoder()
                if enc is not None:
                    subsample = TJSAMP_422 if subsample_422 else TJSAMP_420
                    jpeg_bytes = enc.encode(
                        frame,
                        quality=int(quality),
                        pixel_format=TJPF_BGR,
                        jpeg_subsample=subsample,
                        flags=TJFLAG_FASTDCT,
                    )
                    if jpeg_bytes:
                        return jpeg_bytes
            except Exception as e:
                if not _warned_fallback:
                    logger.warning("TurboJPEG encode error (%s). Falling back to OpenCV.", e)
                    _warned_fallback = True

        # 2. Standard fallback path: OpenCV imencode (also releases GIL in C++)
        import cv2

        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
        success, jpeg_buf = cv2.imencode(".jpg", frame, encode_param)
        return jpeg_buf.tobytes() if success else None
