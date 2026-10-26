/**
 * @file jpeg_encoder.cpp
 * @brief UYVY -> planar YUV422P (ARM NEON vld4_u8 / vst2_u8) -> libturbojpeg tjCompressFromYUV.
 *
 * Why UYVY -> YUV422P instead of UYVY -> BGR -> JPEG?
 *  1. Avoids expensive YUV->RGB colour-space multiplication entirely.
 *  2. Keeps data at 2 bytes/pixel (vs 3 for BGR) — 33% less memory bandwidth.
 *  3. De-interleave is a pure byte shuffle using ARM NEON vld4_u8 / vst2_u8 (~1.2 ms).
 *  4. tjCompressFromYUV skips libjpeg's internal RGB->YCbCr step AND uses
 *     NEON-accelerated DCT + quantization when TJFLAG_FASTDCT | TJFLAG_NOREALLOC is set.
 */

#include "jpeg_encoder.h"
#include "log.h"

#include <cstdlib>
#include <cstring>

#if defined(__ARM_NEON) || defined(__ARM_NEON__)
#include <arm_neon.h>
#endif

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
    if (jpeg_buf_) {
        tjFree(jpeg_buf_);
        jpeg_buf_ = nullptr;
    }
}

/* ── ensure_buffers ────────────────────────────────────────────────── */

void JpegEncoder::ensure_buffers(int width, int height) {
    /* 1. YUV 4:2:2 planar: Y(w*h) + U(w/2*h) + V(w/2*h) = w*h*2 */
    size_t needed_yuv = static_cast<size_t>(width) * static_cast<size_t>(height) * 2;
    if (!yuv_buf_ || yuv_buf_cap_ < needed_yuv) {
        free(yuv_buf_);
        yuv_buf_ = static_cast<uint8_t*>(malloc(needed_yuv));
        yuv_buf_cap_ = yuv_buf_ ? needed_yuv : 0;
        if (!yuv_buf_)
            LOG_ERROR("Failed to allocate %zu bytes for YUV conversion buffer", needed_yuv);
    }

    /* 2. Pre-allocated JPEG output buffer (avoids tjAlloc/tjFree per frame) */
    unsigned long needed_jpeg = tjBufSize(width, height, TJSAMP_422);
    if (!jpeg_buf_ || jpeg_cap_ < needed_jpeg) {
        if (jpeg_buf_) tjFree(jpeg_buf_);
        jpeg_buf_ = tjAlloc(static_cast<int>(needed_jpeg));
        jpeg_cap_ = jpeg_buf_ ? needed_jpeg : 0;
        if (!jpeg_buf_)
            LOG_ERROR("Failed to allocate %lu bytes for TurboJPEG buffer", needed_jpeg);
    }
}

/* ── uyvy_to_yuv422p_buffer ────────────────────────────────────────
 * De-interleaves packed UYVY into contiguous Y / U / V planes.
 *
 * Input  (UYVY):  [U0 Y0 V0 Y1] [U2 Y2 V2 Y3] ...
 * Output (planar): [Y0 Y1 Y2 Y3 ...] [U0 U2 ...] [V0 V2 ...]
 * ──────────────────────────────────────────────────────────────────── */

void JpegEncoder::uyvy_to_yuv422p_buffer(const uint8_t* src, uint8_t* dst_yuv422p,
                                         int width, int height) {
    const int half_w = width / 2;
    uint8_t* y_dst = dst_yuv422p;
    uint8_t* u_dst = dst_yuv422p + width * height;
    uint8_t* v_dst = u_dst + half_w * height;

    for (int row = 0; row < height; ++row) {
        const uint8_t* s = src + row * width * 2;
        uint8_t* y = y_dst + row * width;
        uint8_t* u = u_dst + row * half_w;
        uint8_t* v = v_dst + row * half_w;

        int col = 0;
#if defined(__ARM_NEON) || defined(__ARM_NEON__)
        /* Process 16 pixels (32 bytes UYVY: 16 Y, 8 U, 8 V) per iteration using ARM NEON */
        for (; col <= width - 16; col += 16) {
            /* vld4_u8 deinterleaves:
             * val[0] = U0, U2, U4, U6, U8, U10, U12, U14  (8 U samples)
             * val[1] = Y0, Y2, Y4, Y6, Y8, Y10, Y12, Y14  (8 Y even samples)
             * val[2] = V0, V2, V4, V6, V8, V10, V12, V14  (8 V samples)
             * val[3] = Y1, Y3, Y5, Y7, Y9, Y11, Y13, Y15  (8 Y odd samples)
             */
            uint8x8x4_t raw = vld4_u8(s);
            vst1_u8(u, raw.val[0]);
            vst1_u8(v, raw.val[2]);

            /* Re-interleave Y0, Y1, Y2, Y3... into contiguous Y plane */
            uint8x8x2_t y_pair = {raw.val[1], raw.val[3]};
            vst2_u8(y, y_pair);

            s += 32;
            y += 16;
            u += 8;
            v += 8;
        }
#endif
        /* Scalar fallback for remaining pixels or non-ARM architectures */
        for (; col < width; col += 2) {
            *u++ = s[0];  /* U  */
            *y++ = s[1];  /* Y0 */
            *v++ = s[2];  /* V  */
            *y++ = s[3];  /* Y1 */
            s += 4;
        }
    }
}

void JpegEncoder::uyvy_to_yuv422p(const uint8_t* src, int width, int height) {
    uyvy_to_yuv422p_buffer(src, yuv_buf_, width, height);
}

/* ── encode ────────────────────────────────────────────────────────── */

bool JpegEncoder::encode(const uint8_t* uyvy_data, int width, int height,
                         uint8_t*& jpeg_buf, unsigned long& jpeg_size,
                         double* neon_ms, double* encode_ms) {
    if (!handle_ || !uyvy_data) return false;

    ensure_buffers(width, height);
    if (!yuv_buf_ || !jpeg_buf_) return false;

    /* Step 1: UYVY → planar YUV 4:2:2 */
    double t0 = neon_ms ? time_now_sec() : 0.0;
    uyvy_to_yuv422p(uyvy_data, width, height);
    if (neon_ms) *neon_ms = (time_now_sec() - t0) * 1000.0;

    /* Step 2: Compress via libturbojpeg (NEON-accelerated DCT, zero realloc) */
    double t1 = encode_ms ? time_now_sec() : 0.0;
    jpeg_buf  = jpeg_buf_;
    jpeg_size = jpeg_cap_;

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
        TJFLAG_FASTDCT | TJFLAG_NOREALLOC
    );
    if (encode_ms) *encode_ms = (time_now_sec() - t1) * 1000.0;

    if (ret != 0) {
        LOG_WARN("tjCompressFromYUV failed: %s", tjGetErrorStr());
        jpeg_buf  = nullptr;
        jpeg_size = 0;
        return false;
    }

    return true;
}

/* ── free_buffer ───────────────────────────────────────────────────── */

void JpegEncoder::free_buffer(uint8_t* buf) {
    /* If caller holds a buffer different from our reusable jpeg_buf_, free it */
    if (buf && buf != jpeg_buf_) {
        tjFree(buf);
    }
}
