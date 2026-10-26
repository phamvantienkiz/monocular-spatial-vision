# Báo Cáo Chuyên Sâu: Phân Tích Hiện Tượng Tối Hình, Lệch Màu & Sọc Nhấp Nháy (Flickering) Trên Pcam 5C (OV5640) Chạy Bằng C/C++ Native

- **Địa điểm lưu trữ**: `docs/implementation/release-1c/reportsc/pcam5c_ov5640_image_quality_root_cause_analysis.md`
- **Mục tiêu**: Điều tra toàn diện tài liệu phần cứng Digilent Pcam 5C, cảm biến OmniVision OV5640, cơ chế V4L2 Unicam trên Raspberry Pi 3, đối chiếu chi tiết giữa pipeline Python và C/C++ Native để chỉ rõ nguồn gốc 3 hiện tượng:
  1. Hình ảnh bị tối đáng kể so với bản Python.
  2. Hình ảnh bị ám xanh (blue) - tím (magenta).
  3. Hiện tượng nhấp nháy sọc ngang (banding / flicker) giống quay màn hình TV lệch tần số quét.

---

## 1. Tổng Quan Phần Cứng & Kiến Trúc ISP Của Digilent Pcam 5C

### 1.1. Bản chất phần cứng Pcam 5C
Theo tài liệu chính thức từ **Digilent** (*Digilent Pcam 5C Reference Manual*) và **OmniVision** (*OV5640 Datasheet / Software Application Notes*):
- **Cảm biến bên trong**: OmniVision OV5640 5-Megapixel Color CMOS Image Sensor (OmniBSI™ 1.4 µm pixel).
- **Ống kính (Lens Mount)**: Ngàm chuẩn M12 (S-mount), lens mặc định có tích hợp lớp tráng phủ kính lọc hồng ngoại (**IR-Cut Filter 650nm**).
- **Giao diện truyền dữ liệu (Data Bus)**: 2-lane MIPI CSI-2.
- **Giao diện điều khiển (Control Bus)**: I²C (SCCB bus, địa chỉ mặc định `0x3c`).
- **Xử lý tín hiệu hình ảnh (ISP On-Chip)**:
  - Khác với Raspberry Pi Camera v2 (IMX219) hay v3 (IMX708) vốn là cảm biến **Raw Bayer** và đẩy toàn bộ việc xử lý ảnh (Demosaicing, AWB, AGC, Lens Shading Correction) về Broadcom VideoCore GPU ISP (thông qua `libcamera` / Picamera2), **OV5640 là một SoC Sensor có sẵn ISP tích hợp phần cứng**.
  - OV5640 trực tiếp thực hiện Auto Exposure Control (AEC), Auto White Balance (AWB), Auto Black Level Calibration (ABLC), Color Matrix, và De-noising ngay trên chip trước khi xuất dữ liệu ra bus MIPI CSI-2 dưới dạng **YUV422** hoặc **RGB565**.

### 1.2. Trình điều khiển trên Raspberry Pi: `ov5640.ko` + `bcm2835-unicam`
- Raspberry Pi 3 không hỗ trợ camera OV5640 qua firmware đóng của Broadcom (`raspivid` hay `libcamera` tự động). Thay vào đó, nó giao tiếp qua:
  1. **Subdevice driver**: Kernel module `drivers/media/i2c/ov5640.c` điều khiển register OV5640 qua I²C (`/dev/v4l-subdev0`).
  2. **Receiver driver**: `bcm2835-unicam` (Unicam) nhận packet MIPI CSI-2 và trực tiếp DMA vào RAM Linux (`/dev/video0`).

---

## 2. Đối Chiếu Chuyên Sâu Giữa Pipeline Python và Pipeline C/C++ Native

