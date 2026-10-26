/**
 * @file v4l2_camera.cpp
 * @brief V4L2 camera implementation — direct ioctl + mmap, subdev FPS/flip/exposure,
 *        and 720x480 -> 640x480 anti-stripe center-crop.
 *
 * Replaces: camera.py CameraDriver.open(), read_frame(), release(), find_unicam()
 */

#include "v4l2_camera.h"
#include "log.h"

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/select.h>
#include <unistd.h>
#include <linux/videodev2.h>
#include <linux/v4l2-subdev.h>

/* ── helpers ───────────────────────────────────────────────────────── */

static int xioctl(int fd, unsigned long request, void* arg) {
    int r;
    do { r = ioctl(fd, request, arg); } while (r == -1 && errno == EINTR);
    return r;
}

/* ── constructor / destructor ──────────────────────────────────────── */

V4l2Camera::V4l2Camera(const std::string& device, int width, int height,
                       int fps, bool rotate_180, int buf_count, bool vflip_only)
    : device_(device), req_w_(width), req_h_(height),
      fps_(fps), rotate_180_(rotate_180), vflip_only_(vflip_only),
      buf_count_(buf_count < 2 ? 4 : buf_count) {
    if (req_w_ == 640 && req_h_ == 480) {
        need_crop_ = true;
        capture_w_ = 720;
        capture_h_ = 480;
        actual_w_  = 640;
        actual_h_  = 480;
        crop_buf_.resize(640 * 480 * 2);
        LOG_INFO("Anti-stripe mode active: hardware captures 720x480, center-cropped to 640x480");
    } else {
        need_crop_ = false;
        capture_w_ = req_w_;
        capture_h_ = req_h_;
        actual_w_  = req_w_;
        actual_h_  = req_h_;
    }
}

V4l2Camera::~V4l2Camera() { close(); }

/* ── probe_unicam ──────────────────────────────────────────────────
 * Equivalent of Python find_unicam(): runs media-ctl to discover the
 * active unicam pipeline and extracts the video node + sensor entity.
 * If found, also sets the sensor pad format via media-ctl -V.
 * ──────────────────────────────────────────────────────────────────── */

