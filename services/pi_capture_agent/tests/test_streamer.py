"""Unit tests for SocketStreamer client connection and transmission."""

import socket
import threading
import time
import pytest

from pi_capture_agent.streamer import SocketStreamer


def test_socket_streamer_connect_and_send():
    """Tests that SocketStreamer connects to a TCP server and sends data."""
    received_bytes = bytearray()
    server_ready = threading.Event()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    port = server.getsockname()[1]
    server.listen(1)

    def server_worker():
        server_ready.set()
        client_conn, _ = server.accept()
        data = client_conn.recv(1024)
        received_bytes.extend(data)
        client_conn.close()
        server.close()

    t = threading.Thread(target=server_worker, daemon=True)
    t.start()
    server_ready.wait(timeout=2.0)

    streamer = SocketStreamer(host="127.0.0.1", port=port, retry_delay=0.1)
    connected = streamer.connect()
    assert connected is True
    assert streamer.is_connected is True

    test_payload = b"PING_FRAME_DATA_123"
    sent = streamer.send_frame_packet(test_payload)
    assert sent is True

    t.join(timeout=2.0)
    assert bytes(received_bytes) == test_payload
    streamer.close()
    assert streamer.is_connected is False


def test_socket_streamer_connection_refused():
    """Ensures streamer handles unavailable host without crashing."""
    # Connect to unused high port on loopback
    streamer = SocketStreamer(host="127.0.0.1", port=65432, retry_delay=0.1)
    connected = streamer.connect()
    assert connected is False
    assert streamer.is_connected is False

    # send_frame_packet should return False without raising exception
    sent = streamer.send_frame_packet(b"hello")
    assert sent is False
    streamer.close()
