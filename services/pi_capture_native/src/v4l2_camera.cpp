/**
 * @file v4l2_camera.cpp
 * @brief V4L2 camera implementation — direct ioctl + mmap, hardware flip.
 *
 * Replaces: camera.py CameraDriver.open(), read_frame(), release()
 *           camera.py find_unicam()
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
#include <unistd.h>
#include <linux/videodev2.h>

/* ── helpers ───────────────────────────────────────────────────────── */

static int xioctl(int fd, unsigned long request, void* arg) {
    int r;
    do { r = ioctl(fd, request, arg); } while (r == -1 && errno == EINTR);
    return r;
}

/* ── constructor / destructor ──────────────────────────────────────── */

V4l2Camera::V4l2Camera(const std::string& device, int width, int height,
                       int fps, bool rotate_180, int buf_count)
    : device_(device), req_w_(width), req_h_(height),
      fps_(fps), rotate_180_(rotate_180), buf_count_(buf_count) {}

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
            auto pos = output.find("ov5640 ");
            if (pos == std::string::npos) continue;
            /* Walk back to find "entity N: " */
            auto entity_start = output.rfind("entity ", pos);
            if (entity_start == std::string::npos) continue;
            auto colon = output.find(':', entity_start);
            if (colon == std::string::npos) continue;
            auto name_start = colon + 2; // skip ": "
            auto name_end = output.find_first_of(" \t\n(", name_start + 6);
            if (name_end == std::string::npos) name_end = output.size();
            sensor_entity = output.substr(name_start, name_end - name_start);
            /* Trim trailing whitespace */
            while (!sensor_entity.empty() && sensor_entity.back() <= ' ')
                sensor_entity.pop_back();
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

        /* Configure sensor pad format via media-ctl (same as Python's subprocess call) */
        char mcmd[512];
        snprintf(mcmd, sizeof(mcmd),
                 "media-ctl -d %s -V \"'%s':0 [fmt:UYVY8_1X16/%dx%d]\" 2>&1",
                 media_dev, sensor_entity.c_str(), req_w_, req_h_);
        FILE* mc = popen(mcmd, "r");
        if (mc) {
            char buf[256];
            while (fgets(buf, sizeof(buf), mc)) {} /* consume output */
            int rc = pclose(mc);
            if (rc == 0)
                LOG_INFO("Set media-ctl format UYVY8_1X16/%dx%d", req_w_, req_h_);
            else
                LOG_WARN("media-ctl format notice (rc=%d)", rc);
        }

        device_ = video_node;
        return true;
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

    /* 8. Start streaming */
    if (!start_streaming()) { close(); return false; }

    LOG_INFO("Camera opened: %s  %dx%d  (requested %dx%d @ %d fps)",
             device_.c_str(), actual_w_, actual_h_, req_w_, req_h_, fps_);
    return true;
}

/* ── configure_format ─────────────────────────────────────────────── */

bool V4l2Camera::configure_format() {
    struct v4l2_format fmt{};
    fmt.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    fmt.fmt.pix.width       = static_cast<uint32_t>(req_w_);
    fmt.fmt.pix.height      = static_cast<uint32_t>(req_h_);
    fmt.fmt.pix.pixelformat = V4L2_PIX_FMT_UYVY;
    fmt.fmt.pix.field       = V4L2_FIELD_NONE;

    if (xioctl(fd_, VIDIOC_S_FMT, &fmt) < 0) {
        LOG_ERROR("VIDIOC_S_FMT failed: %s", strerror(errno));
        return false;
    }

    actual_w_ = static_cast<int>(fmt.fmt.pix.width);
    actual_h_ = static_cast<int>(fmt.fmt.pix.height);

    if (fmt.fmt.pix.pixelformat != V4L2_PIX_FMT_UYVY)
        LOG_WARN("Driver chose different pixel format 0x%08X", fmt.fmt.pix.pixelformat);

    return true;
}

/* ── configure_framerate ──────────────────────────────────────────── */

bool V4l2Camera::configure_framerate() {
    struct v4l2_streamparm parm{};
    parm.type = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    parm.parm.capture.timeperframe.numerator   = 1;
    parm.parm.capture.timeperframe.denominator = static_cast<uint32_t>(fps_);

    if (xioctl(fd_, VIDIOC_S_PARM, &parm) < 0) {
        LOG_WARN("VIDIOC_S_PARM failed (fps may not be configurable): %s", strerror(errno));
        return false;
    }
    return true;
}

/* ── set_hardware_flip ────────────────────────────────────────────
 * Writes V4L2_CID_HFLIP and V4L2_CID_VFLIP to the sensor.
 * The kernel ov5640 driver translates these into I2C writes to
 * REG_TIMING_TC_REG20 (vflip) and REG_TIMING_TC_REG21 (hflip).
 * With rotation=180 in the DTS, the driver XORs with upside_down flag.
 * ──────────────────────────────────────────────────────────────────── */

void V4l2Camera::set_hardware_flip() {
    if (!rotate_180_) return;

    struct v4l2_control ctrl{};

    ctrl.id    = V4L2_CID_HFLIP;
    ctrl.value = 1;
    if (xioctl(fd_, VIDIOC_S_CTRL, &ctrl) < 0)
        LOG_WARN("Failed to set HFLIP: %s", strerror(errno));

    ctrl.id    = V4L2_CID_VFLIP;
    ctrl.value = 1;
    if (xioctl(fd_, VIDIOC_S_CTRL, &ctrl) < 0)
        LOG_WARN("Failed to set VFLIP: %s", strerror(errno));

    LOG_INFO("Hardware flip enabled (HFLIP=1, VFLIP=1)");
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

bool V4l2Camera::dequeue_frame(const uint8_t*& data, size_t& bytes, int& index) {
    struct v4l2_buffer buf{};
    buf.type   = V4L2_BUF_TYPE_VIDEO_CAPTURE;
    buf.memory = V4L2_MEMORY_MMAP;

    /* Use select() to wait for a frame with timeout (500ms) */
    fd_set fds;
    FD_ZERO(&fds);
    FD_SET(fd_, &fds);
    struct timeval tv = {0, 500000}; /* 500ms */
    int r = select(fd_ + 1, &fds, nullptr, nullptr, &tv);
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
    data  = static_cast<const uint8_t*>(buffers_[index].start);
    bytes = buf.bytesused;
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