bool V4l2Camera::probe_unicam() {
    for (int i = 0; i < 8; ++i) {
        char media_dev[32];
        snprintf(media_dev, sizeof(media_dev), "/dev/media%d", i);

        if (access(media_dev, F_OK) != 0) continue;

        char cmd[128];
        snprintf(cmd, sizeof(cmd), "media-ctl -d %s -p 2>/dev/null", media_dev);
        FILE* fp = popen(cmd, "r");
        if (!fp) continue;

        char line[512];
        std::string output;
        while (fgets(line, sizeof(line), fp))
            output += line;
        pclose(fp);

        /* Check for unicam driver */
        if (output.find("unicam") == std::string::npos) continue;

        /* Extract sensor entity name, e.g. "ov5640 10-003c" */
        std::string sensor_entity;
        {
            auto pos = output.find("ov5640");
            if (pos == std::string::npos) continue;
            /* Walk back to find "entity N: " */
            auto entity_start = output.rfind("entity ", pos);
            if (entity_start == std::string::npos) continue;
            auto colon = output.find(':', entity_start);
            if (colon == std::string::npos) continue;
            auto name_start = colon + 2; // skip ": "
            auto paren = output.find(" (", name_start);
            if (paren == std::string::npos) paren = output.find('\n', name_start);
            if (paren == std::string::npos) paren = output.size();
            sensor_entity = output.substr(name_start, paren - name_start);
            /* Trim trailing whitespace */
            while (!sensor_entity.empty() && sensor_entity.back() <= ' ')
                sensor_entity.pop_back();
        }

        /* Extract subdev node for sensor controls (HFLIP/VFLIP/EXPOSURE/GAIN), e.g. "/dev/v4l-subdev0" */
        {
            auto pos = output.find(sensor_entity);
            if (pos != std::string::npos) {
                auto subdev_pos = output.find("/dev/v4l-subdev", pos);
                if (subdev_pos != std::string::npos) {
                    auto end = output.find_first_not_of("0123456789", subdev_pos + 15);
                    if (end == std::string::npos) end = output.size();
                    subdev_node_ = output.substr(subdev_pos, end - subdev_pos);
                    LOG_INFO("Found sensor subdevice node: %s", subdev_node_.c_str());
                }
            }
        }

        /* Extract video node for unicam-image, e.g. "/dev/video0" */
        std::string video_node;
        {
            auto img_pos = output.find("unicam-image");
            if (img_pos == std::string::npos) continue;
            auto dev_pos = output.find("/dev/video", img_pos);
            if (dev_pos == std::string::npos) continue;
            auto end = output.find_first_not_of("0123456789", dev_pos + 10);
            video_node = output.substr(dev_pos, end - dev_pos);
        }

        LOG_INFO("Detected unicam pipeline: media=%s video=%s sensor='%s'",
                 media_dev, video_node.c_str(), sensor_entity.c_str());

        /* Configure sensor pad format & FPS via media-ctl */
        char mcmd[512];
        snprintf(mcmd, sizeof(mcmd),
                 "media-ctl -d %s -V \"'%s':0 [fmt:UYVY8_1X16/%dx%d@1/%d]\" 2>&1",
                 media_dev, sensor_entity.c_str(), capture_w_, capture_h_, fps_);
        FILE* mc = popen(mcmd, "r");
        if (mc) {
            char buf[256];
            while (fgets(buf, sizeof(buf), mc)) {} /* consume output */
            int rc = pclose(mc);
            if (rc == 0)
                LOG_INFO("Set media-ctl format UYVY8_1X16/%dx%d @ 1/%d", capture_w_, capture_h_, fps_);
            else
                LOG_WARN("media-ctl format notice (rc=%d)", rc);
        }

        device_ = video_node;
        return true;
    }

    /* Fallback: if /dev/v4l-subdev0 exists even without media-ctl output, record it */
    if (subdev_node_.empty() && access("/dev/v4l-subdev0", F_OK) == 0) {
        subdev_node_ = "/dev/v4l-subdev0";
    }
    return false;
}

/* ── open ──────────────────────────────────────────────────────────── */

bool V4l2Camera::open() {
    /* 1. Try to discover unicam pipeline (overrides device_ if found) */
    probe_unicam();

    /* 2. Open V4L2 device */
    fd_ = ::open(device_.c_str(), O_RDWR | O_NONBLOCK);
    if (fd_ < 0) {
        LOG_ERROR("Cannot open %s: %s", device_.c_str(), strerror(errno));
        return false;
    }

    /* 3. Verify capabilities */
    struct v4l2_capability cap{};
    if (xioctl(fd_, VIDIOC_QUERYCAP, &cap) < 0) {
        LOG_ERROR("VIDIOC_QUERYCAP failed: %s", strerror(errno));
        close();
        return false;
    }
    if (!(cap.capabilities & V4L2_CAP_VIDEO_CAPTURE)) {
        LOG_ERROR("%s is not a video capture device", device_.c_str());
        close();
        return false;
    }
    if (!(cap.capabilities & V4L2_CAP_STREAMING)) {
        LOG_ERROR("%s does not support streaming I/O", device_.c_str());
        close();
        return false;
    }

    /* 4. Hardware flip (writes OV5640 REG20/REG21 via kernel driver) */
    set_hardware_flip();

    /* 5. Configure pixel format and resolution */
    if (!configure_format()) { close(); return false; }

    /* 6. Configure frame rate */
    configure_framerate();

    /* 7. Request and map buffers */
    if (!request_buffers()) { close(); return false; }

    /* 8. Re-assert frame rate right before streaming */
    configure_framerate();

    /* 9. Start streaming */
    if (!start_streaming()) { close(); return false; }

    LOG_INFO("Camera opened: %s  %dx%d  (requested %dx%d @ %d fps, buffers=%d)",
             device_.c_str(), actual_w_, actual_h_, req_w_, req_h_, fps_, mapped_count_);
    return true;
}

