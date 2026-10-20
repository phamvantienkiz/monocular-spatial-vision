# Technical Design — Release 1c Pure C/C++ Native Pipeline

> **Layer:** Implementation Layer (`docs/implementation/release-1c/technical-design.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Status:** Approved Baseline  

---

## 1. Multi-threaded Architecture & Concurrency Model

Khác biệt cốt lõi giữa phiên bản C++ và phiên bản Python là khả năng kiểm soát luồng phần cứng ở mức vi xử lý, không bị khóa toàn cục GIL, **khóa cứng khung hình gốc $1280 \times 720$** và loại bỏ hoàn toàn chi phí bản sao bộ nhớ (Zero-copy memory model).

Tiến trình C++ trên Raspberry Pi 3 được thiết kế theo mô hình **4 luồng chuyên biệt độc lập (4 Dedicated Threads)** tương ứng với 4 nhân Cortex-A53:

```mermaid
flowchart TD
    subgraph HARDWARE ["Tầng Phần Cứng (Hardware Layer)"]
        OV["OmniVision OV5640<br/>(MIPI CSI-2 2-lane, Native 1280x720)"]
        MPU["IMU MPU6050<br/>(I2C-1 @ 400kHz Fast Mode)"]
    end

    subgraph DRIVERS ["Tầng Nhân Hệ Điều Hành (Kernel Drivers)"]
        V4L2_DEV["/dev/video0 (V4L2 Kernel Subsystem)<br/>4x MMAP Ring Buffers (1280x720 UYVY)"]
        I2C_DEV["/dev/i2c-1 (Linux I2C Subsystem)"]
    end

    subgraph THREADS ["Tiến Trình C++ Thuần Túy Trên Pi 3"]
        TH_CAP["1. Capture Thread<br/>(VIDIOC_DQBUF -> Zero-Copy Pointer)"]
        TH_IMU["2. IMU Telemetry Thread<br/>(50Hz High-Resolution Timer Loop)"]
        
        QUEUE_RAW["Thread-Safe Raw Queue<br/>(Capacity = 2 frames, Drop-Stale)"]
        
        TH_ENC["3. Encode Worker Thread<br/>(TurboJPEG 720p C API + ARM NEON SIMD)"]
        
        QUEUE_TX["Thread-Safe TX Queue<br/>(Capacity = 1 frame, Latest Always)"]
        
        TH_STREAM["4. POSIX Streamer Thread<br/>(TCP Socket, TCP_NODELAY, Auto-Reconnect)"]
    end

    subgraph JETSON ["Tầng Tính Toán AI (Jetson AGX Xavier)"]
        NET_STREAM["Socket Stream: 40B Header + 720p JPEG"]
        GPU_RESIZE["TensorRT / CUDA Letterbox (GPU VRAM)<br/>(1280x720 -> 640x640 trong < 0.2ms)"]
        YOLO["YOLOv8-seg Inference"]
    end

    OV --> V4L2_DEV
    MPU --> I2C_DEV
    
    V4L2_DEV -->|mmap memory pointer| TH_CAP
    I2C_DEV -->|ioctl 14 bytes read| TH_IMU
    
    TH_CAP --> QUEUE_RAW
    QUEUE_RAW --> TH_ENC
    
    TH_IMU -.->|Atomic pitch & roll| TH_ENC
    TH_ENC -->|Packed Binary Packet 720p| QUEUE_TX
    
    QUEUE_TX --> TH_STREAM
    TH_STREAM --> NET_STREAM
    NET_STREAM --> GPU_RESIZE
    GPU_RESIZE --> YOLO
```

---

## 2. Chu Trình Xử Lý Khung Hình (Sequence Diagram)

```mermaid
sequenceDiagram
    autonumber
    participant KERNEL_V4L2 as Kernel V4L2 (/dev/video0)
    participant CAP_TH as Thread 1: Capture (Pi 3)
    participant IMU_TH as Thread 2: IMU (Pi 3)
    participant ENC_TH as Thread 3: Encode 720p (Pi 3)
    participant TX_TH as Thread 4: Streamer (Pi 3)
    participant JET_GPU as Jetson AGX Xavier (CUDA GPU)

    Note over CAP_TH,KERNEL_V4L2: Khởi tạo: 4 buffers MMAP 1280x720 sẵn sàng
    loop Chu kỳ mỗi 33.3ms (30 FPS)
        CAP_TH->>KERNEL_V4L2: ioctl(VIDIOC_DQBUF) - Lấy frame 720p từ DMA
        KERNEL_V4L2-->>CAP_TH: Trả về index buffer (con trỏ mmap thô UYVY)
        CAP_TH->>ENC_TH: Chuyển giao con trỏ buffer (Zero-copy, Zero-resize)
        
        IMU_TH->>IMU_TH: Đọc mẫu I2C 50Hz, cập nhật atomic {pitch, roll}
        
        activate ENC_TH
        ENC_TH->>ENC_TH: tjCompress2() 720p với ARM NEON SIMD (7 - 9ms)
        ENC_TH->>ENC_TH: Đóng gói PackedFrameHeader 40B (w=1280, h=720)
        ENC_TH->>CAP_TH: Báo hoàn tất nén
        deactivate ENC_TH
        
        CAP_TH->>KERNEL_V4L2: ioctl(VIDIOC_QBUF) - Trả buffer lại cho camera DMA
        
        ENC_TH->>TX_TH: Đẩy gói tin vào hàng đợi truyền dẫn (Ghi đè nếu bận)
        
        TX_TH->>JET_GPU: send() Header 40B + send() JPEG payload 720p qua TCP
        activate JET_GPU
        JET_GPU->>JET_GPU: Giải mã JPEG và CUDA Letterbox sang 640x640 (< 0.2ms)
        JET_GPU->>JET_GPU: Suy luận TensorRT YOLOv8-seg
        deactivate JET_GPU
    end
```

---

## 3. Mô Hình Bộ Nhớ Zero-Copy & Triệt Tiêu Chi Phí Resize

Nhằm tối ưu hóa tài nguyên trên RAM $1\text{GB}$ của Raspberry Pi 3:
1. **Không sao chép bộ đệm camera:** Dữ liệu hình ảnh từ cảm biến OV5640 được phần cứng DMA ghi trực tiếp vào 4 vùng nhớ kernel (`v4l2_buffer`) tại kích thước chuẩn $1280 \times 720 \times 2\text{ bytes} \approx 1.84\text{MB}$. Khi nén ảnh, con trỏ vùng nhớ `mmap_buffers[i]` được truyền thẳng vào hàm `tjCompress2()` của `libjpeg-turbo`.
2. **Loại bỏ 100% chi phí Resize trên Pi 3:** Tuyệt đối không gọi bất kỳ hàm nội suy co nhỏ ảnh nào. Toàn bộ chu kỳ CPU của Pi 3 chỉ dành cho nén SIMD và gửi mạng.
3. **Bộ nhớ nén tái sử dụng (Pre-allocated JPEG Buffer):** Vùng nhớ chứa kết quả JPEG nén được cấp phát trước một lần duy nhất lúc khởi động (`max_jpeg_size = tjBufSize(1280, 720, TJSAMP_422)` $\approx 1.3\text{MB}$). Không có thao tác `malloc()` hay `free()` nào diễn ra trong vòng lặp chính.
4. **Cơ chế thả trôi khung hình (Drop-Stale Policy):** Khi mạng bị nghẽn, hàng đợi truyền dẫn chỉ giữ dung lượng tối đa 1 khung hình. Khung hình mới nén xong sẽ ghi đè trực tiếp lên khung hình cũ nếu khung hình cũ chưa kịp gửi, đảm bảo độ trễ hình ảnh tới đích luôn $< 20\text{ms}$.

---

## 4. Đặc Tả Struct Nhị Phân & Endianness (40 Bytes)

Cấu trúc Binary Header 40 bytes được định nghĩa chặt chẽ bằng ngôn ngữ C để tương thích $100\%$ với socket server trên Jetson AGX Xavier:

```cpp
#pragma pack(push, 1)
struct PackedFrameHeader {
    uint16_t magic;         // 0x5043 ('PC') - Big-Endian
    uint16_t version;       // 1 - Big-Endian
    uint32_t frame_id;      // Số thứ tự khung hình tăng dần - Big-Endian
    uint64_t timestamp_ns;  // Thời gian chụp (Unix epoch nanoseconds) - Big-Endian
    float    pitch_deg;     // Góc nghiêng trục pitch (độ) - IEEE 754 Big-Endian
    float    roll_deg;      // Góc nghiêng trục roll (độ) - IEEE 754 Big-Endian
    uint32_t payload_len;   // Kích thước mảng bytes JPEG 720p - Big-Endian
    uint32_t width;         // Cố định: 1280 - Big-Endian
    uint32_t height;        // Cố định: 720 - Big-Endian
    uint32_t reserved;      // Dự phòng căn lề: 0x00000000 - Big-Endian
};
#pragma pack(pop)
static_assert(sizeof(PackedFrameHeader) == 40, "Header size must be strictly 40 bytes!");
```

Mọi trường số nguyên và số thực dấu phẩy động đều được chuyển đổi sang chuẩn mạng (Network Byte Order - Big-Endian) thông qua `htons()`, `htonl()`, `htobe64()`.

---

## 5. Kiến Trúc Quản Lý Gói & Toolchain (Conan 2.0 + CMake)

Để đảm bảo nguyên tắc bất biến **Zero System Pollution**, toàn bộ cây phụ thuộc C++ được quản lý theo mô hình phân tầng:

```mermaid
flowchart LR
    subgraph PYTHON_ISOLATION ["1. Tầng Cô Lập Môi Trường (Workspace Root)"]
        UV[".venv (Tạo bởi uv)"]
        CONAN_CLI["Conan 2.0 CLI (uv pip install conan)"]
        UV --> CONAN_CLI
    end

    subgraph REPO_CACHE ["2. Tầng Cache Cục Bộ (In-Workspace Cache)"]
        CONAN_HOME[".conan/ (export CONAN_HOME=$PWD/.conan)<br/>Tất cả cache, recipe và binaries đã build"]
    end

    subgraph CMAKE_BUILD ["3. Tầng Biên Dịch Dự Án (Build Artifacts)"]
        BUILD_DIR["build/<br/>generators/conan_toolchain.cmake<br/>bin/pi_capture_agent_cpp"]
    end

    CONAN_CLI -->|Quản lý cache tại| CONAN_HOME
    CONAN_CLI -->|Sinh Toolchain vào| BUILD_DIR
    BUILD_DIR -->|Biên dịch an toàn với -j2| BINARY["pi_capture_agent_cpp (Native ELF ARMv8 720p)"]
```
