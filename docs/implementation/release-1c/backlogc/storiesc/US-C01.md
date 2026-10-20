# US-C01: Thu Nhận V4L2 MMAP Trực Tiếp & Nén Ảnh TurboJPEG ARM NEON (C++ Native)

> **Layer:** Implementation Layer (`docs/implementation/release-1c/backlogc/storiesc/US-C01.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Story ID:** US-C01  
> **Status:** Ready for Development  

---

## 1. User Story

**Là một** Kỹ sư Thị giác Nhúng (Embedded Vision Engineer),  
**Tôi muốn** module bắt hình trên Raspberry Pi 3 được viết bằng C++ thuần túy, trực tiếp điều khiển thiết bị `/dev/video0` bằng Linux V4L2 ioctl và nén ảnh bằng TurboJPEG có tăng tốc ARM NEON SIMD,  
**Để** giải phóng toàn bộ nghẽn GIL của Python, giảm thời gian nén ảnh từ $65\text{ms}$ xuống dưới $10\text{ms}$, và đạt tốc độ khung hình ổn định $25 - 30\text{ FPS}$ mà không gây quá nhiệt CPU.

---

## 2. Acceptance Criteria (Given-When-Then)

### Kịch bản 1: Cấu hình V4L2 và cấp phát bộ đệm MMAP thành công
- **Given:** Cảm biến OmniVision OV5640 được kết nối qua MIPI CSI-2 và thiết bị `/dev/video0` sẵn sàng.
- **When:** Lớp `V4l2CameraDriver` thực thi phương thức `open("/dev/video0", 1280, 720, 30)`.
- **Then:**
  1. Lệnh `ioctl(VIDIOC_S_FMT)` thiết lập thành công định dạng `V4L2_PIX_FMT_UYVY` tại $1280 \times 720$.
  2. Lệnh `ioctl(VIDIOC_REQBUFS)` cấp phát thành công 4 bộ đệm `V4L2_MEMORY_MMAP`.
  3. Lệnh `ioctl(VIDIOC_STREAMON)` kích hoạt luồng DMA phần cứng không trả về lỗi.

### Kịch bản 2: Tự động kích hoạt lật ảnh dọc phần cứng (Hardware Vertical Flip)
- **Given:** Camera được gắn ngược $180^\circ$ trên giá đỡ của Mobile Robot.
- **When:** Phương thức khởi tạo camera đọc cấu hình `vflip = true`.
- **Then:** Module gửi lệnh `ioctl(VIDIOC_S_CTRL)` với `V4L2_CID_VFLIP = 1`, cảm biến OV5640 tự động đảo chiều khung hình từ mạch silicon; thời gian grab khung hình không bị tăng thêm $1\text{ms}$ nào so với khi không lật.

### Kịch bản 3: Nén ảnh TurboJPEG với chỉ lệnh SIMD ARM NEON
- **Given:** Con trỏ bộ đệm UYVY $1280 \times 720$ vừa được lấy ra từ `VIDIOC_DQBUF`.
- **When:** Module `TurboJpegEncoder` gọi hàm `tjCompress2()` với cờ `TJFLAG_FASTDCT` và hệ số chất lượng $Q=70$.
- **Then:**
  1. Thời gian nén đo được trên CPU Cortex-A53 của Raspberry Pi 3 phải $\le 12.0\text{ms}$ (khuyến nghị $\le 9.5\text{ms}$).
  2. Dữ liệu JPEG đầu ra có kích thước từ $35\text{KB} - 65\text{KB}$, bắt đầu bằng 2 byte Magic chuẩn `0xFF 0xD8`.
  3. Buffer DMA camera được trả lại hàng đợi ngay bằng `ioctl(VIDIOC_QBUF)`.

---

## 3. ARCHITECTURE GUARDRAILS FOR CODING AGENT

> ⛔ **BẮT BUỘC TUÂN THỦ:** Trước khi viết hoặc sửa đổi mã nguồn, AI Coding Agent phải đối chiếu các ràng buộc kiến trúc sau:

1. **Nguyên Tắc Zero-Copy:**
   - Đối chiếu: [docs/architecture/09-design-principles.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/09-design-principles.md).
   - *Ràng buộc:* Tuyệt đối không copy dữ liệu từ vùng đệm `mmap` sang `std::vector` trung gian trước khi nén. Con trỏ `mmap` phải được truyền trực tiếp vào `tjCompress2()`.
2. **Vị Trí Mã Nguồn:**
   - Đối chiếu: [docs/architecture/10-folder-structure.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/10-folder-structure.md).
   - *Ràng buộc:* Toàn bộ mã nguồn driver camera C++ phải nằm trong thư mục `services/pi_capture_agent_cpp/src/camera/` và headers trong `services/pi_capture_agent_cpp/include/camera/`.
3. **Phòng Ngừa Rò Rỉ Tài Nguyên (RAII):**
   - File descriptor V4L2 và vùng nhớ `munmap` bắt buộc phải được giải phóng tự động trong Destructor của lớp `V4l2CameraDriver` theo chuẩn RAII (Resource Acquisition Is Initialization).