/* ── configure_format ─────────────────────────────────────────────── */

bool V4l2Camera::configure_format() {
    struct v4l2_format fmt{};
    fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    fmt.fmt.pix.width       = static_cast<uint32_t>(capture_w_);
    fmt.fmt.pix.height      = static_cast<uint32_t>(capture_h_);
    fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_UYVY;
    fmt.fmt.pix.field       = V4L2_FIELD_NONE;

    if (xioctl(fd_, VIDIOC_S_FMT, &fmt) < 0) {
        LOG_ERROR("VIDIOC_S_FMT failed: %s", strerror(errno));
        return false;
    }

    if (!need_crop_) {
        actual_w_ = static_cast<int>(fmt.fmt.pix.width);
        actual_h_ = static_cast<int>(fmt.fmt.pix.height);
    }

    if (fmt.fmt.pix.pixelformat != V4L2_PIX_FMT_UYVY)
        LOG_WARN("Driver chose different pixel format 0x%08X", fmt.fmt.pix.pixelformat);

    return true;
}

/* ── configure_framerate ──────────────────────────────────────────── */

bool V4l2Camera::configure_framerate() {
    /* 1. Explicitly configure sensor hardware subdevice to requested FPS */
    if (!subdev_node_.empty()) {
        int sfd = ::open(subdev_node_.c_str(), O_RDWR);
        if (sfd >= 0) {
            struct v4l2_subdev_frame_interval ival{};
            ival.pad = 0;
            ival.interval.numerator = 1;
            ival.interval.denominator = static_cast<uint32_t>(fps_);
            if (xioctl(sfd, VIDIOC_SUBDEV_S_FRAME_INTERVAL, &ival) == 0) {
                LOG_INFO("Set sensor subdev %s frame interval to 1/%d via ioctl",
                         subdev_node_.c_str(), ival.interval.denominator);
            }
            ::close(sfd);
        }

        char cmd[256];
        snprintf(cmd, sizeof(cmd),
                 "v4l2-ctl -d %s --set-subdev-fps=pad=0,fps=%d 2>&1",
                 subdev_node_.c_str(), fps_);
        FILE* fp = popen(cmd, "r");
        if (fp) {
            char buf[128];
            while (fgets(buf, sizeof(buf), fp)) {}
            int rc = pclose(fp);
            if (rc == 0) {
                LOG_INFO("Set sensor subdevice %s to %d FPS", subdev_node_.c_str(), fps_);
                return true;
            }
        }
    }

    /* 2. Fallback to standard V4L2 VIDIOC_S_PARM on video node */
    struct v4l2_streamparm parm{};
    parm.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    parm.parm.capture.timeperframe.numerator   = 1;
    parm.parm.capture.timeperframe.denominator = static_cast<uint32_t>(fps_);

    if (xioctl(fd_, VIDIOC_S_PARM, &parm) < 0) {
        return false;
    }
    return true;
}

/* ── set_hardware_flip ────────────────────────────────────────────
 * Writes V4L2_CID_HFLIP and V4L2_CID_VFLIP to the sensor.
 * The kernel ov5640 driver translates these into I2C writes to
 * REG_TIMING_TC_REG20 (vflip) and REG_TIMING_TC_REG21 (hflip).
 * ──────────────────────────────────────────────────────────────────── */

