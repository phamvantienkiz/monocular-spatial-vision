"""Unit tests for binary frame packaging protocol."""

import struct
import pytest
from pi_capture_agent.packer import (
    BinaryFramePacker,
    HEADER_FORMAT,
    HEADER_SIZE,
    MAGIC_NUMBER,
    PROTOCOL_VERSION,
)


def test_header_size():
    """Validates that header format matches calculated struct size (40 bytes for >HHIQffIIII)."""
    assert HEADER_SIZE == 40
    assert struct.calcsize(HEADER_FORMAT) == 40



def test_pack_and_unpack():
    """Tests packaging and unpacking of frame metadata and payload."""
    frame_id = 42
    timestamp_ns = 1728468000123456789
    pitch_deg = 12.5
    roll_deg = -1.25
    payload = b"FAKE_JPEG_IMAGE_DATA_BYTES_1234567890"

    packet = BinaryFramePacker.pack(
        frame_id=frame_id,
        timestamp_ns=timestamp_ns,
        pitch_deg=pitch_deg,
        roll_deg=roll_deg,
        image_bytes=payload,
        width=1280,
        height=720,
    )

    assert len(packet) == HEADER_SIZE + len(payload)

    header, extracted_payload = BinaryFramePacker.unpack(packet)

    assert header["magic"] == MAGIC_NUMBER
    assert header["version"] == PROTOCOL_VERSION
    assert header["frame_id"] == frame_id
    assert header["timestamp_ns"] == timestamp_ns
    assert pytest.approx(header["pitch_deg"], 0.001) == pitch_deg
    assert pytest.approx(header["roll_deg"], 0.001) == roll_deg
    assert header["payload_len"] == len(payload)
    assert header["width"] == 1280
    assert header["height"] == 720
    assert header["reserved"] == 0
    assert extracted_payload == payload


def test_invalid_magic_number():
    """Ensures unpacking raises ValueError when magic number is corrupted."""
    corrupted_header = struct.pack(
        HEADER_FORMAT,
        0x1234,  # wrong magic
        PROTOCOL_VERSION,
        1,
        1000,
        0.0,
        0.0,
        4,
        1280,
        720,
        0,
    )
    with pytest.raises(ValueError, match="Invalid magic number"):
        BinaryFramePacker.unpack_header(corrupted_header)


def test_short_header():
    """Ensures unpacking raises ValueError on truncated header."""
    with pytest.raises(ValueError, match="Header length too short"):
        BinaryFramePacker.unpack_header(b"too_short")
