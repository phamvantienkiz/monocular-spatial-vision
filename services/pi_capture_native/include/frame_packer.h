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
 *   16      float32   pitch_deg
 *   20      float32   roll_deg
 *   24      uint32    payload_len  (byte length of JPEG that follows)
 *   28      uint32    width
 *   32      uint32    height
 *   36      uint32    reserved     = 0
 *   40      [payload_len bytes of JPEG data]
 *
 * All multi-byte fields are big-endian (network byte order).
 */

#pragma once

#include <cstdint>
#include <vector>

constexpr uint16_t PROTO_MAGIC   = 0x5043;
constexpr uint16_t PROTO_VERSION = 1;
constexpr size_t   HEADER_SIZE   = 40;

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
