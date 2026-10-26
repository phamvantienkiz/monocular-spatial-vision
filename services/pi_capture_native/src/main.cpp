/**
 * @file main.cpp
 * @brief Entrypoint for pi_capture_native — high-performance C++ replacement
 *        for the Python pi_capture_agent streaming & diagnostic pipeline on Pi 3.
 *
 * Replaces: pi_capture_agent/cli.py (all 6 modes: preview, stream, snapshot, diag, test-imu, test-perf)
 *
 * Key Architecture & Optimizations:
 *  - 3-thread decoupled pipeline in --mode stream (Capture -> NEON+TurboJPEG Encode -> TCP Send)
 *  - Zero-allocation swap buffers (no per-frame malloc/tjFree overhead)
 *  - Low-latency HTTP MJPEG + Telemetry HUD server in --mode preview (detached HTTP worker
 *    threads with TCP_NODELAY & SO_SNDBUF=64KB cap, displaying live Exposure & Gain)
 *  - Built-in OV5640 exposure/gain readout & --lock-30fps control for 15fps vs 30fps diagnostics
 */

#include "v4l2_camera.h"
#include "jpeg_encoder.h"
#include "socket_streamer.h"
#include "frame_packer.h"
#include "imu_reader.h"
#include "log.h"

#include <arpa/inet.h>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <getopt.h>
#include <mutex>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <string>
#include <sys/select.h>
#include <sys/socket.h>
#include <thread>
#include <unistd.h>
#include <vector>

/* ── globals for signal handler ────────────────────────────────────── */
static std::atomic<bool> g_running{true};
static std::atomic<bool> g_swap_uv{false};
static std::atomic<bool> g_yuyv_order{false};

static void signal_handler(int) { g_running.store(false); }

/* ── Stage 1 -> Stage 2: Raw Frame Slot ────────────────────────────── */

struct RawFrameSlot {
    std::vector<uint8_t> pixels;   /* copied from mmap buffer */
    uint64_t             ts_ns   = 0;
    float                pitch   = 0.0f;
    float                roll    = 0.0f;
    bool                 valid   = false;
};

static std::mutex              g_raw_mutex;
static std::condition_variable g_raw_cv;
static RawFrameSlot            g_raw_slot;

/* ── Stage 2 -> Stage 3: Encoded Packet Slot ───────────────────────── */

struct PacketSlot {
    std::vector<uint8_t> packet;
    uint32_t             frame_id = 0;
    float                pitch    = 0.0f;
    float                roll     = 0.0f;
    bool                 valid    = false;
};

static std::mutex              g_packet_mutex;
static std::condition_variable g_packet_cv;
static PacketSlot              g_packet_slot;

/* ── Thread 1: capture worker ───────────────────────────────────────
 * Reads raw UYVY frame from V4L2 + IMU attitude, publishes to raw slot,
 * and immediately returns the V4L2 MMAP buffer to the kernel.
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
            std::lock_guard<std::mutex> lk(g_raw_mutex);
            /* Pre-size buffer to avoid repeated heap allocation */
            if (g_raw_slot.pixels.size() != bytes)
                g_raw_slot.pixels.resize(bytes);
            memcpy(g_raw_slot.pixels.data(), data, bytes);
            g_raw_slot.ts_ns = ts;
            g_raw_slot.pitch = att.pitch_deg;
            g_raw_slot.roll  = att.roll_deg;
            g_raw_slot.valid = true;
        }
        g_raw_cv.notify_one();

        /* Return mmap buffer to V4L2 immediately */
        cam.requeue_buffer(buf_idx);
    }
}

/* ── Thread 2: encode worker ────────────────────────────────────────
 * Pops raw UYVY frame, converts with ARM NEON, compresses with TurboJPEG,
 * and packs binary packet into packet slot.
 * ──────────────────────────────────────────────────────────────────── */

static void encode_worker(int width, int height, int jpeg_quality) {
    JpegEncoder encoder(jpeg_quality, g_swap_uv.load(), g_yuyv_order.load());
    std::vector<uint8_t> local_pixels;
    std::vector<uint8_t> local_packet;
    uint32_t frame_id = 0;

    while (g_running.load()) {
        encoder.set_swap_uv(g_swap_uv.load());
        encoder.set_yuyv_order(g_yuyv_order.load());
        uint64_t ts = 0;
        float pitch = 0.0f;
        float roll  = 0.0f;

        {
            std::unique_lock<std::mutex> lk(g_raw_mutex);
            g_raw_cv.wait_for(lk, std::chrono::milliseconds(100),
                              [] { return g_raw_slot.valid || !g_running.load(); });
            if (!g_running.load()) break;
            if (!g_raw_slot.valid) continue;

            /* Zero-allocation pointer swap with pre-allocated buffer */
            local_pixels.swap(g_raw_slot.pixels);
            ts    = g_raw_slot.ts_ns;
            pitch = g_raw_slot.pitch;
            roll  = g_raw_slot.roll;
            g_raw_slot.valid = false;
        }

        /* TurboJPEG compression (ARM NEON accelerated) */
        uint8_t* jpeg_buf = nullptr;
        unsigned long jpeg_size = 0;
        if (!encoder.encode(local_pixels.data(), width, height, jpeg_buf, jpeg_size))
            continue;

        /* Pack into reusable vector without extra heap allocations */
        pack_frame_to(local_packet, frame_id, ts, pitch, roll,
                      jpeg_buf, static_cast<uint32_t>(jpeg_size),
                      static_cast<uint32_t>(width), static_cast<uint32_t>(height));
        encoder.free_buffer(jpeg_buf);

        {
            std::lock_guard<std::mutex> lk(g_packet_mutex);
            g_packet_slot.packet.swap(local_packet);
            g_packet_slot.frame_id = frame_id++;
            g_packet_slot.pitch    = pitch;
            g_packet_slot.roll     = roll;
            g_packet_slot.valid    = true;
        }
        g_packet_cv.notify_one();
    }
}

/* ── MODE 1: run_stream (3-thread decoupled TCP streamer) ──────────── */

