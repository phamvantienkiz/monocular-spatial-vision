"""TCP client network streamer with auto-reconnect backoff logic.

Establishes TCP socket connection to target host and port, configures TCP_NODELAY
for minimal latency, and provides robust frame transmission with exponential backoff retry.
"""

import socket
import time
import logging
from typing import Optional

logger = logging.getLogger("pi_capture_agent.streamer")


class SocketStreamer:
    """Robust TCP streaming client with automatic reconnect handling."""

    def __init__(
        self,
        host: str,
        port: int,
        retry_delay: float = 2.0,
        max_backoff: float = 15.0,
        connect_timeout: float = 3.0,
        send_timeout: float = 5.0,
    ):
        """Initializes SocketStreamer.

        Args:
            host: Target ingest host IP address.
            port: Target ingest TCP port.
            retry_delay: Initial retry backoff delay in seconds (default: 2.0).
            max_backoff: Maximum backoff delay cap in seconds (default: 15.0).
            connect_timeout: Socket connection timeout in seconds.
            send_timeout: Socket sendall timeout in seconds.
        """
        self.host = host
        self.port = port
        self.retry_delay = retry_delay
        self.max_backoff = max_backoff
        self.connect_timeout = connect_timeout
        self.send_timeout = send_timeout

        self._sock: Optional[socket.socket] = None
        self._is_connected: bool = False
        self._current_backoff: float = retry_delay
        self._last_connect_attempt: float = 0.0

    @property
    def is_connected(self) -> bool:
        """Returns True if socket connection is currently active."""
        return self._is_connected and self._sock is not None

    def connect(self) -> bool:
        """Attempts to connect to the ingest server with low-latency socket configuration."""
        self.close()
        self._last_connect_attempt = time.time()
        logger.info("Attempting connection to ingest server at %s:%d...", self.host, self.port)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # TCP_NODELAY disables Nagle's algorithm for immediate transmission of frame buffers
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.settimeout(self.connect_timeout)

            sock.connect((self.host, self.port))
            sock.settimeout(self.send_timeout)

            self._sock = sock
            self._is_connected = True
            self._current_backoff = self.retry_delay  # Reset backoff on success
            logger.info("Successfully connected to ingest server at %s:%d.", self.host, self.port)
            return True

        except (ConnectionRefusedError, socket.timeout, OSError) as e:
            logger.warning(
                "Failed to connect to %s:%d (%s). Retrying in %.1fs...",
                self.host,
                self.port,
                e,
                self._current_backoff,
            )
            self._is_connected = False
            self.close()
            return False

    def send_frame_packet(self, packet_bytes: bytes) -> bool:
        """Sends packed binary frame over TCP socket.

        If disconnected, attempts reconnect when backoff delay has elapsed.
        If connection drops mid-send, gracefully closes socket without crashing.

        Args:
            packet_bytes: Packed frame header + JPEG payload buffer.

        Returns:
            bool: True if transmission succeeded, False otherwise.
        """
        now = time.time()

        if not self.is_connected:
            if now - self._last_connect_attempt >= self._current_backoff:
                success = self.connect()
                if not success:
                    # Exponential backoff
                    self._current_backoff = min(self._current_backoff * 1.5, self.max_backoff)
                    return False
            else:
                # Backoff period not expired yet
                return False

        if self._sock is None:
            return False

        try:
            self._sock.sendall(packet_bytes)
            return True
        except (socket.error, BrokenPipeError, ConnectionResetError, TimeoutError, OSError) as e:
            logger.warning("Socket error during transmission (%s). Closing connection.", e)
            self.close()
            self._last_connect_attempt = now
            self._current_backoff = min(self._current_backoff * 1.5, self.max_backoff)
            return False

    def close(self) -> None:
        """Closes active socket connection safely."""
        if self._sock:
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        self._is_connected = False

    def __enter__(self) -> "SocketStreamer":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

