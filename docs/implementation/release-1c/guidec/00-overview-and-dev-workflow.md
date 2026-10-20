# Release 1c: Tổng Quan Quy Trình Phát Triển Thực Chiến C/C++

> **Layer:** Implementation Layer (`docs/implementation/release-1c/guidec/00-overview-and-dev-workflow.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Status:** Approved Baseline — Practical Engineering Standard  

---

## 1. Triết Lý Phát Triển: Đơn Giản Hóa, Khóa Chuẩn 720p & Thực Dụng Tối Đa

Khi phát triển phần mềm C/C++ cho hệ thống nhúng Linux như Raspberry Pi 3 từ môi trường máy tính Windows, kỹ sư thường bị phân tâm bởi các mô hình phức tạp và các tác vụ tiền xử lý không cần thiết:
- **Biên dịch chéo (Cross-compilation) từ Windows:** Đòi hỏi cấu hình sysroot, MinGW/Clang ARM, glibc version matching cực kỳ phức tạp và dễ phát sinh lỗi ABI bí ẩn khi chạy trên Pi.
- **Thao tác Resize/Downscale cồng kềnh trên Pi 3:** Lịch sử phiên bản Python đã chứng minh việc cố tình co nhỏ ảnh trên Pi 3 ngốn CPU, gây rớt frame và phát sinh lỗi mất đồng bộ phần cứng CSI-2. Trong Release 1c, **Pi 3 khóa cứng độ phân giải chuẩn phần cứng $1280 \times 720 @ 30\text{ FPS}$** và đẩy toàn bộ việc resize sang GPU của Jetson AGX Xavier.

**Quy trình chuẩn hóa thực chiến cho Release 1c:**
1. **Viết mã nguồn (Editing):** Thực hiện hoàn toàn trên **VS Code** tại máy tính Windows trong workspace Git cục bộ.
2. **Quản lý phiên bản (VCS):** `git commit` và `git push` lên GitHub/GitLab.
3. **Môi trường thực thi & Biên dịch (Build Target):** Mở terminal SSH vào **Raspberry Pi 3**, `git pull` và **biên dịch Native trực tiếp trên Pi 3**.
4. **Quản lý phụ thuộc (Dependency Management):** Dùng chính **`uv` + `.venv`** để bọc công cụ **`Conan 2.0`**, lưu cache tại `.conan/` nội bộ trong repo, đảm bảo không có bất kỳ thư viện C++ nào bị cài vào hệ thống Linux toàn cục.

```mermaid
flowchart LR
    subgraph WIN_DEV ["1. Trạm Lập Trình (Windows Laptop)"]
        VSCODE["Visual Studio Code (IDE Chính)"]
        GIT_LOCAL["Git Workspace Cục Bộ"]
        BROWSER["Trình Duyệt Web (Xem HUD Laptop)"]
        VSCODE -->|Commit code C++| GIT_LOCAL
    end

    subgraph GIT_HUB ["2. Trung Gian Đồng Bộ (VCS)"]
        REPO["Git Repository (GitHub / Local Git Server)"]
    end

    subgraph PI3_NATIVE ["3. Máy Tính Nhúng Robot (Raspberry Pi 3)"]
        VENV["Python .venv (Tạo bởi uv)"]
        CONAN["Conan 2.0 CLI (uv pip install conan)"]
        CACHE[".conan/ (export CONAN_HOME=$PWD/.conan)"]
        BUILD["build/ (CMake Toolchain)"]
        APP["Binary C++ Native: pi_capture_agent_cpp (Khóa 720p)"]
        
        VENV --> CONAN
        CONAN -->|Tải gói vào| CACHE
        CONAN -->|Sinh toolchain vào| BUILD
        BUILD -->|cmake --build build -j2| APP
    end

    subgraph BACKEND_JETSON ["4. Máy Tính AI / Laptop Tiếp Nhận"]
        INGEST["TCP Socket Ingest Server (:9876)"]
        CUDA_RESIZE["CUDA / TensorRT Letterbox (GPU VRAM < 0.2ms)"]
        YOLO["YOLOv8-seg + IPM 3D Solver"]
        
        INGEST --> CUDA_RESIZE --> YOLO
    end

    GIT_LOCAL ==>|git push| REPO
    REPO ==>|git pull| PI3_NATIVE
    
    APP ==>|Stream nhị phân TCP 9876 (720p Native)| INGEST
    YOLO -.->|Telemetry & MJPEG Live| BROWSER
```

---

## 2. Chi Tiết Các Bước Trong Vòng Lặp Phát Triển (Dev Loop)

### Bước 1: Viết Code & Kiểm Soát Kiểu Trên Windows (VS Code)
- Mở thư mục dự án `monocular-spatial-vision` trên VS Code (Windows).
- Chỉnh sửa code trong `services/pi_capture_agent_cpp/` hoặc cấu hình `configs/capture_pi.yaml`.
- Thực hiện commit:
  ```bash
  git add services/pi_capture_agent_cpp/
  git commit -m "feat(US-C01): lock 1280x720 native capture pipeline"
  git push origin main
  ```

---

### Bước 2: Đồng Bộ & Build Native Trên Raspberry Pi 3
- Mở terminal kết nối SSH vào Pi 3:
  ```bash
  ssh pi@192.168.1.10
  cd ~/workspaces/monocular-spatial-vision
  git pull origin main
  ```
- Kích hoạt môi trường ảo và biên dịch:
  ```bash
  # 1. Kích hoạt môi trường uv
  source .venv/bin/activate

  # 2. Đặt cache conan cục bộ trong repo
  export CONAN_HOME="$(pwd)/.conan"

  # 3. Kéo thư viện nếu có thay đổi trong conanfile.txt
  uv run conan install . --build=missing -s build_type=Release

  # 4. Biên dịch bằng CMake (Giới hạn tối đa 2 luồng -j2)
  cmake --build build -j2
  ```

---

### Bước 3: Chạy & Giám Sát Hiệu Năng Tại Chỗ
- Chạy thử nghiệm chế độ benchmark 100 frames 720p:
  ```bash
  ./build/bin/pi_capture_agent_cpp --mode test-perf --frames 100
  ```
  *Kỳ vọng đầu ra terminal:*
  ```text
  [INFO] V4L2 Device /dev/video0 opened: 1280x720 @ 30 FPS, fmt=UYVY
  [INFO] Hardware Vertical Flip: ACTIVE (Sensor OV5640 silicon)
  [INFO] Zero-Resize Policy: ACTIVE (Native 720p locked, resize offloaded to GPU)
  [INFO] TurboJPEG ARM NEON SIMD Encoder initialized (Quality: 70)
  Avg Grab Time:   2.14 ms
  Avg Encode Time: 8.42 ms
  Cycle Latency:   10.56 ms ( 29.8 FPS )
  Avg Payload:     52.3 KB
  CPU Usage:       18.4%
  RSS Memory:      24.6 MB
  ```
- Khởi động chế độ stream chính thức đẩy gói tin 720p sang máy nhận:
  ```bash
  ./build/bin/pi_capture_agent_cpp --mode stream --host 192.168.1.20 --port 9876
  ```
