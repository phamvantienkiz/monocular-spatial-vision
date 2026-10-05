# PRD / SRS — Module Camera Đơn (Pcam 5C) cho Mobile Robot

| Mục                         | Nội dung                                                                                                                                                                                                     |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Dự án                       | Mobile Robot LiDAR — ASIC Lab, Computer Engineering                                                                                                                                                          |
| Module                      | `mono_perception` — camera đơn Pcam 5C (Digilent, cảm biến OV5640) trên 1× Raspberry Pi 3, xử lý trung tâm tại Jetson AGX Xavier                                                                             |
| Quan hệ với tài liệu stereo | Đây là **phương án phần cứng thay thế** cho `stereo_camera_module_PRD_SRS.md` (2× IMX219 + 2× Pi3). Giữ gần như nguyên cấu trúc tài liệu đó; phần nội dung bắt buộc phải viết lại được đánh dấu rõ ở mục 0.1 |
| Phiên bản tài liệu          | v0.1 (draft để thảo luận với lead)                                                                                                                                                                           |
| Ngày                        | 2026-10-01                                                                                                                                                                                                   |
| Phạm vi chi tiết            | RQ1–RQ3 **đã được định nghĩa lại** cho camera đơn (xem 0.1). RQ4, RQ5 chỉ đặt interface/kỳ vọng (mục 10)                                                                                                     |
| Đối tượng đọc               | Nhóm nghiên cứu + AI coding agents                                                                                                                                                                           |

---

## 0. Cách đọc tài liệu này

### 0.1 Khác biệt cốt lõi so với phương án stereo — đọc trước khi dùng tài liệu

Đổi từ 2 camera sang **1 camera duy nhất** không phải là một thay đổi "đổi tên linh kiện" — nó loại bỏ hoàn toàn cơ sở vật lý của stereo vision:

| Thành phần trong tài liệu stereo                            | Vì sao không còn áp dụng được                                    | Thay bằng gì trong tài liệu này                                                                                                                                                                |
| ----------------------------------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| RQ1 — đồng bộ 2 luồng ảnh từ 2 máy                          | Chỉ có 1 camera, không có luồng thứ hai để đồng bộ               | RQ1 **định nghĩa lại**: đồng bộ giữa **thời điểm chụp ảnh** và **thời điểm pose/chuyển động của robot** (wheel odometry + IMU + EKF) — cần cho "motion stereo" và cho việc chiếu LiDAR lên ảnh |
| RQ2 — hiệu chuẩn stereo + depth từ disparity                | Không có baseline vật lý giữa 2 ống kính, không có disparity map | RQ2 **định nghĩa lại**: hiệu chuẩn camera đơn (nội) + hiệu chuẩn ngoại camera↔robot/camera↔LiDAR, và **lựa chọn/đánh giá một chiến lược ước lượng độ sâu đơn mắt** trong 3 ứng viên (mục 8.3)  |
| RQ3 — kết hợp detection với depth map stereo                | Không còn depth map dày đặc từ stereo matching                   | RQ3 **giữ nguyên cấu trúc** (detection/segmentation + robust aggregation → XYZ) nhưng nguồn depth đổi sang 1 trong 3 ứng viên của RQ2                                                          |
| Bối cảnh hệ thống, NFR, repo layout, roadmap, risk register | Không phụ thuộc vào số lượng camera                              | **Giữ gần như nguyên**, chỉ chỉnh chi tiết phần cứng (1 Pi thay vì 2, không còn mạng đồng bộ liên-Pi)                                                                                          |

**Vì sao vẫn giữ tên "RQ1/RQ2/RQ3"** thay vì đặt câu hỏi hoàn toàn mới: để tài liệu này dễ đối chiếu song song với tài liệu stereo khi trình bày với lead, và để nếu sau này quay lại phương án stereo thì cấu trúc RQ vẫn nhất quán. **Khuyến nghị:** khi trình bày với lead, nói rõ đây là một bộ câu hỏi nghiên cứu **mới, tương ứng vị trí** với RQ1–RQ3 cũ, không phải bản thu gọn của bộ cũ — cần lead xác nhận lại (câu hỏi Q-01 ở mục 16).

### 0.2 Quy ước nhãn và quy tắc cho AI Agent

Giữ nguyên quy ước như tài liệu stereo: `[FACT]` (có nguồn xác nhận), `[ASSUMPTION]` (giả định tạm, phải kiểm chứng), `[TBD]` (chưa biết), `[PROPOSED]` (đề xuất của tài liệu, chưa được lead duyệt). AI Agent không bịa thông số phần cứng/ống kính/driver; không tự hạ ngưỡng khi gate không đạt; mọi thí nghiệm phải tái lập được (log cấu hình, git hash, dữ liệu thô); đơn vị SI, timestamp `int64` nanosecond.

---

## 1. Tóm tắt điều hành (TL;DR)

- **Bài toán:** dùng **1 camera Pcam 5C** (cảm biến OV5640, 5 MP, Digilent) nối qua **1 Raspberry Pi 3** để xác định vật thể 3D cho robot vi sai trong nhà — khoảng cách, XYZ, kích thước, 3D bounding box; pose 6DoF vẫn ngoài phạm vi cốt lõi (như tài liệu stereo).
- **Rủi ro kỹ thuật số 1 — khác hẳn tài liệu stereo:** không phải vấn đề đồng bộ thời gian, mà là **liệu Pcam 5C có chạy được trên Raspberry Pi hay không**. Digilent (nhà sản xuất) nói thẳng trong tài liệu chính thức: tuy đầu nối FFC tương thích chân với cổng camera Raspberry Pi, **Digilent chưa kiểm chứng việc này hoạt động và không cung cấp phần mềm hỗ trợ**. Cảm biến OV5640 có driver V4L2 mainline trong nhân Linux và đã chạy được trên một số nền tảng khác (TI AM62x, i.MX8, Allwinner H3...) thông qua device-tree overlay riêng, nhưng **không phải là cảm biến được hỗ trợ sẵn trong stack `libcamera`/Raspberry Pi OS tiêu chuẩn** (không có sẵn tuning file ISP như các camera chính hãng IMX219/IMX708/IMX477). Đây là việc cần kiểm chứng **đầu tiên**, trước mọi việc khác trong tài liệu này (mục 4.2, H-00).
- **Vì không còn stereo, bài toán depth phải chọn 1 trong 3 hướng (hoặc kết hợp), cần lead quyết định (RQ2, mục 8):**
  1. **Motion stereo / Structure-from-Motion**: dùng chính chuyển động của robot làm "baseline ảo" giữa 2 khung hình chụp cách nhau một khoảng thời gian, tam giác hóa như stereo nhưng theo trục thời gian thay vì trục không gian cố định. Ưu điểm: baseline có thể chọn lớn hơn stereo cố định (robot đi xa hơn giữa 2 keyframe → baseline lớn hơn → depth chính xác hơn ở khoảng cách xa). **Nhược điểm cốt lõi: độ chính xác phụ thuộc vào độ chính xác pose (EKF/odometry) giữa 2 khung hình, không phải vào đồng bộ thời gian** — đây là sự đánh đổi rủi ro mới thay cho rủi ro đồng bộ 2 camera cũ.
  2. **Mạng ước lượng độ sâu đơn mắt (monocular depth estimation)**: cho ra depth map từ 1 ảnh, nhưng về bản chất **thiếu tỉ lệ (scale-ambiguous)** trừ khi dùng mô hình "metric depth" đã huấn luyện cho thang đo tuyệt đối hoặc neo tỉ lệ bằng một tham chiếu đã biết (kích thước vật, hoặc dữ liệu LiDAR).
  3. **Kết hợp với LiDAR 2D sẵn có (RPLIDAR S2E)**: robot đã có LiDAR 2D đáng tin cậy — chiếu điểm LiDAR vào vùng phát hiện 2D trên ảnh để lấy khoảng cách/góc phương vị, kết hợp giả định mặt phẳng sàn + hình học pinhole để ước lượng chiều cao/kích thước. **Đây là phương án ít rủi ro kỹ thuật nhất** vì tận dụng cảm biến đã hoạt động ổn định, nhưng chỉ cho khoảng cách tại độ cao mặt phẳng LiDAR, không đo trực tiếp được kích thước 3D đầy đủ như stereo.