void V4l2Camera::set_hardware_flip() {
    if (!rotate_180_ && !vflip_only_) return;

    int target_fd = fd_;
    int subdev_fd = -1;

    if (!subdev_node_.empty()) {
        subdev_fd = ::open(subdev_node_.c_str(), O_RDWR);
        if (subdev_fd >= 0) {
            target_fd = subdev_fd;
        } else {
            LOG_WARN("Cannot open subdev %s for flip: %s", subdev_node_.c_str(), strerror(errno));
        }
    }

    struct v4l2_control ctrl{};

    if (rotate_180_) {
        ctrl.id    = V4L2_CID_HFLIP;
        ctrl.value = 1;
        if (xioctl(target_fd, VIDIOC_S_CTRL, &ctrl) < 0)
            LOG_WARN("Failed to set HFLIP on %s: %s",
                     (subdev_fd >= 0 ? subdev_node_.c_str() : device_.c_str()), strerror(errno));
    }

    ctrl.id    = V4L2_CID_VFLIP;
    ctrl.value = 1;
    if (xioctl(target_fd, VIDIOC_S_CTRL, &ctrl) < 0)
        LOG_WARN("Failed to set VFLIP on %s: %s",
                 (subdev_fd >= 0 ? subdev_node_.c_str() : device_.c_str()), strerror(errno));

    if (subdev_fd >= 0) {
        ::close(subdev_fd);
    }

    if (rotate_180_)
        LOG_INFO("Hardware flip configured (HFLIP=1, VFLIP=1)");
    else
        LOG_INFO("Hardware vertical flip configured (VFLIP=1)");
}

/* ── set_exposure_mode ──────────────────────────────────────────────
 * Configures OV5640 exposure, gain, AWB, and 50Hz power-line anti-flicker.
 *
 * Technical Context (Balanced 25-30 FPS & Anti-Flicker Design):
 *  - In 640x480 / 720x480 MIPI mode, VTS = 1000 lines, max AEC exposure = 984 lines.
 *  - Under 50Hz AC mains (Vietnam), indoor lights pulse at 100Hz (period = 10.0 ms).
 *  - At 30 FPS (1 line = 33.33 us), 300 lines = 10.0 ms (1 cycle), 600 lines = 20.0 ms (2 cycles).
 *    At 25 FPS (1 line = 40.00 us), 250 lines = 10.0 ms (1 cycle), 500 lines = 20.0 ms (2 cycles).
 *  - Setting exposure = 350 lines (11.66 ms) caused BOTH underexposure (-60% light vs Python)
 *    AND rolling horizontal banding (11.66 ms is not a multiple of 10.0 ms).
 *  - Setting manual gain (e.g. 48 or 250) disabled hardware AGC (`V4L2_CID_AUTOGAIN=0`),
 *    starving the OV5640 AWB statistics engine of valid mid-luminance pixels and causing
 *    a blue-purple color cast.
 *  - Balanced Solution:
 *    1. Default --lock-30fps shutter exposure is scaled to exactly 20.0 ms (600 lines at 30fps,
 *       500 lines at 25fps) — +71% brighter than 350 lines AND 100% aligned with 50Hz mains!
 *    2. Hardware AGC (`V4L2_CID_AUTOGAIN=1`) and AWB (`V4L2_CID_AUTO_WHITE_BALANCE=1`) stay ON
 *       by default so OV5640 dynamically converges white balance and gain without purple tint.
 * ──────────────────────────────────────────────────────────────────── */

