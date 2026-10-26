# Báo Cáo Kỹ Thuật: Tối Ưu Chất Lượng Hình Ảnh, Xử Lý Lỗi Kênh Màu Bayer & Đánh Giá Hiệu Năng Luồng `pi_capture_native` (Digilent Pcam 5C / OV5640 trên Raspberry Pi 3)

- **Dự án**: Monocular Spatial Vision (`release-1c`)
- **Thành phần hệ thống**: `services/pi_capture_native` (C++17 / V4L2 MMAP / ARM NEON / libjpeg-turbo)
- **Phần cứng mục tiêu**: Raspberry Pi 3 Model B/B+ (`bcm2835-unicam`) + Camera MIPI CSI-2 Digilent Pcam 5C (OmniVision OV5640)
- **Ngày lập báo cáo**: 2026-10-26
- **Trạng thái hiện tại**: Đã khắc phục triệt để lỗi thiếu sáng, sọc ngang nhấp nháy (flicker banding), sai lệch pha màu Bayer (viền cầu vồng/ám xanh-tím-đỏ) và lật gương ngang. Tồn đọng vấn đề suy giảm tốc độ khung hình (~9.2–9.3 FPS) và độ trễ hiển thị (~1s) cần tối ưu tiếp ở giai đoạn kế tiếp.

---

## 1. Tổng Quan Bối Cảnh Kỹ Thuật

Dịch vụ thu nhận ảnh `pi_capture_native` được chuyển đổi từ Python (`pi_capture_agent`) sang C++ thuần nhằm giải quyết bài toán nghẽn cổ chai CPU trên Raspberry Pi 3 (4 nhân Cortex-A53 @ 1.2GHz). Kiến trúc C++ sử dụng trực tiếp giao diện kernel V4L2 (`VIDIOC_DQBUF`/`VIDIOC_QBUF` với bộ đệm `MMAP`), tập lệnh SIMD ARM NEON (`vld4_u8`) để tách kênh màu `UYVY -> YUV422P`, và thư viện `libjpeg-turbo` (`tjCompressFromYUVPlanes`) để nén ảnh JPEG phục vụ luồng stream TCP và giao diện HTTP MJPEG Preview.

Trong quá trình kiểm thử thực tế trên phần cứng Raspberry Pi 3 kết nối với mô-đun **Digilent Pcam 5C (cảm biến OmniVision OV5640)**, hệ thống đã phát sinh chuỗi vấn đề phức tạp liên quan đến tương tác giữa driver kernel `drivers/media/i2c/ov5640.c`, bộ thu nhận CSI-2 `bcm2835-unicam` và bộ xử lý tín hiệu ảnh nội vi (On-chip ISP) của cảm biến OV5640.

---

## 2. Các Vấn Đề Kỹ Thuật Đã Ghi Nhận

Qua các chu kỳ kiểm thử thực nghiệm ở độ phân giải mục tiêu `640x480` (capturing phần cứng ở `720x480` và crop tâm về `640x480`), hệ thống ghi nhận 5 vấn đề cốt lõi:

### 2.1. Lỗi biên dịch và cảnh báo trên trình biên dịch GCC 14.2 (ARM 32-bit)
- **Hiện tượng**: Khi biên dịch ở chế độ `-DCMAKE_BUILD_TYPE=Release` (kích hoạt cờ `-DNDEBUG`), macro `TEST_CHECK()` trong `tests/test_native.cpp` trước đó phụ thuộc vào biểu thức kiểm tra không sử dụng hết các biến cục bộ (`v_plane`, `ok`), gây cảnh báo `-Wunused-variable` và tiềm ẩn nguy cơ bị tối ưu hóa bỏ qua câu lệnh kiểm thử.