static void run_stream(const std::string& device, int width, int height,
                       int fps, bool rotate_180, bool vflip_only, int buf_count,
                       int jpeg_quality, const std::string& host, int port,
                       int imu_bus, int imu_addr,
                       bool lock_30fps, int exposure, int gain,
                       int red_bal, int blue_bal) {
    /* Camera */
    V4l2Camera cam(device, width, height, fps, rotate_180, buf_count, vflip_only);
    if (!cam.open()) {
        LOG_ERROR("Failed to open camera. Aborting.");
        return;
    }
    cam.set_exposure_mode(lock_30fps, exposure, gain);
    if (red_bal > 0 || blue_bal > 0) {
        cam.set_white_balance_gains(red_bal, blue_bal);
    }

    /* IMU (best-effort, same as Python) */
    ImuReader imu(imu_bus, imu_addr);
    ImuReader* imu_ptr = nullptr;
    if (imu.initialize()) {
        imu_ptr = &imu;
    } else {
        LOG_WARN("IMU init failed. Continuing with pitch=0, roll=0.");
    }

    /* Network Streamer */
    SocketStreamer streamer(host, port);
    streamer.connect();

    /* Warm-up: discard first 5 frames */
    LOG_INFO("Warming up camera sensor...");
    for (int i = 0; i < 5 && g_running.load(); ++i) {
        const uint8_t* d; size_t n; int idx;
        if (cam.dequeue_frame(d, n, idx))
            cam.requeue_buffer(idx);
    }

    /* Launch Thread 1 (Capture) and Thread 2 (Encode) */
    std::thread cap_thread(capture_worker, std::ref(cam), imu_ptr);
    std::thread enc_thread(encode_worker, cam.width(), cam.height(), jpeg_quality);

    LOG_INFO("=== Streaming pipeline active (3-thread decoupled) ===");
    LOG_INFO("  Target: %s:%d", host.c_str(), port);
    LOG_INFO("  Video:  %dx%d @ %d fps (UYVY → NEON → TurboJPEG Q%d)",
             cam.width(), cam.height(), fps, jpeg_quality);

    std::vector<uint8_t> send_buf; /* Persistent buffer OUTSIDE while loop */
    uint32_t frames_sent  = 0;
    size_t   bytes_sent   = 0;
    double   t_stats      = time_now_sec();
    uint32_t cur_frame_id = 0;
    float    cur_pitch    = 0.0f;
    float    cur_roll     = 0.0f;

    /* Main thread = Thread 3 (Network streamer) */
    while (g_running.load()) {
        {
            std::unique_lock<std::mutex> lk(g_packet_mutex);
            g_packet_cv.wait_for(lk, std::chrono::milliseconds(100),
                                 [] { return g_packet_slot.valid || !g_running.load(); });
            if (!g_running.load()) break;
            if (!g_packet_slot.valid) continue;

            /* Zero-allocation swap */
            send_buf.swap(g_packet_slot.packet);
            cur_frame_id = g_packet_slot.frame_id;
            cur_pitch    = g_packet_slot.pitch;
            cur_roll     = g_packet_slot.roll;
            g_packet_slot.valid = false;
        }

        /* Send over TCP */
        bool ok = streamer.send_packet(send_buf.data(), send_buf.size());
        if (ok) {
            ++frames_sent;
            bytes_sent += send_buf.size();
        }

        /* Periodic statistics (every ~1 second) */
        double now = time_now_sec();
        double elapsed = now - t_stats;
        if (elapsed >= 1.0) {
            double fps_actual = frames_sent / elapsed;
            double kb_rate    = (bytes_sent / 1024.0) / elapsed;
            SensorExposureInfo exp_info = cam.query_exposure_gain();
            const char* status = streamer.is_connected() ? "CONNECTED" : "RECONNECTING";
            LOG_INFO("[%s] Frame #%u | Rate: %.1f FPS (%.1f KB/s) | Pitch: %+.2f° | Roll: %+.2f° | Exp: %d | Gain: %d",
                     status, cur_frame_id, fps_actual, kb_rate, cur_pitch, cur_roll,
                     exp_info.exposure, exp_info.gain);
            frames_sent = 0;
            bytes_sent  = 0;
            t_stats     = now;
        }
    }

    /* Clean shutdown */
    LOG_INFO("Shutting down streaming pipeline...");
    g_running.store(false);
    g_raw_cv.notify_all();
    g_packet_cv.notify_all();
    if (cap_thread.joinable()) cap_thread.join();
    if (enc_thread.joinable()) enc_thread.join();
    streamer.close();
    cam.close();
    imu.close();
    LOG_INFO("Streaming session closed cleanly.");
}

/* ── MODE 2: run_snapshot ──────────────────────────────────────────── */