void V4l2Camera::set_exposure_mode(bool lock_30fps, int manual_exposure, int manual_gain) {
    int target_fd = fd_;
    int subdev_fd = -1;

    if (!subdev_node_.empty()) {
        subdev_fd = ::open(subdev_node_.c_str(), O_RDWR);
        if (subdev_fd >= 0) {
            target_fd = subdev_fd;
        }
    }

    /* 1. Always set 50Hz anti-flicker (Vietnam electrical grid) */
    struct v4l2_control flk{};
    flk.id    = V4L2_CID_POWER_LINE_FREQUENCY;
    flk.value = V4L2_CID_POWER_LINE_FREQUENCY_50HZ;
    xioctl(target_fd, VIDIOC_S_CTRL, &flk);

    /* 2. Always ensure hardware Auto White Balance (AWB) is active */
    struct v4l2_control awb{};
    awb.id    = V4L2_CID_AUTO_WHITE_BALANCE;
    awb.value = 1;
    xioctl(target_fd, VIDIOC_S_CTRL, &awb);

    struct v4l2_control ctrl{};

    if (lock_30fps || manual_exposure > 0) {
        /* Compute 20ms (2x 100Hz flicker period) anti-banding default based on target FPS:
         * 600 lines @ 30fps (~20.0ms), 500 lines @ 25fps (~20.0ms) */
        int default_20ms_lines = (fps_ > 0 && fps_ <= 30) ? (fps_ * 20) : 600;
        int exp_val = (manual_exposure > 0) ? manual_exposure : default_20ms_lines;
        if (exp_val > 984) exp_val = 984; /* OV5640 VTS=1000 max shutter limit */

        /* Switch to manual exposure */
        ctrl.id    = V4L2_CID_EXPOSURE_AUTO;
        ctrl.value = V4L2_EXPOSURE_MANUAL;
        if (xioctl(target_fd, VIDIOC_S_CTRL, &ctrl) < 0) {
            LOG_WARN("Failed to set manual exposure mode: %s", strerror(errno));
        }

        /* Set manual exposure shutter lines */
        ctrl.id    = V4L2_CID_EXPOSURE;
        ctrl.value = exp_val;
        if (xioctl(target_fd, VIDIOC_S_CTRL, &ctrl) < 0) {
            LOG_WARN("Failed to set exposure=%d: %s", exp_val, strerror(errno));
        }

        if (manual_gain > 0) {
            /* Disable auto gain only when user explicitly requests a manual gain */
            ctrl.id    = V4L2_CID_AUTOGAIN;
            ctrl.value = 0;
            xioctl(target_fd, VIDIOC_S_CTRL, &ctrl);

            ctrl.id    = V4L2_CID_GAIN;
            ctrl.value = manual_gain;
            if (xioctl(target_fd, VIDIOC_S_CTRL, &ctrl) < 0) {
                ctrl.id    = V4L2_CID_ANALOGUE_GAIN;
                ctrl.value = manual_gain;
                xioctl(target_fd, VIDIOC_S_CTRL, &ctrl);
            }
            LOG_INFO("Exposure locked (exposure=%d lines [~20ms 50Hz-aligned], manual gain=%d, AWB=ON)",
                     exp_val, manual_gain);
        } else {
            /* Keep hardware AGC enabled so OV5640 adapts gain & AWB smoothly without purple tint */
            ctrl.id    = V4L2_CID_AUTOGAIN;
            ctrl.value = 1;
            xioctl(target_fd, VIDIOC_S_CTRL, &ctrl);
            LOG_INFO("Balanced shutter lock active (exposure=%d lines [~20ms 50Hz-aligned], autogain=ON, AWB=ON)",
                     exp_val);
        }
    } else {
        /* Default: Auto-exposure + Auto-gain + AWB + 50Hz anti-flicker */
        ctrl.id    = V4L2_CID_EXPOSURE_AUTO;
        ctrl.value = V4L2_EXPOSURE_AUTO;
        xioctl(target_fd, VIDIOC_S_CTRL, &ctrl);

        ctrl.id    = V4L2_CID_AUTOGAIN;
        ctrl.value = 1;
        xioctl(target_fd, VIDIOC_S_CTRL, &ctrl);

        LOG_INFO("Sensor exposure mode: AUTO AEC/AGC/AWB (50Hz anti-flicker enabled)");
    }

    if (subdev_fd >= 0) {
        ::close(subdev_fd);
    }
}

void V4l2Camera::set_white_balance_gains(int red_bal, int blue_bal) {
    if (red_bal <= 0 && blue_bal <= 0) return;

    int target_fd = fd_;
    int subdev_fd = -1;
    if (!subdev_node_.empty()) {
        subdev_fd = ::open(subdev_node_.c_str(), O_RDWR);
        if (subdev_fd >= 0) target_fd = subdev_fd;
    }

    struct v4l2_control ctrl{};
    ctrl.id    = V4L2_CID_AUTO_WHITE_BALANCE;
    ctrl.value = 0;
    xioctl(target_fd, VIDIOC_S_CTRL, &ctrl);

    if (red_bal > 0) {
        ctrl.id    = V4L2_CID_RED_BALANCE;
        ctrl.value = red_bal;
        xioctl(target_fd, VIDIOC_S_CTRL, &ctrl);
    }
    if (blue_bal > 0) {
        ctrl.id    = V4L2_CID_BLUE_BALANCE;
        ctrl.value = blue_bal;
        xioctl(target_fd, VIDIOC_S_CTRL, &ctrl);
    }

    if (subdev_fd >= 0) ::close(subdev_fd);
    LOG_INFO("Manual white balance set (red=%d, blue=%d)", red_bal, blue_bal);
}

