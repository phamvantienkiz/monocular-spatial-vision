/**
 * @file jpeg_encoder.cpp
 * @brief JPEG encoder — UYVY→YUV422P conversion + libturbojpeg compression.
 *
 * Replaces: CameraDriver.encode_to_jpeg() which used cv2.imencode(".jpg")
 *
 * Performance path on Pi 3 (ARM Cortex-A53):
 *   1. UYVY→YUV422P de-interleave (auto-vectorised by GCC with -O2 -mfpu=neon)
 *   2. tjCompressFromYUV with TJFLAG_FASTDCT (triggers NEON DCT kernels
 *      inside libjpeg-turbo's assembly backend)
 *
 * Expected: ~15-20ms for 1280x720 @ quality 65 (vs ~80ms in Python/OpenCV)
 */

#include "jpeg_encoder.h"
#include "log.h"

#include <cstdlib>
#include <cstring>

/* ── constructor / destructor ──────────────────────────────────────── */

JpegEncoder::JpegEncoder(int quality) : quality_(quality) {
    handle_ = tjInitCompress();
    if (!handle_)
        LOG_ERROR("tjInitCompress failed: %s", tjGetErrorStr());
}

JpegEncoder::~JpegEncoder() {
    if (handle_) {
        tjDestroy(handle_);
        handle_ = nullptr;
    }
    free(yuv_buf_);
    yuv_buf_ = nullptr;
}

/* ── ensure_yuv_buffer ─────────────────────────────────────────────── */

void JpegEncoder::ensure_yuv_buffer(int width, int height) {
    /* YUV 4:2:2 planar: Y(w*h) + U(w/2*h) + V(w/2*h) = w*h*2 */
    size_t needed = static_cast<size_t>(width) * height * 2;
    if (yuv_buf_ && yuv_buf_cap_ >= needed) return;

    free(yuv_buf_);
    yuv_buf_ = static_cast<uint8_t*>(malloc(needed));
    yuv_buf_cap_ = needed;

    if (!yuv_buf_)
        LOG_ERROR("Failed to allocate %zu bytes for YUV conversion buffer", needed);
}

/* ── uyvy_to_yuv422p ───────────────────────────────────────────────
 * De-interleaves packed UYVY into contiguous Y / U / V planes.
 *
 * Input  (UYVY):  [U0 Y0 V0 Y1] [U2 Y2 V2 Y3] ...
 * Output (planar): [Y0 Y1 Y2 Y3 ...] [U0 U2 ...] [V0 V2 ...]
 *
 * Inner loop compiles to efficient NEON load/store with -O2 -mfpu=neon.
 * ──────────────────────────────────────────────────────────────────── */

void JpegEncoder::uyvy_to_yuv422p(const uint8_t* src, int width, int height) {
    const int half_w = width / 2;
    uint8_t* y_dst = yuv_buf_;
    uint8_t* u_dst = yuv_buf_ + width * height;
    uint8_t* v_dst = u_dst + half_w * height;

    for (int row = 0; row < height; ++row) {
        const uint8_t* s = src + row * width * 2;
        uint8_t* y = y_dst + row * width;
        uint8_t* u = u_dst + row * half_w;
        uint8_t* v = v_dst + row * half_w;

        for (int p = 0; p < half_w; ++p) {
            u[p]         = s[0];  /* U  */
            y[p * 2]     = s[1];  /* Y0 */
            v[p]         = s[2];  /* V  */
            y[p * 2 + 1] = s[3];  /* Y1 */
            s += 4;
        }
    }
}

/* ── encode ────────────────────────────────────────────────────────── */

bool JpegEncoder::encode(const uint8_t* uyvy_data, int width, int height,
                         uint8_t*& jpeg_buf, unsigned long& jpeg_size) {
    if (!handle_) return false;

    ensure_yuv_buffer(width, height);
    if (!yuv_buf_) return false;

    /* Step 1: UYVY → planar YUV 4:2:2 */
    uyvy_to_yuv422p(uyvy_data, width, height);

    /* Step 2: Compress via libturbojpeg (NEON-accelerated DCT) */
    jpeg_buf = nullptr;
    jpeg_size = 0;

    int ret = tjCompressFromYUV(
        handle_,
        yuv_buf_,
        width,
        1,              /* align = 1 (no row padding) */
        height,
        TJSAMP_422,     /* matches our 4:2:2 planar layout */
        &jpeg_buf,
        &jpeg_size,
        quality_,
        TJFLAG_FASTDCT  /* triggers NEON SIMD path on ARM */
    );

    if (ret != 0) {
        LOG_WARN("tjCompressFromYUV failed: %s", tjGetErrorStr());
        if (jpeg_buf) { tjFree(jpeg_buf); jpeg_buf = nullptr; }
        return false;
    }

    return true;
}

/* ── free_buffer ───────────────────────────────────────────────────── */

void JpegEncoder::free_buffer(uint8_t* buf) {
    if (buf) tjFree(buf);
}
