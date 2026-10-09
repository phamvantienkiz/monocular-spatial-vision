"""Command-line interface entrypoint for Raspberry Pi 3 capture agent.

Provides execution modes:
  - snapshot: captures a single test frame and writes to disk with IMU telemetry.
  - preview: starts a lightweight HTTP server serving live MJPEG stream and IMU telemetry.
  - test-imu: continuously prints raw and filtered IMU angles to terminal at 50Hz.
  - stream: runs the continuous streaming loop to the remote ingest server (Laptop/Jetson).
  - check-hardware: diagnostic scan of V4L2 camera nodes and I2C MPU6050 bus.
"""

import argparse
import json
import logging
import math
import os
import signal
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any, Dict, Optional, Tuple

import yaml

from pi_capture_agent.camera import CameraDriver
from pi_capture_agent.imu import IMUReader
from pi_capture_agent.packer import BinaryFramePacker
from pi_capture_agent.streamer import SocketStreamer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pi_capture_agent")


def load_config(config_path: str) -> Dict[str, Any]:
    """Loads configuration YAML file with robust fallback defaults."""
    default_config: Dict[str, Any] = {
        "device": {
            "video_device": "/dev/video0",
            "width": 1280,
            "height": 720,
            "fps": 30,
            "pixel_format": "MJPG",
            "rotate_180": True,
        },
        "imu": {
            "i2c_bus": 1,
            "i2c_address": 0x68,
            "sampling_rate_hz": 50,
        },
        "stream": {
            "target_host": "192.168.1.20",
            "target_port": 9876,
            "reconnect_delay_sec": 2.0,
            "max_reconnect_attempts": -1,
        },
    }

    # Search for config file in current directory, parent dirs, or relative to module root
    search_paths = [
        config_path,
        os.path.join("..", "..", config_path),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", config_path),
    ]
    resolved_path = None
    for p in search_paths:
        if os.path.exists(p):
            resolved_path = p
            break

    if resolved_path:
        try:
            with open(resolved_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    for section, values in loaded.items():
                        if section in default_config and isinstance(values, dict):
                            default_config[section].update(values)
                        else:
                            default_config[section] = values
            logger.info("Loaded configuration from %s", resolved_path)
        except Exception as e:
            logger.warning("Could not load config from %s: %s. Using defaults.", resolved_path, e)
    else:
        logger.info("Config file %s not found. Using defaults.", config_path)

    return default_config



def run_snapshot(config: Dict[str, Any], output_path: str) -> None:
    """Captures a single frame, queries IMU, and saves image to disk."""
    dev_cfg = config["device"]
    imu_cfg = config["imu"]

    logger.info("Initializing camera for single snapshot...")
    cam = CameraDriver(
        device=dev_cfg.get("video_device", "/dev/video0"),
        width=int(dev_cfg.get("width", 1280)),
        height=int(dev_cfg.get("height", 720)),
        fps=int(dev_cfg.get("fps", 30)),
        pixel_format=dev_cfg.get("pixel_format", "MJPG"),
        rotate_180=bool(dev_cfg.get("rotate_180", True)),
    )


    if not cam.open():
        logger.error("Failed to open camera for snapshot.")
        sys.exit(1)

    # Initialize IMU (best-effort)
    imu: Optional[IMUReader] = None
    try:
        imu = IMUReader(
            bus_id=int(imu_cfg.get("i2c_bus", 1)),
            address=int(imu_cfg.get("i2c_address", 0x68)),
        )
        imu.initialize()
    except Exception as e:
        logger.warning("IMU initialization skipped or failed: %s", e)
        imu = None

    try:
        # Discard first 5 frames to let sensor auto-exposure and gain stabilize
        logger.info("Warming up camera sensor (auto-exposure/white-balance settling)...")
        for _ in range(5):
            cam.read_frame(encode_jpeg=False)
            time.sleep(0.05)

        ts_ns, frame, jpeg_bytes = cam.read_frame(encode_jpeg=True, jpeg_quality=90)
        if frame is None or jpeg_bytes is None:
            logger.error("Failed to capture frame.")
            sys.exit(1)

        pitch_deg = 0.0
        roll_deg = 0.0
        accel = (0.0, 0.0, 0.0)
        if imu is not None:
            try:
                pitch_deg, roll_deg, accel = imu.read_attitude()
            except Exception as e:
                logger.warning("Failed to query IMU attitude: %s", e)

        # Ensure target directory exists
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(jpeg_bytes)

        logger.info("================ SNAPSHOT RESULT ================")
        logger.info("Saved snapshot: %s (%d bytes)", output_path, len(jpeg_bytes))
        logger.info("Image Resolution: %dx%d", frame.shape[1], frame.shape[0])
        logger.info("Timestamp: %d ns", ts_ns)
        logger.info(
            "IMU Telemetry: Pitch=%.2f deg, Roll=%.2f deg, Accel=(%.2f, %.2f, %.2f)g",
            pitch_deg,
            roll_deg,
            accel[0],
            accel[1],
            accel[2],
        )
        logger.info("================================================")
    finally:
        cam.release()
        if imu:
            imu.close()


def run_test_imu(config: Dict[str, Any]) -> None:
    """Continuously queries IMU and prints formatted telemetry to terminal."""
    imu_cfg = config["imu"]
    rate_hz = float(imu_cfg.get("sampling_rate_hz", 50))
    interval = 1.0 / max(rate_hz, 1.0)

    logger.info(
        "Starting IMU continuous test (Bus: %d, Addr: 0x%02X, Rate: %.1f Hz)...",
        imu_cfg.get("i2c_bus", 1),
        imu_cfg.get("i2c_address", 0x68),
        rate_hz,
    )

    imu = IMUReader(
        bus_id=int(imu_cfg.get("i2c_bus", 1)),
        address=int(imu_cfg.get("i2c_address", 0x68)),
        alpha_filter=0.98,
        use_filter=True,
    )

    try:
        imu.initialize()
    except Exception as e:
        logger.error("Could not initialize IMU: %s", e)
        sys.exit(1)

    print("\nPress Ctrl+C to exit IMU test loop.\n")
    print(f"{'Time':<12} | {'Ax (g)':<7} {'Ay (g)':<7} {'Az (g)':<7} | {'Pitch (deg)':<12} {'Roll (deg)':<12} | {'Gx (dps)':<7} {'Gy (dps)':<7} {'Gz (dps)':<7}")
    print("-" * 88)

    sample_count = 0
    start_time = time.time()
    try:
        while True:
            t0 = time.time()
            pitch_deg, roll_deg, (ax, ay, az) = imu.read_attitude()
            _, (gx, gy, gz), _ = imu.read_raw_sensors()

            sample_count += 1
            elapsed_str = f"{time.time() - start_time:06.2f}s"
            print(
                f"\r{elapsed_str:<12} | {ax:+06.2f}  {ay:+06.2f}  {az:+06.2f}  | {pitch_deg:+07.2f}      {roll_deg:+07.2f}      | {gx:+06.1f}  {gy:+06.1f}  {gz:+06.1f}",
                end="",
                flush=True,
            )

            dt = time.time() - t0
            sleep_time = interval - dt
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n")
        total_time = time.time() - start_time
        avg_rate = sample_count / total_time if total_time > 0 else 0
        logger.info("IMU test stopped. Total samples: %d in %.2fs (avg %.1f Hz)", sample_count, total_time, avg_rate)
    finally:
        imu.close()


class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def run_preview(config: Dict[str, Any], port: int = 8080) -> None:
    """Spawns lightweight HTTP server providing live MJPEG stream and IMU HUD."""
    dev_cfg = config["device"]
    imu_cfg = config["imu"]

    cam = CameraDriver(
        device=dev_cfg.get("video_device", "/dev/video0"),
        width=int(dev_cfg.get("width", 1280)),
        height=int(dev_cfg.get("height", 720)),
        fps=int(dev_cfg.get("fps", 30)),
        pixel_format=dev_cfg.get("pixel_format", "MJPG"),
        rotate_180=bool(dev_cfg.get("rotate_180", True)),
    )

    if not cam.open():
        logger.error("Failed to open camera for preview server.")
        sys.exit(1)

    imu: Optional[IMUReader] = None
    try:
        imu = IMUReader(
            bus_id=int(imu_cfg.get("i2c_bus", 1)),
            address=int(imu_cfg.get("i2c_address", 0x68)),
        )
        imu.initialize()
    except Exception as e:
        logger.warning("IMU initialization failed or sensor missing: %s", e)
        imu = None

    shared_state = {
        "jpeg": None,
        "telemetry": {
            "pitch_deg": 0.0,
            "roll_deg": 0.0,
            "accel": [0.0, 0.0, 1.0],
            "fps": 0.0,
            "timestamp_ns": 0,
        },
        "running": True,
    }
    state_lock = threading.Lock()

    def capture_worker():
        frame_count = 0
        t_start = time.time()
        while shared_state["running"]:
            ts_ns, _, jpeg_bytes = cam.read_frame(encode_jpeg=True, jpeg_quality=75)
            if jpeg_bytes is not None:
                pitch, roll, accel = (0.0, 0.0, (0.0, 0.0, 0.0))
                if imu is not None:
                    try:
                        pitch, roll, accel = imu.read_attitude()
                    except Exception:
                        pass

                frame_count += 1
                curr_fps = frame_count / max(time.time() - t_start, 0.001)

                with state_lock:
                    shared_state["jpeg"] = jpeg_bytes
                    shared_state["telemetry"] = {
                        "pitch_deg": round(pitch, 2),
                        "roll_deg": round(roll, 2),
                        "accel": [round(a, 2) for a in accel],
                        "fps": round(curr_fps, 1),
                        "timestamp_ns": ts_ns,
                    }
            time.sleep(0.03)

    worker = threading.Thread(target=capture_worker, daemon=True)
    worker.start()

    class PreviewHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            return  # Suppress HTTP request terminal spam

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                html = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Pi 3 Camera & IMU Preview</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { margin: 0; background: #0f172a; color: #f8fafc; font-family: monospace, sans-serif; display: flex; flex-direction: column; align-items: center; padding: 20px; }
    h1 { margin-bottom: 8px; font-size: 20px; color: #38bdf8; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px; margin: 8px 0; width: 90%; max-width: 800px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); }
    img { width: 100%; border-radius: 6px; background: #020617; }
    .hud-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 10px; }
    .hud-stat { background: #0f172a; padding: 10px; border-radius: 6px; border-left: 4px solid #38bdf8; }
    .hud-stat.warn { border-left-color: #f59e0b; }
    .hud-label { font-size: 11px; color: #94a3b8; text-transform: uppercase; }
    .hud-val { font-size: 18px; font-weight: bold; margin-top: 4px; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; background: #22c55e22; color: #22c55e; border: 1px solid #22c55e44; }
  </style>
</head>
<body>
  <h1>Raspberry Pi 3: Pcam 5C & MPU6050 Diagnostic HUD</h1>
  <div class="card">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
      <span><strong>Live Stream (1280x720 MJPEG)</strong></span>
      <span class="badge" id="hud-status">STREAMING</span>
    </div>
    <img src="/stream.mjpg" alt="Live Camera Stream">
  </div>
  <div class="card">
    <strong>IMU Sensor Telemetry</strong>
    <div class="hud-grid">
      <div class="hud-stat" id="stat-pitch"><div class="hud-label">Pitch Angle (theta)</div><div class="hud-val" id="val-pitch">-- deg</div></div>
      <div class="hud-stat" id="stat-roll"><div class="hud-label">Roll Angle (phi)</div><div class="hud-val" id="val-roll">-- deg</div></div>
      <div class="hud-stat"><div class="hud-label">Acceleration [Ax, Ay, Az]</div><div class="hud-val" id="val-accel">--</div></div>
      <div class="hud-stat"><div class="hud-label">Camera FPS</div><div class="hud-val" id="val-fps">--</div></div>
    </div>
  </div>
  <script>
    setInterval(async () => {
      try {
        const res = await fetch('/telemetry');
        const data = await res.json();
        document.getElementById('val-pitch').innerText = `${data.pitch_deg > 0 ? '+' : ''}${data.pitch_deg}°`;
        document.getElementById('val-roll').innerText = `${data.roll_deg > 0 ? '+' : ''}${data.roll_deg}°`;
        document.getElementById('val-accel').innerText = `[${data.accel.join(', ')}]g`;
        document.getElementById('val-fps').innerText = `${data.fps} FPS`;
      } catch (e) {}
    }, 200);
  </script>
</body>
</html>"""
                self.wfile.write(html.encode("utf-8"))

            elif self.path == "/snapshot.jpg":
                with state_lock:
                    jpeg = shared_state["jpeg"]
                if jpeg:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(jpeg)))
                    self.end_headers()
                    self.wfile.write(jpeg)
                else:
                    self.send_error(503, "No frame available yet")

            elif self.path == "/telemetry":
                with state_lock:
                    telem = shared_state["telemetry"]
                data_bytes = json.dumps(telem).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data_bytes)))
                self.end_headers()
                self.wfile.write(data_bytes)

            elif self.path == "/stream.mjpg":
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=--frameboundary")
                self.end_headers()
                try:
                    while shared_state["running"]:
                        with state_lock:
                            jpeg = shared_state["jpeg"]
                        if jpeg:
                            self.wfile.write(b"--frameboundary\r\n")
                            self.wfile.write(b"Content-Type: image/jpeg\r\n")
                            self.wfile.write(f"Content-Length: {len(jpeg)}\r\n\r\n".encode("utf-8"))
                            self.wfile.write(jpeg)
                            self.wfile.write(b"\r\n")
                        time.sleep(0.04)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            else:
                self.send_error(404, "Endpoint Not Found")

    server = _ThreadedHTTPServer(("0.0.0.0", port), PreviewHandler)
    logger.info("================ PREVIEW SERVER STARTED ================")
    logger.info("HTTP Preview running on port %d", port)
    logger.info("Access from developer laptop browser:")
    logger.info("  👉  http://<pi_ip>:%d/              (Interactive Web HUD)", port)
    logger.info("  👉  http://<pi_ip>:%d/snapshot.jpg  (Raw Single JPEG)", port)
    logger.info("  👉  http://<pi_ip>:%d/telemetry     (JSON IMU telemetry)", port)
    logger.info("Press Ctrl+C to terminate preview server.")
    logger.info("========================================================")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down preview server...")
    finally:
        shared_state["running"] = False
        server.server_close()
        cam.release()
        if imu:
            imu.close()


def run_stream(
    config: Dict[str, Any],
    host_override: Optional[str] = None,
    port_override: Optional[int] = None,
) -> None:
    """Continuously acquires camera frames and IMU attitude, packs binary frame, and transmits via TCP."""
    dev_cfg = config["device"]
    imu_cfg = config["imu"]
    stream_cfg = config["stream"]

    target_host = host_override or stream_cfg.get("target_host", "192.168.1.20")
    target_port = port_override or int(stream_cfg.get("target_port", 9876))
    retry_delay = float(stream_cfg.get("reconnect_delay_sec", 2.0))
    target_fps = int(dev_cfg.get("fps", 30))
    frame_interval = 1.0 / max(target_fps, 1)

    width = int(dev_cfg.get("width", 1280))
    height = int(dev_cfg.get("height", 720))

    logger.info("Starting live capture and streaming pipeline:")
    logger.info("  Target Ingest Server: %s:%d", target_host, target_port)
    logger.info("  Video: %dx%d @ %d FPS (%s)", width, height, target_fps, dev_cfg.get("pixel_format", "MJPG"))
    logger.info("  IMU: Bus %d, Addr 0x%02X", imu_cfg.get("i2c_bus", 1), imu_cfg.get("i2c_address", 0x68))

    cam = CameraDriver(
        device=dev_cfg.get("video_device", "/dev/video0"),
        width=width,
        height=height,
        fps=target_fps,
        pixel_format=dev_cfg.get("pixel_format", "MJPG"),
        rotate_180=bool(dev_cfg.get("rotate_180", True)),
    )

    if not cam.open():
        logger.error("Failed to open camera device.")
        sys.exit(1)

    imu: Optional[IMUReader] = None
    try:
        imu = IMUReader(
            bus_id=int(imu_cfg.get("i2c_bus", 1)),
            address=int(imu_cfg.get("i2c_address", 0x68)),
        )
        imu.initialize()
    except Exception as e:
        logger.warning("IMU initialization warning: %s. Continuing with pitch=0.0, roll=0.0.", e)
        imu = None

    streamer = SocketStreamer(host=target_host, port=target_port, retry_delay=retry_delay)
    streamer.connect()

    running = True

    def sig_handler(sig, frame):
        nonlocal running
        logger.info("Interrupt signal received. Stopping streaming loop...")
        running = False

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    frame_id = 0
    frames_sent = 0
    bytes_sent = 0
    t_stats = time.time()

    try:
        while running:
            t0 = time.time()
            ts_ns, _, jpeg_bytes = cam.read_frame(encode_jpeg=True, jpeg_quality=80)

            if jpeg_bytes is not None:
                pitch_deg, roll_deg = 0.0, 0.0
                if imu is not None:
                    try:
                        pitch_deg, roll_deg, _ = imu.read_attitude()
                    except Exception:
                        pass

                packet = BinaryFramePacker.pack(
                    frame_id=frame_id,
                    timestamp_ns=ts_ns,
                    pitch_deg=pitch_deg,
                    roll_deg=roll_deg,
                    image_bytes=jpeg_bytes,
                    width=width,
                    height=height,
                )

                success = streamer.send_frame_packet(packet)
                frame_id += 1
                if success:
                    frames_sent += 1
                    bytes_sent += len(packet)

            # Periodic statistics report every second
            now = time.time()
            elapsed_stats = now - t_stats
            if elapsed_stats >= 1.0:
                fps = frames_sent / elapsed_stats
                kb_rate = (bytes_sent / 1024.0) / elapsed_stats
                conn_status = "CONNECTED" if streamer.is_connected else "RECONNECTING"
                logger.info(
                    "[%s] Frame #%d | Rate: %.1f FPS (%.1f KB/s) | Pitch: %+.2f° | Roll: %+.2f°",
                    conn_status,
                    frame_id,
                    fps,
                    kb_rate,
                    pitch_deg if 'pitch_deg' in locals() else 0.0,
                    roll_deg if 'roll_deg' in locals() else 0.0,
                )
                frames_sent = 0
                bytes_sent = 0
                t_stats = now

            # Throttle to target FPS
            dt = time.time() - t0
            sleep_time = frame_interval - dt
            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        logger.info("Cleaning up streaming resources...")
        streamer.close()
        cam.release()
        if imu:
            imu.close()
        logger.info("Streaming session closed cleanly.")


def run_check_hardware(config: Dict[str, Any]) -> None:
    """Performs non-destructive hardware diagnostic scan of Camera and IMU on Raspberry Pi."""
    print("=" * 60)
    print("      Raspberry Pi 3 Hardware Diagnostic Sanity Check")
    print("=" * 60)

    # 1. Check I2C / MPU-6050
    print("\n[1/2] Checking I2C Bus & MPU6050 Sensor...")
    imu_cfg = config.get("imu", {})
    bus_id = int(imu_cfg.get("i2c_bus", 1))
    target_addr = int(imu_cfg.get("i2c_address", 0x68))

    i2c_dev = f"/dev/i2c-{bus_id}"
    if not os.path.exists(i2c_dev):
        print(f"  ❌ I2C device node {i2c_dev} does not exist.")
        print("     Resolution: Run 'sudo raspi-config nonint do_i2c 0' and add 'dtparam=i2c_arm=on' to config.txt.")
    else:
        print(f"  ✓ I2C device node {i2c_dev} exists.")
        try:
            import smbus2

            bus = smbus2.SMBus(bus_id)
            try:
                who_am_i = bus.read_byte_data(target_addr, 0x75)
                print(f"  ✓ MPU6050 responded at address 0x{target_addr:02X} (WHO_AM_I = 0x{who_am_i:02X})")
            except Exception as e:
                print(f"  ❌ Failed to communicate with 0x{target_addr:02X}: {e}")
                print("     Check wiring: Pin 1 (3.3V), Pin 6 (GND), Pin 3 (SDA), Pin 5 (SCL).")
                print("     Try scanning with: i2cdetect -y 1")
            finally:
                bus.close()
        except ImportError:
            print("  ⚠️ smbus2 python package is not installed (pip install smbus2).")

    # 2. Check V4L2 Camera / OV5640
    print("\n[2/2] Checking V4L2 Camera Nodes & Pcam 5C...")
    dev_cfg = config.get("device", {})
    cam_dev = dev_cfg.get("video_device", "/dev/video0")

    if not os.path.exists(cam_dev):
        print(f"  ❌ Video device {cam_dev} does not exist.")
        print("     Resolution: Ensure 15-pin FFC ribbon is properly seated in CSI port.")
        print("     Ensure 'dtoverlay=ov5640' is added to /boot/firmware/config.txt or /boot/config.txt.")
        print("     Run 'v4l2-ctl --list-devices' or 'dmesg | grep -i ov5640'.")
    else:
        print(f"  ✓ Video device node {cam_dev} exists.")
        try:
            import cv2

            cap = cv2.VideoCapture(cam_dev, cv2.CAP_V4L2) if hasattr(cv2, "CAP_V4L2") else cv2.VideoCapture(cam_dev)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"  ✓ Camera successfully captured test frame: {frame.shape[1]}x{frame.shape[0]} BGR")
                else:
                    print("  ⚠️ Camera opened, but failed to capture frame buffer.")
                cap.release()
            else:
                print(f"  ❌ OpenCV could not open {cam_dev}.")
        except ImportError:
            print("  ⚠️ opencv-python-headless is not installed (pip install opencv-python-headless).")

    print("\n" + "=" * 60)
    print("Diagnostic complete.")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Raspberry Pi 3 Pcam 5C & IMU Capture Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 1. Sanity check camera and IMU connection:
  python -m pi_capture_agent.cli --mode check-hardware

  # 2. Capture a test frame and print IMU attitude:
  python -m pi_capture_agent.cli --mode snapshot --output data/test_frame.jpg

  # 3. Test IMU angles in real-time in terminal:
  python -m pi_capture_agent.cli --mode test-imu

  # 4. Start HTTP preview server (view in laptop browser at http://<pi_ip>:8080):
  python -m pi_capture_agent.cli --mode preview --preview-port 8080

  # 5. Continuous streaming to laptop / Jetson:
  python -m pi_capture_agent.cli --mode stream --host 192.168.1.100 --port 9876
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["snapshot", "preview", "test-imu", "stream", "check-hardware"],
        default="stream",
        help="Operating mode (default: stream)",
    )
    parser.add_argument("--config", default="configs/capture_pi.yaml", help="Path to config YAML")
    parser.add_argument("--output", default="data/test_frame.jpg", help="Path to save test snapshot image")
    parser.add_argument("--host", default=None, help="Target ingest host IP (overrides config)")
    parser.add_argument("--port", type=int, default=None, help="Target ingest port (overrides config)")
    parser.add_argument("--device", default=None, help="Camera device path (e.g. /dev/video0, overrides config)")
    parser.add_argument("--preview-port", type=int, default=8080, help="HTTP preview server port (default: 8080)")
    parser.add_argument("--rotate-180", dest="rotate_180", action="store_true", default=None, help="Rotate image 180 degrees")
    parser.add_argument("--no-rotate", dest="rotate_180", action="store_false", help="Do not rotate image")

    args = parser.parse_args()
    config = load_config(args.config)

    # CLI parameter overrides
    if args.device:
        config["device"]["video_device"] = args.device
    if args.rotate_180 is not None:
        config["device"]["rotate_180"] = args.rotate_180


    logger.info("Selected mode: %s", args.mode)

    if args.mode == "snapshot":
        run_snapshot(config, args.output)
    elif args.mode == "preview":
        run_preview(config, port=args.preview_port)
    elif args.mode == "test-imu":
        run_test_imu(config)
    elif args.mode == "stream":
        run_stream(config, host_override=args.host, port_override=args.port)
    elif args.mode == "check-hardware":
        run_check_hardware(config)
    else:
        logger.error("Unknown mode: %s", args.mode)
        sys.exit(1)


if __name__ == "__main__":
    main()

