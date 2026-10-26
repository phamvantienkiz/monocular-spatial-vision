# Giải Pháp 4: Khóa Cứng 720p Gốc Cho Luồng Stream & Đẩy Tác Vụ Letterbox Sang GPU Jetson

> **Layer:** Implementation Layer (`docs/implementation/release-1c/solutionsc/04-zero-resize-edge-and-gpu-offload.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Target Sensor:** Digilent Pcam 5C (OmniVision OV5640 5MP MIPI CSI-2)  
> **Target Compute:** Raspberry Pi 3 (Native 720p Stream + NEON Preview) & Jetson AGX Xavier (CUDA GPU Letterbox)  
> **Status:** Approved Baseline (Audit-Remediated)  

---

## 1. Bản Chất Phần Cứng Của Pcam 5C (OmniVision OV5640)

### Sự Thật Kỹ Thuật Tầng Phần Cứng (Hardware Reality):
1. **Chế độ 16:9 gốc ổn định nhất của OV5640 trên bộ thu `bcm2835-unicam`:**
   - Cảm biến OV5640 giao tiếp qua 2 lane MIPI CSI-2 với bộ tạo xung nội vi (Internal PLL).
   - Điểm làm việc (Operating Sweet Spot) ổn định nhất của mạch silicon OV5640 ở tỷ lệ chuẩn 16:9 là **`1280 x 720 @ 30 FPS`** với định dạng bus **`UYVY8_1X16`** (`V4L2_PIX_FMT_UYVY`).
2. **Tại sao không cấu hình phần cứng cảm biến xuất `640x360`?**
   - Trong lịch sử thực nghiệm ([`services/pi_capture_agent/pi_capture_agent/camera.py`](file:///E:/UIT/monocular-spatial-vision/services/pi_capture_agent/pi_capture_agent/camera.py)), việc ép `media-ctl` cấu hình pad cảm biến thành `640x360` gây sai lệch tần số PLL của OV5640, dẫn đến mất đồng bộ CSI-2 (CSI Desync).
3. **Tại sao không dùng chế độ `640x480`?**
   - `640x480` là tỷ lệ **4:3 (VGA)** làm hẹp trường nhìn ngang (Horizontal FOV) và phá vỡ ma trận nội tham số $K$ đã hiệu chuẩn ở tỷ lệ 16:9 cho thuật toán Inverse Perspective Mapping (IPM).

---

## 2. Phân Tách Rạch Ròi Giữa Chế Độ `--mode stream` Và `--mode preview`

Trong phiên bản Python cũ, việc gọi `cv2.resize()` bằng phần mềm trên mọi khung hình trước khi nén làm tiêu tốn CPU vô ích. Trong Release 1c (C++), chúng ta áp dụng chính sách phân tách thông minh:

```mermaid
flowchart LR
    subgraph PI3 ["Raspberry Pi 3 (C++17 Edge Capture)"]
        OV["OV5640 Hardware<br/>1280x720 @ 30 FPS"] -->|"V4L2 MMAP"| NEON["ARM NEON vld2q_u8"]
        NEON -->|"Chế độ --mode stream<br/>(Zero-Resize: 1280x720 gốc)"| ENC_720["tjCompressFromYUV<br/>(1280x720, Q=70)"]
        NEON -.->|"Chế độ --mode preview<br/>(NEON 2x2 Decimation: 640x360)"| ENC_360["tjCompressFromYUV<br/>(640x360, Q=65)"]
    end

    subgraph TARGETS ["Thiết Bị Tiếp Nhận (Wi-Fi & Ethernet)"]
        ENC_720 ==>|"Ethernet (Jetson / Laptop Hub Type-C)<br/>hoặc Wi-Fi (Laptop)"| INGEST["TCP Ingest (:9876)<br/>+ GPU CUDA Letterbox (< 0.2ms)"]
        ENC_360 -.->|"Wi-Fi hoặc Ethernet (Hub Type-C)"| BROWSER["Laptop Web Browser<br/>(http://<PI_IP>:8080/preview)"]
    end
```

### 2.1. Ở Chế Độ `--mode stream` (TCP Binary `:9876` — Zero-Resize On Edge)
- **Trên Raspberry Pi 3:** Khóa cứng độ phân giải gốc **`1280 x 720 @ 30 FPS`**, không thực hiện bất kỳ phép co giãn ảnh nào ($\mathbf{0.00\text{ ms}}$ chi phí resize). Toàn bộ chi tiết điểm tiếp xúc mặt đất ($v_{bottom}$) của vật cản ở xa được bảo toàn nguyên vẹn.
- **Trên Jetson AGX Xavier / Laptop GPU:** Tác vụ chuyển đổi khung hình $1280 \times 720$ sang $640 \times 640$ Letterbox cho mạng YOLOv8-seg được thực hiện trực tiếp trên GPU trong **$< 0.2\text{ ms}$**, và tọa độ Bounding Box được quy chiếu ngược về hệ quy chiếu $1280 \times 720$ để tính khoảng cách 3D IPM chính xác tuyệt đối.

### 2.2. Ở Chế Độ `--mode preview` (HTTP MJPEG `:8080` — Tối Ưu Cho Trình Duyệt Qua Wi-Fi)
- Khi kỹ sư sử dụng `--mode preview` để xem trực tiếp trên trình duyệt Laptop qua Wi-Fi, hàm tách kênh NEON hỗ trợ lấy mẫu giảm chiều `2x2` (`1280x720 -> 640x360`) ngay trong lúc đọc thanh ghi mà chỉ mất `~0.6 ms`, giúp luồng MJPEG trên trình duyệt Web cực nhẹ ($\approx 4.5\text{ Mbps}$) và mượt mà ở $30\text{ FPS}$.

---

## 3. Lợi Ích Vượt Trội Cho Toàn Hệ Thống Robot

| Tiêu chí đánh giá | Ép Pi 3 `cv2.resize` (Python cũ) | Kiến trúc Release 1c (C++ Native) | Lợi thế đạt được |
| :--- | :---: | :---: | :--- |
| **Chi phí Resize trong `--mode stream`** | Tốn $5 - 15\text{ms}$/frame trên CPU | **$0.0\text{ms}$ (Zero-Resize)** | Tiết kiệm $100\%$ chu kỳ CPU trên Pi 3 |
| **Độ ổn định xung nhịp cảm biến OV5640** | Dễ lỗi CSI desync nếu đổi mode | **Khóa cứng `1280x720@30` ổn định 100%** | PLL OV5640 luôn chạy ở điểm ngọt phần cứng |
| **Độ chính xác đo khoảng cách 3D IPM** | Giảm do mất chi tiết cạnh đáy | **Ảnh 720p nguyên bản sắc nét** | Sai số khoảng cách mét giảm tối đa |
| **Sự tiện lợi khi test qua Wi-Fi / Ethernet** | Có `--mode preview` & `stream` | **Giữ nguyên 100% cả `preview` & `stream`** | Linh hoạt tuyệt đối trên cả Laptop và Jetson |