- **Yêu cầu đồng bộ thời gian giờ đây lỏng hơn nhiều so với tài liệu stereo**: không cần `Δt < 1–2 ms` giữa 2 camera; chỉ cần đồng bộ ảnh với pose/LiDAR ở mức "chuẩn ROS 2 thông thường" (vài chục ms, dùng `message_filters::ApproximateTime` như thực hành phổ biến trong robotics) — xem phân tích định lượng ở mục 6.2.
- **Việc cần làm ngay tuần đầu:** xác nhận Pcam 5C chạy được trên Pi 3 ở mức cơ bản nhất (ra được `/dev/videoX`, lấy được ít nhất 1 frame) — đây là gate chặn trước tất cả các việc khác (mục 4.2, H-00); song song xác nhận các thông số lens/sensor còn thiếu; và họp với lead để chốt chiến lược depth (Q-01, Q-02 ở mục 16).

---

## 2. Bối cảnh: hệ thống Mobile Robot hiện có

Không đổi so với tài liệu stereo — trích lại để tài liệu này độc lập đọc được.

### 2.1 Nền tảng

| Hạng mục         | Giá trị                                                                                              |
| ---------------- | ---------------------------------------------------------------------------------------------------- |
| Compute chính    | Jetson AGX Xavier Developer Kit 16 GB trên Auvidea X221-AI (SKU 70415-AI)                            |
| OS / ROS         | Ubuntu 20.04 / ROS 2 Foxy; DDS: FastRTPS/FastDDS                                                     |
| Điều hướng       | slam_toolbox, Nav2 (AMCL, NavFn/A\*, DWB), EKF (`robot_localization`)                                |
| Cảm biến hiện có | RPLIDAR S2E (qua LAN), IMU BNO055 (I2C, 50 Hz), siêu âm (cấu hình phần mềm, phần cứng chưa xác nhận) |
| Dẫn động         | Differential drive, STM32F103RCT6 (hoverboard) + ESP32 (điều khiển tay)                              |
| Giám sát         | RViz trên laptop qua WiFi (DDS discovery)                                                            |
| Frames hiện có   | `map`, `odom`, `base_footprint`, `imu_link`, `laser_frame`                                           |
| Topic chính      | `/odom`, `/odometry/filtered`, `/imu/data`, `/scan`, `/scan_filtered`, `/cmd_vel`                    |

### 2.2 Các con số trong hệ thống robot ảnh hưởng thiết kế camera

| Số liệu (nguồn)                                                             | Ảnh hưởng tới module camera đơn                                                                                                                                                                        |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Nav2 `max_vel_x = 0.4 m/s`, `max_vel_theta = 1.5 rad/s` (giới hạn phần mềm) | Quyết định baseline ảo tối đa cho motion stereo trong một khoảng thời gian cho trước; quyết định ngân sách sai số timing (mục 6.2)                                                                     |
| Local costmap 5×5 m, inflation 0.12/0.25 m                                  | Vùng quan tâm chính 0.3–3 m, như tài liệu stereo                                                                                                                                                       |
| Footprint ≈ x∈[−0.12, 0.32], y∈±0.30 m                                      | Vị trí lắp camera trong `base_footprint` còn `[TBD]`                                                                                                                                                   |
| LiDAR dùng cổng LAN của Jetson                                              | Pi3 (camera) cần đường mạng riêng — **nhẹ hơn yêu cầu cũ** vì chỉ có 1 Pi, không cần switch đa cổng phức tạp như phương án 2-Pi                                                                        |
| EKF `robot_localization`, 50 Hz, two_d_mode                                 | Đây chính là nguồn pose dùng cho motion stereo và cho chiếu LiDAR lên ảnh — **độ chính xác của EKF giờ ảnh hưởng trực tiếp tới độ chính xác depth**, một liên kết không tồn tại trong phương án stereo |
| Robot chưa có thông tin pin/nguồn/khối lượng                                | Ngân sách công suất cho 1 Pi3 + Pcam5C `[TBD]`, nhẹ hơn đáng kể so với 2 Pi3                                                                                                                           |

### 2.3 Điểm tích hợp

- Module phải xuất dữ liệu vào cùng cây TF (`base_footprint → camera_link → camera_optical_frame`), dùng chung đồng hồ ROS của Jetson.
- Kết quả 3D (RQ3) đi vào RQ4 (world frame) như tài liệu stereo.
- **Khác biệt quan trọng:** vì không có depth map stereo độc lập, pipeline của tài liệu này **phụ thuộc trực tiếp và liên tục vào `/odometry/filtered` và/hoặc `/scan_filtered`** ngay trong RQ2/RQ3 (không chỉ ở RQ4 như phương án stereo) — đây là một ràng buộc kiến trúc mới cần lưu ý khi code.

---

## 3. Phạm vi, mục tiêu, phi mục tiêu

### 3.1 Mục tiêu (Goals)

| ID                         | Mục tiêu                                                                                                                |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| G1                         | Có pipeline đồng bộ ảnh ↔ pose/LiDAR với Δt đo được và đạt gate ở mục 7                                                 |
| G2                         | Chọn và đánh giá được 1 (hoặc kết hợp) trong 3 chiến lược depth đơn mắt, có sai số định lượng theo khoảng cách (mục 8)  |
| G3                         | Có ước lượng vị trí 3D vật thể (camera frame) với sai số so với ground-truth (mục 9)                                    |
| G4                         | Chạy thời gian gần thực trên Jetson (≥ 10 Hz cho pipeline đầy đủ `[PROPOSED]`)                                          |
| G5                         | Dữ liệu, code, cấu hình đủ rõ để tái lập và mở rộng sang RQ4–RQ5                                                        |
| G0 (mới, ưu tiên cao nhất) | Xác nhận Pcam 5C hoạt động được trên Raspberry Pi 3 ở mức lấy được ảnh thô ổn định — **điều kiện tiên quyết cho G1–G4** |