/* ── query_exposure_gain ────────────────────────────────────────────
 * Reads current exposure and gain from /dev/v4l-subdev0.
 * Matches Claude's diagnostic command:
 *   v4l2-ctl -d /dev/v4l-subdev0 -C exposure,gain
 * ──────────────────────────────────────────────────────────────────── */

SensorExposureInfo V4l2Camera::query_exposure_gain() const {
    SensorExposureInfo info{};
    int target_fd = fd_;
    int subdev_fd = -1;

    if (!subdev_node_.empty()) {
        subdev_fd = ::open(subdev_node_.c_str(), O_RDONLY);
        if (subdev_fd >= 0) target_fd = subdev_fd;
    }

    if (target_fd >= 0) {
        struct v4l2_control ctrl{};

        ctrl.id = V4L2_CID_EXPOSURE;
        if (xioctl(target_fd, VIDIOC_G_CTRL, &ctrl) == 0)
            info.exposure = ctrl.value;

        ctrl.id = V4L2_CID_GAIN;
        if (xioctl(target_fd, VIDIOC_G_CTRL, &ctrl) == 0) {
            info.gain = ctrl.value;
        } else {
            ctrl.id = V4L2_CID_ANALOGUE_GAIN;
            if (xioctl(target_fd, VIDIOC_G_CTRL, &ctrl) == 0)
                info.gain = ctrl.value;
        }

        ctrl.id = V4L2_CID_EXPOSURE_AUTO;
        if (xioctl(target_fd, VIDIOC_G_CTRL, &ctrl) == 0)
            info.auto_exposure = ctrl.value;

        ctrl.id = V4L2_CID_AUTOGAIN;
        if (xioctl(target_fd, VIDIOC_G_CTRL, &ctrl) == 0)
            info.autogain = ctrl.value;
    }

    if (subdev_fd >= 0) {
        ::close(subdev_fd);
    }
    return info;
}

/* ── request_buffers + mmap ───────────────────────────────────────── */

bool V4l2Camera::request_buffers() {
    struct v4l2_requestbuffers req{};
    req.count  = static_cast<uint32_t>(buf_count_);
    req.type   = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    req.memory = V4L2_MEMORY_MMAP;

    if (xioctl(fd_, VIDIOC_REQBUFS, &req) < 0) {
        LOG_ERROR("VIDIOC_REQBUFS failed: %s", strerror(errno));
        return false;
    }
    if (req.count < 2) {
        LOG_ERROR("Insufficient buffers (got %u)", req.count);
        return false;
    }

    buffers_ = new MmapBuffer[req.count]();
    mapped_count_ = static_cast<int>(req.count);

    for (uint32_t i = 0; i < req.count; ++i) {
        struct v4l2_buffer buf{};
        buf.type   = V4L2_BUF_TYPE_VIDEO_CAPTURE;
        buf.memory = V4L2_MEMORY_MMAP;
        buf.index  = i;

        if (xioctl(fd_, VIDIOC_QUERYBUF, &buf) < 0) {
            LOG_ERROR("VIDIOC_QUERYBUF [%u] failed: %s", i, strerror(errno));
            return false;
        }

        buffers_[i].length = buf.length;
        buffers_[i].start  = mmap(nullptr, buf.length,
                                  PROT_READ | PROT_WRITE, MAP_SHARED,
                                  fd_, buf.m.offset);
        if (buffers_[i].start == MAP_FAILED) {
            LOG_ERROR("mmap [%u] failed: %s", i, strerror(errno));
            buffers_[i].start = nullptr;
            return false;
        }

        /* Enqueue buffer for initial fill */
        if (xioctl(fd_, VIDIOC_QBUF, &buf) < 0) {
            LOG_ERROR("VIDIOC_QBUF [%u] failed: %s", i, strerror(errno));
            return false;
        }
    }

    LOG_INFO("Mapped %d V4L2 buffers (mmap)", mapped_count_);
    return true;
}

