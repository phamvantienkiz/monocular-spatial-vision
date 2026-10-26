# pi_capture_native (C++17 Edge Capture & Streaming Service for Raspberry Pi 3)

High-performance C++17 native implementation for Raspberry Pi 3 (Broadcom BCM2837, 4x Cortex-A53) with Digilent Pcam 5C (OmniVision OV5640 MIPI CSI-2) and MPU-6050 IMU.

## Key Architectural Highlights

| Component | Python (`pi_capture_agent`) | C++ Native (`pi_capture_native`) |
| :--- | :--- | :--- |
| **Camera Capture** | `cv2.VideoCapture` (OpenCV BGR copy) | Direct V4L2 `ioctl` + 4x `mmap` DMA buffers (Zero-copy dequeue) |
| **Unicam & FPS Lock** | `media-ctl` subprocess | Automatic `/dev/media*` + `/dev/v4l-subdev*` discovery & `VIDIOC_SUBDEV_S_FRAME_INTERVAL` |
| **VGA Anti-Stripe** | Software resize | Hardware `720x480` capture + instant center-crop to `640x480` (zero MIPI clock drift) |
| **Image Flip** | `cv2.flip()` or `v4l2-ctl` | Direct `V4L2_CID_HFLIP` + `V4L2_CID_VFLIP` ioctl on `/dev/v4l-subdev0` (0% CPU) |
| **Color De-interleave** | CPU `UYVY -> BGR` | ARM NEON SIMD `vld4_u8` + `vst2_u8` (`UYVY -> YUV422P` in ~1.2 ms) |
| **JPEG Compression** | `PyTurboJPEG` / `cv2.imencode` | `tjCompressFromYUV` (`TJSAMP_422`, `TJFLAG_FASTDCT \| TJFLAG_NOREALLOC`, ~7-8 ms) |
| **Exposure & 30FPS Lock**| Auto or CLI `--exposure` | 50Hz Anti-Flicker + `--lock-30fps` (`--exposure 350 --gain 48`) + live `exposure/gain` readout |
| **6 CLI Modes** | `preview`, `stream`, `snapshot`, `diag`, `test-imu`, `test-perf` | Full 1:1 parity (`preview`, `stream`, `snapshot`, `diag`, `test-imu`, `test-perf`) |

---

## 1. Build on Raspberry Pi 3

```bash
cd ~/mobile_robot/monocular-spatial-vision/services/pi_capture_native
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j2
```

Run C++ unit tests:
```bash
ctest --output-on-failure
```

---

## 2. Usage (All 6 CLI Modes)

### Mode 1: Live Browser Preview + Telemetry HUD (`--mode preview`)
```bash
# Native 1280x720 preview:
./pi_capture_native --mode preview --width 1280 --height 720 --rotate-180

# Anti-stripe 640x480 preview:
./pi_capture_native --mode preview --width 640 --height 480 --rotate-180

# Lock shutter for 30 FPS indoor without purple tint / overexposure:
./pi_capture_native --mode preview --width 640 --height 480 --rotate-180 --lock-30fps --exposure 350 --gain 48
```
Open `http://<PI_IP>:8080/` in your Laptop browser to inspect the live MJPEG stream, FPS, Pitch/Roll, and live **Exposure / Gain** register values.

### Mode 2: High-Throughput TCP Binary Stream (`--mode stream`)
```bash
# Stream to Laptop (mock_ingest_server.py or FastAPI Backend) over Wi-Fi or USB Type-C Ethernet Hub:
./pi_capture_native --mode stream --host <LAPTOP_IP> --port 9876 --rotate-180

# Stream at 640x480 with 30 FPS indoor lock:
./pi_capture_native --mode stream --host <LAPTOP_IP> --port 9876 --width 640 --height 480 --rotate-180 --lock-30fps
```

### Mode 3: Hardware & Exposure/Gain Diagnostic (`--mode diag`)
```bash
# Measure actual sensor FPS and read OV5640 exposure & gain registers (15fps vs 30fps check):
./pi_capture_native --mode diag --width 640 --height 480 --fps 30 --rotate-180
```

### Mode 4: Single JPEG Snapshot (`--mode snapshot`)
```bash
./pi_capture_native --mode snapshot --output test.jpg --rotate-180
```

### Mode 5: Real-Time 50Hz IMU Attitude Test (`--mode test-imu`)
```bash
./pi_capture_native --mode test-imu
```

### Mode 6: Hardware Timing Benchmark (`--mode test-perf`)
```bash
./pi_capture_native --mode test-perf --frames 100 --rotate-180
```