### 3.2 Phi mục tiêu

Giống tài liệu stereo (không thiết kế lại phần cứng, không SLAM thị giác thay LiDAR, không semantic memory/active perception ở giai đoạn này, không tối ưu trong điều kiện cực đoan). Bổ sung: **không coi độ sâu đơn mắt là thay thế hoàn toàn cho stereo về độ chính xác** — mục tiêu là một giải pháp "đủ dùng" (good-enough) với phần cứng hiện có, không phải tái tạo lại chất lượng stereo bằng 1 camera.

### 3.3 Làm rõ phạm vi: "mọi vật thể" và "pose 6DoF" với camera đơn `[PROPOSED — cần lead duyệt]`

Giữ nguyên 4 tầng T1–T4 như tài liệu stereo, nhưng **hạ kỳ vọng** ở T2 vì thiếu thị sai tức thời (instantaneous parallax) của stereo:

| Tầng         | Đối tượng                          | Đầu ra                                                   | Ghi chú khác biệt so với stereo                                                                                                                                                                                                                                      |
| ------------ | ---------------------------------- | -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **T1 (MVP)** | Vật thể thuộc tập lớp đã biết      | class, distance, XYZ (tâm), extents, 3D axis-aligned box | Độ chính xác XYZ phụ thuộc chiến lược depth đã chọn (RQ2); nếu dùng LiDAR fusion, "extents" theo chiều cao chủ yếu suy từ hình học pinhole + giả định mặt sàn, không đo trực tiếp                                                                                    |
| **T2**       | Như T1 + hướng (yaw)               | 3D box định hướng theo trọng lực                         | **Khó hơn đáng kể so với stereo**: không có depth map tức thời để suy yaw từ hình dạng bề mặt; chủ yếu dựa vào hình chiếu 2D (orientation của bbox/mask) + giả định vật nằm trên sàn — độ tin cậy thấp hơn, nên lead cân nhắc có đưa vào phạm vi RQ3 ngay hay để sau |
| **T3**       | Vật thể chưa biết (class-agnostic) | cụm điểm 3D/khoảng cách/box, nhãn `unknown`              | Nếu dùng motion stereo: vẫn khả thi tương tự stereo (chỉ cần disparity theo thời gian thay vì theo baseline cố định). Nếu chỉ dùng LiDAR fusion: giới hạn ở "có vật cản tại góc/khoảng cách X", không có hình dạng 3D                                                |
| **T4**       | Pose 6DoF đầy đủ                   | —                                                        | Ngoài phạm vi, như tài liệu stereo — **càng khó hơn với camera đơn**                                                                                                                                                                                                 |

---

## 4. Phần cứng và ràng buộc

### 4.1 Đã có (`[FACT]`)

- **1× Pcam 5C** (Digilent): cảm biến màu Omnivision **OV5640**, 5 MP, giao tiếp **MIPI CSI-2 2 lane**, đầu nối **FFC 15 chân tương thích chân với cổng camera Raspberry Pi** (không phải "tương thích hoàn toàn", xem H-00), cáp FFC 10 cm đi kèm, lens **M12 fixed-focus lắp sẵn tại nhà máy**, bus điều khiển **SCCB** (2 dây, tương tự I2C), có header 1×7 chân phụ (100-mil) cho tín hiệu camera phụ trợ. Hỗ trợ các mode: **QSXGA (2592×1944) @15 Hz, 1080p @30 Hz, 720p @60 Hz, VGA @90 Hz, QVGA @120 Hz**; định dạng đầu ra theo datasheet sensor: RAW10, RGB565, CCIR656, YUV422/420, YCbCr422, nén JPEG (Digilent chỉ chính thức hỗ trợ/kiểm chứng **RAW10** trong IP core của họ).
- **1× Raspberry Pi 3**, 3B/3B+ `[TBD]`.
- Jetson AGX Xavier 16 GB + Auvidea X221-AI làm trung tâm (không đổi).

### 4.2 Rủi ro/việc cần xác nhận — ưu tiên theo mức độ chặn (blocking)

| ID       | Câu hỏi                                                                                                                                                                                       | Mức chặn               | Vì sao quan trọng                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | Cách xác nhận                                                                                                                                                                                                                                        |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **H-00** | **Pcam 5C có chạy được trên Raspberry Pi 3 (Raspberry Pi OS) không, ở mức cơ bản nhất?**                                                                                                      | **Chặn toàn bộ dự án** | `[FACT]` Chính Digilent ghi rõ: dù đầu nối tương thích chân với Raspberry Pi, **họ chưa kiểm chứng và không cung cấp phần mềm hỗ trợ** cho việc này. `[FACT]` OV5640 có driver V4L2 mainline trong nhân Linux (`drivers/media/i2c/ov5640.c`) và đã chạy trên nhiều nền tảng khác (TI AM62x, NXP i.MX8, Allwinner H3/sun8i) thông qua **device-tree overlay riêng cho từng nền tảng** — nhưng **không có overlay/tuning chính thức cho Raspberry Pi OS + `libcamera`** như các camera gốc Pi (IMX219/IMX708/IMX477). Khả năng cao cần: (a) tự viết/tìm device-tree overlay cho Pi, (b) chạy qua `v4l2-ctl` thô (bỏ qua `libcamera`) với ISP/debayer tự xử lý phần mềm (tốn CPU Pi3 vốn đã yếu), hoặc (c) không hoạt động được và phải đổi hướng (nối Pcam 5C trực tiếp vào Jetson nếu driver L4T có hỗ trợ OV5640 — cũng `[TBD]`, hoặc tìm board trung gian khác) | **Spike kỹ thuật ngay tuần đầu**: cắm thử, chạy `dmesg`, `v4l2-ctl --list-devices`, thử device-tree overlay cộng đồng cho `ov5640` nếu có, đo xem có `/dev/videoX` không và có đọc được frame thô không — không phụ thuộc vào `libcamera` ở bước đầu |
| H-01     | Thông số lens thực tế: tiêu cự (focal length), FOV, độ méo                                                                                                                                    | Cao                    | Quyết định toàn bộ phép tính hình học ở mục 6 và chất lượng detection ở khoảng cách xa                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           | Datasheet Pcam 5C / đo bằng checkerboard sau khi H-00 qua                                                                                                                                                                                            |
| H-02     | Pi 3 là 3B hay 3B+                                                                                                                                                                            | TB                     | Ảnh hưởng băng thông mạng Pi→Jetson                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | `cat /proc/device-tree/model`                                                                                                                                                                                                                        |
| H-03     | Nguồn cấp cho Pcam 5C qua FFC: điện áp/dòng có khớp với những gì Pi cấp qua cổng camera không (tín hiệu `PWUP` theo tài liệu Pcam 5C cần được driver/host điều khiển đúng trình tự bật nguồn) | Cao (gắn với H-00)     | Nếu trình tự bật nguồn (power-up sequence) không được driver Pi điều khiển đúng, cảm biến có thể không khởi động được dù đi dây đúng                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Đọc kỹ reference manual Pcam 5C phần power-up sequence; so sánh với cách Raspberry Pi cấp nguồn/điều khiển `CAM_GPIO`/`PWUP` cho camera gốc                                                                                                          |
| H-04     | Vị trí lắp module trên robot (x,y,z, pitch) so với `base_footprint`, và so với vị trí LiDAR                                                                                                   | Cao                    | Cần cho TF, cho hiệu chuẩn ngoại camera↔LiDAR (RQ2), và cho giả định mặt phẳng sàn                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               | Đo cơ khí                                                                                                                                                                                                                                            |
| H-05     | Cố định cơ khí, chống rung                                                                                                                                                                    | TB                     | Rung làm sai lệch hiệu chuẩn ngoại và làm giảm chất lượng motion stereo (vốn đã nhạy với sai số pose)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            | Kẹp cứng                                                                                                                                                                                                                                             |
| H-06     | Độ phân giải/FPS vận hành thực tế đạt được trên Pi3 sau khi driver chạy được                                                                                                                  | Cao                    | Pi3 yếu (RAM 1 GB); ở QSXGA chỉ 15 fps và tốn băng thông/CPU debayer nếu không có ISP phần cứng hỗ trợ; có thể phải chọn 720p/1080p                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Đo sau H-00                                                                                                                                                                                                                                          |

