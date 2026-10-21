/**
 * @file v4l2_camera.h
 * @brief V4L2 camera driver for OV5640 (Pcam 5C) on Raspberry Pi 3.
 *
 * Replaces: pi_capture_agent/camera.py  (CameraDriver + find_unicam)
 *
 * Key differences from Python version:
 *  - V4L2 ioctl + mmap   instead of  OpenCV cv2.VideoCapture
 *  - Hardware flip via V4L2_CID_HFLIP/VFLIP  instead of  cv2.flip()
 *  - Zero-copy: dequeue returns a pointer into kernel-mapped DMA buffer
 */

#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

struct MmapBuffer {
    void*  start  = nullptr;
    size_t length = 0;
};

class V4l2Camera {
public:
    /**
     * @param device      V4L2 device path (e.g. "/dev/video0").
     * @param width       Desired capture width  (default 1280).
     * @param height      Desired capture height (default 720).
     * @param fps         Desired frame rate      (default 30).
     * @param rotate_180  If true, sets V4L2 HFLIP+VFLIP on the sensor (zero CPU cost).
     * @param buf_count   Number of V4L2 mmap buffers (3-4 recommended).
     */
    V4l2Camera(const std::string& device, int width, int height,
               int fps, bool rotate_180, int buf_count = 4);
    ~V4l2Camera();

    V4l2Camera(const V4l2Camera&) = delete;
    V4l2Camera& operator=(const V4l2Camera&) = delete;

    /** Opens device, configures format, maps buffers, starts streaming. */
    bool open();

    /** Stops streaming, unmaps buffers, closes device. */
    void close();

    /**
     * Dequeues a filled frame buffer from V4L2.
     * @param[out] data   Pointer to UYVY pixel data (valid until requeue).
     * @param[out] bytes  Size of the pixel data in bytes.
     * @param[out] index  Buffer index (must pass to requeue_buffer()).
     * @return true on success, false on error or timeout.
     */
    bool dequeue_frame(const uint8_t*& data, size_t& bytes, int& index);

    /** Returns a previously dequeued buffer to V4L2's incoming queue. */
    bool requeue_buffer(int index);

    int width()  const { return actual_w_; }
    int height() const { return actual_h_; }

    /**
     * Probes /dev/media* for an active unicam + ov5640 pipeline.
     * If found, overrides device_ and configures the sensor pad via media-ctl.
     * @return true if unicam pipeline was detected and configured.
     */
    bool probe_unicam();

private:
    bool configure_format();
    bool configure_framerate();
    bool request_buffers();
    bool start_streaming();
    void stop_streaming();
    void set_hardware_flip();

    std::string device_;
    std::string subdev_node_;
    int req_w_, req_h_, fps_;
    bool rotate_180_;
    int buf_count_;

    int fd_ = -1;
    MmapBuffer* buffers_ = nullptr;
    int mapped_count_ = 0;
    int actual_w_ = 0, actual_h_ = 0;
    bool streaming_ = false;
};
