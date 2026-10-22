/**
 * @file main.cpp
 * @brief Entrypoint for pi_capture_native — high-performance C++ replacement
 *        for the Python pi_capture_agent streaming pipeline.
 *
 * Replaces: pi_capture_agent/cli.py  run_stream(), run_snapshot(), run_preview()
 *
 * Architecture (matches Python's Producer-Consumer model):
 *   Thread 1 (capture): V4L2 DQBUF → memcpy → QBUF + IMU read → push to slot
 *   Thread 2 (main):    pop slot → JPEG encode → pack header → TCP send / HTTP server
 *
 * Usage:
 *   ./pi_capture_native --mode stream  --host 192.168.1.20 --port 9876
 *   ./pi_capture_native --mode preview --preview-port 8080
 *   ./pi_capture_native --mode snapshot --output test.jpg
 *   ./pi_capture_native --help
 */

#include "v4l2_camera.h"
#include "jpeg_encoder.h"
#include "socket_streamer.h"
#include "frame_packer.h"
#include "imu_reader.h"
#include "log.h"

#include <arpa/inet.h>
#include <atomic>
#include <condition_variable>
#include <csignal>
#include <cstdlib>
#include <cstring>
#include <getopt.h>
#include <mutex>
#include <netinet/in.h>
#include <string>
#include <sys/select.h>
#include <sys/socket.h>
#include <thread>
#include <unistd.h>
#include <vector>

/* ── globals for signal handler ────────────────────────────────────── */
static std::atomic<bool> g_running{true};

static void signal_handler(int) { g_running.store(false); }

/* ── Stage 1 -> Stage 2: Raw Frame Slot ── */

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

