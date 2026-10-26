# US-C01: Thu Nhận V4L2 MMAP (`media-ctl` + `v4l-subdev0`), Tách Kênh NEON `vld2_u8` & Nén Ảnh `tjCompressFromYUV`

> **Layer:** Implementation Layer (`docs/implementation/release-1c/backlogc/storiesc/US-C01.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Story ID:** US-C01  
> **Status:** Ready for Development (Audit-Remediated)  

---

## 1. User Story

**Là một** Kỹ sư Thị giác Nhúng (Embedded Vision Engineer),  
**Tôi muốn** module bắt hình trên Raspberry Pi 3 được viết bằng C++17 thuần túy, tự động đồng bộ đường ống phần cứng `bcm2835-unicam` (`/dev/media0`, `/dev/v4l-subdev0`, `/dev/video0`), tách kênh `UYVY -> YUV422P` bằng tập lệnh SIMD ARM NEON `vld2_u8` và nén ảnh bằng `tjCompressFromYUV()` của `libjpeg-turbo`,  
**Để** giải phóng toàn bộ nghẽn GIL của Python, trả bộ đệm DMA V4L2 về kernel trong vòng $< 1.5\text{ms}$, giảm tổng thời gian xử lý CPU mỗi khung hình xuống $< 10\text{ms}$, và đạt tốc độ khung hình ổn định $30\text{ FPS}$ không gây quá nhiệt CPU.

---

## 2. Acceptance Criteria (Given-When-Then)

### Kịch bản 1: Đồng bộ Media Controller (`bcm2835-unicam`) và cấp phát bộ đệm MMAP thành công
- **Given:** Cảm biến OmniVision OV5640 được kết nối qua MIPI CSI-2 trên Raspberry Pi 3 (`bcm2835-unicam`).
- **When:** Lớp `V4l2CameraDriver` thực thi phương thức `open("/dev/video0", "/dev/v4l-subdev0", 1280, 720, 30, true)`.
- **Then:**
  1. Đường ống Media Controller (`/dev/media0`) được cấu hình định dạng `'ov5640 10-003c':0 [fmt:UYVY8_1X16/1280x720@1/30 field:none]` khớp với `/dev/video0` (tránh lỗi `VIDIOC_STREAMON` trả về `-EPIPE`).
  2. Lệnh `ioctl(VIDIOC_S_FMT)` trên `/dev/video0` thiết lập thành công định dạng `V4L2_PIX_FMT_UYVY` tại $1280 \times 720$.
  3. Lệnh `ioctl(VIDIOC_REQBUFS)` cấp phát thành công 4 bộ đệm `V4L2_MEMORY_MMAP`.
  4. Lệnh `ioctl(VIDIOC_STREAMON)` kích hoạt luồng DMA phần cứng không trả về lỗi.

### Kịch bản 2: Tự động kích hoạt lật ảnh dọc phần cứng (Hardware Vertical Flip trên Sub-device)
- **Given:** Camera OV5640 được gắn ngược $180^\circ$ trên giá đỡ của Mobile Robot và driver `bcm2835-unicam` quản lý các thanh ghi cảm biến trên `/dev/v4l-subdev0`.
- **When:** Phương thức khởi tạo camera đọc cấu hình `vflip = true`.
- **Then:** Module gửi lệnh `ioctl(subdev_fd, VIDIOC_S_CTRL)` với `V4L2_CID_VFLIP = 1` trực tiếp tới `/dev/v4l-subdev0` (kèm fallback sang `/dev/video0`), cảm biến OV5640 tự động đảo chiều khung hình từ mạch silicon; thời gian grab khung hình không bị tăng thêm $1\text{ms}$ nào.

### Kịch bản 3: Bắt hình an toàn với `poll()` + Tách kênh ARM NEON `vld2_u8` + Nén `tjCompressFromYUV`
- **Given:** Thiết bị `/dev/video0` được mở ở chế độ `O_NONBLOCK` và luồng DMA đang hoạt động ở $30\text{ FPS}$.
- **When:** Luồng bắt hình chờ sự kiện VSYNC bằng `poll(&pfd, 1, 100)` (`POLLIN`), lấy khung hình bằng `VIDIOC_DQBUF`, tách kênh `UYVY` sang `YUV422P` (`Y`, `U`, `V` phẳng) bằng chỉ lệnh ARM NEON `vld2_u8` và gọi `tjCompressFromYUV(..., TJSAMP_422, 70, TJFLAG_FASTDCT | TJFLAG_NOREALLOC)`.
- **Then:**
  1. Không xảy ra lỗi `EAGAIN` hay đọc rác bộ nhớ khi cảm biến chưa xuất xong khung hình.
  2. Bộ đệm DMA V4L2 được trả lại hàng đợi kernel ngay lập tức bằng `ioctl(fd, VIDIOC_QBUF, &buf)` ngay sau bước tách kênh NEON ($\approx 1.2\text{ms}$), tuyệt đối không giữ khóa bộ đệm DMA trong lúc nén JPEG hay gửi mạng.
  3. Tổng thời gian CPU active (NEON de-interleave + `tjCompressFromYUV`) đo được trên Cortex-A53 của Raspberry Pi 3 phải $\le 12.0\text{ms}$ (mục tiêu $\approx 8.5 - 9.6\text{ms}$).
  4. Dữ liệu JPEG đầu ra có kích thước từ $35\text{KB} - 65\text{KB}$, bắt đầu bằng `0xFF 0xD8` và kết thúc bằng `0xFF 0xD9`.

### Kịch bản 4: Hỗ trợ chế độ chẩn đoán phần cứng (`--mode diag`) và chụp ảnh tĩnh (`--mode snapshot`)
- **Given:** Kỹ sư muốn kiểm tra nhanh kết nối MIPI CSI-2 và chất lượng ống kính trước khi stream.
- **When:** Chạy lệnh `./pi_capture_agent_cpp --mode diag` hoặc `./pi_capture_agent_cpp --mode snapshot --out /tmp/test.jpg`.
- **Then:** Hệ thống kiểm tra đầy đủ `/dev/media0`, `/dev/v4l-subdev0`, `/dev/video0`, `/dev/i2c-1` và lưu tệp ảnh JPEG hợp lệ giống hệt hành vi của bản Python hiện tại.

---

## 3. ARCHITECTURE GUARDRAILS FOR CODING AGENT

> ⛔ **BẮT BUỘC TUÂN THỦ:** Trước khi viết hoặc sửa đổi mã nguồn, AI Coding Agent phải đối chiếu các ràng buộc kiến trúc sau:

1. **Tương Thích Chính Xác Với API `libjpeg-turbo` (`<turbojpeg.h>`):**
   - Đối chiếu: [docs/implementation/release-1c/solutionsc/02-libjpeg-turbo-arm-neon-c-api.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/solutionsc/02-libjpeg-turbo-arm-neon-c-api.md).
   - *Ràng buộc:* `<turbojpeg.h>` **KHÔNG** có hằng số `TJPF_UYVY`. Nghiêm cấm truyền mảng `UYVY` vào `tjCompress2()`. Bắt buộc phải tách kênh `UYVY` sang 3 mặt phẳng `Y`, `U`, `V` (`YUV422P`) trong vùng đệm cấp phát sẵn rồi gọi `tjCompressFromYUV()`.
2. **Giải Phóng Sớm V4L2 Buffer & Cấp Phát Tĩnh (Zero Dynamic Allocation in Hot Loop):**
   - Đối chiếu: [docs/architecture/09-design-principles.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/09-design-principles.md).
   - *Ràng buộc:* Các vùng đệm `YUV422P` và `JPEG` phải được cấp phát 1 lần duy nhất khi khởi tạo (`Pre-allocated Triple Buffer Pool`). Nghiêm cấm gọi `new`, `malloc`, hoặc tạo `std::vector` mới trong vòng lặp $30\text{Hz}$.
3. **Vị Trí Mã Nguồn & Quản Lý Tài Nguyên RAII:**
   - Đối chiếu: [docs/architecture/10-folder-structure.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/10-folder-structure.md).
   - *Ràng buộc:* Mã nguồn đặt tại `services/pi_capture_agent_cpp/src/camera/` và `include/camera/`. Mọi file descriptor (`video_fd_`, `subdev_fd_`), vùng nhớ `mmap` và handle `tjhandle` phải được giải phóng tự động trong Destructor theo chuẩn RAII.
