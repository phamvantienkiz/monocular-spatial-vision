/**
 * @file main.cpp
 * @brief Entrypoint for pi_capture_native — high-performance C++ replacement
 *        for the Python pi_capture_agent streaming pipeline.
 *
 * Replaces: pi_capture_agent/cli.py  run_stream() + run_snapshot()
 *
 * Architecture (matches Python's Producer-Consumer model):
 *   Thread 1 (capture): V4L2 DQBUF → memcpy → QBUF + IMU read → push to slot
 *   Thread 2 (main):    pop slot → JPEG encode → pack header → TCP send
 *
 * Usage:
 *   ./pi_capture_native --mode stream  --host 192.168.1.20 --port 9876
 *   ./pi_capture_native --mode snapshot --output test.jpg
 *   ./pi_capture_native --help
 */

#include "v4l2_camera.h"
#include "jpeg_encoder.h"
#include "socket_streamer.h"
#include "frame_packer.h"
#include "imu_reader.h"
#include "log.h"

#include <atomic>
#include <condition_variable>
#include <csignal>
#include <cstdlib>
#include <cstring>
#include <getopt.h>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

/* ── globals for signal handler ────────────────────────────────────── */
static std::atomic<bool> g_running{true};

static void signal_handler(int) { g_running.store(false); }

/* ── single-slot frame exchange (matches Python Queue(maxsize=1)) ── */

struct FrameSlot {
    std::vector<uint8_t> pixels;   /* copied from mmap buffer */
    uint64_t             ts_ns   = 0;
    float                pitch   = 0.0f;
    float                roll    = 0.0f;
    bool                 valid   = false;
};

static std::mutex              g_slot_mutex;
static std::condition_variable g_slot_cv;
static FrameSlot               g_slot;

/* ── capture worker thread ─────────────────────────────────────────
 * Mirrors Python's capture_worker() in cli.py:
 *   - Reads raw UYVY frame from V4L2
 *   - Reads IMU attitude
 *   - Publishes to single-slot (drops old frame if consumer is slow)
 * ──────────────────────────────────────────────────────────────────── */

static void capture_worker(V4l2Camera& cam, ImuReader* imu) {
    while (g_running.load()) {
        const uint8_t* data = nullptr;
        size_t bytes = 0;
        int buf_idx = -1;

        if (!cam.dequeue_frame(data, bytes, buf_idx))
            continue;

        /* Read IMU (best-effort, same as Python) */
        Attitude att;
        if (imu && imu->is_initialized())
            att = imu->read_attitude();

        uint64_t ts = timestamp_ns();

        {
            std::lock_guard<std::mutex> lk(g_slot_mutex);
            /* Ensure pixel buffer is pre-sized to avoid repeated allocation */
            if (g_slot.pixels.size() != bytes)
                g_slot.pixels.resize(bytes);
            memcpy(g_slot.pixels.data(), data, bytes);
            g_slot.ts_ns = ts;
            g_slot.pitch = att.pitch_deg;
            g_slot.roll  = att.roll_deg;
            g_slot.valid = true;
        }
        g_slot_cv.notify_one();

        /* Return mmap buffer to V4L2 immediately */
        cam.requeue_buffer(buf_idx);
    }
}

/* ── run_stream ────────────────────────────────────────────────────── */