### 4.3 Đặc tính cảm biến/nền tảng `[FACT]/[ASSUMPTION]`

- OV5640 cũng là rolling shutter (giống IMX219) — tương tự lưu ý về rolling shutter trong tài liệu stereo vẫn áp dụng nếu dùng kỹ thuật đo quang học để kiểm tra timestamp (mục 7.5).
- Pi 3: 4×Cortex-A53, RAM 1 GB — nếu phải debayer/ISP bằng phần mềm (do thiếu driver ISP đầy đủ cho OV5640 trên Pi), đây sẽ là gánh nặng CPU đáng kể, cần đo sớm (H-06).
- Không có thông tin công khai về tiêu cự/FOV cụ thể của lens M12 đi kèm Pcam 5C trong các nguồn đã tra cứu — coi là `[TBD]`, không suy luận từ các module khác.

---

## 5. Kiến trúc hệ thống đề xuất `[PROPOSED]`

### 5.1 Sơ đồ khối

```
 Pcam 5C (OV5640) ──FFC 15-pin──► Raspberry Pi 3
                                        │  capture (v4l2/libcamera nếu chạy được)
                                        │  + gắn metadata thời gian mỗi frame
                                        │  Ethernet (có dây)
                                        ▼
 ┌────────────────────────── Jetson AGX Xavier ──────────────────────────┐
 │ mono_ingest_node ─► Image + CameraInfo + stamp                        │
 │                                                                       │
 │      ┌─────────────── depth_engine (chọn 1 hoặc kết hợp) ──────────┐  │
 │      │ (a) motion_stereo: dùng 2+ keyframe + pose từ EKF            │  │
 │      │ (b) mono_depth_net: mạng ước lượng độ sâu đơn mắt            │  │
 │      │ (c) lidar_fusion: chiếu /scan_filtered lên ảnh + ground plane│  │
 │      └───────────────────────────────────────────────────────────┘  │
 │                           │                                          │
 │                           ▼                                          │
 │                  detector/segmenter(image) ─► object3d_node          │
 │                                                     │                 │
 │  TF: base_footprint → camera_link → camera_optical_frame             │
 │  Input bắt buộc: /odometry/filtered (motion stereo, chiếu LiDAR),    │
 │                  /scan_filtered (lidar_fusion)                       │
 │                                                     ▼                 │
 │                                       /perception/objects_3d          │
 └────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Thành phần và trách nhiệm

| Thành phần                                                                                            | Chạy ở         | Trách nhiệm                                                                                                                                         |
| ----------------------------------------------------------------------------------------------------- | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pi_capture_agent` (đơn giản hơn tài liệu stereo — chỉ 1 luồng, không cần thuật toán đồng bộ liên-Pi) | Pi 3           | Cấu hình camera, khóa exposure/gain/AWB khi cần cho calibration, gắn timestamp mỗi frame, nén nhẹ, gửi qua mạng                                     |
| `mono_ingest_node`                                                                                    | Jetson (ROS 2) | Nhận ảnh, phát `sensor_msgs/Image` + `CameraInfo`                                                                                                   |
| `motion_stereo_node`                                                                                  | Jetson         | Chọn cặp keyframe đủ baseline ảo, tra pose từ `/odometry/filtered` tại 2 thời điểm, tam giác hóa                                                    |
| `mono_depth_net_node`                                                                                 | Jetson (GPU)   | Chạy mạng ước lượng độ sâu đơn mắt, xử lý vấn đề scale (mục 8.3)                                                                                    |
| `lidar_fusion_node`                                                                                   | Jetson         | Chiếu `/scan_filtered` lên ảnh bằng extrinsic camera↔LiDAR, lấy khoảng cách theo góc phương vị khớp với vùng phát hiện                              |
| `object3d_node`                                                                                       | Jetson         | Detection/segmentation + kết hợp 1 trong 3 nguồn depth trên → `Object3D` (giữ nguyên thiết kế robust aggregation như tài liệu stereo, mục 9.4 ở đó) |
| `sync_eval`                                                                                           | Jetson/laptop  | Đo Δt ảnh↔pose/LiDAR (mục 6, 7)                                                                                                                     |

**Lý do giữ Pi3 làm bridge thay vì cắm Pcam 5C trực tiếp vào Jetson:** đầu nối FFC của Pcam 5C tương thích chân với cổng camera Raspberry Pi, không phải cổng camera của Jetson (khác pinout/điện áp) — nên vẫn cần Pi3 làm cầu nối, trừ khi xác nhận được Jetson có driver OV5640 native cho L4T `[TBD — phương án dự phòng nếu H-00 thất bại trên Pi3]`.

### 5.3 Mạng

Đơn giản hơn tài liệu stereo (không cần đồng bộ liên-Pi): 1 đường Ethernet có dây Pi3↔Jetson là đủ. Băng thông ước tính ở 720p@30fps raw ~ 1280×720×30×8 bit ≈ **221 Mbps** chưa nén — cần nén (MJPEG) tương tự tài liệu stereo, đặc biệt nếu Pi3 là 3B (Ethernet 100 Mbps).

### 5.4 Hợp đồng giao tiếp ROS 2 (Jetson) `[PROPOSED]`

| Topic                                  | Kiểu                                                       | Ghi chú                                                                   |
| -------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------- | -------- | ------------------------------------------------ |
| `/mono/image_raw`, `/mono/camera_info` | `sensor_msgs/Image`, `CameraInfo`                          |                                                                           |
| `/mono/depth`                          | `sensor_msgs/Image` (32FC1) hoặc `sensor_msgs/PointCloud2` | Tùy nguồn depth đang dùng; gắn trường `source: motion_stereo              | mono_net | lidar_fusion` vào metadata kèm theo (custom msg) |
| `/perception/objects_3d`               | custom `Object3DArray`                                     | Giữ schema như tài liệu stereo (mục 9.5 ở đó), thêm trường `depth_source` |

