"""Command-line interface entrypoint for Raspberry Pi 3 capture agent.

Provides diagnostic routines and operational pipelines:
- diag: automated sanity check for I2C bus, MPU6050, and V4L2 camera.
- snapshot: captures a single test frame and writes to disk.
- test-imu: prints raw acceleration and computed attitude angles to terminal.
- preview: starts a lightweight diagnostic HTTP server to inspect camera feed from laptop.
- stream: runs the continuous streaming loop to the remote ingest server.
"""

import argparse
import sys
import os
import time
import signal
import logging
import json
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Optional
import yaml

from pi_capture_agent.camera import CameraDriver
from pi_capture_agent.imu import IMUReader
from pi_capture_agent.packer import BinaryFramePacker
from pi_capture_agent.streamer import SocketStreamer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pi_capture_agent")


def load_config(config_path: str) -> dict:
    """Loads YAML configuration file with intelligent path resolution across working directories."""
    from pathlib import Path

    candidates = [
        Path(config_path),
        Path("..") / config_path,
        Path("..") / ".." / config_path,
        Path(__file__).resolve().parents[3] / config_path,
        Path(__file__).resolve().parents[2] / config_path,
    ]

    for p in candidates:
        if p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                    logger.info("Loaded configuration from: %s", p.resolve())
                    return cfg
            except Exception as e:
                logger.warning("Could not parse config file %s: %s", p, e)

    logger.warning("Config file %s not found in search paths. Using defaults.", config_path)
    return {}


def run_diag(
    device: str,
    width: int,
    height: int,
    i2c_bus: int,
    i2c_addr: int,
    pixel_format: str = "UYVY",
    vflip: bool = True,
    rotate_180: bool = False,
) -> None:
    """Performs automated hardware and interface diagnosis."""
    print("=" * 65)
    print("  MONOCULAR SPATIAL VISION — HARDWARE SANITY DIAGNOSTIC")
    print("=" * 65)

    all_passed = True

    # 1. IMU Check
    print(f"\n[1/2] Probing MPU6050 IMU on I2C bus {i2c_bus} at address 0x{i2c_addr:02X}...")
    imu = IMUReader(bus_id=i2c_bus, address=i2c_addr)
    if imu.initialize():
        pitch, roll, (ax, ay, az) = imu.read_attitude()
        print(f"  -> [PASS] MPU6050 responding.")
        print(f"     Acc: Ax={ax:+.3f}g, Ay={ay:+.3f}g, Az={az:+.3f}g")
        print(f"     Angles: Pitch={pitch:+.2f}°, Roll={roll:+.2f}°")
        imu.close()
    else:
        print("  -> [FAIL] MPU6050 not detected. Verify 3.3V, GND, SDA (Pin 3), SCL (Pin 5).")
        all_passed = False

    # 2. Camera Check
    print(f"\n[2/2] Probing Camera Device {device} ({width}x{height}, fmt={pixel_format})...")
    cam = CameraDriver(
        device=device,
        width=width,
        height=height,
        fps=30,
        pixel_format=pixel_format,
        vflip=vflip,
        rotate_180=rotate_180,
    )
    if cam.open():
        print(f"  -> [PASS] Camera device node opened.")
        # Grab 5 test frames to verify frame acquisition rate
        times = []
        hardware_ok = True
        for _ in range(5):
            t0 = time.time()
            cam.read_frame()
            if getattr(cam, "is_synthetic_active", False) or cam.mock_mode:
                hardware_ok = False
            times.append(time.time() - t0)

        if not hardware_ok:
            print("  -> [FAIL] Device /dev/video0 is present, but NO physical frames could be captured from sensor!")
            print("            (Software fell back to synthetic mock images. OV5640 hardware is offline).")
            all_passed = False
        else:
            avg_time = sum(times) / len(times)
            fps = 1.0 / avg_time if avg_time > 0 else 0
            print(f"  -> [PASS] Physical frames acquired: {avg_time * 1000:.1f}ms per frame (~{fps:.1f} FPS)")
        cam.release()
    else:
        print("  -> [FAIL] Camera device failed to open.")
        all_passed = False

    print("\n" + "=" * 65)
    if all_passed:
        print("  RESULT: [SUCCESS] All hardware interfaces operational!")
    else:
        print("  RESULT: [WARNING] Some checks failed or are running in mock mode.")
    print("=" * 65 + "\n")