/* ── Stage 2 -> Stage 3: Encoded Packet Slot ── */

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
 * Reads raw UYVY frame from V4L2 + IMU attitude, publishes to raw slot.
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
    JpegEncoder encoder(jpeg_quality);
    std::vector<uint8_t> local_pixels;
    std::vector<uint8_t> local_packet;
    uint32_t frame_id = 0;

    while (g_running.load()) {
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

        /* TurboJPEG compression (NEON accelerated) */
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

/* ── run_stream (Thread 3: Network streamer) ─────────────────────── */

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
            const char* status = streamer.is_connected() ? "CONNECTED" : "RECONNECTING";
            LOG_INFO("[%s] Frame #%u | Rate: %.1f FPS (%.1f KB/s) | Pitch: %+.2f° | Roll: %+.2f°",
                     status, cur_frame_id, fps_actual, kb_rate, cur_pitch, cur_roll);
            frames_sent = 0;
            bytes_sent = 0;
            t_stats = now;
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

/* ── run_preview (Embedded HTTP MJPEG + HUD Server) ───────────────── */

struct PreviewFrame {
    std::vector<uint8_t> jpeg;
    float pitch = 0.0f;
    float roll  = 0.0f;
    double fps  = 0.0;
    uint64_t seq = 0;
};

static std::mutex g_prev_mutex;
static std::condition_variable g_prev_cv;
static PreviewFrame g_prev_frame;

static void handle_http_client(int client_fd) {
    char req[2048] = {0};
    ssize_t n = recv(client_fd, req, sizeof(req) - 1, 0);
    if (n <= 0) {
        close(client_fd);
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
        if (send(client_fd, header, strlen(header), MSG_NOSIGNAL) <= 0) {
            close(client_fd);
            return;
        }

        uint64_t last_sent_seq = 0;
        while (g_running.load()) {
            std::vector<uint8_t> cur_jpeg;
            {
                std::unique_lock<std::mutex> lk(g_prev_mutex);
                g_prev_cv.wait_for(lk, std::chrono::milliseconds(100),
                    [&] { return g_prev_frame.seq > last_sent_seq || !g_running.load(); });
                if (!g_running.load()) break;
                if (g_prev_frame.seq == last_sent_seq || g_prev_frame.jpeg.empty())
                    continue;
                cur_jpeg = g_prev_frame.jpeg;
                last_sent_seq = g_prev_frame.seq;
            }

            char part_hdr[128];
            snprintf(part_hdr, sizeof(part_hdr),
                     "--frameboundary\r\nContent-Type: image/jpeg\r\nContent-Length: %zu\r\n\r\n",
                     cur_jpeg.size());
            if (send(client_fd, part_hdr, strlen(part_hdr), MSG_NOSIGNAL) <= 0) break;
            if (send(client_fd, cur_jpeg.data(), cur_jpeg.size(), MSG_NOSIGNAL) <= 0) break;
            if (send(client_fd, "\r\n", 2, MSG_NOSIGNAL) <= 0) break;
        }
    } else if (strstr(req, "GET /telemetry")) {
        float p = 0.0f, r = 0.0f;
        double f = 0.0;
        {
            std::lock_guard<std::mutex> lk(g_prev_mutex);
            p = g_prev_frame.pitch;
            r = g_prev_frame.roll;
            f = g_prev_frame.fps;
        }
        char json[256];
        snprintf(json, sizeof(json),
                 "{\"pitch_deg\":%.2f,\"roll_deg\":%.2f,\"fps\":%.1f}", p, r, f);
        char resp[512];
        snprintf(resp, sizeof(resp),
                 "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %zu\r\nConnection: close\r\n\r\n%s",
                 strlen(json), json);
        send(client_fd, resp, strlen(resp), MSG_NOSIGNAL);
    } else if (strstr(req, "GET /snapshot.jpg")) {
        std::vector<uint8_t> cur_jpeg;
        {
            std::lock_guard<std::mutex> lk(g_prev_mutex);
            cur_jpeg = g_prev_frame.jpeg;
        }
        if (!cur_jpeg.empty()) {
            char resp[256];
            snprintf(resp, sizeof(resp),
                     "HTTP/1.1 200 OK\r\nContent-Type: image/jpeg\r\nContent-Length: %zu\r\nConnection: close\r\n\r\n",
                     cur_jpeg.size());
            send(client_fd, resp, strlen(resp), MSG_NOSIGNAL);
            send(client_fd, cur_jpeg.data(), cur_jpeg.size(), MSG_NOSIGNAL);
        } else {
            const char* not_ready = "HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
            send(client_fd, not_ready, strlen(not_ready), MSG_NOSIGNAL);
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
            "    .hud-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 10px; }\n"
            "    .hud-stat { background: #0f172a; padding: 10px; border-radius: 6px; border-left: 4px solid #38bdf8; }\n"
            "    .hud-label { font-size: 11px; color: #94a3b8; text-transform: uppercase; }\n"
            "    .hud-val { font-size: 20px; font-weight: bold; margin-top: 4px; color: #38bdf8; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            "  <h1>⚡ Pi 3 Native C++ Stream (libturbojpeg + ARM NEON)</h1>\n"
            "  <div class=\"card\">\n"
            "    <img src=\"/stream.mjpg\" alt=\"Live Camera Stream\">\n"
            "  </div>\n"
            "  <div class=\"card\">\n"
            "    <strong>IMU Sensor Telemetry</strong>\n"
            "    <div class=\"hud-grid\">\n"
            "      <div class=\"hud-stat\"><div class=\"hud-label\">Pitch Angle</div><div class=\"hud-val\" id=\"val-pitch\">-- deg</div></div>\n"
            "      <div class=\"hud-stat\"><div class=\"hud-label\">Roll Angle</div><div class=\"hud-val\" id=\"val-roll\">-- deg</div></div>\n"
            "      <div class=\"hud-stat\"><div class=\"hud-label\">Camera FPS</div><div class=\"hud-val\" id=\"val-fps\">-- FPS</div></div>\n"
            "    </div>\n"
            "  </div>\n"
            "  <script>\n"
            "    setInterval(async () => {\n"
            "      try {\n"
            "        const res = await fetch('/telemetry');\n"
            "        const data = await res.json();\n"
            "        document.getElementById('val-pitch').innerText = `${data.pitch_deg > 0 ? '+' : ''}${data.pitch_deg.toFixed(2)}°`;\n"
            "        document.getElementById('val-roll').innerText = `${data.roll_deg > 0 ? '+' : ''}${data.roll_deg.toFixed(2)}°`;\n"
            "        document.getElementById('val-fps').innerText = `${data.fps.toFixed(1)} FPS`;\n"
            "      } catch (e) {}\n"
            "    }, 250);\n"
            "  </script>\n"
            "</body>\n"
            "</html>\n";

        char resp[4096];
        snprintf(resp, sizeof(resp),
                 "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: %zu\r\nConnection: close\r\n\r\n%s",
                 strlen(html), html);
        send(client_fd, resp, strlen(resp), MSG_NOSIGNAL);
    }

    close(client_fd);
}

static void run_preview(const std::string& device, int width, int height,
                        int fps, bool rotate_180, int jpeg_quality,
                        int preview_port, int imu_bus, int imu_addr) {
    V4l2Camera cam(device, width, height, fps, rotate_180);
    if (!cam.open()) {
        LOG_ERROR("Failed to open camera for preview.");
        return;
    }

    ImuReader imu(imu_bus, imu_addr);
    ImuReader* imu_ptr = nullptr;
    if (imu.initialize()) {
        imu_ptr = &imu;
    } else {
        LOG_WARN("IMU init failed. Continuing without IMU.");
    }

    JpegEncoder encoder(jpeg_quality);

    /* Warm-up */
    for (int i = 0; i < 5; ++i) {
        const uint8_t* d; size_t n; int idx;
        if (cam.dequeue_frame(d, n, idx))
            cam.requeue_buffer(idx);
    }

    /* Capture & encode worker */
    std::thread worker([&]() {
        uint64_t seq = 0;
        uint32_t frame_count = 0;
        double t_start = time_now_sec();
        while (g_running.load()) {
            const uint8_t* data = nullptr;
            size_t bytes = 0;
            int idx = -1;
            if (!cam.dequeue_frame(data, bytes, idx))
                continue;

            Attitude att;
            if (imu_ptr) att = imu_ptr->read_attitude();

            uint8_t* jpeg_buf = nullptr;
            unsigned long jpeg_size = 0;
            if (encoder.encode(data, cam.width(), cam.height(), jpeg_buf, jpeg_size)) {
                frame_count++;
                double elapsed = time_now_sec() - t_start;
                double cur_fps = elapsed > 0 ? (frame_count / elapsed) : 0;
                if (elapsed > 5.0) {
                    t_start = time_now_sec();
                    frame_count = 0;
                }

                {
                    std::lock_guard<std::mutex> lk(g_prev_mutex);
                    g_prev_frame.jpeg.assign(jpeg_buf, jpeg_buf + jpeg_size);
                    g_prev_frame.pitch = att.pitch_deg;
                    g_prev_frame.roll  = att.roll_deg;
                    g_prev_frame.fps   = cur_fps;
                    g_prev_frame.seq   = ++seq;
                }
                g_prev_cv.notify_all();
                encoder.free_buffer(jpeg_buf);
            }
            cam.requeue_buffer(idx);
        }
    });

    /* Open HTTP server socket */
    int srv = socket(AF_INET, SOCK_STREAM, 0);
    int opt = 1;
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    sockaddr_in sin{};
    sin.sin_family = AF_INET;
    sin.sin_addr.s_addr = INADDR_ANY;
    sin.sin_port = htons(static_cast<uint16_t>(preview_port));

    if (bind(srv, (sockaddr*)&sin, sizeof(sin)) < 0) {
        LOG_ERROR("Cannot bind HTTP server to port %d: %s", preview_port, strerror(errno));
        g_running.store(false);
        if (worker.joinable()) worker.join();
        cam.close();
        return;
    }

    listen(srv, 5);

    LOG_INFO("================ PREVIEW SERVER STARTED ================");
    LOG_INFO("HTTP Preview running on port %d", preview_port);
    LOG_INFO("Open from your Laptop browser (Chrome, Edge, Firefox):");
    LOG_INFO("  👉  http://<IP_PI>:%d/              (Interactive Web HUD)", preview_port);
    LOG_INFO("  👉  http://<IP_PI>:%d/stream.mjpg  (Raw MJPEG Stream)", preview_port);
    LOG_INFO("Press Ctrl+C to terminate preview server.");
    LOG_INFO("========================================================");

    std::vector<std::thread> client_threads;

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
                client_threads.emplace_back([cfd]() {
                    handle_http_client(cfd);
                });
            }
        }
    }

    close(srv);
    g_prev_cv.notify_all();
    if (worker.joinable()) worker.join();
    for (auto& t : client_threads) {
        if (t.joinable()) t.join();
    }
    cam.close();
    imu.close();
    LOG_INFO("Preview server shut down.");
}

