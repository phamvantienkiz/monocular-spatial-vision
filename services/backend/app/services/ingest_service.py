"""Network Ingest Service: TCP server receiving binary frames from Pi 3.

TODO for Students:
- Bind TCP server to port (default: 9876).
- Accept client connection from Raspberry Pi 3.
- Unpack 36-byte header, validate magic 0x5043.
- Read exact payload_len bytes into memory.
- Store latest frame in thread-safe collections.deque(maxlen=5) ring buffer.
- Provide get_latest_frame() for the perception pipeline.
"""

import collections
import logging
import threading
from typing import Optional, Tuple
import numpy as np

logger = logging.getLogger("monocular_backend.ingest")


class IngestService:
    """TCP Server daemon receiving raw frames and telemetry."""

    def __init__(self, port: int = 9876, buffer_size: int = 5):
        self.port = port
        self.buffer_size = buffer_size
        self._buffer = collections.deque(maxlen=buffer_size)
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Starts background TCP ingest listener thread."""
        logger.info("Starting TCP Ingest Server on port %d...", self.port)
        self._running = True
        # TODO: Implement socket listener loop in self._thread

    def stop(self) -> None:
        """Stops ingest server."""
        self._running = False
        logger.info("Ingest Server stopped.")

    def get_latest_frame(self) -> Optional[Tuple[dict, np.ndarray]]:
        """Retrieves the newest frame and telemetry dictionary from ring buffer.

        Returns:
            Optional[Tuple[dict, np.ndarray]]:
                - Telemetry dict (frame_id, timestamp_ns, pitch_deg, roll_deg)
                - Decoded BGR numpy image array
        """
        # TODO: Implement thread-safe pop
        return None