def run_snapshot(
    device: str,
    width: int,
    height: int,
    output_path: str,
    i2c_bus: int,
    i2c_addr: int,
    pixel_format: str = "UYVY",
    vflip: bool = True,
    rotate_180: bool = False,
) -> None:
    """Captures a single frame, logs attitude, and saves image to disk."""
    import cv2

    imu = IMUReader(bus_id=i2c_bus, address=i2c_addr)
    imu.initialize()
    pitch, roll, _ = imu.read_attitude()
    imu.close()

    cam = CameraDriver(
        device=device,
        width=width,
        height=height,
        pixel_format=pixel_format,
        vflip=vflip,
        rotate_180=rotate_180,
    )
    cam.open()
    # Warm up camera auto-exposure with 3 frames
    for _ in range(3):
        cam.read_frame()

    ts_ns, frame, jpeg_bytes = cam.read_frame()
    is_synth = getattr(cam, "is_synthetic_active", False) or cam.mock_mode
    cam.release()

    if frame is not None:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        cv2.imwrite(output_path, frame)
        if is_synth:
            logger.warning(
                "[NOTICE] Snapshot saved to %s is a SYNTHETIC FALLBACK (Res: %dx%d, Pitch: %.2f°, Roll: %.2f°). Sensor is offline.",
                output_path,
                frame.shape[1],
                frame.shape[0],
                pitch,
                roll,
            )
        else:
            logger.info(
                "Snapshot saved to %s (Res: %dx%d, Pitch: %.2f°, Roll: %.2f°)",
                output_path,
                frame.shape[1],
                frame.shape[0],
                pitch,
                roll,
            )
    else:
        logger.error("Failed to capture valid frame.")


def run_test_imu(i2c_bus: int, i2c_addr: int, rate_hz: float = 20.0) -> None:
    """Continuously prints IMU telemetry to terminal."""
    imu = IMUReader(bus_id=i2c_bus, address=i2c_addr)
    if not imu.initialize():
        logger.warning("Could not initialize hardware IMU. Running in mock mode.")

    delay = 1.0 / rate_hz
    logger.info("Starting IMU readout loop at %.1f Hz (Press Ctrl+C to stop)...", rate_hz)

    try:
        while True:
            pitch, roll, (ax, ay, az) = imu.read_attitude()
            print(
                f"\r[IMU] Ax: {ax:+6.3f}g | Ay: {ay:+6.3f}g | Az: {az:+6.3f}g | "
                f"Pitch(θ): {pitch:+6.2f}° | Roll(φ): {roll:+6.2f}°",
                end="",
                flush=True,
            )
            time.sleep(delay)
    except KeyboardInterrupt:
        print("\nStopping IMU loop.")
    finally:
        imu.close()