---

## 6. Nền tảng định lượng

### 6.1 Motion stereo: công thức và đánh đổi

Dạng công thức giống stereo cổ điển nhưng baseline là **quãng đường robot đi giữa 2 keyframe**, lấy từ `/odometry/filtered`:

```
Z = f·B_virtual / d
B_virtual ≈ ∫ v dt  (trong khoảng thời gian giữa 2 keyframe, theo EKF)
σ_Z ≈ Z²·σ_d / (f·B_virtual)                         (nhiễu matching — giống stereo)
σ_Z_pose ≈ Z · (σ_B / B_virtual)                      (sai số MỚI: do lỗi ước lượng B_virtual từ EKF)
```

**Khác biệt cốt lõi so với stereo cố định:** stereo có `B` **cố định và đo được chính xác bằng thước cặp** (sai số ~1–2%, mục H-02 tài liệu stereo); motion stereo có `B_virtual` **ước lượng gián tiếp qua tích phân vận tốc của EKF**, vốn tích lũy sai số theo thời gian và theo điều kiện trượt bánh/bề mặt (đã nêu trong báo cáo hệ thống: wheel odometry dễ tích lũy sai số khi bánh trượt). Vì vậy:

- **Ưu điểm:** `B_virtual` có thể lớn hơn nhiều baseline stereo vật lý (6 cm) nếu chọn 2 keyframe cách xa nhau hơn (ví dụ robot đi 20–40 cm giữa 2 keyframe) → `σ_Z` do nhiễu matching nhỏ hơn đáng kể ở cùng khoảng cách Z (so bảng 6.1 trong tài liệu stereo).
- **Nhược điểm:** `σ_Z_pose` là một nguồn sai số **hoàn toàn mới**, không tồn tại trong stereo cố định, và **không giảm được bằng cách cải thiện đồng bộ thời gian** — chỉ giảm được bằng cách cải thiện chất lượng EKF/odometry hoặc dùng baseline ngắn hơn (đánh đổi ngược lại với ưu điểm trên).
- **Ràng buộc bắt buộc:** motion stereo cần robot **tịnh tiến thực sự** giữa 2 keyframe (không chỉ xoay tại chỗ) — nếu robot chỉ xoay, không có thị sai, không tam giác hóa được. Cần chính sách chọn keyframe (ví dụ: chỉ chọn cặp có `B_virtual` ước lượng ≥ ngưỡng, ví dụ 10 cm).

### 6.2 Ngân sách đồng bộ ảnh↔pose (thay cho ngân sách đồng bộ 2-camera của tài liệu stereo)

Khi ảnh và pose lệch thời gian `Δt_sync`, sai số lan vào ước lượng `B_virtual` và vào góc xoay dùng để rectify:

```
δB ≈ v · Δt_sync          (sai số tịnh tiến do lệch thời gian)
δθ ≈ ω · Δt_sync           (sai số góc xoay dùng để rectify cặp keyframe)
```

Với `v_max = 0.4 m/s`, `ω_max = 1.5 rad/s` (giới hạn Nav2):

| Δt_sync                                | δB (tịnh tiến tối đa) | δθ (góc tối đa) |
| -------------------------------------- | --------------------- | --------------- |
| 10 ms                                  | 4 mm                  | 0.86°           |
| 20 ms                                  | 8 mm                  | 1.72°           |
| 50 ms                                  | 20 mm                 | 4.3°            |
| 100 ms (≈ 1 chu kỳ quét LiDAR ở 10 Hz) | 40 mm                 | 8.6°            |

So với `B_virtual` cỡ 10–40 cm (mục 6.1), `δB` ở mức 8–40 mm (Δt_sync 20–100 ms) chỉ chiếm **2–20% của B_virtual** — **lỏng hơn rất nhiều** so với yêu cầu `< 1–2 px disparity` của stereo 2-camera (tài liệu stereo, mục 6.2), vì ở đây sai số so sánh với một baseline lớn hơn nhiều (10–40 cm so với 6 cm).

**Kết luận thiết kế:** `[PROPOSED]` mục tiêu `Δt_sync (ảnh↔pose) p99 ≤ 50 ms` là đủ dùng cho motion stereo trong phần lớn điều kiện vận hành — tương đương mức dung sai (`slop`) thường dùng với `message_filters::ApproximateTime` trong ROS 2 (phổ biến 50–100 ms), **không cần** hạ tầng đồng bộ đặc biệt như PPS/genlock đã đề xuất cho phương án stereo. Đây là lý do RQ1 của tài liệu này **nhẹ hơn hẳn** RQ1 của tài liệu stereo.

### 6.3 Vấn đề tỉ lệ (scale) của mạng depth đơn mắt

Hầu hết mạng ước lượng độ sâu đơn mắt chỉ cho **độ sâu tương đối** (thứ tự xa/gần đúng, nhưng không có đơn vị mét thật) trừ khi: (a) mô hình được huấn luyện riêng cho "metric depth" trên một dải khoảng cách cụ thể, hoặc (b) có một tham chiếu tỉ lệ trong cảnh (vật kích thước đã biết, hoặc một điểm có khoảng cách đã biết từ LiDAR). `[TBD]` lựa chọn mô hình cụ thể cần tra cứu lại tại thời điểm triển khai (tốc độ/độ chính xác thay đổi nhanh); không chốt tên mô hình trong tài liệu này để tránh lỗi thời — xem Q-03.

**Khuyến nghị thực dụng:** nếu dùng hướng (b) mục 1 (mạng depth đơn mắt), **luôn neo tỉ lệ bằng LiDAR** (lấy khoảng cách LiDAR tại vài điểm trong khung hình làm "mỏ neo" để co giãn depth map tương đối thành depth map mét) — tức là kết hợp ứng viên 2 và 3 với nhau, không dùng ứng viên 2 độc lập.

### 6.4 Hình học LiDAR fusion + giả định mặt phẳng sàn

Với giả định vật thể đứng trên sàn phẳng (hợp lý trong nhà, đã dùng ngầm bởi Nav2/costmap 2D của robot):

```
Khoảng cách ngang (x,y) tại mặt sàn: lấy trực tiếp từ /scan_filtered theo góc phương vị của tâm bbox
Chiều cao vật ước lượng: h ≈ (y_top_px − y_bottom_px) · Z / f   (Z lấy từ LiDAR, f từ calibration nội)
```

Giới hạn: chỉ đúng nếu đáy vật thể chạm sàn và nằm trong góc quét ngang của LiDAR (LiDAR 2D không "thấy" vật treo lơ lửng hoặc vật có đáy cao hơn/thấp hơn mặt phẳng LiDAR).

---

## 7. RQ1 (định nghĩa lại) — Đồng bộ ảnh ↔ pose/LiDAR

### 7.1 Câu hỏi nghiên cứu

