# pi_capture_native

High-performance C++ replacement for `pi_capture_agent` (Python) — the camera streaming pipeline on Raspberry Pi 3.

## What Changed

| Component | Python (old) | C++ (new) |
|---|---|---|
| Camera capture | `cv2.VideoCapture` (OpenCV) | V4L2 `ioctl` + `mmap` (zero-copy) |
| Image flip | `cv2.flip(frame, -1)` (CPU) | `V4L2_CID_HFLIP` + `V4L2_CID_VFLIP` (sensor hardware) |
| JPEG encode | `cv2.imencode(".jpg")` | `libturbojpeg` + ARM NEON (TJFLAG_FASTDCT) |
| TCP streaming | Python `socket` | POSIX `socket` (MSG_NOSIGNAL) |
| Binary protocol | `struct.pack` | Manual big-endian pack (htobe32/htobe64) |
| IMU (MPU6050) | `smbus2` (Python) | `/dev/i2c-*` + `ioctl(I2C_SLAVE)` |
| Threading | `threading.Thread` + `queue.Queue(1)` | `std::thread` + `std::mutex` + `std::condition_variable` |

## Build on Raspberry Pi

```bash
# 1. Install dependencies
sudo apt update
sudo apt install -y build-essential cmake libturbojpeg0-dev v4l-utils

# 2. Copy source to Pi (or git clone)
scp -r services/pi_capture_native/ pi@<pi_ip>:~/pi_capture_native/

# 3. Build
cd ~/pi_capture_native
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j4

# 4. Verify
./pi_capture_native --help
```

## Cross-Compile from x86 Host

```bash
# Requires arm-linux-gnueabihf toolchain
mkdir build-cross && cd build-cross
cmake .. \
  -DCMAKE_TOOLCHAIN_FILE=/path/to/arm-toolchain.cmake \
  -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
scp pi_capture_native pi@<pi_ip>:~/
```

## Usage

```bash
# Stream to laptop (replaces: python -m pi_capture_agent.cli --mode stream)
./pi_capture_native --mode stream --host 192.168.1.20 --port 9876

# With hardware flip and custom resolution
./pi_capture_native --mode stream --host 192.168.1.20 --port 9876 \
    --rotate-180 --width 640 --height 480 --quality 60

# Test snapshot (replaces: python -m pi_capture_agent.cli --mode snapshot)
./pi_capture_native --mode snapshot --output test.jpg --rotate-180
```

## File Mapping (Python → C++)

| Python module | C++ files | Class/Function |
|---|---|---|
| `camera.py` `find_unicam()` | `v4l2_camera.h/.cpp` | `V4l2Camera::probe_unicam()` |
| `camera.py` `CameraDriver.open()` | `v4l2_camera.h/.cpp` | `V4l2Camera::open()` |
| `camera.py` `CameraDriver.read_frame()` | `v4l2_camera.h/.cpp` | `V4l2Camera::dequeue_frame()` |
| `camera.py` `CameraDriver.encode_to_jpeg()` | `jpeg_encoder.h/.cpp` | `JpegEncoder::encode()` |
| `streamer.py` `SocketStreamer` | `socket_streamer.h/.cpp` | `SocketStreamer` |
| `packer.py` `BinaryFramePacker.pack()` | `frame_packer.h/.cpp` | `pack_frame()` |
| `imu.py` `IMUReader` | `imu_reader.h/.cpp` | `ImuReader` |
| `cli.py` `run_stream()` | `main.cpp` | `run_stream()` |
| `cli.py` `run_snapshot()` | `main.cpp` | `run_snapshot()` |
