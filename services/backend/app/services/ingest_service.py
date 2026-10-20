"""Network Ingest Service: TCP server receiving binary frames from Pi 3.

Decouples network socket reception from perception AI inference using a thread-safe
ring buffer and handles 40-byte big-endian binary protocol frames.
"""

import socket
import struct
import collections
import logging
import threading
import time
from typing import Optional, Tuple
import cv2
import numpy as np

logger = logging.getLogger("monocular_backend.ingest")

HEADER_FORMAT = ">HHIQffIIII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 40 bytes
MAGIC_NUMBER = 0x5043  # 'PC' in hex
PROTOCOL_VERSION = 1


class IngestService:
    """TCP Server daemon receiving raw frames and telemetry from Raspberry Pi 3."""

    def __init__(self, host: str = "0.0.0.0", port: int = 9876, buffer_size: int = 5):
        self.host = host
        self.port = port
        self.buffer_size = buffer_size
        self._buffer = collections.deque(maxlen=buffer_size)
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._server_sock: Optional[socket.socket] = None
        self._latest_telemetry: dict = {
            "frame_id": 0,
            "timestamp_ns": 0,
            "pitch_deg": 12.5,
            "roll_deg": 0.0,
            "camera_height_m": 0.285,
            "fps": 0.0,
            "is_streaming": False,
        }
        self._frame_count = 0
        self._last_fps_calc_time = time.time()
        self._fps = 0.0

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Starts background TCP ingest listener thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._socket_listener_loop, daemon=True, name="IngestServerThread")
        self._thread.start()
        logger.info("TCP Ingest Server daemon started on %s:%d (Buffer size: %d)", self.host, self.port, self.buffer_size)

    def _socket_listener_loop(self) -> None:
        """Main listening loop accepting Pi 3 socket connections."""
        try:
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.bind((self.host, self.port))
            self._server_sock.listen(2)
            self._server_sock.settimeout(1.0)  # Check self._running periodically
            logger.info("Ingest Server listening on %s:%d...", self.host, self.port)
        except Exception as e:
            logger.error("Failed to bind Ingest Server to %s:%d: %s", self.host, self.port, e)
            self._running = False
            return

        while self._running:
            try:
                client_sock, client_addr = self._server_sock.accept()
                logger.info("New connection established from Pi Agent at %s", client_addr)
                self._handle_client(client_sock)
            except socket.timeout:
                continue
            except Exception as e:
                if self._running:
                    logger.warning("Socket accept exception: %s", e)

        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None

    def _recv_exact(self, sock: socket.socket, num_bytes: int) -> Optional[bytes]:
        """Reads exactly num_bytes from socket, returning None on EOF or error."""
        buf = bytearray()
        while len(buf) < num_bytes and self._running:
            try:
                chunk = sock.recv(num_bytes - len(buf))
                if not chunk:
                    return None
                buf.extend(chunk)
            except (socket.timeout, BlockingIOError):
                continue
            except Exception:
                return None
        return bytes(buf) if len(buf) == num_bytes else None

    def _handle_client(self, client_sock: socket.socket) -> None:
        """Receives and unpacks stream frames from a single connected client."""
        client_sock.settimeout(3.0)
        try:
            client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass

        client_frames = 0
        client_start_time = time.time()

        try:
            while self._running:
                # 1. Read 40-byte header
                header_bytes = self._recv_exact(client_sock, HEADER_SIZE)
                if not header_bytes:
                    break

                magic, version, frame_id, ts_ns, pitch_deg, roll_deg, payload_len, width, height, _ = struct.unpack(
                    HEADER_FORMAT, header_bytes
                )

                if magic != MAGIC_NUMBER:
                    logger.warning("Invalid magic number 0x%04X received. Discarding frame.", magic)
                    continue

                # 2. Read image payload
                payload_bytes = self._recv_exact(client_sock, payload_len)
                if not payload_bytes:
                    break

                # 3. Decode JPEG to BGR numpy array
                img_buf = np.frombuffer(payload_bytes, dtype=np.uint8)
                frame_bgr = cv2.imdecode(img_buf, cv2.IMREAD_COLOR)

                if frame_bgr is None:
                    logger.warning("Corrupted JPEG payload for frame #%d", frame_id)
                    continue

                # 4. Update FPS calculation
                client_frames += 1
                self._frame_count += 1
                now = time.time()
                if now - self._last_fps_calc_time >= 1.0:
                    self._fps = client_frames / (now - client_start_time)
                    self._last_fps_calc_time = now

                telemetry = {
                    "frame_id": frame_id,
                    "timestamp_ns": ts_ns,
                    "pitch_deg": round(float(pitch_deg), 2),
                    "roll_deg": round(float(roll_deg), 2),
                    "camera_height_m": 0.285,
                    "width": int(width),
                    "height": int(height),
                    "payload_len": int(payload_len),
                    "fps": round(self._fps, 1),
                    "is_streaming": True,
                    "received_at": now,
                }

                # 5. Push into Ring Buffer
                with self._lock:
                    self._buffer.append((telemetry, frame_bgr, payload_bytes))
                    self._latest_telemetry = telemetry

        except Exception as e:
            logger.info("Client session ended: %s", e)
        finally:
            try:
                client_sock.close()
            except Exception:
                pass
            with self._lock:
                self._latest_telemetry["is_streaming"] = False
            logger.info("Client disconnected from Ingest Server.")

    def get_latest_frame(self) -> Optional[Tuple[dict, np.ndarray, bytes]]:
        """Retrieves the newest frame, telemetry dictionary, and JPEG bytes.

        Returns:
            Optional[Tuple[dict, np.ndarray, bytes]]:
                - Telemetry dict
                - Decoded BGR image
                - Compressed JPEG byte array
        """
        with self._lock:
            if self._buffer:
                return self._buffer[-1]

        # If no client connected yet, generate a standby waiting frame
        return self._generate_standby_frame()

    def _generate_standby_frame(self) -> Tuple[dict, np.ndarray, bytes]:
        """Generates an aesthetic standby frame with live clock when waiting for Pi 3."""
        w, h = 1280, 720
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (17, 24, 39)  # Dark slate background #111827

        # Grid lines
        for y in range(0, h, 60):
            cv2.line(frame, (0, y), (w, y), (31, 41, 55), 1)
        for x in range(0, w, 80):
            cv2.line(frame, (x, 0), (x, h), (31, 41, 55), 1)

        # Standby text
        cv2.putText(
            frame,
            "MONOCULAR SPATIAL VISION - INGEST SERVER ACTIVE",
            (180, 320),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 220, 255),
            2,
        )
        cv2.putText(
            frame,
            f"Waiting for Raspberry Pi 3 TCP stream on port {self.port}...",
            (280, 380),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (156, 163, 175),
            2,
        )
        cv2.putText(
            frame,
            f"Local Server Time: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            (440, 430),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (107, 114, 128),
            1,
        )

        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        jpeg_bytes = buf.tobytes()

        telemetry = {
            "frame_id": 0,
            "timestamp_ns": time.time_ns(),
            "pitch_deg": 12.5,
            "roll_deg": 0.0,
            "camera_height_m": 0.285,
            "fps": 0.0,
            "is_streaming": False,
        }
        return telemetry, frame, jpeg_bytes

    def get_latest_telemetry(self) -> dict:
        """Returns the current telemetry status dictionary."""
        with self._lock:
            return dict(self._latest_telemetry)

    def stop(self) -> None:
        """Stops ingest server cleanly."""
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("Ingest Server stopped.")


_global_ingest_service: Optional[IngestService] = None


def get_ingest_service(host: str = "0.0.0.0", port: int = 9876, buffer_size: int = 5) -> IngestService:
    """Returns singleton IngestService instance."""
    global _global_ingest_service
    if _global_ingest_service is None:
        _global_ingest_service = IngestService(host=host, port=port, buffer_size=buffer_size)
    return _global_ingest_service
