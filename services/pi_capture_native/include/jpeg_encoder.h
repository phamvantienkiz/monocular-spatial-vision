/**
 * @file jpeg_encoder.h
 * @brief JPEG encoder using libturbojpeg with automatic ARM NEON acceleration.
 *
 * Replaces: CameraDriver.encode_to_jpeg() in camera.py & FastJpegEncoder in jpeg.py
 *
 * C++ calls libturbojpeg directly — same library that PyTurboJPEG wraps,
 * but without the Python GIL, object marshalling, or numpy copy overhead.
 *
 * TJFLAG_FASTDCT triggers the NEON-optimised DCT path inside libjpeg-turbo
 * (auto-detected at runtime via getauxval(AT_HWCAP)).
 */

#pragma once

#include <cstddef>
#include <cstdint>
#include <turbojpeg.h>

class JpegEncoder {
public:
    /**
     * @param quality     JPEG quality 1-100 (recommended 60-70 for streaming).
     * @param swap_uv     If true, swaps U (Cb) and V (Cr) chroma planes during de-interleave.
     * @param yuyv_order  If true, treats input bytes as [Y0 U0 Y1 V0] (YUYV) instead of [U0 Y0 V0 Y1] (UYVY).
     */
    explicit JpegEncoder(int quality = 65, bool swap_uv = false, bool yuyv_order = false);
    ~JpegEncoder();

    JpegEncoder(const JpegEncoder&) = delete;
    JpegEncoder& operator=(const JpegEncoder&) = delete;

    void set_swap_uv(bool swap_uv)       { swap_uv_ = swap_uv; }
    void set_yuyv_order(bool yuyv_order) { yuyv_order_ = yuyv_order; }
    bool swap_uv() const                 { return swap_uv_; }
    bool yuyv_order() const              { return yuyv_order_; }

    /**
     * Converts a UYVY/YUYV frame to planar YUV422P (using ARM NEON SIMD) and
     * compresses to JPEG via tjCompressFromYUV.
     *
     * @param uyvy_data   Input frame in UYVY/YUYV format (width * height * 2 bytes).
     * @param width       Frame width in pixels.
     * @param height      Frame height in pixels.
     * @param[out] jpeg_buf   Internal or newly-allocated buffer holding JPEG bytes.
     * @param[out] jpeg_size  Size of JPEG data in bytes.
     * @param[out] neon_ms    Optional pointer to record NEON de-interleave latency (ms).
     * @param[out] encode_ms  Optional pointer to record TurboJPEG DCT latency (ms).
     * @return true on success.
     */
    bool encode(const uint8_t* uyvy_data, int width, int height,
                uint8_t*& jpeg_buf, unsigned long& jpeg_size,
                double* neon_ms = nullptr, double* encode_ms = nullptr);

    /** Frees a buffer previously returned by encode() (no-op if using reusable internal pool). */
    void free_buffer(uint8_t* buf);

    /** Static helper exposed for unit testing UYVY/YUYV -> YUV422P conversion. */
    static void uyvy_to_yuv422p_buffer(const uint8_t* src, uint8_t* dst_yuv422p,
                                       int width, int height,
                                       bool swap_uv = false, bool yuyv_order = false);

private:
    void ensure_buffers(int width, int height);
    void uyvy_to_yuv422p(const uint8_t* src, int width, int height);

    tjhandle handle_        = nullptr;
    int      quality_       = 65;
    bool     swap_uv_       = false;
    bool     yuyv_order_    = false;
    uint8_t* yuv_buf_       = nullptr;
    size_t   yuv_buf_cap_   = 0;
    uint8_t* jpeg_buf_      = nullptr;
    unsigned long jpeg_cap_ = 0;
};
