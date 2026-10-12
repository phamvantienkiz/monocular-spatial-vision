"""Network Ingest Service: TCP server receiving binary frames from Pi 3.

Listens on a TCP port, accepts one client connection from the Raspberry Pi,
reads the 36-byte BinaryFramePacker header, validates the magic number,
reads exactly payload_len bytes of JPEG payload, decodes to BGR ndarray,
and pushes (header_dict, bgr_frame) into a thread-safe ring buffer.
"""

import collections
import logging
import socket
import struct
import threading
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("monocular_backend.ingest")

# Binary frame protocol constants — must mirror pi_capture_agent/packer.py exactly.
# Format: magic(H) version(H) frame_id(I) timestamp_ns(Q) pitch(f) roll(f)
#         payload_len(I) width(I) height(I) reserved(I)  — all Big-Endian.
_HEADER_FORMAT = ">HHIQffIIII"
_HEADER_SIZE = struct.calcsize(_HEADER_FORMAT)   # 36 bytes
_MAGIC = 0x5043                                   # 'PC'


def _recv_exact(sock: socket.socket, n: int) -> Optional[bytes]:
    """Reads exactly n bytes from a TCP socket, handling stream fragmentation.

    Returns None if the connection is closed before all bytes arrive.
    """
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def _unpack_header(raw: bytes) -> dict:
    """Parses 36-byte header, raises ValueError on bad magic."""
    (magic, version, frame_id, timestamp_ns,
     pitch_deg, roll_deg, payload_len,
     width, height, _reserved) = struct.unpack(_HEADER_FORMAT, raw)
    if magic != _MAGIC:
        raise ValueError(f"Bad magic 0x{magic:04X}, expected 0x{_MAGIC:04X}")
    return {
        "frame_id": frame_id,
        "timestamp_ns": timestamp_ns,
        "pitch_deg": pitch_deg,
        "roll_deg": roll_deg,
        "payload_len": payload_len,
        "width": width,
        "height": height,
    }


class IngestService:
    """TCP Server daemon receiving raw frames and telemetry from Pi 3."""

    def __init__(self, port: int = 9876, buffer_size: int = 5):
        self.port = port
        self.buffer_size = buffer_size
        self._buffer: collections.deque = collections.deque(maxlen=buffer_size)
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._server_sock: Optional[socket.socket] = None

    def start(self) -> None:
        """Starts background TCP ingest listener thread."""
        logger.info("Starting TCP Ingest Server on port %d...", self.port)
        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stops ingest server and closes the listening socket."""
        self._running = False
        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None
        logger.info("Ingest Server stopped.")

    def get_latest_frame(self) -> Optional[Tuple[dict, np.ndarray]]:
        """Retrieves the newest (header_dict, bgr_frame) from the ring buffer.

        Returns:
            Optional[Tuple[dict, np.ndarray]]:
                - header dict: frame_id, timestamp_ns, pitch_deg, roll_deg,
                  width, height
                - Decoded BGR numpy array
            Returns None if no frame has been received yet.
        """
        with self._lock:
            if not self._buffer:
                return None
            return self._buffer[-1]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _listen_loop(self) -> None:
        """Main TCP accept loop. Re-accepts whenever the Pi reconnects."""
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind(("0.0.0.0", self.port))
        self._server_sock.listen(1)
        self._server_sock.settimeout(1.0)  # allows _running check every second
        logger.info("TCP Ingest Server listening on 0.0.0.0:%d", self.port)

        while self._running:
            try:
                client_sock, addr = self._server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            logger.info("Pi connected from %s:%d — receiving frames.", addr[0], addr[1])
            client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            client_sock.settimeout(5.0)
            self._receive_loop(client_sock, addr)

        logger.info("Ingest listener thread exited.")

    def _receive_loop(self, sock: socket.socket, addr: tuple) -> None:
        """Reads frames from a single connected Pi until disconnect."""
        try:
            while self._running:
                # 1. Read fixed-size header
                header_bytes = _recv_exact(sock, _HEADER_SIZE)
                if header_bytes is None:
                    logger.info("Pi %s:%d disconnected (header EOF).", addr[0], addr[1])
                    break

                # 2. Parse and validate header
                try:
                    header = _unpack_header(header_bytes)
                except ValueError as e:
                    logger.warning("Invalid header from %s:%d — %s. Closing.", addr[0], addr[1], e)
                    break

                payload_len = header["payload_len"]
                if payload_len == 0 or payload_len > 10 * 1024 * 1024:
                    logger.warning("Suspicious payload_len=%d from %s. Closing.", payload_len, addr[0])
                    break

                # 3. Read exact JPEG payload
                jpeg_bytes = _recv_exact(sock, payload_len)
                if jpeg_bytes is None:
                    logger.info("Pi %s:%d disconnected (payload EOF).", addr[0], addr[1])
                    break

                # 4. Decode JPEG → BGR ndarray
                buf = np.frombuffer(jpeg_bytes, dtype=np.uint8)
                bgr_frame = cv2.imdecode(buf, cv2.IMREAD_COLOR)
                if bgr_frame is None:
                    logger.warning("cv2.imdecode failed on frame #%d. Skipping.", header["frame_id"])
                    continue

                # 5. Push (header, frame) into ring buffer — overwrites oldest if full
                with self._lock:
                    self._buffer.append((header, bgr_frame))

        except (socket.timeout, ConnectionResetError, OSError) as e:
            logger.warning("Connection error from %s:%d: %s", addr[0], addr[1], e)
        finally:
            try:
                sock.close()
            except Exception:
                pass
            logger.info("Pi %s:%d session closed.", addr[0], addr[1])
