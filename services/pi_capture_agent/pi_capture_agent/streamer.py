"""TCP client network streamer with auto-reconnect backoff logic.

Guarantees robust transmission of 40-byte binary header + JPEG image packets
over TCP sockets to the Ingest Server (on Developer Laptop or Jetson AGX Xavier).
"""

import socket
import time
import logging
from typing import Optional

logger = logging.getLogger("pi_capture_agent.streamer")


class SocketStreamer:
    """Robust TCP streaming client with exponential backoff auto-reconnect."""

    def __init__(
        self,
        host: str,
        port: int,
        retry_delay: float = 2.0,
        max_retry_delay: float = 10.0,
    ):
        self.host = host
        self.port = port
        self.retry_delay = retry_delay
        self.max_retry_delay = max_retry_delay
        self._current_backoff = retry_delay
        self._sock: Optional[socket.socket] = None
        self._last_attempt_time: float = 0.0

    @property
    def is_connected(self) -> bool:
        """Returns True if socket is currently established."""
        return self._sock is not None

    def connect(self) -> bool:
        """Connects to the ingest server with socket configuration."""
        self.close()
        now = time.time()

        # Throttle connection attempts
        if now - self._last_attempt_time < self._current_backoff:
            return False

        self._last_attempt_time = now
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # TCP_NODELAY disables Nagle algorithm to minimize per-packet video latency
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # Bound TCP send buffer (128 KB) to prevent multi-second kernel bufferbloat over slow Wi-Fi
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 131072)
            except Exception:
                pass
            sock.settimeout(3.0)

            sock.connect((self.host, self.port))
            # Restore normal timeout for streaming
            sock.settimeout(5.0)

            self._sock = sock
            self._current_backoff = self.retry_delay  # Reset backoff on success
            logger.info("Successfully connected to ingest server at %s:%d", self.host, self.port)
            return True

        except (socket.error, ConnectionRefusedError, TimeoutError, OSError) as e:
            logger.warning(
                "Could not connect to %s:%d (%s). Retrying in %.1fs...",
                self.host,
                self.port,
                e,
                self._current_backoff,
            )
            # Exponential backoff
            self._current_backoff = min(self._current_backoff * 1.5, self.max_retry_delay)
            self.close()
            return False

    def send_frame_packet(self, packet_bytes: bytes) -> bool:
        """Sends packed binary frame over TCP socket with error recovery.

        Returns:
            bool: True if transmitted completely, False otherwise.
        """
        if self._sock is None:
            if not self.connect():
                return False

        try:
            self._sock.sendall(packet_bytes)
            return True

        except (BrokenPipeError, ConnectionResetError, socket.timeout, OSError) as e:
            logger.warning("Socket send failure (%s). Dropping packet and triggering reconnect.", e)
            self.close()
            return False

    def close(self) -> None:
        """Closes active socket connection."""
        if self._sock is not None:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