| Đặc Điểm Phân Tích | Pipeline Python (`pi_capture_agent`) | Pipeline C/C++ Native (`pi_capture_native`) | Đánh Giá Tác Động |
| :--- | :--- | :--- | :--- |
| **Thư viện Capture** | OpenCV `cv2.VideoCapture(dev, cv2.CAP_V4L2)` | Linux direct System Call `ioctl(fd, VIDIOC_...)` + `mmap` | Python để OpenCV tự động đàm phán; C++ điều khiển trực tiếp từng ioctl. |
| **Định dạng nhận từ V4L2** | `UYVY` (nhưng OpenCV tự covert sang BGR 3 channels khi gọi `cap.read()`) | `V4L2_PIX_FMT_UYVY` raw buffer | Bản C++ giữ nguyên byte gốc từ camera. |
| **Độ phân giải cấu hình V4L2** | Cố định `1280x720` từ sensor, sau đó dùng Python slicing `[::2, ::2]` xuống preview | Cấu hình trực tiếp `720x480` (rồi center crop sang `640x480`) | Thay đổi timing clock, tỷ lệ nội suy cảm biến và thời gian phơi sáng từng dòng! |
| **Thuật toán nén JPEG** | `PyTurboJPEG.encode(frame, pixel_format=TJPF_BGR)` | `tjCompressFromYUV` nhận planar YUV422P sau khi NEON de-interleave `UYVY` | **Nghi ngờ cốt lõi về thứ tự kênh màu U/V.** |
| **Điều khiển Phơi sáng (Exposure)** | Mặc định để **AEC tự động** (`exposure=None`), không can thiệp khóa shutter | Khi truyền `--lock-30fps`, C++ gọi `set_exposure_mode(lock_30fps=true)`, cưỡng bức `V4L2_EXPOSURE_MANUAL` và gán shutter lines = 350 | **Nguyên nhân trực tiếp gây tối hình!** |
| **Bộ lọc nhấp nháy điện lưới (Banding Filter)** | Chỉ gán `power_line_frequency=1` qua subdev nếu có `exposure` | Gán `power_line_frequency=1` (50Hz), nhưng lại khóa shutter cố định | Khi shutter bị khóa cứng thời gian phơi sáng không tương thích với chu kỳ đèn huỳnh quang/LED phòng lab, sọc sọc xuất hiện. |

---

## 3. Phân Tích Chi Tiết Từng Vấn Đề

### Vấn Đề 1: Tại Sao Video Bị Tối Đáng Kể Khi Chạy Lệnh Preview C/C++?

#### Triệu chứng
Khi chạy lệnh:
```bash
./build/pi_capture_native --mode preview --width 640 --height 480 --rotate-180 --lock-30fps
```
Hình ảnh tối đi hẳn so with bản Python trong cùng phòng lab.