### 2.2. Hình ảnh bị tối nghiêm trọng khi khóa tốc độ khung hình cao (`--lock-30fps`)
- **Hiện tượng**: Khi ép tốc độ khung hình lên 30 FPS thông qua cờ `--lock-30fps`, video thu được tối hơn đáng kể (~60%) so với bản Python trong cùng điều kiện ánh sáng phòng thí nghiệm.
- **Nguyên nhân gốc rễ**:
  - Giá trị phơi sáng mặc định ban đầu được khóa cứng ở `exposure = 350` lines (~11.66 ms), kết hợp với việc tắt Auto Gain (`V4L2_CID_AUTOGAIN = 0`) ở mức khuếch đại thấp.
  - Ở chế độ `720x480` (`OV5640_MODE_NTSC_720_480`, `VTS = 984–1000` lines), thời gian phơi sáng 350 lines là quá ngắn đối với môi trường ánh sáng đèn huỳnh quang/LED trong nhà với khẩu độ ống kính M12 cố định F/2.0 của Pcam 5C.

### 2.3. Hiện tượng sọc ngang trôi/nhấp nháy (Rolling Shutter Banding / Flicker)
- **Hiện tượng**: Xuất hiện các vệt sọc ngang sáng–tối交替 (tương tự hiện tượng quay màn hình TV bằng điện thoại) khi chạy ở tốc độ khung hình 25–30 FPS với mức phơi sáng thấp (`350`–`600` lines).
- **Nguyên nhân gốc rễ**:
  - Lưới điện xoay chiều 50Hz tạo ra tần số nhấp nháy quang học 100Hz (chu kỳ phát sáng $T_{\text{light}} = 10.0\text{ ms}$).
  - Cảm biến OV5640 sử dụng màn trập lăn (Electronic Rolling Shutter). Khi thời gian tích quang (Integration Time) không phải là bội số nguyên của chu kỳ ánh sáng $10.0\text{ ms}$ (đặc biệt khi xung nhịp đầu vào `xclk` trên Pcam 5C được cấu hình lại giữa `24 MHz`, `18 MHz` hoặc `15 MHz` trong Device Tree `cam1clk-enable.dts`), mỗi hàng pixel trên cảm biến tích lũy một pha năng lượng ánh sáng khác nhau, tạo ra các dải sọc ngang trên khung hình.

### 2.4. Sai lệch màu sắc nghiêm trọng, viền màu giả cầu vồng (False-Color Rainbow Fringing) và lật gương ngang
- **Hiện tượng** (được ghi nhận trực quan tại ảnh chụp gốc [Screenshot 2026-10-26 122248.png](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/reportsc/Screenshot%202026-10-26%20122248.png)):
  1. Toàn bộ khung hình bị ám xanh dương – tím hoặc ám đỏ; khi điều chỉnh giảm kênh Red hoặc cân bằng trắng thủ công, ảnh chuyển sang ám xanh lá (green) pha xám.
  2. Tại các vùng có ánh sáng mạnh và độ tương phản cao (như rèm cửa sổ phía sau), xuất hiện các **dải viền cầu vồng màu tím, hồng cánh sen, đỏ và xanh điện (chromatic false-color fringes)**.
  3. Chữ viết trên hộp thiết bị (`"Pcam 5C"`) và trên giấy ghi chú bị **lật gương theo chiều ngang (horizontally mirrored)** dù đã truyền tham số `--rotate-180`.
