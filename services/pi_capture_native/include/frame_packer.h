/**
 * @file frame_packer.h
 * @brief Binary protocol frame packer — 40-byte big-endian header + JPEG payload.
 *
 * Replaces: pi_capture_agent/packer.py  (BinaryFramePacker)
 *
 * Wire format matches Python's struct.pack(">HHIQffIIII", ...) exactly:
 *
 *   Offset  Type      Field
 *   ------  --------  ---------
 *    0      uint16    magic        = 0x5043 ('PC')
 *    2      uint16    version      = 1
 *    4      uint32    frame_id
 *    8      uint64    timestamp_ns
 *   16      float32   pitch_deg    (IEEE-754 float bits in big-endian)
 *   20      float32   roll_deg     (IEEE-754 float bits in big-endian)
 *   24      uint32    payload_len  (byte length of JPEG that follows)
 *   28      uint32    width
 *   32      uint32    height
 *   36      uint32    reserved     = 0
 *   40      [payload_len bytes of JPEG data]
 *
 * All multi-byte fields are big-endian (network byte order) and strict-aliasing safe.
 */

#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

constexpr uint16_t PROTO_MAGIC   = 0x5043;
constexpr uint16_t PROTO_VERSION = 1;
constexpr size_t   HEADER_SIZE   = 40;

#pragma pack(push, 1)
struct PackedFrameHeader {
    uint16_t magic_be;         // Offset 0:  0x5043 ('PC') - Big-Endian
    uint16_t version_be;       // Offset 2:  1 - Big-Endian
    uint32_t frame_id_be;      // Offset 4:  Sequence counter - Big-Endian
    uint64_t timestamp_ns_be;  // Offset 8:  Capture timestamp (ns) - Big-Endian
    uint32_t pitch_deg_be;     // Offset 16: IEEE-754 float32 bits - Big-Endian
    uint32_t roll_deg_be;      // Offset 20: IEEE-754 float32 bits - Big-Endian
    uint32_t payload_len_be;   // Offset 24: JPEG payload size (bytes) - Big-Endian
    uint32_t width_be;         // Offset 28: Frame width - Big-Endian
    uint32_t height_be;        // Offset 32: Frame height - Big-Endian
    uint32_t reserved_be;      // Offset 36: 0x00000000
};
#pragma pack(pop)

static_assert(sizeof(PackedFrameHeader) == HEADER_SIZE, "PackedFrameHeader must be strictly 40 bytes!");

/**
 * Packs the 40-byte header + JPEG payload into a single contiguous buffer.
 * Integer/float fields are converted to big-endian for wire compatibility.
 */
std::vector<uint8_t> pack_frame(uint32_t frame_id,
                                uint64_t timestamp_ns,
                                float    pitch_deg,
                                float    roll_deg,
                                const uint8_t* jpeg_data,
                                uint32_t jpeg_size,
                                uint32_t width,
                                uint32_t height);

/** Reusable-buffer version to avoid heap allocation on every frame. */
void pack_frame_to(std::vector<uint8_t>& packet,
                   uint32_t frame_id,
                   uint64_t timestamp_ns,
                   float    pitch_deg,
                   float    roll_deg,
                   const uint8_t* jpeg_data,
                   uint32_t jpeg_size,
                   uint32_t width,
                   uint32_t height);
