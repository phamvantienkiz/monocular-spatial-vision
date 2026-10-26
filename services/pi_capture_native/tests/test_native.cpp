/**
 * @file test_native.cpp
 * @brief Unit tests for BinaryFramePacker (40-byte header) and UYVY->YUV422P->JPEG pipeline.
 */

#include "frame_packer.h"
#include "jpeg_encoder.h"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <endian.h>
#include <vector>

#define TEST_CHECK(cond)                                                            \
    do {                                                                            \
        if (!(cond)) {                                                              \
            std::fprintf(stderr, "[FAIL] %s:%d: %s\n", __FILE__, __LINE__, #cond);  \
            std::abort();                                                           \
        }                                                                           \
    } while (0)

static float read_be_float(const uint8_t* src) {
    uint32_t bits = 0;
    std::memcpy(&bits, src, sizeof(bits));
    bits = be32toh(bits);
    float val = 0.0f;
    std::memcpy(&val, &bits, sizeof(val));
    return val;
}

static void test_frame_packer_wire_format() {
    const uint8_t dummy_jpeg[8] = {0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0xFF, 0xD9};
    uint32_t frame_id = 42;
    uint64_t ts_ns    = 1729900000123456789ULL;
    float    pitch    = -12.345f;
    float    roll     = 3.75f;
    uint32_t width    = 1280;
    uint32_t height   = 720;

    std::vector<uint8_t> pkt = pack_frame(frame_id, ts_ns, pitch, roll,
                                          dummy_jpeg, sizeof(dummy_jpeg),
                                          width, height);
    TEST_CHECK(pkt.size() == HEADER_SIZE + sizeof(dummy_jpeg));

    /* Verify Magic 'PC' (0x50, 0x43) */
    TEST_CHECK(pkt[0] == 0x50 && pkt[1] == 0x43);

    /* Verify Version == 1 */
    uint16_t ver_be = 0;
    std::memcpy(&ver_be, pkt.data() + 2, 2);
    TEST_CHECK(be16toh(ver_be) == 1);

    /* Verify frame_id */
    uint32_t fid_be = 0;
    std::memcpy(&fid_be, pkt.data() + 4, 4);
    TEST_CHECK(be32toh(fid_be) == frame_id);

    /* Verify timestamp_ns */
    uint64_t ts_be = 0;
    std::memcpy(&ts_be, pkt.data() + 8, 8);
    TEST_CHECK(be64toh(ts_be) == ts_ns);

    /* Verify IEEE-754 floats */
    TEST_CHECK(std::fabs(read_be_float(pkt.data() + 16) - pitch) < 1e-5f);
    TEST_CHECK(std::fabs(read_be_float(pkt.data() + 20) - roll)  < 1e-5f);

    /* Verify payload_len, width, height, reserved */
    uint32_t plen_be = 0, w_be = 0, h_be = 0, res_be = 0;
    std::memcpy(&plen_be, pkt.data() + 24, 4);
    std::memcpy(&w_be,    pkt.data() + 28, 4);
    std::memcpy(&h_be,    pkt.data() + 32, 4);
    std::memcpy(&res_be,  pkt.data() + 36, 4);
    TEST_CHECK(be32toh(plen_be) == sizeof(dummy_jpeg));
    TEST_CHECK(be32toh(w_be)    == width);
    TEST_CHECK(be32toh(h_be)    == height);
    TEST_CHECK(be32toh(res_be)  == 0);

    /* Verify JPEG payload bytes */
    TEST_CHECK(std::memcmp(pkt.data() + HEADER_SIZE, dummy_jpeg, sizeof(dummy_jpeg)) == 0);
    printf("[PASS] test_frame_packer_wire_format (40-byte big-endian header verified)\n");
}

static void test_uyvy_deinterleave_and_jpeg_encode() {
    const int w = 64;
    const int h = 32;
    std::vector<uint8_t> uyvy(w * h * 2, 0);

    /* Fill synthetic pattern: U=90, Y0=180, V=140, Y1=200 */
    for (size_t i = 0; i < uyvy.size(); i += 4) {
        uyvy[i + 0] = 90;
        uyvy[i + 1] = 180;
        uyvy[i + 2] = 140;
        uyvy[i + 3] = 200;
    }

    std::vector<uint8_t> planar(w * h * 2, 0);
    JpegEncoder::uyvy_to_yuv422p_buffer(uyvy.data(), planar.data(), w, h);

    const uint8_t* y_plane = planar.data();
    const uint8_t* u_plane = y_plane + (w * h);
    const uint8_t* v_plane = u_plane + ((w / 2) * h);

    TEST_CHECK(y_plane[0] == 180 && y_plane[1] == 200);
    TEST_CHECK(u_plane[0] == 90);
    TEST_CHECK(v_plane[0] == 140);

    JpegEncoder encoder(70);
    uint8_t* jpeg_buf = nullptr;
    unsigned long jpeg_size = 0;
    bool ok = encoder.encode(uyvy.data(), w, h, jpeg_buf, jpeg_size);
    TEST_CHECK(ok);
    TEST_CHECK(jpeg_buf != nullptr && jpeg_size > 2);
    /* Verify JPEG SOI (0xFF 0xD8) and EOI (0xFF 0xD9) markers */
    TEST_CHECK(jpeg_buf[0] == 0xFF && jpeg_buf[1] == 0xD8);
    TEST_CHECK(jpeg_buf[jpeg_size - 2] == 0xFF && jpeg_buf[jpeg_size - 1] == 0xD9);
    encoder.free_buffer(jpeg_buf);

    printf("[PASS] test_uyvy_deinterleave_and_jpeg_encode (SOI/EOI markers verified, size=%luB)\n",
           jpeg_size);
}

int main() {
    test_frame_packer_wire_format();
    test_uyvy_deinterleave_and_jpeg_encode();
    printf("All native C++ unit tests PASSED.\n");
    return 0;
}