- **Nguyên nhân gốc rễ (Lỗi phần cứng thanh ghi `0x3820` / `0x3821` của OV5640 ở chế độ Binning/Subsampling)**:
  - Khi bật `--rotate-180` bằng phần cứng thông qua `V4L2_CID_HFLIP = 1` và `V4L2_CID_VFLIP = 1` trên `/dev/v4l-subdev0`, driver kernel `ov5640.c` ghi trực tiếp vào thanh ghi `TIMING_TC_REG20 (0x3820)` và `TIMING_TC_REG21 (0x3821)`.
  - Ở chế độ phân giải thấp (`720x480` / `640x480`), cảm biến OV5640 kích hoạt tính năng **2x2 Subsampling & Horizontal Binning** (`0x3820 = 0x41`, `0x3821 = 0x07`). Việc bật bit lật phần cứng (`BIT(1)` và `BIT(2)`) trên OV5640 trong khi đang bật Binning làm dịch vị trí cửa sổ đọc mảng điểm ảnh đi 1 pixel lẻ, dẫn đến **lệch pha mẫu lọc màu Bayer CFA (`BGGR` bị dịch thành `RGGB` hoặc `GBRG`) trước khi đưa vào khối ISP Debayer và AWB nội vi của OV5640**.
  - Hệ quả là khối nội suy màu (Demosaicing) trên chip ghép nhầm kênh Green và Red/Blue tại mọi biên sáng (tạo ra viền cầu vồng tím/hồng/xanh ở rèm cửa sổ) và làm hỏng hoàn toàn ma trận màu đầu ra `UYVY`. Đồng thời, do cơ chế quản lý nguồn Runtime PM của kernel (`sensor->power_count == 0` trước khi `VIDIOC_STREAMON`), một số lệnh `VIDIOC_S_CTRL` gửi trước khi luồng bắt đầu đã bị bỏ qua hoặc thực thi không đồng bộ.

---

## 3. Các Giải Pháp Kỹ Thuật Đã Triển Khai

Để giải quyết triệt để các vấn đề về chất lượng hình ảnh và màu sắc, các giải pháp sau đã được thiết kế và tích hợp vào mã nguồn `pi_capture_native`:

