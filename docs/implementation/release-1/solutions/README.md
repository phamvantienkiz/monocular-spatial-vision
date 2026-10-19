# Danh Mục Giải Pháp Tối Ưu Hóa Hiệu Năng Raspberry Pi 3 (Capture Agent Optimization)

> **Layer:** Implementation Layer (`docs/implementation/release-1/solutions/README.md`)  
> **Release:** Release 1 (Phase 1 Sandbox)  
> **Target Hardware:** Raspberry Pi 3 Model B+ (Broadcom BCM2837B0, 4x Cortex-A53 @ 1.4 GHz, VideoCore IV VPU)  
> **Mục tiêu:** Nâng tốc độ khung hình từ 12–15 FPS lên 25–30 FPS ổn định, giảm tải CPU tiêu thụ từ 100% xuống dưới 30%, triệt tiêu hiện tượng trễ khung hình (delay).

---

## 1. Bối Cảnh & Phân Tích Điểm Nghẽn

Trong quá trình thực nghiệm thực địa với camera Digilent Pcam 5C (OmniVision OV5640) và cảm biến IMU MPU6050 trên Raspberry Pi 3, hệ thống gặp hiện tượng:
- Tốc độ khung hình bị chặn cứng ở mức **12 – 15 FPS**.
- **1 nhân CPU bị ép chạy 100%** công suất.
- Hình ảnh truyền qua mạng Wi-Fi bị **trễ (delay) từ vài trăm ms đến vài giây**.

Qua phân tích mã nguồn tại [`services/pi_capture_agent/`](file:///E:/UIT/monocular-spatial-vision/services/pi_capture_agent/), nguyên nhân cốt lõi không nằm ở phần cứng camera hay I2C IMU, mà nằm ở **3 tác vụ tiền xử lý ảnh bằng CPU phần mềm đơn luồng**:
1. Phép lật ma trận ảnh [`cv2.flip(frame, 0)`](file:///E:/UIT/monocular-spatial-vision/services/pi_capture_agent/pi_capture_agent/camera.py#L220) ngốn **8 – 15ms** CPU cho mỗi khung hình 720p.
2. Thuật toán nén ảnh JPEG phần mềm mặc định [`cv2.imencode()`](file:///E:/UIT/monocular-spatial-vision/services/pi_capture_agent/pi_capture_agent/camera.py#L257) ngốn **45 – 65ms** CPU cho mỗi khung hình 720p.
3. Việc nén mất 65ms khiến vòng lặp chỉ đạt tối đa $\approx 15\text{ FPS}$, tạo ra sự chênh lệch nhịp truyền dẫn khiến bộ đệm socket TCP bị dồn ứ (bufferbloat) trên sóng Wi-Fi.

---

## 2. Bản Đồ 3 Tầng Giải Pháp Tối Ưu (3-Tier Optimization Architecture)

Để giải quyết triệt để vấn đề mà không làm xáo trộn kiến trúc hệ thống, 3 giải pháp được thiết kế theo cấu trúc phân tầng lũy tiến:

```mermaid
flowchart TD
    subgraph SENSOR["Tầng Cảm Biến (Sensor Level)"]
        SOL1["Giải Pháp 1: Lật ảnh phần cứng trên chip OV5640<br/>(Hardware Vertical Flip qua V4L2 Control)"]
    end

    subgraph CPU_SIMD["Tầng Vi Xử Lý & SIMD (CPU Vectorization Level)"]
        SOL2["Giải Pháp 2: Nén JPEG bằng TurboJPEG + ARM NEON<br/>(Tận dụng 128-bit SIMD của Cortex-A53)"]
    end

    subgraph VPU_HW["Tầng Tăng Tốc GPU/VPU (Hardware VPU Offload Level)"]
        SOL3["Giải Pháp 3: Mã hóa phần cứng VideoCore IV<br/>(V4L2 M2M bcm2835-codec / MJPEG)"]
    end

    SOL1 -->|Tiết kiệm 10-15ms CPU| SOL2
    SOL2 -->|Tiết kiệm 30-40ms CPU -> Đạt 30 FPS| SOL3
    SOL3 -->|Giải phóng hoàn toàn CPU (< 5% load)| PROD["Hệ Thống Đạt Chuẩn 30 FPS Siêu Nhẹ"]
```

---

## 3. Danh Mục Tài Liệu Chi Tiết

| Tệp tài liệu | Nội dung trọng tâm | Độ phức tạp | Kỳ vọng cải thiện |
| :--- | :--- | :---: | :---: |
| [01-hardware-flip-ov5640.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/solutions/01-hardware-flip-ov5640.md) | Kích hoạt lật ảnh silicon bằng thanh ghi cảm biến OV5640 qua V4L2, loại bỏ `cv2.flip` | Thấp (Đã xong) | Tiết kiệm 10–15ms CPU / frame |
| [02-arm-neon-turbojpeg.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/solutions/02-arm-neon-turbojpeg.md) | Tích hợp thư viện `PyTurboJPEG` tận dụng chỉ lệnh SIMD ARM NEON tăng tốc nén JPEG | Trung bình (Đã xong) | Nén NEON vector với TJSAMP_420 + FastDCT |
| [03-bcm2835-codec-hardware-m2m.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/solutions/03-bcm2835-codec-hardware-m2m.md) | Khai thác bộ mã hóa phần cứng VideoCore IV của Pi 3 qua V4L2 M2M (`/dev/video11`) | Nâng cao | CPU tiêu thụ giảm xuống < 8%, nén 720p trong 4.2ms |
| [04-comparative-benchmark-and-plan.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/solutions/04-comparative-benchmark-and-plan.md) | Bảng đối chuẩn hiệu năng thực nghiệm trên Pi 3 và lộ trình triển khai 2 giai đoạn | Tổng hợp | Đối chuẩn nghiệm thu toàn diện |
| [05-sensor-hardware-binning-640.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/solutions/05-sensor-hardware-binning-640.md) | Phân tích Crop vs Resize cho YOLO; cấu hình Hardware Binning 640x360 bảo toàn Full FOV | Trung bình (Giai đoạn 2A) | Đạt ngay 28–30 FPS, tải CPU < 35%, tăng nhạy sáng |
| [06-multithreaded-pipeline-and-videocore-vpu.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/solutions/06-multithreaded-pipeline-and-videocore-vpu.md) | Đường ống bất đồng bộ Producer-Consumer đa nhân và tích hợp phần cứng VideoCore IV VPU | Nâng cao (Giai đoạn 2B) | Đạt 30 FPS kịch trần ở 720p, tải CPU < 8% |

---

## 4. Nguyên Tắc Thiết Kế Cốt Lõi

1. **Zero-Breaking Changes cho Backend:** Mọi giải pháp xuất ra payload hình ảnh vẫn giữ nguyên định dạng chuẩn JPEG và cấu trúc 36-byte Binary Header. Backend trên Laptop/Jetson tiếp nhận bình thường mà không cần sửa đổi dù chỉ 1 dòng code.
2. **Graceful Fallback:** Nếu phần cứng không hỗ trợ hoặc thiếu thư viện mở rộng, code tự động lùi về pipeline tiêu chuẩn (OpenCV) có ghi log cảnh báo, không làm crash tiến trình.
3. **Environment Isolation:** Mọi phụ thuộc mới đều được quản lý biệt lập trong virtual environment `.venv` theo đúng quy định tại [AGENTS.md](file:///E:/UIT/monocular-spatial-vision/AGENTS.md).
