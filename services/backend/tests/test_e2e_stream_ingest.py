"""Integration test: verifies end-to-end TCP streaming from Pi Agent to Ingest Service."""

import time
import cv2
import numpy as np
import pytest

from pi_capture_agent.packer import BinaryFramePacker
from pi_capture_agent.streamer import SocketStreamer
from app.services.ingest_service import IngestService


def test_e2e_stream_and_ingest():
    """Validates that frames sent via SocketStreamer are correctly received and unpacked by IngestService."""
    port = 19877
    ingest = IngestService(host="127.0.0.1", port=port, buffer_size=5)
    ingest.start()
    time.sleep(0.1)  # Allow socket server to bind

    streamer = SocketStreamer(host="127.0.0.1", port=port, retry_delay=0.1)
    connected = streamer.connect()
    assert connected is True
    assert streamer.is_connected is True

    # Create dummy JPEG image
    test_img = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.putText(test_img, "E2E INTEGRATION TEST", (100, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 2)
    _, buf = cv2.imencode(".jpg", test_img)
    jpeg_bytes = buf.tobytes()

    # Pack and transmit frame #99
    ts_ns = 1775460000000000
    packet = BinaryFramePacker.pack(
        frame_id=99,
        timestamp_ns=ts_ns,
        pitch_deg=14.25,
        roll_deg=-0.85,
        image_bytes=jpeg_bytes,
        width=1280,
        height=720,
    )

    success = streamer.send_frame_packet(packet)
    assert success is True

    # Allow ingest thread to process packet
    time.sleep(0.2)

    latest = ingest.get_latest_frame()
    assert latest is not None
    telem, frame, raw_bytes = latest

    assert telem["frame_id"] == 99
    assert telem["timestamp_ns"] == ts_ns
    assert telem["pitch_deg"] == 14.25
    assert telem["roll_deg"] == -0.85
    assert telem["width"] == 1280
    assert telem["height"] == 720
    assert telem["is_streaming"] is True

    assert frame is not None
    assert frame.shape == (720, 1280, 3)

    # Cleanup
    streamer.close()
    ingest.stop()