### 3.1. Chuẩn hóa cơ chế kiểm thử đơn vị (`tests/test_native.cpp`)
- Thay thế toàn bộ việc kiểm tra điều kiện trong [test_native.cpp](file:///E:/UIT/monocular-spatial-vision/services/pi_capture_native/tests/test_native.cpp) bằng macro `TEST_CHECK(cond)` độc lập với cờ `NDEBUG`, đồng thời xác thực đầy đủ cả 3 mặt phẳng `Y`, `U`, `V` sau khi tách kênh và sau khi hoán đổi chroma (`swap_uv`). Quá trình biên dịch đạt 0 cảnh báo (`0 warnings`) trên GCC 14.2.0.

### 3.2. Khôi phục pha màu Bayer gốc trên phần cứng OV5640 và chuyển dịch phép xoay 180° sang phần mềm
- **Reset cứng `HFLIP = 0` và `VFLIP = 0` sau khi bật luồng (`VIDIOC_STREAMON`)**:
  - Trong [`V4l2Camera::open()`](file:///E:/UIT/monocular-spatial-vision/services/pi_capture_native/src/v4l2_camera.cpp#L208-L216), [`V4l2Camera::set_hardware_flip()`](file:///E:/UIT/monocular-spatial-vision/services/pi_capture_native/src/v4l2_camera.cpp#L309-L339) và [`V4l2Camera::set_exposure_mode()`](file:///E:/UIT/monocular-spatial-vision/services/pi_capture_native/src/v4l2_camera.cpp#L372-L380), hệ thống luôn ghi tường minh `V4L2_CID_HFLIP = 0` và `V4L2_CID_VFLIP = 0` xuống `/dev/v4l-subdev0` khi cảm biến đã ở trạng thái cấp nguồn (`power_count > 0`).
  - Việc này giữ cho hai thanh ghi `0x3820` và `0x3821` luôn ở trạng thái căn chỉnh Bayer gốc của nhà sản xuất, giúp khối ISP Debayer và Auto White Balance (AWB) trên chip OV5640 tái tạo màu sắc trung thực, loại bỏ 100% hiện tượng viền cầu vồng tím/hồng ở vùng sáng.
- **Xoay 180° (`rotate_180_`) và lật dọc (`vflip_only_`) trực tiếp trên không gian `UYVY`**:
  - Trong [`V4l2Camera::dequeue_frame()`](file:///E:/UIT/monocular-spatial-vision/services/pi_capture_native/src/v4l2_camera.cpp#L646-L685), quá trình xoay 180° được tích hợp trực tiếp vào bước sao chép và cắt khung hình (`720x480 -> 640x480`) vào bộ đệm `crop_buf_`.
  - Với mỗi macropixel 4-byte `[U, Y0, V, Y1]`, thuật toán đọc từ hàng cuối lên hàng đầu (`actual_h_ - 1 - row`), đảo ngược thứ tự các macropixel từ phải sang trái (`macro_count - 1 - m`) và hoán đổi vị trí hai mẫu độ chói `Y0 <-> Y1` (`[U, Y1, V, Y0]`) trong khi giữ nguyên cặp sắc độ `(U, V)`.

### 3.3. Tinh chỉnh điểm làm việc Exposure / Gain mặc định và đồng bộ hóa sau bước Warm-up
- **Điểm làm việc cân bằng mặc định (`exposure = 800`, `gain = 48`)**:
  - Trong [`V4l2Camera::set_exposure_mode()`](file:///E:/UIT/monocular-spatial-vision/services/pi_capture_native/src/v4l2_camera.cpp#L397-L420) và [`main.cpp`](file:///E:/UIT/monocular-spatial-vision/services/pi_capture_native/src/main.cpp#L1148-L1152), thông số mặc định của chế độ `--lock-30fps` được nâng lên `exposure = 800` lines (~26.7 ms) và `gain = 48` (3.0x analog gain), kết hợp bật bộ lọc chống nhấp nháy lưới điện 50Hz (`V4L2_CID_POWER_LINE_FREQUENCY_50HZ`) và cân bằng trắng tự động (`V4L2_CID_AUTO_WHITE_BALANCE = 1`).
- **Tái xác lập cấu hình sau chu kỳ Warm-up**:
  - Trong [`run_preview()`](file:///E:/UIT/monocular-spatial-vision/services/pi_capture_native/src/main.cpp#L677-L687), [`run_stream()`](file:///E:/UIT/monocular-spatial-vision/services/pi_capture_native/src/main.cpp#L205-L216) và [`run_snapshot()`](file:///E:/UIT/monocular-spatial-vision/services/pi_capture_native/src/main.cpp#L306-L315), hàm `set_exposure_mode()` được gọi lại ngay sau khi xả bỏ 5 khung hình khởi động đầu tiên, đảm bảo cấu hình I2C không bị quá trình khởi tạo `ov5640_s_stream(1)` ghi đè.

### 3.4. Bổ sung bộ công cụ chẩn đoán thời gian thực trên Web Preview HUD
- Tích hợp thêm các tham số dòng lệnh (`--swap-uv`, `--yuyv`, `--red-balance`, `--blue-balance`) và các endpoint điều khiển trực tiếp trên giao diện HTTP Preview (`/adj-exp`, `/adj-gain`, `/adj-wb`, `/toggle-uv`, `/toggle-yuyv`) giúp quan sát và kiểm chứng tức thời phản hồi của phần cứng cảm biến.

---

## 4. Kết Quả Đạt Được Hiện Tại (Đối Chiếu Thực Nghiệm)

Đối chiếu giữa ảnh chụp trước khi xử lý ([Screenshot 2026-10-26 122248.png](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/reportsc/Screenshot%202026-10-26%20122248.png)) và ảnh chụp sau khi áp dụng các giải pháp trên ([Screenshot 2026-10-26 124633.png](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/reportsc/Screenshot%202026-10-26%20124633.png)):

| Tiêu chí đánh giá | Trước khi xử lý (`Screenshot ... 122248.png`) | Sau khi xử lý (`Screenshot ... 124633.png`) |
| :--- | :--- | :--- |
| **Độ sáng tổng thể** | Tối, thiếu chi tiết vùng tối ngay khi khởi động | **Sáng rõ ngay khi khởi động**, độ tương phản tốt |
| **Hiện tượng sọc ngang (Flicker)** | Xuất hiện sọc ngang rõ rệt ở cấu hình mặc định | **Triệt tiêu hoàn toàn sọc ngang** |
| **Màu sắc & Cân bằng trắng** | Ám tím/xanh dương hoặc xanh lá/xám khi chỉnh WB | **Màu sắc trung thực, ổn định** (nhãn LaVie xanh dương chuẩn, giấy note vàng, mặt bàn trắng) |
| **Viền cầu vồng vùng sáng (Rèm cửa)** | Nhiễu viền cầu vồng tím/hồng/xanh rất nặng | **Biến mất hoàn toàn hiện tượng cầu vồng giả màu** |
| **Chiều hướng hình ảnh (`--rotate-180`)** | Bị lật gương ngang (chữ `"Pcam 5C"` bị ngược) | **Thuận chiều 100%** (chữ `"Pcam 5C"` và `"LaVie"` hiển thị đúng chiều) |

---

## 5. Vấn Đề Tồn Đọng Mới Phát Sinh: Suy Giảm FPS (~9.2–9.3 FPS) và Độ Trễ (~1s)

Mặc dù chất lượng hình ảnh (độ sáng, màu sắc, khử sọc, chiều ảnh) trong [Screenshot 2026-10-26 124633.png](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/reportsc/Screenshot%202026-10-26%20124633.png) đã đạt yêu cầu, hệ thống phát sinh hiện tượng:
1. **Tốc độ khung hình thực tế giảm xuống ~9.2 – 9.3 FPS**: Ghi nhận đồng nhất trên cả HUD của Web Preview lẫn log console của Raspberry Pi 3.
2. **Độ trễ chuyển động (~1 giây) và hiện tượng giật khi có chuyển động nhanh**: Luồng video hiển thị mượt ở trạng thái tĩnh nhưng phản hồi trễ khoảng ~1 giây khi có vật thể di chuyển.

### Đánh Giá Sơ Bộ & Định Hướng Giải Pháp Khôi Phục 25 FPS

Dưới đây là các giả thuyết kỹ thuật sơ bộ và hướng tiếp cận để khôi phục tốc độ khung hình về mức 25 FPS và giảm độ trễ xuống mức mili-giây:

1. **Kiểm tra lại tần số xung nhịp ngoại vi `clock-frequency` (`xclk`) trong Device Tree (`cam1clk-enable.dts`)**:
   - Trước đó, thông số `clock-frequency` trong `cam1clk-enable.dts` đã được thử nghiệm hạ từ `24000000` (24 MHz) xuống `18000000` (18 MHz) hoặc `15000000` (15 MHz), kết hợp với việc driver `ov5640.c` tính toán bộ chia PLL dựa trên hằng số 24 MHz.
   - Khi `xclk` thực tế thấp hơn 24 MHz hoặc khi kết hợp với lệnh đặt lại `V4L2_CID_HFLIP=0`/`V4L2_CID_VFLIP=0` và `exposure = 800` sau khi `STREAMON`, tổng thời gian đọc khung hình (`VTS` / Frame Interval) của cảm biến có thể bị kéo giãn xuống mốc ~9.2–10 FPS. Cần kiểm tra lại giá trị `clock-frequency = <24000000>;` trong `/boot/firmware/overlays/cam1clk-enable.dtbo`.

2. **Tương tác giữa `V4L2_CID_EXPOSURE = 800`, `V4L2_CID_POWER_LINE_FREQUENCY_50HZ` và thanh ghi `VTS` của OV5640**:
   - Khi gọi `set_exposure_mode()` lần thứ hai **sau** khi `VIDIOC_STREAMON` đã chạy, việc bật lại `V4L2_CID_POWER_LINE_FREQUENCY_50HZ` hoặc `V4L2_CID_AUTO_WHITE_BALANCE` trên `ov5640.c` có thể kích hoạt hàm nội bộ của driver ghi đè lại thanh ghi timing hoặc bật chế độ Night Mode / Auto Frame Rate Adjustment (thanh ghi `0x3a00` bit `BIT(2)` trên OV5640), khiến cảm biến tự động nhân đôi/nhân ba `VTS` (hạ FPS từ 30 FPS xuống ~10 FPS để tăng thời gian phơi sáng).
   - **Hướng thử nghiệm**: Giảm nhẹ `exposure` từ `800` xuống vùng `500–600` (tăng `gain` lên `64–80` để bù sáng) hoặc gọi lại `configure_framerate()` (`VIDIOC_SUBDEV_S_FRAME_INTERVAL`) ngay sau khi thiết lập xong `set_exposure_mode()`.

3. **Tối ưu hóa vòng lặp xoay 180° bằng phần mềm trong `V4l2Camera::dequeue_frame()`**:
   - Hiện tại, nhánh `if (rotate_180_)` trong [`V4l2Camera::dequeue_frame()`](file:///E:/UIT/monocular-spatial-vision/services/pi_capture_native/src/v4l2_camera.cpp#L653-L669) đang duyệt từng macropixel 4-byte bằng vòng lặp tuần tự trên vùng nhớ `buffers_[index].start` được ánh xạ qua `mmap()` từ DMA của `bcm2835-unicam`.
   - Trên kiến trúc ARMv7/ARMv8 của Raspberry Pi 3, vùng bộ nhớ DMA `V4L2_MEMORY_MMAP` thường được ánh xạ ở chế độ **Uncached / Write-Combining (DMA coherent)**. Việc đọc truy cập ngẫu nhiên ngược chiều (`(macro_count - 1 - m) * 4`) từng 4 byte trực tiếp từ bộ nhớ DMA uncached thay vì `memcpy` cả dòng liên tục vào bộ đệm L1/L2 cache trước khi đảo chiều có thể gây phạt trễ bus bộ nhớ (memory bus stall) rất lớn trên mỗi khung hình!
   - **Hướng giải quyết**: Trong `dequeue_frame()`, luôn dùng `memcpy` để chép nguyên dòng liên tục từ bộ nhớ DMA `raw` sang bộ đệm cached (hoặc thực hiện đảo chiều 180° trực tiếp bên trong hàm NEON [`JpegEncoder::uyvy_to_yuv422p_buffer()`](file:///E:/UIT/monocular-spatial-vision/services/pi_capture_native/src/jpeg_encoder.cpp) ở Thread 2 sau khi dữ liệu đã nằm trong RAM cached `local_pixels`). Cách này vừa giải phóng ngay lập tức Thread 1 (Capture), vừa tránh hoàn toàn việc đọc lùi từng 4-byte trên vùng nhớ DMA uncached.

4. **Khắc phục độ trễ ~1 giây trên trình duyệt (HTTP MJPEG Buffering)**:
   - Khi tốc độ tạo frame ở phía Pi giảm xuống ~9.2 FPS nhưng trình duyệt Chrome/Edge vẫn giữ cơ chế đệm luồng `multipart/x-mixed-replace` (thường tích lũy từ 5–10 khung hình trước khi render mượt), độ trễ hiển thị sẽ tăng lên $\approx \frac{8 \text{ frames}}{9.2 \text{ FPS}} \approx 0.9 \text{ giây}$.
   - Khi khôi phục tốc độ cảm biến/CPU trở lại 25–30 FPS (kết hợp giảm kích thước `SO_SNDBUF` hoặc dùng cơ chế nạp ảnh/WebSocket nếu cần), độ trễ hiển thị sẽ tự động giảm về lại mức dưới 100 ms như trước.