_Pipeline chụp ảnh trên 1 Pi3 và luồng pose/LiDAR trên Jetson có đồng bộ đủ tốt để làm motion stereo và chiếu LiDAR lên ảnh không?_ Đầu ra đo được: **Δt (ảnh↔pose), Δt (ảnh↔LiDAR scan), jitter, dropped-frame rate, FPS thực của Pcam 5C trên Pi3**.

### 7.2 Định nghĩa metric

Tương tự tài liệu stereo (mục 7.2) nhưng đối tượng so sánh đổi từ (camera A, camera B) thành (ảnh, pose nội suy từ EKF) và (ảnh, scan LiDAR gần nhất). Giữ nguyên cách đo: p50/p95/p99/max, dùng `chronyc tracking` để biết trạng thái đồng hồ Pi3↔Jetson.

### 7.3 Nguồn gây sai lệch

1. Lệch đồng hồ Pi3↔Jetson (NTP qua LAN — không cần PPS/PTP phức tạp như tài liệu stereo, vì ngân sách lỏng hơn nhiều, mục 6.2).
2. Độ trễ mạng/mã hóa từ Pi3 tới Jetson.
3. Tần số publish khác nhau giữa ảnh (camera FPS), `/odometry/filtered` (50 Hz theo cấu hình EKF hiện tại) và `/scan_filtered` (theo tần số quét LiDAR, `[TBD]` tra lại thông số RPLIDAR S2E).
4. Độ trễ xử lý nội suy pose (interpolate pose tại đúng timestamp ảnh, không dùng "pose gần nhất" một cách ngây thơ).

### 7.4 Kế hoạch thí nghiệm

| ID   | Thí nghiệm                                                                                                  | Đầu ra                                       |
| ---- | ----------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| E1.0 | **Spike H-00**: xác nhận Pcam 5C ra ảnh được trên Pi3 (có hoặc không qua `libcamera`)                       | Go/no-go cho toàn bộ dự án                   |
| E1.1 | Đo FPS thực, dropped-frame rate của Pcam 5C trên Pi3 ở các mode (VGA/720p/1080p)                            | Chọn mode vận hành (liên quan H-06)          |
| E1.2 | Đo Δt (ảnh↔pose) khi robot đứng yên và khi di chuyển (v, ω theo bảng 6.2)                                   | Δt p50/p95/p99, so với mô hình δB/δθ dự đoán |
| E1.3 | Đo Δt (ảnh↔LiDAR scan) tương tự                                                                             | Như trên                                     |
| E1.4 | Kiểm tra chất lượng nội suy pose (so sánh nội suy tuyến tính vs nội suy từ EKF trực tiếp tại timestamp ảnh) | Chọn phương pháp nội suy                     |

### 7.5 Gate `[PROPOSED]`

| Mức               | Điều kiện                                                                        | Hành động                                                                                        |
| ----------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| PASS              | `Δt(ảnh↔pose) p99 ≤ 50 ms`, FPS thực ≥ 15 (tối thiểu cho motion stereo khả dụng) | Chuyển RQ2                                                                                       |
| PASS có điều kiện | `50 ms < p99 ≤ 100 ms`                                                           | Giới hạn motion stereo cho các đoạn robot di chuyển chậm/thẳng; ưu tiên LiDAR fusion khi `ω` cao |
| FAIL              | H-00 không qua (Pcam 5C không chạy được trên Pi3)                                | Kích hoạt phương án dự phòng phần cứng (mục 15, R-00) trước khi bàn tiếp bất kỳ gate nào khác    |

---

## 8. RQ2 (định nghĩa lại) — Hiệu chuẩn camera đơn + lựa chọn chiến lược depth

### 8.1 Câu hỏi nghiên cứu

_Hiệu chuẩn camera đơn và hiệu chuẩn ngoại camera↔LiDAR/robot thế nào cho đủ chính xác, và trong 3 chiến lược depth đơn mắt, chiến lược nào (hoặc kết hợp nào) đạt sai số chấp nhận được?_ Đầu ra đo được: reprojection error hiệu chuẩn nội, sai số hiệu chuẩn ngoại, **depth MAE/RMSE theo khoảng cách cho từng ứng viên**.

### 8.2 Hiệu chuẩn

**Nội (intrinsic):** quy trình giống tài liệu stereo (mục 8.3 ở đó) nhưng chỉ cho 1 camera — bảng ChArUco, ≥ 40–60 tư thế, tính `fx, fy, cx, cy`, hệ số méo. Không có bước `stereoCalibrate`.

**Ngoại camera↔LiDAR (mới, không có trong tài liệu stereo):** cần thiết cho `lidar_fusion_node` và cho chiếu LiDAR lên ảnh ở RQ1. Phương pháp phổ biến: dùng bảng calibration có đặc trưng cả camera và LiDAR nhận ra được (hoặc đơn giản hơn: đặt vật mốc tại các vị trí đo được bằng tay, ghi nhận cả pixel và góc/khoảng cách LiDAR, giải hệ phương trình hình học để ra phép biến đổi). `[TBD]` chọn phương pháp cụ thể sau khi có H-04 (vị trí lắp tương đối camera↔LiDAR).

**Ngoại camera↔base_footprint:** đo cơ khí (H-04) + tinh chỉnh bằng vật mốc có vị trí biết trước trên sàn.

### 8.3 Ba ứng viên chiến lược depth — kế hoạch đánh giá

| Ứng viên                             | Mô tả                                                                                                     | Thí nghiệm                                                                                                                     | Metric                                                                                             |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| **(a) Motion stereo**                | Mục 6.1; cần chính sách chọn keyframe (baseline tối thiểu, lọc khi `ω` cao)                               | E2.a1: đo depth MAE/RMSE theo Z khi robot di chuyển thẳng ở các tốc độ khác nhau, so với ground-truth (thước/laser)            | MAE/RMSE theo Z, tỷ lệ keyframe hợp lệ (đủ baseline)                                               |
| **(b) Mạng depth đơn mắt**           | Mục 6.3; cần giải quyết scale                                                                             | E2.b1: so sánh depth tương đối với ground-truth sau khi neo tỉ lệ bằng 1–2 điểm LiDAR; đo độ ổn định scale theo thời gian/cảnh | MAE/RMSE sau neo tỉ lệ, độ trôi scale giữa các khung hình                                          |
| **(c) LiDAR fusion + mặt phẳng sàn** | Mục 6.4                                                                                                   | E2.c1: đo sai số khoảng cách (x,y) so với ground-truth, sai số ước lượng chiều cao `h`                                         | MAE khoảng cách, MAE chiều cao, tỷ lệ vật thể LiDAR "thấy" được (nằm trong góc quét, không bị che) |
| **Kết hợp (a)+(c) hoặc (b)+(c)**     | Dùng LiDAR làm tham chiếu ổn định, motion-stereo/mono-net làm nguồn chi tiết hình học khi robot di chuyển | E2.d1: so sánh kết hợp với từng ứng viên đơn lẻ                                                                                | Như trên, cộng thêm tỷ lệ frame "có đủ cả 2 nguồn"                                                 |

### 8.4 Tiêu chí chấp nhận `[PROPOSED — lead xác nhận]`