static void run_snapshot(const std::string& device, int width, int height,
                         int fps, bool rotate_180, bool vflip_only, int buf_count,
                         int jpeg_quality, const std::string& output_path,
                         bool lock_30fps, int exposure, int gain,
                         int red_bal, int blue_bal) {
    V4l2Camera cam(device, width, height, fps, rotate_180, buf_count, vflip_only);
    if (!cam.open()) {
        LOG_ERROR("Failed to open camera for snapshot.");
        return;
    }
    cam.set_exposure_mode(lock_30fps, exposure, gain);
    if (red_bal > 0 || blue_bal > 0) {
        cam.set_white_balance_gains(red_bal, blue_bal);
    }

    /* Warm-up (allow AEC/AWB to settle) */
    for (int i = 0; i < 10 && g_running.load(); ++i) {
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
    JpegEncoder encoder(jpeg_quality, g_swap_uv.load(), g_yuyv_order.load());
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

    SensorExposureInfo exp_info = cam.query_exposure_gain();
    LOG_INFO("Snapshot saved: %s (%lu bytes, %dx%d, exposure=%d, gain=%d)",
             output_path.c_str(), jpeg_size, cam.width(), cam.height(),
             exp_info.exposure, exp_info.gain);

    encoder.free_buffer(jpeg_buf);
    cam.close();
}

/* ── MODE 3: run_preview (Embedded HTTP MJPEG + HUD Server) ────────── */

struct PreviewFrame {
    std::vector<uint8_t> jpeg;
    float    pitch    = 0.0f;
    float    roll     = 0.0f;
    double   fps      = 0.0;
    int      exposure = -1;
    int      gain     = -1;
    int      width    = 0;
    int      height   = 0;
    uint64_t seq      = 0;
};

static std::mutex              g_prev_mutex;
static std::condition_variable g_prev_cv;
static PreviewFrame            g_prev_frame;
static std::atomic<int>        g_active_http_clients{0};
static V4l2Camera*             g_preview_cam = nullptr;
static std::atomic<int>        g_cur_exposure{600};
static std::atomic<int>        g_cur_gain{32};
static std::atomic<int>        g_cur_red_bal{1400};
static std::atomic<int>        g_cur_blue_bal{1200};
static std::atomic<bool>       g_manual_wb{false};

static bool http_send_all(int fd, const void* buf, size_t len) {
    const uint8_t* p = static_cast<const uint8_t*>(buf);
    size_t sent = 0;
    while (sent < len) {
        ssize_t n = send(fd, p + sent, len - sent, MSG_NOSIGNAL);
        if (n <= 0) {
            if (n < 0 && errno == EINTR) continue;
            return false;
        }
        sent += static_cast<size_t>(n);
    }
    return true;
}

static void handle_http_client(int client_fd) {
    g_active_http_clients.fetch_add(1);

    /* Configure low-latency socket options to prevent Wi-Fi bufferbloat */
    int one = 1;
    setsockopt(client_fd, IPPROTO_TCP, TCP_NODELAY, &one, sizeof(one));
    int sndbuf = 65536; /* 64KB cap prevents multi-second MJPEG frame queuing */
    setsockopt(client_fd, SOL_SOCKET, SO_SNDBUF, &sndbuf, sizeof(sndbuf));
    struct timeval tv{2, 0};
    setsockopt(client_fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
    setsockopt(client_fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

    char req[2048] = {0};
    ssize_t n = recv(client_fd, req, sizeof(req) - 1, 0);
    if (n <= 0) {
        ::close(client_fd);
        g_active_http_clients.fetch_sub(1);
        return;
    }

    if (strstr(req, "GET /stream.mjpg")) {
        const char* header =
            "HTTP/1.1 200 OK\r\n"
            "Connection: close\r\n"
            "Server: pi_capture_native\r\n"
            "Cache-Control: no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0\r\n"
            "Pragma: no-cache\r\n"
            "Content-Type: multipart/x-mixed-replace; boundary=--frameboundary\r\n\r\n";
        if (!http_send_all(client_fd, header, strlen(header))) {
            ::close(client_fd);
            g_active_http_clients.fetch_sub(1);
            return;
        }

        uint64_t last_sent_seq = 0;
        std::vector<uint8_t> cur_jpeg;
        while (g_running.load()) {
            {
                std::unique_lock<std::mutex> lk(g_prev_mutex);
                g_prev_cv.wait_for(lk, std::chrono::milliseconds(100),
                    [&] { return g_prev_frame.seq > last_sent_seq || !g_running.load(); });
                if (!g_running.load()) break;
                if (g_prev_frame.seq == last_sent_seq || g_prev_frame.jpeg.empty())
                    continue;
                cur_jpeg      = g_prev_frame.jpeg;
                last_sent_seq = g_prev_frame.seq;
            }

            char part_hdr[128];
            int hdr_len = snprintf(part_hdr, sizeof(part_hdr),
                                   "--frameboundary\r\nContent-Type: image/jpeg\r\nContent-Length: %zu\r\n\r\n",
                                   cur_jpeg.size());
            if (!http_send_all(client_fd, part_hdr, static_cast<size_t>(hdr_len))) break;
            if (!http_send_all(client_fd, cur_jpeg.data(), cur_jpeg.size())) break;
            if (!http_send_all(client_fd, "\r\n", 2)) break;
        }
    } else if (strstr(req, "GET /telemetry")) {
        float p = 0.0f, r = 0.0f;
        double f = 0.0;
        int exp_v = -1, gain_v = -1, w = 0, h = 0;
        uint64_t seq = 0;
        {
            std::lock_guard<std::mutex> lk(g_prev_mutex);
            p      = g_prev_frame.pitch;
            r      = g_prev_frame.roll;
            f      = g_prev_frame.fps;
            exp_v  = g_prev_frame.exposure;
            gain_v = g_prev_frame.gain;
            w      = g_prev_frame.width;
            h      = g_prev_frame.height;
            seq    = g_prev_frame.seq;
        }
        char json[512];
        snprintf(json, sizeof(json),
                 "{\"frame_id\":%llu,\"pitch_deg\":%.2f,\"roll_deg\":%.2f,\"fps\":%.1f,"
                 "\"exposure\":%d,\"gain\":%d,\"width\":%d,\"height\":%d,"
                 "\"swap_uv\":%s,\"yuyv\":%s,\"red_bal\":%d,\"blue_bal\":%d,\"manual_wb\":%s}",
                 static_cast<unsigned long long>(seq), p, r, f, exp_v, gain_v, w, h,
                 g_swap_uv.load() ? "true" : "false",
                 g_yuyv_order.load() ? "true" : "false",
                 g_cur_red_bal.load(), g_cur_blue_bal.load(),
                 g_manual_wb.load() ? "true" : "false");
        char resp[768];
        snprintf(resp, sizeof(resp),
                 "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nCache-Control: no-store\r\n"
                 "Content-Length: %zu\r\nConnection: close\r\n\r\n%s",
                 strlen(json), json);
        http_send_all(client_fd, resp, strlen(resp));
    } else if (strstr(req, "GET /toggle-uv")) {
        bool next = !g_swap_uv.load();
        g_swap_uv.store(next);
        LOG_INFO("[PREVIEW] Toggled chroma --swap-uv = %s", next ? "ON" : "OFF");
        const char* ok_resp = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 11\r\nConnection: close\r\n\r\n{\"ok\":true}";
        http_send_all(client_fd, ok_resp, strlen(ok_resp));
    } else if (strstr(req, "GET /toggle-yuyv")) {
        bool next = !g_yuyv_order.load();
        g_yuyv_order.store(next);
        LOG_INFO("[PREVIEW] Toggled byte order --yuyv = %s", next ? "YUYV" : "UYVY");
        const char* ok_resp = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 11\r\nConnection: close\r\n\r\n{\"ok\":true}";
        http_send_all(client_fd, ok_resp, strlen(ok_resp));
    } else if (strstr(req, "GET /adj-exp?d=")) {
        const char* p = strstr(req, "GET /adj-exp?d=");
        int delta = p ? atoi(p + 15) : 0;
        int next_exp = g_cur_exposure.load() + delta;
        if (next_exp < 50)  next_exp = 50;
        if (next_exp > 984) next_exp = 984;
        g_cur_exposure.store(next_exp);
        if (g_preview_cam) {
            g_preview_cam->set_exposure_mode(true, next_exp, g_cur_gain.load());
        }
        const char* ok_resp = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 11\r\nConnection: close\r\n\r\n{\"ok\":true}";
        http_send_all(client_fd, ok_resp, strlen(ok_resp));
    } else if (strstr(req, "GET /adj-gain?d=")) {
        const char* p = strstr(req, "GET /adj-gain?d=");
        int delta = p ? atoi(p + 16) : 0;
        int next_gain = g_cur_gain.load() + delta;
        if (next_gain < 16)  next_gain = 16;
        if (next_gain > 248) next_gain = 248;
        g_cur_gain.store(next_gain);
        if (g_preview_cam) {
            g_preview_cam->set_exposure_mode(true, g_cur_exposure.load(), next_gain);
        }
        const char* ok_resp = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 11\r\nConnection: close\r\n\r\n{\"ok\":true}";
        http_send_all(client_fd, ok_resp, strlen(ok_resp));
    } else if (strstr(req, "GET /adj-wb?")) {
        const char* pr = strstr(req, "dr=");
        const char* pb = strstr(req, "db=");
        int dr = pr ? atoi(pr + 3) : 0;
        int db = pb ? atoi(pb + 3) : 0;
        if (strstr(req, "auto=1")) {
            g_manual_wb.store(false);
            if (g_preview_cam) {
                g_preview_cam->set_exposure_mode(true, g_cur_exposure.load(), g_cur_gain.load());
            }
        } else {
            int nr = g_cur_red_bal.load() + dr;
            int nb = g_cur_blue_bal.load() + db;
            if (nr < 256)  nr = 256;
            if (nr > 4095) nr = 4095;
            if (nb < 256)  nb = 256;
            if (nb > 4095) nb = 4095;
            g_cur_red_bal.store(nr);
            g_cur_blue_bal.store(nb);
            g_manual_wb.store(true);
            if (g_preview_cam) {
                g_preview_cam->set_white_balance_gains(nr, nb);
            }
        }
        const char* ok_resp = "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 11\r\nConnection: close\r\n\r\n{\"ok\":true}";
        http_send_all(client_fd, ok_resp, strlen(ok_resp));
    } else if (strstr(req, "GET /snapshot.jpg")) {
        std::vector<uint8_t> cur_jpeg;
        {
            std::lock_guard<std::mutex> lk(g_prev_mutex);
            cur_jpeg = g_prev_frame.jpeg;
        }
        if (!cur_jpeg.empty()) {
            char resp[256];
            snprintf(resp, sizeof(resp),
                     "HTTP/1.1 200 OK\r\nContent-Type: image/jpeg\r\nCache-Control: no-store\r\n"
                     "Content-Length: %zu\r\nConnection: close\r\n\r\n",
                     cur_jpeg.size());
            http_send_all(client_fd, resp, strlen(resp));
            http_send_all(client_fd, cur_jpeg.data(), cur_jpeg.size());
        } else {
            const char* not_ready = "HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
            http_send_all(client_fd, not_ready, strlen(not_ready));
        }
    } else {
        const char* html =
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<head>\n"
            "  <meta charset=\"utf-8\">\n"
            "  <title>Pi 3 Native Live Preview</title>\n"
            "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            "  <style>\n"
            "    body { margin: 0; background: #0f172a; color: #f8fafc; font-family: monospace, sans-serif; display: flex; flex-direction: column; align-items: center; padding: 20px; }\n"
            "    h1 { margin-bottom: 8px; font-size: 20px; color: #38bdf8; }\n"
            "    .card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px; margin: 8px 0; width: 90%; max-width: 900px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); }\n"
            "    img { width: 100%; border-radius: 6px; background: #020617; }\n"
            "    .hud-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-top: 10px; }\n"
            "    .hud-stat { background: #0f172a; padding: 10px; border-radius: 6px; border-left: 4px solid #38bdf8; }\n"
            "    .hud-label { font-size: 11px; color: #94a3b8; text-transform: uppercase; }\n"
            "    .hud-val { font-size: 18px; font-weight: bold; margin-top: 4px; color: #38bdf8; }\n"
            "    .btn-row { display: flex; gap: 10px; margin-top: 12px; flex-wrap: wrap; }\n"
            "    button { background: #0284c7; color: #fff; border: none; border-radius: 6px; padding: 8px 14px; font-family: monospace; font-weight: bold; cursor: pointer; }\n"
            "    button:hover { background: #0369a1; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            "  <h1>⚡ Pi 3 Native C++ Stream (libturbojpeg + ARM NEON)</h1>\n"
            "  <div class=\"card\">\n"
            "    <img src=\"/stream.mjpg\" alt=\"Live Camera Stream\">\n"
            "  </div>\n"
            "  <div class=\"card\">\n"
            "    <strong>Sensor & IMU Telemetry</strong>\n"
            "    <div class=\"hud-grid\">\n"
            "      <div class=\"hud-stat\"><div class=\"hud-label\">Camera FPS</div><div class=\"hud-val\" id=\"val-fps\">-- FPS</div></div>\n"
            "      <div class=\"hud-stat\"><div class=\"hud-label\">Resolution</div><div class=\"hud-val\" id=\"val-res\">--</div></div>\n"
            "      <div class=\"hud-stat\"><div class=\"hud-label\">Exposure / Gain</div><div class=\"hud-val\" id=\"val-exp\">-- / --</div></div>\n"
            "      <div class=\"hud-stat\"><div class=\"hud-label\">White Balance (R/B)</div><div class=\"hud-val\" id=\"val-wb\">AUTO</div></div>\n"
            "      <div class=\"hud-stat\"><div class=\"hud-label\">Chroma Mode</div><div class=\"hud-val\" id=\"val-uv\">UYVY (Normal)</div></div>\n"
            "      <div class=\"hud-stat\"><div class=\"hud-label\">Pitch / Roll</div><div class=\"hud-val\" id=\"val-pitch\">-- / --</div></div>\n"
            "    </div>\n"
            "    <div class=\"btn-row\">\n"
            "      <button onclick=\"fetch('/adj-exp?d=-50')\">🔉 Exp -50</button>\n"
            "      <button onclick=\"fetch('/adj-exp?d=50')\">🔆 Exp +50</button>\n"
            "      <button onclick=\"fetch('/adj-gain?d=-8')\">🔉 Gain -8</button>\n"
            "      <button onclick=\"fetch('/adj-gain?d=8')\">🔆 Gain +8</button>\n"
            "      <button onclick=\"fetch('/adj-wb?dr=-100&db=0')\">🔴 Red -100</button>\n"
            "      <button onclick=\"fetch('/adj-wb?dr=100&db=0')\">🔴 Red +100</button>\n"
            "      <button onclick=\"fetch('/adj-wb?dr=0&db=-100')\">🔵 Blue -100</button>\n"
            "      <button onclick=\"fetch('/adj-wb?dr=0&db=100')\">🔵 Blue +100</button>\n"
            "      <button onclick=\"fetch('/adj-wb?auto=1')\">✨ AWB Auto</button>\n"
            "      <button onclick=\"fetch('/toggle-uv')\">🔄 Swap U/V</button>\n"
            "      <button onclick=\"fetch('/toggle-yuyv')\">🔀 UYVY/YUYV</button>\n"
            "    </div>\n"
            "  </div>\n"
            "  <script>\n"
            "    let inFlight = false;\n"
            "    setInterval(async () => {\n"
            "      if (inFlight) return;\n"
            "      inFlight = true;\n"
            "      try {\n"
            "        const res = await fetch('/telemetry');\n"
            "        const data = await res.json();\n"
            "        document.getElementById('val-pitch').innerText = `${data.pitch_deg.toFixed(1)}° / ${data.roll_deg.toFixed(1)}°`;\n"
            "        document.getElementById('val-fps').innerText = `${data.fps.toFixed(1)} FPS`;\n"
            "        document.getElementById('val-res').innerText = `${data.width}x${data.height}`;\n"
            "        document.getElementById('val-exp').innerText = `${data.exposure} / ${data.gain}`;\n"
            "        document.getElementById('val-wb').innerText = data.manual_wb ? `R:${data.red_bal} B:${data.blue_bal}` : 'AUTO';\n"
            "        document.getElementById('val-uv').innerText = `${data.yuyv ? 'YUYV' : 'UYVY'} ${data.swap_uv ? '(Swap)' : ''}`;\n"
            "      } catch (e) {} finally { inFlight = false; }\n"
            "    }, 250);\n"
            "  </script>\n"
            "</body>\n"
            "</html>\n";

        char resp[8192];
        snprintf(resp, sizeof(resp),
                 "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: %zu\r\nConnection: close\r\n\r\n%s",
                 strlen(html), html);
        http_send_all(client_fd, resp, strlen(resp));
    }

    ::close(client_fd);
    g_active_http_clients.fetch_sub(1);
}

static void run_preview(const std::string& device, int width, int height,
                        int fps, bool rotate_180, bool vflip_only, int buf_count,
                        int jpeg_quality, int preview_port, int imu_bus, int imu_addr,
                        bool lock_30fps, int exposure, int gain,
                        int red_bal, int blue_bal) {
    V4l2Camera cam(device, width, height, fps, rotate_180, buf_count, vflip_only);
    if (!cam.open()) {
        LOG_ERROR("Failed to open camera for preview.");
        return;
    }
    g_preview_cam = &cam;
    if (exposure > 0) g_cur_exposure.store(exposure);
    if (gain > 0)     g_cur_gain.store(gain);
    cam.set_exposure_mode(lock_30fps, exposure, gain);
    if (red_bal > 0 || blue_bal > 0) {
        if (red_bal > 0)  g_cur_red_bal.store(red_bal);
        if (blue_bal > 0) g_cur_blue_bal.store(blue_bal);
        g_manual_wb.store(true);
        cam.set_white_balance_gains(g_cur_red_bal.load(), g_cur_blue_bal.load());
    }

    ImuReader imu(imu_bus, imu_addr);
    ImuReader* imu_ptr = nullptr;
    if (imu.initialize()) {
        imu_ptr = &imu;
    } else {
        LOG_WARN("IMU init failed. Continuing without IMU.");
    }

    /* Warm-up */
    for (int i = 0; i < 5 && g_running.load(); ++i) {
        const uint8_t* d; size_t n; int idx;
        if (cam.dequeue_frame(d, n, idx))
            cam.requeue_buffer(idx);
    }

    /* Launch Thread 1: Camera + IMU Capture Worker */
    std::thread cap_thread(capture_worker, std::ref(cam), imu_ptr);

    /* Launch Thread 2: NEON + TurboJPEG Encode Worker for Preview */
    std::thread enc_thread([&]() {
        JpegEncoder encoder(jpeg_quality, g_swap_uv.load(), g_yuyv_order.load());
        std::vector<uint8_t> local_pixels;
        uint64_t seq = 0;
        uint32_t frame_count = 0;
        double t_start = time_now_sec();
        double cur_fps = 0.0;
        SensorExposureInfo exp_info = cam.query_exposure_gain();

        while (g_running.load()) {
            encoder.set_swap_uv(g_swap_uv.load());
            encoder.set_yuyv_order(g_yuyv_order.load());
            float pitch = 0.0f;
            float roll  = 0.0f;

            {
                std::unique_lock<std::mutex> lk(g_raw_mutex);
                g_raw_cv.wait_for(lk, std::chrono::milliseconds(100),
                                  [] { return g_raw_slot.valid || !g_running.load(); });
                if (!g_running.load()) break;
                if (!g_raw_slot.valid) continue;

                local_pixels.swap(g_raw_slot.pixels);
                pitch = g_raw_slot.pitch;
                roll  = g_raw_slot.roll;
                g_raw_slot.valid = false;
            }

            uint8_t* jpeg_buf = nullptr;
            unsigned long jpeg_size = 0;
            if (encoder.encode(local_pixels.data(), cam.width(), cam.height(), jpeg_buf, jpeg_size)) {
                frame_count++;
                double now = time_now_sec();
                double elapsed = now - t_start;
                if (elapsed >= 1.0) {
                    cur_fps  = frame_count / elapsed;
                    exp_info = cam.query_exposure_gain();
                    LOG_INFO("[PREVIEW] Rate: %.1f FPS | Res: %dx%d | Exp: %d | Gain: %d | Pitch: %+.2f° | Roll: %+.2f°",
                             cur_fps, cam.width(), cam.height(),
                             exp_info.exposure, exp_info.gain, pitch, roll);
                    t_start     = now;
                    frame_count = 0;
                } else if (cur_fps == 0.0 && elapsed > 0.0) {
                    cur_fps = frame_count / elapsed;
                }

                {
                    std::lock_guard<std::mutex> lk(g_prev_mutex);
                    g_prev_frame.jpeg.assign(jpeg_buf, jpeg_buf + jpeg_size);
                    g_prev_frame.pitch    = pitch;
                    g_prev_frame.roll     = roll;
                    g_prev_frame.fps      = cur_fps;
                    g_prev_frame.exposure = exp_info.exposure;
                    g_prev_frame.gain     = exp_info.gain;
                    g_prev_frame.width    = cam.width();
                    g_prev_frame.height   = cam.height();
                    g_prev_frame.seq      = ++seq;
                }
                g_prev_cv.notify_all();
                encoder.free_buffer(jpeg_buf);
            }
        }
    });

    /* Open HTTP server socket */
    int srv = socket(AF_INET, SOCK_STREAM, 0);
    int opt = 1;
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    sockaddr_in sin{};
    sin.sin_family      = AF_INET;
    sin.sin_addr.s_addr = INADDR_ANY;
    sin.sin_port        = htons(static_cast<uint16_t>(preview_port));

    if (bind(srv, (sockaddr*)&sin, sizeof(sin)) < 0) {
        LOG_ERROR("Cannot bind HTTP server to port %d: %s", preview_port, strerror(errno));
        g_running.store(false);
        g_raw_cv.notify_all();
        if (cap_thread.joinable()) cap_thread.join();
        if (enc_thread.joinable()) enc_thread.join();
        cam.close();
        imu.close();
        return;
    }

    listen(srv, 8);

    LOG_INFO("================ PREVIEW SERVER STARTED ================");
    LOG_INFO("HTTP Preview running on port %d (%dx%d @ %d FPS target)",
             preview_port, cam.width(), cam.height(), fps);
    LOG_INFO("Open from your Laptop browser (Chrome, Edge, Firefox):");
    LOG_INFO("  👉  http://<IP_PI>:%d/              (Interactive Web HUD)", preview_port);
    LOG_INFO("  👉  http://<IP_PI>:%d/preview       (Interactive Web HUD)", preview_port);
    LOG_INFO("  👉  http://<IP_PI>:%d/stream.mjpg   (Raw MJPEG Stream)", preview_port);
    LOG_INFO("  👉  http://<IP_PI>:%d/telemetry     (Live JSON Telemetry)", preview_port);
    LOG_INFO("Press Ctrl+C to terminate preview server.");
    LOG_INFO("========================================================");

    while (g_running.load()) {
        fd_set fds;
        FD_ZERO(&fds);
        FD_SET(srv, &fds);
        timeval tv{1, 0};
        int r = select(srv + 1, &fds, nullptr, nullptr, &tv);
        if (r > 0) {
            sockaddr_in client_addr{};
            socklen_t client_len = sizeof(client_addr);
            int cfd = accept(srv, (sockaddr*)&client_addr, &client_len);
            if (cfd >= 0) {
                /* Detach client thread to avoid unbounded vector accumulation */
                std::thread(handle_http_client, cfd).detach();
            }
        }
    }

    ::close(srv);
    g_raw_cv.notify_all();
    g_prev_cv.notify_all();
    if (cap_thread.joinable()) cap_thread.join();
    if (enc_thread.joinable()) enc_thread.join();

    /* Brief wait for any active HTTP client threads to exit cleanly */
    for (int i = 0; i < 20 && g_active_http_clients.load() > 0; ++i) {
        usleep(50000);
    }

    g_preview_cam = nullptr;
    cam.close();
    imu.close();
    LOG_INFO("Preview server shut down.");
}

/* ── MODE 4: run_diag (Hardware & Exposure/Gain Diagnostic) ────────── */

static int run_diag(const std::string& device, int width, int height,
                    int fps, bool rotate_180, bool vflip_only, int buf_count,
                    int imu_bus, int imu_addr,
                    bool lock_30fps, int exposure, int gain) {
    LOG_INFO("====================================================================");
    LOG_INFO("PI CAPTURE NATIVE — HARDWARE & SENSOR EXPOSURE DIAGNOSTIC");
    LOG_INFO("====================================================================");

    /* 1. Check IMU */
    ImuReader imu(imu_bus, imu_addr);
    if (imu.initialize()) {
        Attitude att = imu.read_attitude();
        LOG_INFO("[PASS] IMU MPU6050 (/dev/i2c-%d @ 0x%02X, WHO_AM_I=0x%02X): "
                 "Pitch=%+.2f° Roll=%+.2f° (Ax=%+.3fg Ay=%+.3fg Az=%+.3fg)",
                 imu_bus, imu_addr, imu.who_am_i(),
                 att.pitch_deg, att.roll_deg, att.ax, att.ay, att.az);
    } else {
        LOG_WARN("[WARN] IMU MPU6050 not detected on /dev/i2c-%d (0x%02X)", imu_bus, imu_addr);
    }

    /* 2. Check Camera + Unicam Subdev + Exposure/Gain */
    V4l2Camera cam(device, width, height, fps, rotate_180, buf_count, vflip_only);
    if (!cam.open()) {
        LOG_ERROR("[FAIL] Could not open V4L2 camera %s", device.c_str());
        imu.close();
        return 1;
    }
    cam.set_exposure_mode(lock_30fps, exposure, gain);

    LOG_INFO("Waiting ~1.5s (30 warmup frames) for OV5640 AEC/AWB to stabilize...");
    double t0 = time_now_sec();
    int captured = 0;
    for (int i = 0; i < 30 && g_running.load(); ++i) {
        const uint8_t* d = nullptr;
        size_t n = 0;
        int idx = -1;
        if (cam.dequeue_frame(d, n, idx)) {
            cam.requeue_buffer(idx);
            captured++;
        }
    }
    double elapsed = time_now_sec() - t0;
    double measured_fps = (elapsed > 0.0) ? (captured / elapsed) : 0.0;

    SensorExposureInfo exp_info = cam.query_exposure_gain();
    LOG_INFO("[PASS] Camera %s (%dx%d) subdev=%s:",
             cam.device_node().c_str(), cam.width(), cam.height(),
             cam.subdev_node().empty() ? "none" : cam.subdev_node().c_str());
    LOG_INFO("       Measured Sensor Rate : %.2f FPS (%d frames in %.2fs)",
             measured_fps, captured, elapsed);
    LOG_INFO("       Current Exposure     : %d lines (auto_exposure=%d, VTS max=984)",
             exp_info.exposure, exp_info.auto_exposure);
    LOG_INFO("       Current Gain         : %d (autogain=%d)",
             exp_info.gain, exp_info.autogain);

    if (exp_info.exposure >= 950) {
        LOG_WARN("       [DIAGNOSIS] Exposure (%d) is near ceiling (984 lines) -> Scene is low-light!",
                 exp_info.exposure);
        LOG_WARN("       -> Add front LED lighting OR pass --lock-30fps --exposure 350 --gain 48");
    } else {
        LOG_INFO("       [DIAGNOSIS] Exposure (%d) has sufficient light headroom for 30 FPS.",
                 exp_info.exposure);
    }
    LOG_INFO("====================================================================");

    cam.close();
    imu.close();
    return 0;
}

/* ── MODE 5: run_test_imu (50Hz Real-Time Attitude Readout) ────────── */

static int run_test_imu(int imu_bus, int imu_addr) {
    ImuReader imu(imu_bus, imu_addr);
    if (!imu.initialize()) {
        LOG_ERROR("Failed to initialize MPU6050 on /dev/i2c-%d (0x%02X).", imu_bus, imu_addr);
        return 1;
    }

    LOG_INFO("Streaming IMU telemetry at 50 Hz (Press Ctrl+C to stop)...");
    while (g_running.load()) {
        Attitude att = imu.read_attitude();
        fprintf(stdout,
                "\r[IMU-TEST] Ax: %+6.3fg | Ay: %+6.3fg | Az: %+6.3fg | "
                "Pitch (theta): %+6.2f° | Roll (phi): %+6.2f°   ",
                att.ax, att.ay, att.az, att.pitch_deg, att.roll_deg);
        fflush(stdout);
        usleep(20000); /* 20ms = 50Hz */
    }
    fprintf(stdout, "\n");
    imu.close();
    return 0;
}

/* ── MODE 6: run_test_perf (Hardware VSYNC + NEON + TurboJPEG Benchmark) */

static int run_test_perf(const std::string& device, int width, int height,
                         int fps, bool rotate_180, bool vflip_only, int buf_count,
                         int jpeg_quality, int num_frames,
                         bool lock_30fps, int exposure, int gain) {
    LOG_INFO("====================================================================");
    LOG_INFO("PI CAPTURE NATIVE C++ — PERFORMANCE BENCHMARK (%d FRAMES)", num_frames);
    LOG_INFO("====================================================================");

    V4l2Camera cam(device, width, height, fps, rotate_180, buf_count, vflip_only);
    if (!cam.open()) {
        LOG_ERROR("Failed to open camera for benchmark.");
        return 1;
    }
    cam.set_exposure_mode(lock_30fps, exposure, gain);

    JpegEncoder encoder(jpeg_quality, g_swap_uv.load(), g_yuyv_order.load());

    /* Warmup 10 frames */
    LOG_INFO("Running sensor warmup (10 frames)...");
    for (int i = 0; i < 10 && g_running.load(); ++i) {
        const uint8_t* d; size_t n; int idx;
        if (cam.dequeue_frame(d, n, idx))
            cam.requeue_buffer(idx);
    }

    double total_wait_ms   = 0.0;
    double total_neon_ms   = 0.0;
    double total_encode_ms = 0.0;
    size_t total_jpeg_bytes = 0;
    int    completed = 0;

    double t_wall_start = time_now_sec();

    for (int i = 0; i < num_frames && g_running.load(); ++i) {
        const uint8_t* data = nullptr;
        size_t bytes = 0;
        int idx = -1;
        double wait_ms = 0.0;

        if (!cam.dequeue_frame(data, bytes, idx, &wait_ms))
            continue;

        uint8_t* jpeg_buf = nullptr;
        unsigned long jpeg_size = 0;
        double neon_ms = 0.0, encode_ms = 0.0;

        bool ok = encoder.encode(data, cam.width(), cam.height(),
                                 jpeg_buf, jpeg_size, &neon_ms, &encode_ms);
        cam.requeue_buffer(idx);

        if (ok) {
            total_wait_ms    += wait_ms;
            total_neon_ms    += neon_ms;
            total_encode_ms  += encode_ms;
            total_jpeg_bytes += jpeg_size;
            completed++;
            encoder.free_buffer(jpeg_buf);
        }
    }

    double wall_sec = time_now_sec() - t_wall_start;
    SensorExposureInfo exp_info = cam.query_exposure_gain();
    cam.close();

    if (completed == 0) {
        LOG_ERROR("No frames completed during benchmark.");
        return 1;
    }

    double avg_wait   = total_wait_ms / completed;
    double avg_neon   = total_neon_ms / completed;
    double avg_enc    = total_encode_ms / completed;
    double avg_active = avg_neon + avg_enc;
    double eff_fps    = wall_sec > 0.0 ? (completed / wall_sec) : 0.0;
    double avg_kb     = (total_jpeg_bytes / 1024.0) / completed;

    LOG_INFO("--------------------------------------------------------------------");
    LOG_INFO("Resolution & Format      : %dx%d UYVY -> YUV422P -> JPEG (Q=%d)",
             width, height, jpeg_quality);
    LOG_INFO("Sensor Exposure / Gain   : exposure=%d lines | gain=%d",
             exp_info.exposure, exp_info.gain);
    LOG_INFO("Avg VSYNC Poll Wait      : %.2f ms", avg_wait);
    LOG_INFO("Avg NEON UYVY->YUV422P   : %.2f ms", avg_neon);
    LOG_INFO("Avg TurboJPEG Encode     : %.2f ms", avg_enc);
    LOG_INFO("Total Active CPU / Frame : %.2f ms (Max Theoretical CPU Rate: %.1f FPS)",
             avg_active, avg_active > 0.0 ? (1000.0 / avg_active) : 0.0);
    LOG_INFO("Effective Frame Rate     : %.2f FPS (%d frames in %.2f s)",
             eff_fps, completed, wall_sec);
    LOG_INFO("Avg JPEG Payload Size    : %.1f KB", avg_kb);
    LOG_INFO("====================================================================");
    return 0;
}

/* ── main ──────────────────────────────────────────────────────────── */

static void print_usage(const char* prog) {
    fprintf(stderr,
        "Usage: %s [options]\n"
        "\n"
        "Modes:\n"
        "  --mode preview    Embedded HTTP MJPEG + Telemetry HUD server (default)\n"
        "  --mode stream     3-thread continuous capture → NEON → TurboJPEG → TCP\n"
        "  --mode snapshot   Single frame → JPEG file\n"
        "  --mode diag       Hardware & OV5640 exposure/gain diagnostic check\n"
        "  --mode test-imu   Real-time 50Hz MPU6050 pitch/roll console readout\n"
        "  --mode test-perf  Benchmark V4L2 VSYNC + ARM NEON + TurboJPEG latency\n"
        "\n"
        "Camera options:\n"
        "  --device PATH     V4L2 device (default: /dev/video0)\n"
        "  --width  N        Capture width  (default: 1280)\n"
        "  --height N        Capture height (default: 720)\n"
        "  --fps    N        Frame rate     (default: 30)\n"
        "  --quality N       JPEG quality 1-100 (default: 65)\n"
        "  --buffers N       V4L2 MMAP buffer count (default: 4)\n"
        "  --rotate-180      Enable hardware HFLIP+VFLIP on OV5640\n"
        "  --vflip           Enable hardware VFLIP only on OV5640\n"
        "  --lock-30fps      Balanced 25-30 FPS shutter lock (exposure=600 [20ms], gain=32)\n"
        "  --exposure N      Manual exposure shutter lines <= 984 (default: 600 with --lock-30fps)\n"
        "  --gain N          Manual gain value (default: 32 with --lock-30fps)\n"
        "  --red-balance N   Manual Red WB gain 256-4095 (disables AWB to fix color cast)\n"
        "  --blue-balance N  Manual Blue WB gain 256-4095 (disables AWB to fix color cast)\n"
        "  --swap-uv         Swap U (Cb) and V (Cr) chroma planes\n"
        "  --yuyv            Interpret sensor byte order as YUYV instead of UYVY\n"
        "\n"
        "Stream options:\n"
        "  --host ADDR       Ingest server IP   (default: 192.168.1.20)\n"
        "  --port N          Ingest server port (default: 9876)\n"
        "\n"
        "Preview options:\n"
        "  --preview-port N  HTTP preview server port (default: 8080)\n"
        "\n"
        "Snapshot / Benchmark options:\n"
        "  --output PATH     Output JPEG file path (default: snapshot.jpg)\n"
        "  --frames N        Number of frames for test-perf (default: 100)\n"
        "\n"
        "IMU options:\n"
        "  --imu-bus N       I2C bus   (default: 1)\n"
        "  --imu-addr HEX    I2C addr  (default: 0x68)\n"
        , prog);
}

int main(int argc, char* argv[]) {
    /* Defaults */
    std::string mode         = "preview";
    std::string device       = "/dev/video0";
    int         width        = 1280;
    int         height       = 720;
    int         fps          = 30;
    int         quality      = 65;
    int         buffers      = 4;
    bool        rotate_180   = false;
    bool        vflip_only   = false;
    bool        lock_30fps   = false;
    int         exposure     = -1;
    int         gain         = -1;
    int         red_bal      = -1;
    int         blue_bal     = -1;
    std::string host         = "192.168.1.20";
    int         port         = 9876;
    int         preview_port = 8080;
    std::string output       = "snapshot.jpg";
    int         frames       = 100;
    int         imu_bus      = 1;
    int         imu_addr     = 0x68;

    static struct option long_opts[] = {
        {"mode",         required_argument, nullptr, 'm'},
        {"device",       required_argument, nullptr, 'd'},
        {"width",        required_argument, nullptr, 'W'},
        {"height",       required_argument, nullptr, 'H'},
        {"fps",          required_argument, nullptr, 'f'},
        {"quality",      required_argument, nullptr, 'q'},
        {"buffers",      required_argument, nullptr, 'B'},
        {"rotate-180",   no_argument,       nullptr, 'r'},
        {"vflip",        no_argument,       nullptr, 'V'},
        {"lock-30fps",   no_argument,       nullptr, 'L'},
        {"exposure",     required_argument, nullptr, 'E'},
        {"gain",         required_argument, nullptr, 'G'},
        {"red-balance",  required_argument, nullptr, 'R'},
        {"blue-balance", required_argument, nullptr, 'C'},
        {"swap-uv",      no_argument,       nullptr, 'U'},
        {"yuyv",         no_argument,       nullptr, 'Y'},
        {"host",         required_argument, nullptr, 'h'},
        {"port",         required_argument, nullptr, 'p'},
        {"preview-port", required_argument, nullptr, 'P'},
        {"output",       required_argument, nullptr, 'o'},
        {"out",          required_argument, nullptr, 'o'},
        {"frames",       required_argument, nullptr, 'n'},
        {"imu-bus",      required_argument, nullptr, 'b'},
        {"imu-addr",     required_argument, nullptr, 'a'},
        {"help",         no_argument,       nullptr, '?'},
        {nullptr, 0, nullptr, 0},
    };

    int c;
    while ((c = getopt_long(argc, argv, "m:d:W:H:f:q:B:rVLE:G:R:C:UYh:p:P:o:n:b:a:", long_opts, nullptr)) != -1) {
        switch (c) {
            case 'm': mode   = optarg; break;
            case 'd': device = optarg; break;
            case 'W': width  = atoi(optarg); break;
            case 'H': height = atoi(optarg); break;
            case 'f': fps    = atoi(optarg); break;
            case 'q': quality = atoi(optarg); break;
            case 'B': buffers = atoi(optarg); break;
            case 'r': rotate_180 = true; break;
            case 'V': vflip_only = true; break;
            case 'L': lock_30fps = true; break;
            case 'E': exposure   = atoi(optarg); break;
            case 'G': gain       = atoi(optarg); break;
            case 'R': red_bal    = atoi(optarg); break;
            case 'C': blue_bal   = atoi(optarg); break;
            case 'U': g_swap_uv.store(true); break;
            case 'Y': g_yuyv_order.store(true); break;
            case 'h': host   = optarg; break;
            case 'p': port   = atoi(optarg); break;
            case 'P': preview_port = atoi(optarg); break;
            case 'o': output = optarg; break;
            case 'n': frames = atoi(optarg); break;
            case 'b': imu_bus  = atoi(optarg); break;
            case 'a': imu_addr = static_cast<int>(strtol(optarg, nullptr, 0)); break;
            default:
                print_usage(argv[0]);
                return (c == '?') ? 0 : 1;
        }
    }

    /* Balanced --lock-30fps defaults:
     * - exposure = 600 lines (20.0ms @ 30fps timing) -> +71% brighter than 350!
     * - gain     = 32 (clean 2.0x analog gain; required because ov5640.c couples AEC/AGC in reg 0x3503) */
    if (lock_30fps && exposure < 0) exposure = 600;
    if (lock_30fps && gain < 0)     gain     = 32;

    /* Install signal handlers */
    signal(SIGINT,  signal_handler);
    signal(SIGTERM, signal_handler);

    LOG_INFO("pi_capture_native — mode: %s", mode.c_str());

    if (mode == "preview") {
        run_preview(device, width, height, fps, rotate_180, vflip_only, buffers,
                    quality, preview_port, imu_bus, imu_addr,
                    lock_30fps, exposure, gain, red_bal, blue_bal);
    } else if (mode == "stream") {
        run_stream(device, width, height, fps, rotate_180, vflip_only, buffers,
                   quality, host, port, imu_bus, imu_addr,
                   lock_30fps, exposure, gain, red_bal, blue_bal);
    } else if (mode == "snapshot") {
        run_snapshot(device, width, height, fps, rotate_180, vflip_only, buffers,
                     quality, output, lock_30fps, exposure, gain, red_bal, blue_bal);
    } else if (mode == "diag") {
        return run_diag(device, width, height, fps, rotate_180, vflip_only, buffers,
                        imu_bus, imu_addr, lock_30fps, exposure, gain);
    } else if (mode == "test-imu") {
        return run_test_imu(imu_bus, imu_addr);
    } else if (mode == "test-perf") {
        return run_test_perf(device, width, height, fps, rotate_180, vflip_only, buffers,
                             quality, frames, lock_30fps, exposure, gain);
    } else {
        LOG_ERROR("Unknown mode: %s", mode.c_str());
        print_usage(argv[0]);
        return 1;
    }

    return 0;
}