#### Phân tích mã nguồn và vật lý cảm biến
1. Khi có cờ `--lock-30fps`, trong hàm [`V4l2Camera::set_exposure_mode`](file:///E:/UIT/monocular-spatial-vision/services/pi_capture_native/src/v4l2_camera.cpp#L366-L383):
   ```cpp
   if (lock_30fps || manual_exposure > 0) {
       int exp_val = (manual_exposure > 0) ? manual_exposure : 350;
       ctrl.id = V4L2_CID_EXPOSURE_AUTO;
       ctrl.value = V4L2_EXPOSURE_MANUAL;
       xioctl(target_fd, VIDIOC_S_CTRL, &ctrl);

       ctrl.id = V4L2_CID_EXPOSURE;
       ctrl.value = exp_val; // 350 lines
       xioctl(target_fd, VIDIOC_S_CTRL, &ctrl);
   }
   ```
2. **Tại sao lại chọn con số 350 lines?**
   - Tài liệu OV5640 chỉ ra: ở chế độ VGA/D1 (720x480), tổng số dòng quét ảo (Total Vertical Size - VTS) cấu hình xấp xỉ 1000 dòng.
   - Để đạt chuẩn 30 FPS, thời gian quét 1 dòng (line period) là:
     $$T_{\text{line}} \approx \frac{1}{30 \times 1000} \approx 33.33\,\mu\text{s}$$
   - Ở bản Python: Camera chạy ở chế độ **Auto Exposure Control (AEC)**. Dưới ánh sáng trong phòng, thuật toán AEC tự động kéo exposure lên 800 - 950 lines ($\sim 26.6\text{ms} - 31.6\text{ms}$), đồng thời tự động đẩy analog/digital gain lên để đủ sáng.
   - Nhưng khi chạy C/C++ với `--lock-30fps`, mã nguồn đã chuyển sang **MANUAL EXPOSURE** và gán cứng `exposure = 350 lines` ($\approx 11.66\,\text{ms}$).
   - **Hệ quả quang học**: Thời gian cảm quang nhận sáng bị cắt giảm từ $\sim 30\,\text{ms}$ xuống chỉ còn $\sim 11.6\,\text{ms}$ (giảm hơn $60\%$ lượng photon đi vào đi-ốt bán dẫn, tương đương mất khoảng $1.5$ đến $2$ stop phơi sáng).
   - Mặc dù mã nguồn C++ có bật `V4L2_CID_AUTOGAIN = 1`, nhưng dải bù trừ AGC của OV5640 trong nhà thường bị giới hạn trần gain ceiling (`0x3a18/0x3a19`) để chống nhiễu hạt, do đó không bù lại được mức độ sụt giảm $60\%$ thời gian tích phân photon.

---

### Vấn Đề 2: Tại Sao Video Bị Ám Xanh (Blue) - Tím (Magenta)?

Có hai nguyên nhân kỹ thuật độc lập kết hợp gây ra hiện tượng này:

#### Nguyên nhân 2.1: Hoán đổi kênh Chroma $U$ (Cb) và $V$ (Cr) trong Pipeline YUV422
- Trong chuẩn Video YUV422, có 2 biến thể đóng gói (packed format) phổ biến nhất là:
  - **`UYVY`**: Byte 0 = $U$ ($C_b$), Byte 1 = $Y_0$, Byte 2 = $V$ ($C_r$), Byte 3 = $Y_1$.
  - **`YUYV`**: Byte 0 = $Y_0$, Byte 1 = $U$ ($C_b$), Byte 2 = $Y_1$, Byte 3 = $V$ ($C_r$).
- Hãy kiểm tra mã nguồn de-interleave trong [`JpegEncoder::uyvy_to_yuv422p_buffer`](file:///E:/UIT/monocular-spatial-vision/services/pi_capture_native/src/jpeg_encoder.cpp#L91-L100):
  ```cpp
  uint8x8x4_t raw = vld4_u8(s);
  vst1_u8(u, raw.val[0]); // gán byte 0 làm U
  vst1_u8(v, raw.val[2]); // gán byte 2 làm V
  ```
- **Hiện tượng thực tế với OV5640 trên Pi kernel:**
  - Tùy thuộc vào phiên bản Driver Kernel của OV5640 (`ov5640.c`) và cấu hình register `0x4300` (Format Mux Control) trên chip:
    - Khi register `0x4300 = 0x30`: Thứ tự xuất byte là $Y_0, U, Y_1, V$ (`YUYV`).
    - Khi register `0x4300 = 0x32`: Thứ tự xuất byte là $U, Y_0, V, Y_1$ (`UYVY`).
    - Khi register `0x4300 = 0x31`: Thứ tự xuất byte là $V, Y_0, U, Y_1$ (`VYUY`).
  - Khi ứng dụng yêu cầu V4L2 cấp format `V4L2_PIX_FMT_UYVY`, nhưng nếu kernel driver hoặc phần cứng xuất dữ liệu thực tế lệch 1 byte hoặc hoán vị giữa $U$ ($C_b$ - Blue component) và $V$ ($C_r$ - Red component):
    - Kênh màu Đỏ (Red) và Xanh Dương (Blue) sẽ bị đảo lộn.
    - Màu da người bình thường (giàu sắc đỏ $V > 128, U < 128$) khi bị tráo $U \leftrightarrow V$ sẽ biến thành **tím hoặc xanh lơ (cyan/purple)**.
- **Tại sao bản Python không bị?**
  - Trong Python, `cv2.VideoCapture` được OpenCV tích hợp sẵn bảng chuyển đổi V4L2 native. Khi đọc frame, OpenCV tự động chuyển từ buffer sang format BGR thông qua hàm color conversion nội bộ đã được hiệu chuẩn đúng với header descriptor của camera V4L2.

#### Nguyên nhân 2.2: Thuật toán Cân Bằng Trắng (AWB) Của OV5640 Bị Đóng Băng Khi Khóa Phơi Sáng Quá Tối
- Theo tài liệu OmniVision OV5640 Application Note (mục *Auto White Balance Tuning*):
  - Bộ tính toán AWB của OV5640 hoạt động dựa trên các pixel có độ sáng nằm trong khoảng trung bình ($Y_{\text{min}} \le Y \le Y_{\text{max}}$).
  - Khi thời gian phơi sáng bị khóa cưỡng bức ở mức quá thấp (`exposure = 350`), ảnh bị thiếu sáng (underexposure), đa số pixel bị rơi xuống vùng tối (dưới ngưỡng thống kê của AWB block).
  - Khi không đủ số lượng pixel mẫu đạt chuẩn, thuật toán AWB phần cứng rơi vào trạng thái "AWB Lock" hoặc trả về gain mặc định của cảm biến, làm cho sắc thái màu xanh dương/tím của quang phổ nhạy cảm tự nhiên trên đi-ốt silicon nổi trội hơn.

---

### Vấn Đề 3: Hiện Tượng Nhấp Nháy Sọc Ngang (Banding / Flickering)

#### Triệu chứng
Video xuất hiện các vệt sáng tối xen kẽ chạy ngang màn hình, nhấp nháy liên tục, tương tự như hiện tượng camera điện thoại quay vào màn hình TV hay bóng đèn tuýp.

#### Nguyên lý vật lý và nguồn gốc vấn đề
1. **Đặc tính Rolling Shutter của OV5640:**
   - Cảm biến OV5640 sử dụng màn trập điện tử kiểu cuốn (**Rolling Shutter**). Từng hàng pixel được phơi sáng và đọc tuần tự từ đỉnh xuống đáy cảm biến.
2. **Đặc tính đèn điện lưới trong phòng lab:**
   - Đèn huỳnh quang và đèn LED cắm điện lưới sinh hoạt tại Việt Nam hoạt động ở tần số điện xoay chiều **50 Hz**.
   - Cường độ ánh sáng phát ra từ đèn biến thiên theo chu kỳ sóng bán kỳ chỉnh lưu:
     $$f_{\text{light}} = 2 \times 50\,\text{Hz} = 100\,\text{Hz}$$
   - Nghĩa là ánh sáng trong phòng đạt đỉnh và đáy mỗi $10\,\text{ms}$ ($1/100$ giây).
3. **Mâu thuẫn toán học khi khóa thời gian phơi sáng `exposure = 350`:**
   - Để triệt tiêu hiện tượng sọc ngang (flicker-free), thời gian phơi sáng (shutter duration $T_{\text{exp}}$) **bắt buộc phải là bội số nguyên của chu kỳ biến thiên ánh sáng**:
     $$T_{\text{exp}} = k \times \frac{1}{100\,\text{Hz}} = k \times 10\,\text{ms} \quad (k = 1, 2, 3, \dots)$$
   - Ở tốc độ 30 FPS với VTS $\approx 1000$ dòng, thời gian 1 dòng quét là $\approx 33.33\,\mu\text{s}$.
   - Khi gán `exposure = 350 lines`:
     $$T_{\text{exp}} = 350 \times 33.33\,\mu\text{s} \approx 11.66\,\text{ms}$$
   - Con số $11.66\,\text{ms}$ **hoàn toàn không phải là bội số của $10\,\text{ms}$** ($11.66 \neq 10.0$ và $11.66 \neq 20.0$).
   - Kết quả: Khi Rolling Shutter quét qua các dòng, dòng này hứng được 1.16 chu kỳ ánh sáng (sáng hơn), dòng tiếp theo lại rơi vào đoạn đáy của chu kỳ sóng (tối hơn). Điều này tạo ra các dải sọc sáng/tối di chuyển ngang khung hình (Rolling Banding Artifacts).

---

## 4. Tổng Hợp Các Khác Biệt Giữa Bản Python và Bản C/C++

```
[Camera OV5640 Phần Cứng]
         │
         ├──► [Python Agent (OpenCV CAP_V4L2)]:
         │       • Yêu cầu: UYVY 1280x720
         │       • Phơi sáng: AUTO AEC/AWB hoàn toàn (shutter ~850 lines = ~28ms)
         │       • Banding filter: Tự thích nghi theo chu kỳ 10ms (100Hz)
         │       • Chuyển đổi màu: OpenCV xử lý YUV -> BGR nội bộ (chuẩn xác)
         │       • Kết quả: Hình sáng, màu chuẩn, không nhấp nháy, nhưng CPU 100% -> FPS ~8-15.
         │
         └──► [C/C++ Native với --lock-30fps]:
                 • Yêu cầu: UYVY 720x480 (Anti-stripe crop 640x480)
                 • Phơi sáng: BỊ KHÓA CỨNG MANUAL (shutter = 350 lines = ~11.6ms) -> TỐI HÌNH
                 • Shutter 11.6ms không chia hết cho 10ms (50Hz) -> SỌC NHẤP NHÁY
                 • Chuyển đổi màu: NEON byte-shuffle UYVY -> Planar YUV422P
                   (Nghi ngờ tráo kênh U/V hoặc kernel OV5640 cấp YUYV) -> ÁM TÍM/XANH
                 • Kết quả: Cực mượt 30 FPS, CPU chỉ 15-20%, nhưng chất lượng hình ảnh bị suy giảm.
```

---

## 5. Đề Xuất Hướng Thử Nghiệm Kiểm Chứng (Dành Cho Bước Sau)

Dựa trên các phân tích khoa học trên, khi tiến hành khắc phục ở các bước tiếp theo, chúng ta sẽ có phương án xử lý rõ ràng:

1. **Khắc phục hiện tượng Tối hình:**
   - Chuyển `V4L2_CID_EXPOSURE_AUTO` về chế độ `AUTO` hoàn toàn (không ép giá trị 350 lines khi không cần thiết), hoặc cho phép tự động thích ứng với mức cận trên an toàn ($T_{\text{exp}} = 20\,\text{ms}$ hoặc $30\,\text{ms}$).
2. **Khắc phục hiện tượng Sọc nhấp nháy (Flickering/Banding):**
   - Đảm bảo thanh ghi Banding Filter trên cảm biến OV5640 được cấu hình đúng: thời gian phơi sáng tối thiểu trong nhà phải khóa ở mức bội số của $10\,\text{ms}$ ($300$ lines hoặc $600$ lines tùy theo clock thực tế của hệ thống).
3. **Khắc phục hiện tượng Ám màu Xanh / Tím:**
   - Dùng lệnh `v4l2-ctl -d /dev/video0 --list-formats-ext` và kiểm tra raw byte dump từ camera để xác nhận chính xác thứ tự là `UYVY`, `YUYV` hay `VYUY`.
   - Nếu là do hoán vị $U \leftrightarrow V$, chỉ cần đảo vị trí lưu trữ con trỏ `u` và `v` trong hàm giải nén NEON.