/* ── start / stop streaming ───────────────────────────────────────── */

bool V4l2Camera::start_streaming() {
    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    if (xioctl(fd_, VIDIOC_STREAMON, &type) < 0) {
        LOG_ERROR("VIDIOC_STREAMON failed: %s", strerror(errno));
        return false;
    }
    streaming_ = true;
    return true;
}

void V4l2Camera::stop_streaming() {
    if (!streaming_) return;
    enum v4l2_buf_type type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    xioctl(fd_, VIDIOC_STREAMOFF, &type);
    streaming_ = false;
}

/* ── dequeue / requeue ────────────────────────────────────────────── */

bool V4l2Camera::dequeue_frame(const uint8_t*& data, size_t& bytes, int& index,
                               double* wait_ms) {
    struct v4l2_buffer buf{};
    buf.type   = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;

    double t0 = wait_ms ? time_now_sec() : 0.0;

    /* Use select() to wait for a frame with timeout (500ms) */
    fd_set fds;
    FD_ZERO(&fds);
    FD_SET(fd_, &fds);
    struct timeval tv = {0, 500000}; /* 500ms */
    int r = select(fd_ + 1, &fds, nullptr, nullptr, &tv);
    if (wait_ms) *wait_ms = (time_now_sec() - t0) * 1000.0;

    if (r <= 0) {
        if (r == 0) LOG_WARN("Frame dequeue timeout (500ms)");
        return false;
    }

    if (xioctl(fd_, VIDIOC_DQBUF, &buf) < 0) {
        if (errno == EAGAIN) return false;
        LOG_ERROR("VIDIOC_DQBUF failed: %s", strerror(errno));
        return false;
    }

    index = static_cast<int>(buf.index);

    if (need_crop_) {
        const int src_stride = 720 * 2; // 1440 bytes
        const int dst_stride = 640 * 2; // 1280 bytes
        const int offset_bytes = ((720 - 640) / 2) * 2; // 40 px * 2 = 80 bytes
        const uint8_t* raw = static_cast<const uint8_t*>(buffers_[index].start);
        uint8_t* dst = crop_buf_.data();

        for (int row = 0; row < 480; ++row) {
            memcpy(dst + row * dst_stride,
                   raw + row * src_stride + offset_bytes,
                   dst_stride);
        }
        data  = dst;
        bytes = 640 * 480 * 2;
    } else {
        data  = static_cast<const uint8_t*>(buffers_[index].start);
        bytes = buf.bytesused;
    }
    return true;
}

bool V4l2Camera::requeue_buffer(int index) {
    struct v4l2_buffer buf{};
    buf.type   = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;
    buf.index  = static_cast<uint32_t>(index);

    if (xioctl(fd_, VIDIOC_QBUF, &buf) < 0) {
        LOG_ERROR("VIDIOC_QBUF [%d] failed: %s", index, strerror(errno));
        return false;
    }
    return true;
}

/* ── close ─────────────────────────────────────────────────────────── */

void V4l2Camera::close() {
    stop_streaming();

    if (buffers_) {
        for (int i = 0; i < mapped_count_; ++i) {
            if (buffers_[i].start && buffers_[i].start != MAP_FAILED)
                munmap(buffers_[i].start, buffers_[i].length);
        }
        delete[] buffers_;
        buffers_ = nullptr;
        mapped_count_ = 0;
    }

    if (fd_ >= 0) {
        ::close(fd_);
        fd_ = -1;
    }

    LOG_INFO("Camera device closed.");
}