def run_preview_server(
    device: str,
    width: int,
    height: int,
    port: int,
    i2c_bus: int,
    i2c_addr: int,
    pixel_format: str = "UYVY",
    vflip: bool = True,
    rotate_180: bool = False,
    preview_width: int = 640,
    preview_height: int = 360,
    preview_quality: int = 65,
    use_hardware_flip: bool = True,
) -> None:
    """Runs a high-performance diagnostic HTTP preview server serving live frames and telemetry to laptop."""
    import cv2
    from pi_capture_agent.jpeg import FastJpegEncoder

    cam = CameraDriver(
        device=device,
        width=width,
        height=height,
        pixel_format=pixel_format,
        vflip=vflip,
        rotate_180=rotate_180,
        use_hardware_flip=use_hardware_flip,
    )
    if not cam.open():
        logger.error("Could not open camera device %s for preview", device)
        sys.exit(1)

    imu = IMUReader(bus_id=i2c_bus, address=i2c_addr)
    imu.initialize()

    # Shared thread-safe state for streaming
    state = {
        "jpeg": None,
        "pitch": 0.0,
        "roll": 0.0,
        "ax": 0.0,
        "ay": 0.0,
        "az": 0.0,
        "fps": 0.0,
        "frame_id": 0,
    }
    condition = threading.Condition()
    stop_event = threading.Event()

    def capture_worker():
        """Background thread acquiring frames and attitude at full sensor throughput."""
        frame_timestamps = []
        frame_count = 0
        target_size = (preview_width, preview_height)

        while not stop_event.is_set():
            try:
                # DRAIN camera buffer directly at sensor native rate without sleep
                ts_ns, frame = cam.read_raw()
                if frame is None:
                    time.sleep(0.01)
                    continue

                now = time.time()
                frame_timestamps.append(now)
                if len(frame_timestamps) > 20:
                    frame_timestamps.pop(0)
                if len(frame_timestamps) >= 2:
                    current_fps = (len(frame_timestamps) - 1) / (frame_timestamps[-1] - frame_timestamps[0])
                else:
                    current_fps = 0.0

                frame_count += 1

                # Read IMU attitude
                pitch, roll, (ax, ay, az) = imu.read_attitude()

                # Downscale for preview (e.g. 640x360) and encode JPEG at preview_quality (e.g. 65)
                if (preview_width, preview_height) != (frame.shape[1], frame.shape[0]):
                    preview_frame = cv2.resize(frame, target_size, interpolation=cv2.INTER_LINEAR)
                else:
                    preview_frame = frame

                jpeg_bytes = FastJpegEncoder.encode(preview_frame, quality=preview_quality)

                if jpeg_bytes is not None:
                    with condition:
                        state["jpeg"] = jpeg_bytes
                        state["pitch"] = pitch
                        state["roll"] = roll
                        state["ax"] = ax
                        state["ay"] = ay
                        state["az"] = az
                        state["fps"] = current_fps
                        state["frame_id"] = frame_count
                        condition.notify_all()

                # Throttle only in synthetic mock mode to prevent 100% CPU spin when no V4L2 device blocks
                if getattr(cam, "is_synthetic_active", False) or cam.mock_mode:
                    time.sleep(1.0 / max(cam.fps, 1))
            except Exception as e:
                logger.error("Error in capture_worker: %s", e, exc_info=True)
                time.sleep(0.05)

    worker_thread = threading.Thread(target=capture_worker, daemon=True)
    worker_thread.start()

    class PreviewHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Suppress HTTP access noise

        def do_GET(self):
            if self.path in ("/", "/preview", "/preview/"):
                html = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pcam 5C & IMU Live HUD</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #090d16; color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; padding: 12px; }
        .hud-card { background: #131c2e; border: 1px solid #1e293b; border-radius: 12px; padding: 14px; width: 100%; max-width: 580px; box-shadow: 0 8px 24px rgba(0,0,0,0.6); }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .title { font-size: 14px; font-weight: bold; color: #38bdf8; letter-spacing: 0.5px; }
        .badge-live { background: #059669; color: #ecfdf5; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 9999px; display: inline-flex; align-items: center; gap: 4px; }
        .badge-live::before { content: ""; width: 6px; height: 6px; background: #34d399; border-radius: 50%; display: inline-block; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.8); } }
        .video-container { position: relative; width: 100%; aspect-ratio: 16/9; background: #000; border-radius: 8px; overflow: hidden; border: 1px solid #334155; }
        #live-img { width: 100%; height: 100%; object-fit: contain; display: block; }
        .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 10px; }
        .stat-box { background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 8px 10px; text-align: center; }
        .stat-label { font-size: 10px; text-transform: uppercase; color: #94a3b8; margin-bottom: 2px; font-weight: 600; letter-spacing: 0.5px; }
        .stat-value { font-size: 13px; font-weight: 700; font-family: monospace; color: #f8fafc; }
        .fps-val { color: #10b981; }
        .att-val { color: #38bdf8; }
        .imu-val { color: #f59e0b; font-size: 11px; }
    </style>
</head>
<body>
    <div class="hud-card">
        <div class="header">
            <span class="title">PCAM 5C & MPU-6050 HUD</span>
            <span class="badge-live">LIVE FEED</span>
        </div>
        <div class="video-container">
            <img id="live-img" src="/stream.mjpg" alt="Feed">
        </div>
        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-label">Capture FPS</div>
                <div class="stat-value fps-val" id="fps-txt">-- FPS</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Pitch / Roll</div>
                <div class="stat-value att-val" id="att-txt">0.0° / 0.0°</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Accel (Ax, Ay, Az)</div>
                <div class="stat-value imu-val" id="accel-txt">0.00, 0.00, 1.00g</div>
            </div>
        </div>
    </div>
    <script>
        const img = document.getElementById('live-img');
        let useSnapshot = false;
        img.onerror = () => {
            if (!useSnapshot) {
                useSnapshot = true;
                pollSnapshot();
            }
        };
        function pollSnapshot() {
            if (!useSnapshot) return;
            img.src = '/snapshot.jpg?t=' + Date.now();
            setTimeout(pollSnapshot, 66);
        }
        setInterval(() => {
            fetch('/telemetry')
                .then(r => r.json())
                .then(d => {
                    document.getElementById('fps-txt').innerText = d.fps.toFixed(1) + ' FPS';
                    document.getElementById('att-txt').innerText = (d.pitch >= 0 ? '+' : '') + d.pitch.toFixed(1) + '° / ' + (d.roll >= 0 ? '+' : '') + d.roll.toFixed(1) + '°';
                    document.getElementById('accel-txt').innerText = `${d.ax.toFixed(2)}, ${d.ay.toFixed(2)}, ${d.az.toFixed(2)}g`;
                })
                .catch(() => {});
        }, 150);
    </script>
</body>
</html>"""
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(html.encode("utf-8"))
                except (BrokenPipeError, ConnectionResetError):
                    pass

            elif self.path.startswith("/stream.mjpg"):
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self.send_header("Pragma", "no-cache")
                    self.send_header("Expires", "0")
                    self.send_header("Connection", "close")
                    self.end_headers()

                    last_id = -1
                    while not stop_event.is_set():
                        with condition:
                            while state["frame_id"] == last_id and not stop_event.is_set():
                                condition.wait(timeout=0.1)
                            if stop_event.is_set():
                                break
                            jpeg_bytes = state["jpeg"]
                            last_id = state["frame_id"]

                        if jpeg_bytes is None:
                            continue

                        header = (
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n"
                            b"Content-Length: " + str(len(jpeg_bytes)).encode("ascii") + b"\r\n\r\n"
                        )
                        self.wfile.write(header + jpeg_bytes + b"\r\n")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass

            elif self.path.startswith("/snapshot.jpg"):
                with condition:
                    jpeg_bytes = state["jpeg"]
                if jpeg_bytes:
                    try:
                        self.send_response(200)
                        self.send_header("Content-Type", "image/jpeg")
                        self.send_header("Content-Length", str(len(jpeg_bytes)))
                        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                        self.end_headers()
                        self.wfile.write(jpeg_bytes)
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                else:
                    self.send_response(503)
                    self.end_headers()

            elif self.path.startswith("/telemetry"):
                with condition:
                    telemetry = {
                        "fps": state["fps"],
                        "pitch": state["pitch"],
                        "roll": state["roll"],
                        "ax": state["ax"],
                        "ay": state["ay"],
                        "az": state["az"],
                    }
                try:
                    body = json.dumps(telemetry).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            else:
                self.send_response(404)
                self.end_headers()

    class ReusableThreadingHTTPServer(ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    server = ReusableThreadingHTTPServer(("0.0.0.0", port), PreviewHandler)
    logger.info("Diagnostic Preview Server listening on http://0.0.0.0:%d (Press Ctrl+C to stop)", port)
    logger.info("Open http://<pi_ip>:%d/ in your laptop browser to view camera feed.", port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down preview server...")
    finally:
        stop_event.set()
        with condition:
            condition.notify_all()
        server.server_close()
        worker_thread.join(timeout=1.0)
        cam.release()
        imu.close()


def run_stream(
    device: str,
    width: int,
    height: int,
    fps: int,
    host: str,
    port: int,
    i2c_bus: int,
    i2c_addr: int,
    pixel_format: str = "UYVY",
    vflip: bool = True,
    rotate_180: bool = False,
    jpeg_quality: int = 70,
    use_hardware_flip: bool = True,
) -> None:
    """Continuous production streaming loop to remote Ingest Server."""
    running = True

    def sig_handler(sig, frame):
        nonlocal running
        logger.info("Received interrupt signal. Stopping stream...")
        running = False

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    # Initialize components
    cam = CameraDriver(
        device=device,
        width=width,
        height=height,
        fps=fps,
        pixel_format=pixel_format,
        vflip=vflip,
        rotate_180=rotate_180,
        use_hardware_flip=use_hardware_flip,
    )
    if not cam.open():
        logger.error("Could not open camera device %s", device)
        sys.exit(1)

    imu = IMUReader(bus_id=i2c_bus, address=i2c_addr)
    imu.initialize()

    streamer = SocketStreamer(host=host, port=port)
    logger.info("Starting binary streaming loop -> %s:%d (Target FPS: %d, Quality: %d)", host, port, fps, jpeg_quality)

    frame_id = 0
    start_time = time.time()
    last_log_time = time.time()
    sent_count = 0
    dropped_count = 0
    frame_interval = 1.0 / fps

    try:
        while running:
            t_loop_start = time.time()
            frame_id += 1

            # Read sensor telemetry
            pitch, roll, _ = imu.read_attitude()

            # Read frame
            ts_ns, _, jpeg_bytes = cam.read_frame(jpeg_quality=jpeg_quality)
            if jpeg_bytes is None:
                dropped_count += 1
                continue

            # Pack 36-byte header + JPEG payload
            packet = BinaryFramePacker.pack(
                frame_id=frame_id,
                timestamp_ns=ts_ns,
                pitch_deg=pitch,
                roll_deg=roll,
                image_bytes=jpeg_bytes,
                width=width,
                height=height,
            )

            # Transmit packet
            success = streamer.send_frame_packet(packet)
            if success:
                sent_count += 1
            else:
                dropped_count += 1

            # Periodic stats log every 3 seconds
            now = time.time()
            if now - last_log_time >= 3.0:
                elapsed = now - start_time
                current_fps = sent_count / elapsed if elapsed > 0 else 0
                drop_rate = (dropped_count / frame_id * 100.0) if frame_id > 0 else 0
                logger.info(
                    "Stream Status: Frame #%d | Sent: %d | Drop: %.1f%% | FPS: %.1f | Pitch: %.2f°",
                    frame_id,
                    sent_count,
                    drop_rate,
                    current_fps,
                    pitch,
                )
                last_log_time = now

            # Sleep remaining time to maintain target FPS
            t_spent = time.time() - t_loop_start
            sleep_time = frame_interval - t_spent
            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        cam.release()
        imu.close()
        streamer.close()
        logger.info("Streaming agent terminated cleanly.")


def run_test_perf(
    device: str,
    width: int,
    height: int,
    frames: int = 100,
    pixel_format: str = "UYVY",
    vflip: bool = True,
    rotate_180: bool = False,
    jpeg_quality: int = 70,
    use_hardware_flip: bool = True,
) -> None:
    """Measures pipeline component timings and throughput without network transmission."""
    from pi_capture_agent.jpeg import FastJpegEncoder

    print("=" * 68)
    print(f"  PI CAPTURE AGENT — PERFORMANCE BENCHMARK ({frames} FRAMES)")
    print("=" * 68)

    cam = CameraDriver(
        device=device,
        width=width,
        height=height,
        fps=30,
        pixel_format=pixel_format,
        vflip=vflip,
        rotate_180=rotate_180,
        use_hardware_flip=use_hardware_flip,
    )
    if not cam.open():
        logger.error("Could not open camera device %s", device)
        sys.exit(1)

    backend_desc = "PyTurboJPEG (ARM NEON SIMD)" if FastJpegEncoder.is_neon_accelerated() else "OpenCV imencode (Scalar fallback)"
    flip_desc = "ACTIVE (Sensor OV5640 hardware)" if cam._hw_vflip_applied else "INACTIVE (Software CPU fallback)"

    print(f"  Camera Device:       {device} ({width}x{height}, fmt={pixel_format})")
    print(f"  Hardware Flip:       {flip_desc}")
    print(f"  JPEG Backend:        {backend_desc}")
    print(f"  JPEG Quality:        {jpeg_quality}")
    print("  Running warmup frames...")

    for _ in range(3):
        cam.read_frame(jpeg_quality=jpeg_quality)

    print(f"  Benchmarking {frames} frames...")
    t_grab_list = []
    t_encode_list = []
    t_total_list = []
    payload_sizes = []

    t_bench_start = time.time()
    for _ in range(frames):
        t0 = time.time()
        ts_ns, raw_frame = cam.read_raw()
        t1 = time.time()
        jpeg_bytes = FastJpegEncoder.encode(raw_frame, quality=jpeg_quality) if raw_frame is not None else None
        t2 = time.time()

        t_grab_list.append((t1 - t0) * 1000)
        t_encode_list.append((t2 - t1) * 1000)
        t_total_list.append((t2 - t0) * 1000)
        if jpeg_bytes:
            payload_sizes.append(len(jpeg_bytes))

    t_bench_total = time.time() - t_bench_start
    cam.release()

    avg_grab = sum(t_grab_list) / len(t_grab_list) if t_grab_list else 0
    avg_encode = sum(t_encode_list) / len(t_encode_list) if t_encode_list else 0
    avg_total = sum(t_total_list) / len(t_total_list) if t_total_list else 0
    avg_size_kb = (sum(payload_sizes) / len(payload_sizes)) / 1024 if payload_sizes else 0
    measured_fps = frames / t_bench_total if t_bench_total > 0 else 0

    print("-" * 68)
    print(f"  Avg Raw Grab Time:     {avg_grab:6.2f} ms")
    print(f"  Avg Encode Time:       {avg_encode:6.2f} ms")
    print(f"  Avg Total Cycle Time:  {avg_total:6.2f} ms")
    print(f"  Avg JPEG Payload Size: {avg_size_kb:6.1f} KB")
    print(f"  Effective Throughput:  {measured_fps:6.1f} FPS")
    print("=" * 68)
    if measured_fps >= 25:
        print("  RESULT: [EXCELLENT] Target >= 25 FPS achieved successfully!")
    else:
        print("  RESULT: [NOTICE] Below 25 FPS target; verify hardware acceleration.")
    print("=" * 68 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Raspberry Pi 3 Pcam 5C & IMU Capture Agent")
    parser.add_argument(
        "--mode",
        choices=["diag", "snapshot", "test-imu", "preview", "stream", "test-perf"],
        default="stream",
        help="Operating mode (default: stream)",
    )
    parser.add_argument("--config", default="configs/capture_pi.yaml", help="Path to config YAML")
    parser.add_argument("--output", default="data/test_frame.jpg", help="Path to save test image (snapshot mode)")
    parser.add_argument("--frames", type=int, default=100, help="Number of frames for test-perf benchmark")
    parser.add_argument("--host", default=None, help="Target ingest host IP (overrides config)")
    parser.add_argument("--port", type=int, default=None, help="Target ingest port (overrides config)")
    parser.add_argument("--preview-port", type=int, default=8080, help="Port for diagnostic preview server")
    parser.add_argument("--device", default=None, help="Camera device node e.g. /dev/video0")
    parser.add_argument("--pixel-format", default=None, help="Camera pixel format (UYVY, YUYV, MJPG)")
    parser.add_argument("--vflip", action=argparse.BooleanOptionalAction, default=None, help="Enable or disable vertical flip")
    parser.add_argument("--rotate-180", action="store_true", default=None, help="Rotate frames 180 degrees")
    parser.add_argument("--use-hardware-flip", action=argparse.BooleanOptionalAction, default=None, help="Enable OV5640 hardware vertical flip")
    parser.add_argument("--jpeg-quality", type=int, default=None, help="JPEG compression quality (1-100, default: 70)")
    parser.add_argument("--preview-width", type=int, default=None, help="Preview downscale width")
    parser.add_argument("--preview-height", type=int, default=None, help="Preview downscale height")
    parser.add_argument("--preview-quality", type=int, default=None, help="Preview JPEG compression quality (1-100)")

    args = parser.parse_args()

    # Load configuration
    cfg = load_config(args.config)
    dev_cfg = cfg.get("device", {})
    imu_cfg = cfg.get("imu", {})
    stream_cfg = cfg.get("stream", {})

    device = args.device or dev_cfg.get("video_device", "/dev/video0")
    width = dev_cfg.get("width", 1280)
    height = dev_cfg.get("height", 720)
    fps = dev_cfg.get("fps", 30)
    pixel_format = args.pixel_format or dev_cfg.get("pixel_format", "UYVY")
    vflip = args.vflip if args.vflip is not None else dev_cfg.get("vflip", True)
    rotate_180 = args.rotate_180 if args.rotate_180 is not None else dev_cfg.get("rotate_180", False)
    preview_width = args.preview_width or dev_cfg.get("preview_width", 640)
    preview_height = args.preview_height or dev_cfg.get("preview_height", 360)
    preview_quality = args.preview_quality or dev_cfg.get("preview_quality", 65)

    i2c_bus = imu_cfg.get("i2c_bus", 1)
    i2c_addr = imu_cfg.get("i2c_address", 0x68)

    opt_cfg = cfg.get("optimization", {})
    use_hw_flip = args.use_hardware_flip if args.use_hardware_flip is not None else opt_cfg.get("use_hardware_flip", True)
    jpeg_quality = args.jpeg_quality or opt_cfg.get("jpeg_quality") or stream_cfg.get("jpeg_quality", 70)

    host = args.host or stream_cfg.get("target_host", "127.0.0.1")
    port = args.port or stream_cfg.get("target_port", 9876)

    if args.mode == "stream" and host in ("127.0.0.1", "localhost"):
        logger.warning(
            "Stream target is set to %s (Pi 3 localhost). If sending to Laptop, "
            "provide --host <IP_LAPTOP> or update 'target_host' in configs/capture_pi.yaml.",
            host,
        )

    logger.info("Selected mode: %s", args.mode)

    if args.mode == "diag":
        run_diag(
            device=device,
            width=width,
            height=height,
            i2c_bus=i2c_bus,
            i2c_addr=i2c_addr,
            pixel_format=pixel_format,
            vflip=vflip,
            rotate_180=rotate_180,
        )
    elif args.mode == "snapshot":
        run_snapshot(
            device=device,
            width=width,
            height=height,
            output_path=args.output,
            i2c_bus=i2c_bus,
            i2c_addr=i2c_addr,
            pixel_format=pixel_format,
            vflip=vflip,
            rotate_180=rotate_180,
        )
    elif args.mode == "test-imu":
        run_test_imu(i2c_bus=i2c_bus, i2c_addr=i2c_addr)
    elif args.mode == "preview":
        run_preview_server(
            device=device,
            width=width,
            height=height,
            port=args.preview_port,
            i2c_bus=i2c_bus,
            i2c_addr=i2c_addr,
            pixel_format=pixel_format,
            vflip=vflip,
            rotate_180=rotate_180,
            preview_width=preview_width,
            preview_height=preview_height,
            preview_quality=preview_quality,
            use_hardware_flip=use_hw_flip,
        )
    elif args.mode == "test-perf":
        run_test_perf(
            device=device,
            width=width,
            height=height,
            frames=args.frames,
            pixel_format=pixel_format,
            vflip=vflip,
            rotate_180=rotate_180,
            jpeg_quality=jpeg_quality,
            use_hardware_flip=use_hw_flip,
        )
    elif args.mode == "stream":
        run_stream(
            device=device,
            width=width,
            height=height,
            fps=fps,
            host=host,
            port=port,
            i2c_bus=i2c_bus,
            i2c_addr=i2c_addr,
            pixel_format=pixel_format,
            vflip=vflip,
            rotate_180=rotate_180,
            jpeg_quality=jpeg_quality,
            use_hardware_flip=use_hw_flip,
        )
    else:
        logger.error("Unknown mode: %s", args.mode)
        sys.exit(1)


if __name__ == "__main__":
    main()
