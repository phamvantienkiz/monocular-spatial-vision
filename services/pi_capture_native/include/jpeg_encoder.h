/**
 * @file jpeg_encoder.h
 * @brief JPEG encoder using libturbojpeg with automatic ARM NEON acceleration.
 *
 * Replaces: CameraDriver.encode_to_jpeg() in camera.py
 *           (which used cv2.imencode via OpenCV's libjpeg)
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
     * @param quality  JPEG quality 1-100 (recommended 60-70 for streaming).
     */
    explicit JpegEncoder(int quality = 65);
    ~JpegEncoder();

    JpegEncoder(const JpegEncoder&) = delete;
    JpegEncoder& operator=(const JpegEncoder&) = delete;

    /**
     * Compresses a UYVY frame to JPEG.
     *
     * Internally converts UYVY (packed YUV 4:2:2) to planar YUV 4:2:2,
     * then calls tjCompressFromYUV with TJFLAG_FASTDCT (NEON path).
     *
     * @param uyvy_data   Pointer to UYVY pixel data (2 bytes per pixel).
     * @param width       Image width in pixels (must be even).
     * @param height      Image height in pixels.
     * @param[out] jpeg_buf   Receives pointer to compressed JPEG buffer.
     * @param[out] jpeg_size  Receives compressed size in bytes.
     * @return true on success.
     *
     * @note The returned jpeg_buf is owned by libturbojpeg's allocator.
     *       Caller MUST call free_buffer() when done.
     */
    bool encode(const uint8_t* uyvy_data, int width, int height,
                uint8_t*& jpeg_buf, unsigned long& jpeg_size);

    /** Frees a JPEG output buffer returned by encode(). */
    void free_buffer(uint8_t* buf);

    void set_quality(int q) { quality_ = q; }

private:
    /**
     * De-interleaves UYVY packed → YUV 4:2:2 planar (Y, U, V planes).
     * Layout written is contiguous: [Y: w*h] [U: w/2*h] [V: w/2*h]
     * which is the format tjCompressFromYUV expects with subsamp=TJSAMP_422.
     */
    void uyvy_to_yuv422p(const uint8_t* src, int width, int height);

    /** Ensures the planar conversion buffer is large enough. */
    void ensure_yuv_buffer(int width, int height);

    tjhandle handle_ = nullptr;
    int quality_;

    uint8_t* yuv_buf_ = nullptr;
    size_t   yuv_buf_cap_ = 0;
};