Giữ cấu trúc bảng như tài liệu stereo (mục 8.6 ở đó) nhưng **không đặt ngưỡng cố định ở đây** — phải chờ kết quả E2.a1–E2.d1 vì chưa rõ ứng viên nào sẽ là chính thức. Đề xuất ngưỡng tạm để so sánh giữa các ứng viên: `MAE ≤ 10% @ 1–2 m` là "đủ dùng", `MAE ≤ 20% @ 1–2 m` là "cần cải thiện nhưng dùng được với motion gating/LiDAR fallback".

### 8.5 Khi không đạt — checklist chẩn đoán

1. Nếu motion stereo kém: kiểm tra chất lượng EKF trước (đã có log sẵn từ hệ thống robot), không vội kết luận do thuật toán thị giác.
2. Nếu mono-net kém: kiểm tra neo tỉ lệ (điểm LiDAR dùng để neo có đúng không, có bị che khuất không).
3. Nếu LiDAR fusion kém: kiểm tra hiệu chuẩn ngoại camera↔LiDAR trước (sai lệch góc nhỏ gây sai lệch lớn ở xa).

---

## 9. RQ3 (giữ cấu trúc, đổi nguồn depth) — Kết hợp detection/segmentation với depth để ra vị trí 3D

Giữ nguyên toàn bộ thiết kế robust-aggregation, schema `Object3D`, và kế hoạch đánh giá của tài liệu stereo (mục 9), **chỉ thay** "disparity map từ stereo matching" bằng "1 trong 3 nguồn depth đã chọn ở RQ2 (mục 8.3)", và thêm trường `depth_source` vào `Object3D`. Vì nguồn depth giờ không phải lúc nào cũng là một bản đồ dày đặc (motion stereo/LiDAR fusion cho ra điểm thưa hơn disparity map), bước "lấy điểm trong mask" (mục 9.4 tài liệu stereo) cần xử lý trường hợp **số điểm hợp lệ trong mask có thể rất ít hoặc bằng 0** — khi đó trả về `Object3D` với `valid_ratio` thấp và cờ chất lượng, không suy diễn.

**Khác biệt về tiêu chí chấp nhận:** không đặt lại bảng số ở đây — phụ thuộc vào ứng viên depth được chọn ở RQ2; dùng cùng khung đo (sai số Z, X, Y, kích thước, recall vật cản, độ trễ) như tài liệu stereo mục 9.7.

---

## 10. RQ4–RQ5: điều cần chuẩn bị (không đổi về nguyên tắc)

Giống tài liệu stereo mục 10: cần TF `base_footprint → camera_link` đã hiệu chuẩn, `Object3D` có covariance/`depth_source`/`stamp` để data association. **Khác biệt:** vì phụ thuộc trực tiếp vào pose robot ngay từ RQ2/RQ3 (không chỉ RQ4), **chất lượng SLAM/EKF của robot ảnh hưởng tới pipeline nhận thức sớm hơn** so với phương án stereo.

---

## 11. Yêu cầu phi chức năng

Giữ nguyên các NFR của tài liệu stereo (mục 11 ở đó: tài nguyên, độ tin cậy, quan sát được, tái lập, không hardcode, an toàn). Bổ sung:

| ID     | Yêu cầu                                                                                                                     | Ngưỡng đề xuất                                                                                           |
| ------ | --------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| NFR-08 | Hiệu chuẩn ngoại camera↔LiDAR phải ổn định theo thời gian/rung                                                              | Kiểm tra định kỳ bằng vật mốc đã biết vị trí, tương tự kiểm tra vertical disparity trong tài liệu stereo |
| NFR-09 | Pipeline phải hoạt động (ở chế độ suy giảm — degraded mode) khi motion stereo không khả dụng (robot đứng yên hoặc chỉ xoay) | Tự động chuyển sang LiDAR fusion hoặc mono-net khi `B_virtual` ước lượng dưới ngưỡng                     |

---

## 12. Dữ liệu và ghi log

Giữ nguyên định dạng/quy ước của tài liệu stereo (mục 12 ở đó): rosbag2, đặt tên phiên, `session.yaml`. Bổ sung trường `depth_candidate_active` vào `session.yaml` để biết phiên log đang thử ứng viên nào.

---

## 13. Cấu trúc repo `[PROPOSED]`

```
mono_perception/
├─ docs/
├─ configs/              # capture_v*.yaml, calib_*.yaml, depth_candidate.yaml
├─ pi_capture_agent/      # chạy trên Pi 3 duy nhất — đơn giản hơn bản 2-Pi
├─ mono_ingest/           # ROS 2 package: nhận ảnh, phát Image/CameraInfo
├─ sync_eval/             # đo Δt ảnh↔pose/LiDAR
├─ mono_calib/            # hiệu chuẩn nội + ngoại camera↔LiDAR/base_footprint
├─ depth_engine/
│  ├─ motion_stereo/
│  ├─ mono_depth_net/
│  └─ lidar_fusion/
├─ object3d/              # detector/segmenter + robust aggregation (tái dùng thiết kế bản stereo)
├─ msgs/                  # Object3DArray (có depth_source), DepthCandidateMeta
├─ tools/
├─ experiments/
└─ tests/
```

---

## 14. Lộ trình đề xuất `[PROPOSED]`

| Pha                            | Nội dung                                                                                      | Điều kiện thoát                                                  |
| ------------------------------ | --------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| **P0 (tuần 1) — KHÔNG BỎ QUA** | E1.0 (spike H-00): Pcam 5C có chạy được trên Pi3 không                                        | Go/no-go; nếu no-go → mục 15 R-00 trước khi làm tiếp bất cứ gì   |
| **P1 (tuần 1–2)**              | Nếu go: dựng `pi_capture_agent` + `mono_ingest`; đo FPS/drop (E1.1); xác nhận H-01…H-06       | Có ảnh ổn định từ Pcam 5C trên ROS 2                             |
| **P2 (tuần 2–3)**              | Đo Δt ảnh↔pose/LiDAR (E1.2–E1.4); gate RQ1                                                    | Đạt 7.5                                                          |
| **P3 (tuần 3–4)**              | Hiệu chuẩn nội + ngoại camera↔LiDAR/base_footprint                                            | Reprojection error đạt mức tương đương tài liệu stereo (≤0.5 px) |
| **P4 (tuần 4–7)**              | Triển khai song song 3 ứng viên depth (E2.a1–E2.d1); họp lead chọn ứng viên chính thức (Q-02) | Có bảng so sánh 3 ứng viên                                       |
| **P5 (tuần 7–9)**              | RQ3: detector + aggregation với ứng viên đã chọn                                              | Báo cáo sai số theo 9.7 (tài liệu stereo)                        |

---

## 15. Sổ rủi ro

