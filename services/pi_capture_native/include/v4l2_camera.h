/**
 * @file v4l2_camera.h
 * @brief V4L2 camera driver for OV5640 (Pcam 5C) on Raspberry Pi 3 (bcm2835-unicam).
 *
 * Replaces: pi_capture_agent/camera.py  (CameraDriver + find_unicam)
 *
 * Key features learned & refined from Pi 3 field testing:
 *  - Automatic /dev/media* + /dev/v4l-subdev* discovery (bcm2835-unicam)
 *  - Direct VIDIOC_SUBDEV_S_FRAME_INTERVAL ioctl on subdev to enforce 30 FPS
 *  - Anti-stripe mode: 640x480 requests automatically capture at stable 720x480
 *    and center-crop to 640x480 (eliminates MIPI CSI-2 clock drift stripes)
 *  - Hardware flip via V4L2_CID_HFLIP / V4L2_CID_VFLIP on sensor subdev (0% CPU)
 *  - 50Hz Anti-flicker + Configurable Exposure/Gain lock (--lock-30fps) +
 *    real-time exposure/gain readout for 15fps vs 30fps diagnostics
 */

#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

struct MmapBuffer {
    void*  start  = nullptr;
    size_t length = 0;
};

struct SensorExposureInfo {
    int exposure      = -1;
    int gain          = -1;
    int auto_exposure = -1;
    int autogain      = -1;
};

class V4l2Camera {
public:
    /**
     * @param device      V4L2 device path (e.g. "/dev/video0").
     * @param width       Desired capture width  (default 1280).
     * @param height      Desired capture height (default 720).
     * @param fps         Desired frame rate     (default 30).
     * @param rotate_180  If true, sets V4L2 HFLIP+VFLIP on the sensor (zero CPU cost).
     * @param buf_count   Number of V4L2 mmap buffers (4 recommended for bcm2835-unicam).
     * @param vflip_only  If true (and rotate_180 is false), sets V4L2_CID_VFLIP=1.
     */
    V4l2Camera(const std::string& device, int width, int height,
               int fps, bool rotate_180, int buf_count = 4, bool vflip_only = false);
    ~V4l2Camera();

    V4l2Camera(const V4l2Camera&) = delete;
    V4l2Camera& operator=(const V4l2Camera&) = delete;

    /** Opens device, configures media-ctl/subdev format, maps buffers, starts streaming. */
    bool open();

    /** Stops streaming, unmaps buffers, closes device. */
    void close();

    /**
     * Dequeues a filled frame buffer from V4L2.
     * @param[out] data      Pointer to UYVY pixel data (valid until requeue).
     * @param[out] bytes     Size of the pixel data in bytes.
     * @param[out] index     Buffer index (must pass to requeue_buffer()).
     * @param[out] wait_ms   Optional pointer to record VSYNC poll/select wait time (ms).
     * @return true on success, false on error or timeout.
     */
    bool dequeue_frame(const uint8_t*& data, size_t& bytes, int& index,
                       double* wait_ms = nullptr);

    /** Returns a previously dequeued buffer to V4L2's incoming queue. */
    bool requeue_buffer(int index);

    int width()  const { return actual_w_; }
    int height() const { return actual_h_; }
    const std::string& device_node() const { return device_; }
    const std::string& subdev_node() const { return subdev_node_; }

    /**
     * Controls exposure, gain, AWB, and 50Hz power-line anti-flicker on OV5640 subdev:
     * - Always enables 50Hz anti-flicker (Vietnam grid) and Auto White Balance (AWB).
     * - lock_30fps = true: sets shutter exposure to a 50Hz-aligned value (default 600 lines = 20ms,
     *   exact 2x multiple of 10ms 100Hz light cycle) and keeps hardware AGC enabled (or applies
     *   bounded manual_gain if > 0) so image is bright, flicker-free, and maintains 25-30 FPS.
     * - lock_30fps = false: restores automatic exposure (AEC) and automatic gain (AGC),
     *   unless manual_exposure > 0 is explicitly specified.
     */
    void set_exposure_mode(bool lock_30fps, int manual_exposure = -1, int manual_gain = -1);

    /** Sets manual Red/Blue white balance gains (disables AWB when red_bal > 0 or blue_bal > 0). */
    void set_white_balance_gains(int red_bal, int blue_bal);

    /**
     * Reads current exposure (shutter lines) and gain from /dev/v4l-subdev0
     * (Equivalent to: v4l2-ctl -d /dev/v4l-subdev0 -C exposure,gain).
     */
    SensorExposureInfo query_exposure_gain() const;

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
    int capture_w_ = 0, capture_h_ = 0;
    bool rotate_180_;
    bool vflip_only_;
    bool need_crop_ = false;
    int buf_count_;

    std::vector<uint8_t> crop_buf_;

    int fd_ = -1;
    MmapBuffer* buffers_ = nullptr;
    int mapped_count_ = 0;
    int actual_w_ = 0, actual_h_ = 0;
    bool streaming_ = false;
};
