"""Binary protocol packaging for monocular frame transmission.

Format Specification (36 Bytes Header, Big-Endian '>HHIQffIIII'):
- magic: uint16 (0x5043, 'PC')
- version: uint16 (1)
- frame_id: uint32
- timestamp_ns: uint64 (nanoseconds epoch)
- pitch_deg: float32 (degrees)
- roll_deg: float32 (degrees)
- payload_len: uint32 (byte length of subsequent image)
- width: uint32 (1280)
- height: uint32 (720)
- reserved: uint32 (0x00000000)

TODO for Students:
- Use python 'struct' module to pack the 36-byte header.
- Implement pack_frame(frame_id, timestamp_ns, pitch, roll, image_bytes) -> bytes.
- Ensure strict adherence to Big-Endian byte ordering.
"""

import struct

HEADER_FORMAT = ">HHIQffIIII"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # exactly 36 bytes
MAGIC_NUMBER = 0x5043  # 'PC' in hex
PROTOCOL_VERSION = 1


class BinaryFramePacker:
    """Packs telemetry and image bytes into standard network frames."""

    @staticmethod
    def pack(
        frame_id: int,
        timestamp_ns: int,
        pitch_deg: float,
        roll_deg: float,
        image_bytes: bytes,
        width: int = 1280,
        height: int = 720,
    ) -> bytes:
        """Packs header and image payload into a single contiguous byte buffer."""
        payload_len = len(image_bytes)
        header = struct.pack(
            HEADER_FORMAT,
            MAGIC_NUMBER,
            PROTOCOL_VERSION,
            frame_id,
            timestamp_ns,
            pitch_deg,
            roll_deg,
            payload_len,
            width,
            height,
            0,  # reserved
        )
        return header + image_bytes
