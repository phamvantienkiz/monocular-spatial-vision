/**
 * @file frame_packer.cpp
 * @brief Packs 40-byte big-endian header + JPEG payload.
 *
 * Replaces: pi_capture_agent/packer.py  BinaryFramePacker.pack()
 *
 * Wire format must be byte-identical to Python's:
 *   struct.pack(">HHIQffIIII", magic, ver, fid, ts, pitch, roll, plen, w, h, 0)
 */

#include "frame_packer.h"
#include <cstring>
#include <endian.h>

/** Converts a host float to big-endian by bit-casting through uint32_t. */
static void write_be_float(uint8_t* dst, float val) {
    uint32_t bits;
    memcpy(&bits, &val, sizeof(bits));
    bits = htobe32(bits);
    memcpy(dst, &bits, sizeof(bits));
}

static void write_be16(uint8_t* dst, uint16_t v) {
    v = htobe16(v);
    memcpy(dst, &v, sizeof(v));
}

static void write_be32(uint8_t* dst, uint32_t v) {
    v = htobe32(v);
    memcpy(dst, &v, sizeof(v));
}

static void write_be64(uint8_t* dst, uint64_t v) {
    v = htobe64(v);
    memcpy(dst, &v, sizeof(v));
}

void pack_frame_to(std::vector<uint8_t>& packet,
                   uint32_t frame_id,
                   uint64_t ts_ns,
                   float    pitch_deg,
                   float    roll_deg,
                   const uint8_t* jpeg_data,
                   uint32_t jpeg_size,
                   uint32_t width,
                   uint32_t height) {
    size_t total_size = HEADER_SIZE + jpeg_size;
    if (packet.size() != total_size)
        packet.resize(total_size);

    uint8_t* h = packet.data();

    /* Offset  0 */ write_be16(h + 0,  PROTO_MAGIC);
    /* Offset  2 */ write_be16(h + 2,  PROTO_VERSION);
    /* Offset  4 */ write_be32(h + 4,  frame_id);
    /* Offset  8 */ write_be64(h + 8,  ts_ns);
    /* Offset 16 */ write_be_float(h + 16, pitch_deg);
    /* Offset 20 */ write_be_float(h + 20, roll_deg);
    /* Offset 24 */ write_be32(h + 24, jpeg_size);
    /* Offset 28 */ write_be32(h + 28, width);
    /* Offset 32 */ write_be32(h + 32, height);
    /* Offset 36 */ write_be32(h + 36, 0); /* reserved */

    /* Append JPEG payload */
    if (jpeg_size > 0 && jpeg_data)
        memcpy(h + HEADER_SIZE, jpeg_data, jpeg_size);
}

std::vector<uint8_t> pack_frame(uint32_t frame_id,
                                uint64_t ts_ns,
                                float    pitch_deg,
                                float    roll_deg,
                                const uint8_t* jpeg_data,
                                uint32_t jpeg_size,
                                uint32_t width,
                                uint32_t height) {
    std::vector<uint8_t> packet;
    pack_frame_to(packet, frame_id, ts_ns, pitch_deg, roll_deg,
                  jpeg_data, jpeg_size, width, height);
    return packet;
}