| ID       | Rủi ro                                                                                                               | Mức                          | Đối phó                                                                                                                                                                                                                                                                                                                                                       |
| -------- | -------------------------------------------------------------------------------------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **R-00** | **Pcam 5C không chạy được trên Raspberry Pi 3** (driver/overlay không có sẵn, hoặc trình tự nguồn `PWUP` không khớp) | **Cao — chặn toàn bộ dự án** | Spike sớm nhất có thể (E1.0); phương án dự phòng: (a) tìm/viết device-tree overlay cộng đồng cho `ov5640` trên Raspberry Pi kernel, (b) thử cắm Pcam 5C trực tiếp vào Jetson nếu L4T có driver OV5640, (c) nếu cả hai đều thất bại, quay lại phương án camera khác (IMX219 đơn, hoặc USB webcam tạm thời) để không chặn tiến độ nghiên cứu phần depth đơn mắt |
| R-01     | Motion stereo kém chính xác do EKF/odometry trượt bánh                                                               | Cao                          | Ưu tiên đoạn robot đi thẳng, tốc độ thấp cho calibration/đánh giá ban đầu; theo dõi log EKF                                                                                                                                                                                                                                                                   |
| R-02     | Mạng depth đơn mắt không giữ tỉ lệ ổn định theo thời gian/cảnh                                                       | TB                           | Luôn neo bằng LiDAR, không dùng độc lập                                                                                                                                                                                                                                                                                                                       |
| R-03     | LiDAR fusion bỏ sót vật không chạm sàn hoặc ngoài góc quét                                                           | TB                           | Ghi nhận rõ giới hạn, không claim "mọi vật thể" cho ứng viên này riêng lẻ                                                                                                                                                                                                                                                                                     |
| R-04     | Pi3 quá tải nếu phải debayer/ISP bằng phần mềm                                                                       | TB–Cao                       | Đo sớm (H-06); hạ độ phân giải/fps; cân nhắc gửi RAW10 thô về Jetson xử lý nếu Jetson có ISP phần cứng khả dụng, giảm tải cho Pi3                                                                                                                                                                                                                             |
| R-05     | Hiệu chuẩn ngoại camera↔LiDAR trôi theo rung/thời gian                                                               | TB                           | Cố định cơ khí; kiểm tra định kỳ bằng vật mốc                                                                                                                                                                                                                                                                                                                 |

---

## 16. Câu hỏi mở / quyết định cần lead

| ID   | Câu hỏi                                                                                                                                                                                                                  |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Q-01 | Xác nhận việc định nghĩa lại RQ1–RQ3 cho camera đơn (mục 0.1) có được chấp nhận như một hướng nghiên cứu song song/thay thế, hay chỉ là phương án dự phòng tạm thời chờ có đủ IMX219/Pi cho stereo?                      |
| Q-02 | Trong 3 ứng viên depth (motion stereo / mono-net / LiDAR fusion), ưu tiên đầu tư thời gian theo thứ tự nào? Có chấp nhận kết hợp (vd. mono-net + LiDAR neo tỉ lệ) làm phương án chính ngay từ đầu không?                 |
| Q-03 | Có ràng buộc về giấy phép/chi phí khi dùng một mạng ước lượng độ sâu đơn mắt pretrained (một số mô hình có giấy phép phi thương mại)? Việc chọn mô hình cụ thể nên để lúc triển khai (tránh lỗi thời) hay cần chốt ngay? |
| Q-04 | Nếu R-00 xảy ra (Pcam 5C không chạy được trên Pi3), ngân sách/thời gian cho phép thử phương án nào trong 3 phương án dự phòng ở mục 15?                                                                                  |
| Q-05 | T2 (yaw/hướng vật thể) có cần đưa vào phạm vi RQ3 ngay với camera đơn, hay tạm hoãn vì độ tin cậy thấp hơn đáng kể so với stereo (mục 3.3)?                                                                              |

---

## 17. Phụ lục

### 17.1 Công thức tham khảo nhanh

```
Motion stereo:     Z = f·B_virtual/d ;  B_virtual ≈ ∫v dt (EKF)
Sai số matching:   σ_Z ≈ Z²σ_d/(f·B_virtual)
Sai số pose:       σ_Z_pose ≈ Z·(σ_B/B_virtual)   ← nguồn sai số mới so với stereo
Sync-induced err:  δB ≈ v·Δt_sync ;  δθ ≈ ω·Δt_sync
LiDAR+ground-plane: h ≈ (y_top − y_bottom)·Z/f  (Z từ LiDAR)
```

### 17.2 Checklist trước mỗi phiên thu dữ liệu

- [ ] Xác nhận Pcam 5C đang ra ảnh ổn định trên Pi3 (không có lỗi driver lặp lại)
- [ ] `chronyc tracking` sạch giữa Pi3 và Jetson
- [ ] EKF đang chạy bình thường (không báo lỗi timeout sensor)
- [ ] Ghi rõ `depth_candidate_active` đang thử trong `session.yaml`
- [ ] Hiệu chuẩn ngoại camera↔LiDAR còn hiệu lực (chưa có va chạm/tháo lắp từ lần hiệu chuẩn gần nhất)

### 17.3 Thuật ngữ bổ sung (so với tài liệu stereo)

| Thuật ngữ                      | Nghĩa                                                                                                                             |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| Motion stereo / SfM            | Tam giác hóa độ sâu dùng chuyển động của chính camera/robot làm baseline, thay vì 2 camera cố định                                |
| Baseline ảo (`B_virtual`)      | Quãng đường robot di chuyển giữa 2 keyframe, ước lượng từ EKF                                                                     |
| Metric depth vs relative depth | Depth có đơn vị mét thật (metric) vs. depth chỉ đúng thứ tự xa/gần, không có tỉ lệ tuyệt đối (relative)                           |
| Scale anchoring (neo tỉ lệ)    | Dùng một tham chiếu khoảng cách đã biết (LiDAR, vật kích thước biết trước) để quy đổi relative depth thành metric depth           |
| Degraded mode                  | Chế độ pipeline hoạt động với nguồn depth dự phòng khi nguồn chính không khả dụng (ví dụ robot đứng yên → không có motion stereo) |

### 17.4 Nguồn tham chiếu

- Digilent — Pcam 5C Reference Manual và trang sản phẩm: thông số cảm biến OV5640, giao tiếp MIPI CSI-2 2 lane, đầu nối FFC 15 chân tương thích chân Raspberry Pi, và **tuyên bố rõ ràng của Digilent rằng họ chưa kiểm chứng và không hỗ trợ phần mềm cho việc dùng chung với Raspberry Pi**.
- Tài liệu/forum cộng đồng về driver `ov5640` trong nhân Linux mainline và các device-tree overlay cho nền tảng khác (TI AM62x Processor SDK, NXP i.MX8 kernel patches, Armbian/Allwinner H3) — dùng làm bằng chứng driver tồn tại nhưng cần tích hợp riêng cho từng nền tảng, không có sẵn cho Raspberry Pi OS.
- Báo cáo kỹ thuật Mobile Robot LiDAR (tài liệu đính kèm của dự án) — cấu hình EKF, Nav2, LiDAR, frames/topics (không đổi so với tài liệu stereo).
- `stereo_camera_module_PRD_SRS.md` và `RQ1_giai_phap_trigger_dong_ho.md` — tài liệu song song cho phương án 2 camera, dùng để đối chiếu khi cần.

_Hết tài liệu v0.1._