static void run_stream(const std::string& device, int width, int height,
                       int fps, bool rotate_180, int jpeg_quality,
                       const std::string& host, int port,
                       int imu_bus, int imu_addr) {
    /* Camera */
    V4l2Camera cam(device, width, height, fps, rotate_180);
    if (!cam.open()) {
        LOG_ERROR("Failed to open camera. Aborting.");
        return;
    }

    /* IMU (best-effort, same as Python) */
    ImuReader imu(imu_bus, imu_addr);
    ImuReader* imu_ptr = nullptr;
    if (imu.initialize()) {
        imu_ptr = &imu;
    } else {
        LOG_WARN("IMU init failed. Continuing with pitch=0, roll=0.");
    }

    /* JPEG Encoder */
    JpegEncoder encoder(jpeg_quality);

    /* Network Streamer */
    SocketStreamer streamer(host, port);
    streamer.connect();

    /* Warm-up: discard first 5 frames (auto-exposure / white-balance settling) */
    LOG_INFO("Warming up camera sensor...");
    for (int i = 0; i < 5 && g_running.load(); ++i) {
        const uint8_t* d; size_t n; int idx;
        if (cam.dequeue_frame(d, n, idx))
            cam.requeue_buffer(idx);
    }

    /* Launch capture thread */
    std::thread cap_thread(capture_worker, std::ref(cam), imu_ptr);

    LOG_INFO("=== Streaming pipeline active ===");
    LOG_INFO("  Target: %s:%d", host.c_str(), port);
    LOG_INFO("  Video:  %dx%d @ %d fps (UYVY → JPEG Q%d)",
             cam.width(), cam.height(), fps, jpeg_quality);

    uint32_t frame_id    = 0;
    uint32_t frames_sent = 0;
    size_t   bytes_sent  = 0;
    double   t_stats     = time_now_sec();

    /* Main encode-and-send loop (mirrors Python's main thread in run_stream) */
    while (g_running.load()) {
        FrameSlot local;

        {
            std::unique_lock<std::mutex> lk(g_slot_mutex);
            g_slot_cv.wait_for(lk, std::chrono::milliseconds(100),
                               [] { return g_slot.valid || !g_running.load(); });
            if (!g_slot.valid) continue;

            /* Move data to local slot (avoids holding mutex during encode) */
            local.pixels.swap(g_slot.pixels);
            local.ts_ns = g_slot.ts_ns;
            local.pitch = g_slot.pitch;
            local.roll  = g_slot.roll;
            g_slot.valid = false;
        }

        /* JPEG encode */
        uint8_t* jpeg_buf = nullptr;
        unsigned long jpeg_size = 0;
        if (!encoder.encode(local.pixels.data(), cam.width(), cam.height(),
                            jpeg_buf, jpeg_size))
            continue;

        /* Pack binary frame (40-byte header + JPEG payload) */
        auto packet = pack_frame(frame_id, local.ts_ns,
                                 local.pitch, local.roll,
                                 jpeg_buf, static_cast<uint32_t>(jpeg_size),
                                 static_cast<uint32_t>(cam.width()),
                                 static_cast<uint32_t>(cam.height()));
        encoder.free_buffer(jpeg_buf);

        /* Send over TCP */
        bool ok = streamer.send_packet(packet.data(), packet.size());
        ++frame_id;
        if (ok) {
            ++frames_sent;
            bytes_sent += packet.size();
        }

        /* Periodic statistics (every ~1 second, same as Python) */
        double now = time_now_sec();
        double elapsed = now - t_stats;
        if (elapsed >= 1.0) {
            double fps_actual = frames_sent / elapsed;
            double kb_rate    = (bytes_sent / 1024.0) / elapsed;
            const char* status = streamer.is_connected() ? "CONNECTED" : "RECONNECTING";
            LOG_INFO("[%s] Frame #%u | Rate: %.1f FPS (%.1f KB/s) | Pitch: %+.2f° | Roll: %+.2f°",
                     status, frame_id, fps_actual, kb_rate, local.pitch, local.roll);
            frames_sent = 0;
            bytes_sent = 0;
            t_stats = now;
        }
    }

    /* Clean shutdown */
    LOG_INFO("Shutting down streaming pipeline...");
    g_running.store(false);
    g_slot_cv.notify_all();
    if (cap_thread.joinable()) cap_thread.join();
    streamer.close();
    cam.close();
    imu.close();
    LOG_INFO("Streaming session closed cleanly.");
}

/* ── run_snapshot ───────────────────────────────────────────────────── */

static void run_snapshot(const std::string& device, int width, int height,
                         int fps, bool rotate_180, int jpeg_quality,
                         const std::string& output_path) {
    V4l2Camera cam(device, width, height, fps, rotate_180);
    if (!cam.open()) {
        LOG_ERROR("Failed to open camera for snapshot.");
        return;
    }

    /* Warm-up */
    for (int i = 0; i < 5; ++i) {
        const uint8_t* d; size_t n; int idx;
        if (cam.dequeue_frame(d, n, idx))
            cam.requeue_buffer(idx);
    }

    /* Capture one frame */
    const uint8_t* data = nullptr;
    size_t bytes = 0;
    int idx = -1;
    if (!cam.dequeue_frame(data, bytes, idx)) {
        LOG_ERROR("Failed to capture snapshot frame.");
        cam.close();
        return;
    }

    /* Encode JPEG */
    JpegEncoder encoder(jpeg_quality);
    uint8_t* jpeg_buf = nullptr;
    unsigned long jpeg_size = 0;
    if (!encoder.encode(data, cam.width(), cam.height(), jpeg_buf, jpeg_size)) {
        LOG_ERROR("JPEG encoding failed.");
        cam.requeue_buffer(idx);
        cam.close();
        return;
    }
    cam.requeue_buffer(idx);

    /* Write to file */
    FILE* fp = fopen(output_path.c_str(), "wb");
    if (!fp) {
        LOG_ERROR("Cannot open %s for writing: %s", output_path.c_str(), strerror(errno));
        encoder.free_buffer(jpeg_buf);
        cam.close();
        return;
    }
    fwrite(jpeg_buf, 1, jpeg_size, fp);
    fclose(fp);

    LOG_INFO("Snapshot saved: %s (%lu bytes, %dx%d)",
             output_path.c_str(), jpeg_size, cam.width(), cam.height());

    encoder.free_buffer(jpeg_buf);
    cam.close();
}