/* ── main ──────────────────────────────────────────────────────────── */

static void print_usage(const char* prog) {
    fprintf(stderr,
        "Usage: %s [options]\n"
        "\n"
        "Modes:\n"
        "  --mode stream     Continuous capture → JPEG → TCP\n"
        "  --mode preview    Embedded HTTP MJPEG server for browser viewer (default)\n"
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
        "Preview options:\n"
        "  --preview-port N  HTTP preview server port (default: 8080)\n"
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
    /* Defaults */
    std::string mode         = "preview";
    std::string device       = "/dev/video0";
    int         width        = 1280;
    int         height       = 720;
    int         fps          = 30;
    int         quality      = 65;
    bool        rotate_180   = false;
    std::string host         = "192.168.1.20";
    int         port         = 9876;
    int         preview_port = 8080;
    std::string output       = "snapshot.jpg";
    int         imu_bus      = 1;
    int         imu_addr     = 0x68;

    static struct option long_opts[] = {
        {"mode",         required_argument, nullptr, 'm'},
        {"device",       required_argument, nullptr, 'd'},
        {"width",        required_argument, nullptr, 'W'},
        {"height",       required_argument, nullptr, 'H'},
        {"fps",          required_argument, nullptr, 'f'},
        {"quality",      required_argument, nullptr, 'q'},
        {"rotate-180",   no_argument,       nullptr, 'r'},
        {"host",         required_argument, nullptr, 'h'},
        {"port",         required_argument, nullptr, 'p'},
        {"preview-port", required_argument, nullptr, 'P'},
        {"output",       required_argument, nullptr, 'o'},
        {"imu-bus",      required_argument, nullptr, 'b'},
        {"imu-addr",     required_argument, nullptr, 'a'},
        {"help",         no_argument,       nullptr, '?'},
        {nullptr, 0, nullptr, 0},
    };

    int c;
    while ((c = getopt_long(argc, argv, "m:d:W:H:f:q:rh:p:P:o:b:a:", long_opts, nullptr)) != -1) {
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
            case 'P': preview_port = atoi(optarg); break;
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

    if (mode == "preview") {
        run_preview(device, width, height, fps, rotate_180, quality,
                    preview_port, imu_bus, imu_addr);
    } else if (mode == "stream") {
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
