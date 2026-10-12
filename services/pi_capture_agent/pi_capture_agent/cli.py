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
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
import yaml

from pi_capture_agent.camera import CameraDriver
from pi_capture_agent.imu import IMUReader
from pi_capture_agent.packer import BinaryFramePacker
from pi_capture_agent.streamer import SocketStreamer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pi_capture_agent")


def load_config(config_path: str) -> dict:
    """Loads YAML configuration file if present."""
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("Could not parse config file %s: %s. Using defaults.", config_path, e)
    return {}


def run_diag(device: str, width: int, height: int, i2c_bus: int, i2c_addr: int) -> None:
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
    print(f"\n[2/2] Probing Camera Device {device} ({width}x{height})...")
    cam = CameraDriver(device=device, width=width, height=height, fps=30)
    if cam.open():
        print(f"  -> [PASS] Camera opened successfully.")
        # Grab 5 test frames to verify frame acquisition rate
        times = []
        for _ in range(5):
            t0 = time.time()
            cam.read_frame()
            times.append(time.time() - t0)
        avg_time = sum(times) / len(times)
        fps = 1.0 / avg_time if avg_time > 0 else 0
        print(f"  -> Capture benchmark: {avg_time * 1000:.1f}ms per frame (~{fps:.1f} FPS)")
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


def run_snapshot(device: str, width: int, height: int, output_path: str, i2c_bus: int, i2c_addr: int) -> None:
    """Captures a single frame, logs attitude, and saves image to disk."""
    import cv2

    imu = IMUReader(bus_id=i2c_bus, address=i2c_addr)
    imu.initialize()
    pitch, roll, _ = imu.read_attitude()
    imu.close()

    cam = CameraDriver(device=device, width=width, height=height)
    cam.open()
    # Warm up camera auto-exposure with 3 frames
    for _ in range(3):
        cam.read_frame()

    ts_ns, frame, jpeg_bytes = cam.read_frame()
    cam.release()

    if frame is not None:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        cv2.imwrite(output_path, frame)
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


def run_preview_server(device: str, width: int, height: int, port: int, i2c_bus: int, i2c_addr: int) -> None:
    """Runs a lightweight diagnostic HTTP server serving live frames to laptop browser."""
    cam = CameraDriver(device=device, width=width, height=height)
    cam.open()
    imu = IMUReader(bus_id=i2c_bus, address=i2c_addr)
    imu.initialize()

    class PreviewHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Suppress excessive HTTP access logs

        def do_GET(self):
            if self.path in ("/", "/preview"):
                pitch, roll, _ = imu.read_attitude()
                html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Pi 3 Camera Diagnostic Preview</title>
    <style>
        body {{ background: #0f172a; color: #f8fafc; font-family: monospace; text-align: center; margin: 20px; }}
        h1 {{ color: #38bdf8; }}
        .hud-box {{ display: inline-block; background: #1e293b; padding: 15px; border-radius: 8px; border: 1px solid #334155; }}
        img {{ max-width: 90vw; height: auto; border: 2px solid #0284c7; border-radius: 4px; }}
        .badge {{ background: #0284c7; color: white; padding: 4px 10px; border-radius: 4px; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>Raspberry Pi 3 — Pcam 5C & IMU Diagnostic Preview</h1>
    <div class="hud-box">
        <p>
            <span class="badge">LIVE SNAPSHOT</span> &nbsp;
            <strong>Pitch:</strong> {pitch:+.2f}° &nbsp;|&nbsp;
            <strong>Roll:</strong> {roll:+.2f}°
        </p>
        <img id="live-img" src="/snapshot.jpg" alt="Feed">
        <p style="color: #94a3b8; font-size: 12px;">Auto-refreshing every 500ms...</p>
    </div>
    <script>
        setInterval(() => {{
            const img = document.getElementById('live-img');
            img.src = '/snapshot.jpg?t=' + Date.now();
        }}, 500);
    </script>
</body>
</html>"""
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))

            elif self.path.startswith("/snapshot.jpg"):
                ts_ns, frame, jpeg_bytes = cam.read_frame()
                if jpeg_bytes:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(jpeg_bytes)))
                    self.end_headers()
                    self.wfile.write(jpeg_bytes)
                else:
                    self.send_response(500)
                    self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()

    server = HTTPServer(("0.0.0.0", port), PreviewHandler)
    logger.info("Diagnostic Preview Server listening on http://0.0.0.0:%d (Press Ctrl+C to stop)", port)
    logger.info("Open http://<pi_ip>:%d/ in your laptop browser to view camera feed.", port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down preview server...")
    finally:
        server.server_close()
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
    cam = CameraDriver(device=device, width=width, height=height, fps=fps)
    if not cam.open():
        logger.error("Could not open camera device %s", device)
        sys.exit(1)

    imu = IMUReader(bus_id=i2c_bus, address=i2c_addr)
    imu.initialize()

    streamer = SocketStreamer(host=host, port=port)
    logger.info("Starting binary streaming loop -> %s:%d (Target FPS: %d)", host, port, fps)

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
            ts_ns, _, jpeg_bytes = cam.read_frame()
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Raspberry Pi 3 Pcam 5C & IMU Capture Agent")
    parser.add_argument(
        "--mode",
        choices=["diag", "snapshot", "test-imu", "preview", "stream"],
        default="stream",
        help="Operating mode (default: stream)",
    )
    parser.add_argument("--config", default="configs/capture_pi.yaml", help="Path to config YAML")
    parser.add_argument("--output", default="data/test_frame.jpg", help="Path to save test image (snapshot mode)")
    parser.add_argument("--host", default=None, help="Target ingest host IP (overrides config)")
    parser.add_argument("--port", type=int, default=None, help="Target ingest port (overrides config)")
    parser.add_argument("--preview-port", type=int, default=8080, help="Port for diagnostic preview server")
    parser.add_argument("--device", default=None, help="Camera device node e.g. /dev/video0")

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

    i2c_bus = imu_cfg.get("i2c_bus", 1)
    i2c_addr = imu_cfg.get("i2c_address", 0x68)

    host = args.host or stream_cfg.get("target_host", "127.0.0.1")
    port = args.port or stream_cfg.get("target_port", 9876)

    logger.info("Selected mode: %s", args.mode)

    if args.mode == "diag":
        run_diag(device=device, width=width, height=height, i2c_bus=i2c_bus, i2c_addr=i2c_addr)
    elif args.mode == "snapshot":
        run_snapshot(
            device=device,
            width=width,
            height=height,
            output_path=args.output,
            i2c_bus=i2c_bus,
            i2c_addr=i2c_addr,
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
        )
    else:
        logger.error("Unknown mode: %s", args.mode)
        sys.exit(1)


if __name__ == "__main__":
    main()