/* ── main ──────────────────────────────────────────────────────────── */

static void print_usage(const char* prog) {
    fprintf(stderr,
        "Usage: %s [options]\n"
        "\n"
        "Modes:\n"
        "  --mode stream     Continuous capture → JPEG → TCP (default)\n"
        "  --mode snapshot   Single frame → JPEG file\n"
        "\n"
        "Camera options:\n"
        "  --device PATH     V4L2 device (default: /dev/video0)\n"
        "  --width  N        Capture width  (default: 1280)\n"
        "  --height N        Capture height (default: 720)\n"
        "  --fps    N        Frame rate     (default: 30)\n"
        "  --quality N       JPEG quality 1-100 (default: 65)\n"
        "  --rotate-180      Enable hardware HFLIP+VFLIP on OV5640\n"
        "\n"
        "Stream options:\n"
        "  --host ADDR       Ingest server IP   (default: 192.168.1.20)\n"
        "  --port N          Ingest server port  (default: 9876)\n"
        "\n"
        "Snapshot options:\n"
        "  --output PATH     Output JPEG file path (default: snapshot.jpg)\n"
        "\n"
        "IMU options:\n"
        "  --imu-bus N       I2C bus   (default: 1)\n"
        "  --imu-addr HEX    I2C addr  (default: 0x68)\n"
        , prog);
}

int main(int argc, char* argv[]) {
    /* Defaults (match Python configs/capture_pi.yaml) */
    std::string mode       = "stream";
    std::string device     = "/dev/video0";
    int         width      = 1280;
    int         height     = 720;
    int         fps        = 30;
    int         quality    = 65;
    bool        rotate_180 = false;
    std::string host       = "192.168.1.20";
    int         port       = 9876;
    std::string output     = "snapshot.jpg";
    int         imu_bus    = 1;
    int         imu_addr   = 0x68;

    static struct option long_opts[] = {
        {"mode",       required_argument, nullptr, 'm'},
        {"device",     required_argument, nullptr, 'd'},
        {"width",      required_argument, nullptr, 'W'},
        {"height",     required_argument, nullptr, 'H'},
        {"fps",        required_argument, nullptr, 'f'},
        {"quality",    required_argument, nullptr, 'q'},
        {"rotate-180", no_argument,       nullptr, 'r'},
        {"host",       required_argument, nullptr, 'h'},
        {"port",       required_argument, nullptr, 'p'},
        {"output",     required_argument, nullptr, 'o'},
        {"imu-bus",    required_argument, nullptr, 'b'},
        {"imu-addr",   required_argument, nullptr, 'a'},
        {"help",       no_argument,       nullptr, '?'},
        {nullptr, 0, nullptr, 0},
    };

    int c;
    while ((c = getopt_long(argc, argv, "m:d:W:H:f:q:rh:p:o:b:a:", long_opts, nullptr)) != -1) {
        switch (c) {
            case 'm': mode   = optarg; break;
            case 'd': device = optarg; break;
            case 'W': width  = atoi(optarg); break;
            case 'H': height = atoi(optarg); break;
            case 'f': fps    = atoi(optarg); break;
            case 'q': quality = atoi(optarg); break;
            case 'r': rotate_180 = true; break;
            case 'h': host   = optarg; break;
            case 'p': port   = atoi(optarg); break;
            case 'o': output = optarg; break;
            case 'b': imu_bus  = atoi(optarg); break;
            case 'a': imu_addr = static_cast<int>(strtol(optarg, nullptr, 0)); break;
            default:
                print_usage(argv[0]);
                return (c == '?') ? 0 : 1;
        }
    }

    /* Install signal handlers */
    signal(SIGINT,  signal_handler);
    signal(SIGTERM, signal_handler);

    LOG_INFO("pi_capture_native — mode: %s", mode.c_str());

    if (mode == "stream") {
        run_stream(device, width, height, fps, rotate_180, quality,
                   host, port, imu_bus, imu_addr);
    } else if (mode == "snapshot") {
        run_snapshot(device, width, height, fps, rotate_180, quality, output);
    } else {
        LOG_ERROR("Unknown mode: %s", mode.c_str());
        print_usage(argv[0]);
        return 1;
    }

    return 0;
}
