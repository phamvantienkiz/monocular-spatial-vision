# Giải pháp Nhận thức 3D bằng Camera Đơn (Pcam 5C) — Không có LiDAR hỗ trợ

| Mục                        | Nội dung                                                                                                                                                                             |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Dự án                      | Mobile Robot LiDAR — ASIC Lab (camera dùng độc lập, không fusion LiDAR)                                                                                                              |
| Phần cứng                  | 1× Pcam 5C (OV5640, 5MP) + 1× Raspberry Pi 3 — **đã xác nhận chụp ảnh được**                                                                                                         |
| Quan hệ với tài liệu trước | Bổ sung/thay thế mục 8 (RQ2 — chiến lược depth) của `pcam5c_mono_module_PRD_SRS.md`, với ràng buộc mới: **không có LiDAR**, cụm camera cố định vị trí/chiều cao, có thể có IMU riêng |
| Nguồn lý thuyết            | Tổng hợp từ `Monocular_3D_Perception.md` (tài liệu người dùng cung cấp) và áp vào ràng buộc phần cứng thực tế của robot                                                              |
| Phiên bản                  | v0.1                                                                                                                                                                                 |

---

## 0. Ràng buộc đầu vào (nhắc lại để tài liệu tự đứng được)

| Ràng buộc                                                             | Ý nghĩa thiết kế                                                                                                                                                                                                                                                                                                                                                                                                             |
| --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Camera cố định vị trí, biết chiều cao lắp đặt, có thể cố định tiêu cự | Đây là **tài nguyên quý giá nhất** của bài toán — nó mở khóa trực tiếp nhóm phương pháp "ground-plane / homography" mà tài liệu nghiên cứu (mục 8) xác nhận là **rẻ nhất, nhanh nhất** (>60 FPS trên CPU thường) trong mọi phương pháp                                                                                                                                                                                       |
| Robot dẫn động vi sai, 2 bánh + 1 bánh tự do                          | Cho phép lấy chuyển động robot (từ encoder bánh, nếu có) làm nguồn ego-motion cho motion stereo/VIO, giống vai trò `/odometry/filtered` ở tài liệu stereo — nhưng ở đây module camera **độc lập**, nên cần tự quyết định có lấy odometry từ robot hay không (mục 6 bàn kỹ)                                                                                                                                                   |
| Cụm camera **có thể** trang bị IMU/gyro riêng                         | Đây là điểm khác biệt lớn nhất so với tài liệu PRD mono trước: một IMU gắn **ngay tại camera** (không qua cánh tay đòn cơ khí tới IMU chính của robot) cho phép đo trực tiếp vector trọng lực và vận tốc góc của chính camera — dùng để: (a) hiệu chỉnh liên tục góc pitch/roll cho mô hình ground-plane, (b) làm tham chiếu xoay cho motion stereo/VIO, (c) phát hiện rung/va chạm để tạm ngừng tin kết quả (motion gating) |
| **Không có LiDAR hỗ trợ**                                             | Loại bỏ hoàn toàn phương án "LiDAR fusion" đã đề xuất trong `pcam5c_mono_module_PRD_SRS.md` mục 8.3(c). Mọi "mỏ neo tỉ lệ" (scale anchor) giờ phải đến từ: (1) hình học mặt phẳng sàn + chiều cao/góc camera đã biết, hoặc (2) kích thước vật lý đã biết của vật thể, hoặc (3) tri thức học sâu (mạng depth đơn mắt có pretrained trên dữ liệu đa dạng) — đúng 3 "ngõ" mà tài liệu nghiên cứu chỉ ra ở mục 16 của nó         |

**Nguyên lý xuyên suốt tài liệu này** (trích thẳng từ tài liệu nghiên cứu, mục 1 và 16): _monocular vision không thể tự phá vỡ scale ambiguity — mọi phép đo mét (metric) đều phải vay mượn tri thức từ bên ngoài hình ảnh thuần túy._ Thiết kế dưới đây là việc chọn và kết hợp đúng các "khoản vay" đó sao cho phù hợp với những gì robot **thực sự có** (không có LiDAR, nhưng có chiều cao camera cố định và có thể có IMU riêng).

---

## 1. Kiến trúc tổng thể — kết hợp nhiều lớp (như bạn đã lường trước)

```
┌──────────────────────────────────────────────────────────────────────┐
│ LỚP E — Phát hiện chướng ngại tổng quát (không cần phân loại)         │
│   Phân vùng "sàn / không phải sàn" (free-space segmentation)          │
│   → chiếu vùng không-phải-sàn qua Homography (Lớp A) ra tọa độ sàn    │
├──────────────────────────────────────────────────────────────────────┤
│ LỚP D — Tinh chỉnh khi robot di chuyển (temporal / motion stereo)     │
│   Baseline ảo từ chuyển động robot + xoay đo bằng IMU riêng của cam   │
├──────────────────────────────────────────────────────────────────────┤
│ LỚP C — Mạng ước lượng độ sâu đơn mắt (cho vật không chạm sàn/bị che) │
│   Relative hoặc metric depth model → NEO TỈ LỆ bằng Lớp A (không có  │
│   LiDAR để neo như phương án trước)                                   │
├──────────────────────────────────────────────────────────────────────┤
│ LỚP B — Kích thước vật lý đã biết (known-object-size)                 │
│   Z = f·H/h — dùng làm cross-check cho Lớp A, và làm nguồn chính khi  │
│   vật không chạm sàn (vd. vật trên bàn, biển báo treo)                │
├──────────────────────────────────────────────────────────────────────┤
│ LỚP A (NỀN TẢNG, LUÔN CHẠY) — Ground-plane / Inverse Perspective      │
│   Mapping (IPM) dùng chiều cao hc + góc pitch θ đã biết               │
│   Hiệu chỉnh liên tục góc pitch/roll bằng accelerometer riêng (nếu có)│
└──────────────────────────────────────────────────────────────────────┘
```

**Vì sao xếp theo thứ tự này:** Lớp A là lớp **rẻ nhất, tin cậy nhất với dữ liệu đã có** (chiều cao/góc cố định) nên làm nền tảng và cũng làm "mỏ neo tỉ lệ" cho mọi lớp phía trên — đúng vai trò mà LiDAR đã làm trong phương án trước, nay do hình học đảm nhiệm. Các lớp B–E không thay thế Lớp A mà **mở rộng phạm vi áp dụng** của nó (vật không chạm sàn, vật lạ, khi robot di chuyển, chướng ngại không phân loại được).

---

## 2. Lớp A — Ground-plane / Homography (nền tảng)

### 2.1 Nguyên lý

Theo tài liệu nghiên cứu (mục 8): mặt phẳng đất được biểu diễn `n^T·P_W + d = 0`, phép chiếu từ mặt đất 3D lên ảnh 2D là một **ma trận Homography H (3×3)**. Nghịch đảo `p_ground = H⁻¹ · p_image` cho tọa độ thực (bird's-eye view) từ bất kỳ pixel đáy vật thể nào.

Ở dạng đơn giản hơn (khi chỉ cần khoảng cách dọc trục quang, không cần bản đồ đầy đủ), dùng công thức lượng giác trực tiếp với chiều cao camera `h_c`, góc cúi (pitch) `θ`, và tọa độ pixel dọc `v` của điểm chạm đất:

```
Z ≈ h_c / tan(θ + α(v))        với α(v) = arctan((v - c_y) / f_y)
```

(góc `α(v)` là góc lệch của tia nhìn tại hàng pixel `v` so với trục quang, suy từ nội hàm camera `f_y, c_y`).

### 2.2 Yêu cầu dữ liệu

| Tham số                                           | Nguồn                                                                                 | Trạng thái                                              |
| ------------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| `f_x, f_y, c_x, c_y`, hệ số méo                   | Hiệu chuẩn nội camera (ChArUco/checkerboard, quy trình giống tài liệu stereo mục 8.2) | `[TBD]` cần làm                                         |
| `h_c` (chiều cao lắp camera so với sàn)           | Đo cơ khí trực tiếp                                                                   | `[TBD]` — bạn nói đã biết, cần ghi số cụ thể vào config |
| `θ` (góc pitch lắp đặt)                           | Đo cơ khí, hoặc tính từ 1 ảnh checkerboard đặt trên sàn ở khoảng cách đã biết         | `[TBD]`                                                 |
| `φ` (góc roll — camera có bị nghiêng ngang không) | Lý tưởng = 0 nếu lắp cẩn thận; nên đo để loại trừ                                     | `[TBD]`                                                 |

### 2.3 Vai trò của IMU riêng của camera (nếu được trang bị) — điểm khác biệt quan trọng nhất

Tài liệu nghiên cứu (mục 8) chỉ rõ điểm yếu chí mạng của phương pháp ground-plane: _"trong thực tế chuyển động, gia tốc của xe khiến góc pitch dao động mạnh... phá vỡ giả định tĩnh của ma trận biến đổi, đòi hỏi bù trừ ngoại hàm liên tục (online extrinsic calibration) thường qua phân tích đường chân trời hoặc bộ lọc Kalman kết hợp cảm biến gia tốc."_ — **đây chính xác là việc một IMU gắn ngay tại cụm camera có thể giải quyết tốt hơn nhiều so với dùng IMU chính của robot (vốn cách xa qua một cánh tay đòn cơ khí, nên quan hệ hình học với chuyển động sóc/rung của chính camera là gián tiếp):**

- **Accelerometer** đo trực tiếp vector trọng lực tại camera → suy ra góc pitch/roll **tức thời, thực tế** (khác với `θ` cố định đo một lần lúc lắp đặt) → cập nhật `H` (hoặc `θ` trong công thức 2.1) theo thời gian thực, bù rung khi robot đi qua gờ nhỏ, khi tăng/giảm tốc đột ngột.
- **Gyroscope** đo vận tốc góc tức thời của camera → dùng làm tín hiệu "motion gating": khi `|ω_cam|` vượt ngưỡng (rung mạnh, va chạm), tạm đánh dấu kết quả Lớp A có độ tin cậy thấp thay vì báo sai.
- Kết hợp accelerometer + gyro qua một **bộ lọc bù (complementary filter) hoặc Kalman đơn giản** chạy ngay trên Pi3 hoặc trên Jetson → cho ra `θ(t), φ(t)` mượt, cập nhật liên tục — đây là "online extrinsic calibration" mà tài liệu nghiên cứu khuyến nghị, giờ khả thi với phần cứng bạn có.

**Khuyến nghị:** nếu có thể chọn loại IMU, ưu tiên một IMU 6 trục (accelerometer + gyro) giá rẻ (vd. MPU6050/MPU9250 hoặc tương đương) gắn cứng trực tiếp lên khung/vỏ của cụm camera (cùng một khối cơ khí, không qua khớp nối lỏng), kết nối I2C về chính Pi3 để timestamp đi kèm luôn với từng frame ảnh — tránh vấn đề đồng bộ thời gian riêng biệt.

### 2.4 Lan truyền sai số (theo công thức tài liệu nghiên cứu, mục 11)

```
ΔZ ∝ Z² · Δh        (Δh: sai số pixel xác định điểm chạm đất)
```

Nghĩa là: **sai số xác định đúng hàng pixel nơi vật chạm sàn** (do bbox/mask không chính xác, hoặc vật bị che một phần ở đáy) là nguồn sai số nguy hiểm nhất, khuếch đại theo bình phương khoảng cách — giống hệt cơ chế đã nêu trong tài liệu stereo (mục 6.1) nhưng ở đây áp dụng cho điểm chạm đất thay vì disparity. **Hệ quả thiết kế:** cần ưu tiên instance segmentation (mask) hơn bounding box để xác định chính xác điểm chạm đất thấp nhất, và cần xử lý riêng trường hợp vật bị che khuất ở đáy (occlusion) — khi đó Lớp A **không dùng được**, phải chuyển sang Lớp B hoặc C.

### 2.5 Khi nào Lớp A thất bại

- Vật thể không chạm sàn (nằm trên bàn/kệ, treo trên tường, một phần cơ thể người giơ tay).
- Đáy vật bị che khuất bởi vật khác ở phía trước.
- Sàn không phẳng tuyệt đối (ngưỡng cửa, dốc nhỏ, thảm dày) — tài liệu nghiên cứu gọi đây là nguyên nhân "phá sản hoàn toàn" của phương pháp này nếu không bù trừ.
- Pitch/roll tức thời lệch khỏi giá trị đã hiệu chuẩn mà không có IMU để bù (nếu không trang bị IMU riêng, đây là rủi ro thường trực).

→ Đây chính là lý do cần Lớp B và C.

---

## 3. Lớp B — Kích thước vật lý đã biết (known-object-size)

### 3.1 Công thức (từ tài liệu nghiên cứu, mục 4 và 11)

```
Z = f · H_real / h_pixel
ΔZ ∝ Z² · Δh_pixel          (cùng dạng khuếch đại như Lớp A)
```

### 3.2 Khi dùng

- Vật thuộc lớp đã biết kích thước trung bình đáng tin cậy (ví dụ: cửa, bàn ghế tiêu chuẩn, con người ước lượng chiều cao trung bình) **và không chạm sàn trong khung hình** (nên Lớp A không dùng được) — đây là trường hợp bổ sung trực tiếp cho điểm yếu của Lớp A.
- Dùng làm **cross-check** cho Lớp A khi cả hai đều tính được: nếu hai kết quả lệch nhau nhiều, đánh dấu độ tin cậy thấp thay vì chọn bừa một trong hai.

### 3.3 Hạn chế cần lưu ý (đúng như tài liệu nghiên cứu cảnh báo)

- Vật xoay góc (pitch/yaw khác 0 so với mặt phẳng ảnh) làm `h_pixel` biểu kiến nhỏ hơn thật → tính ra khoảng cách xa hơn thực tế. Với vật "lạ" không rõ hướng xoay, nên dùng giá trị `H_real` là cận trên (kích thước lớn nhất có thể theo hướng quan sát) để tránh đánh giá xa hơn mức an toàn (thiên về thận trọng cho né vật cản).
- Phương pháp **sụp đổ hoàn toàn** khi vật bị cắt xén (truncation) ở viền ảnh hoặc bị che khuất một phần — không có cách bù, chỉ có thể hạ độ tin cậy.

---

## 4. Lớp C — Mạng ước lượng độ sâu đơn mắt (neo tỉ lệ bằng Lớp A, không dùng LiDAR)

### 4.1 Vai trò

Lấp khoảng trống của Lớp A/B: vật lạ (không rõ class/kích thước), vật không chạm sàn, cảnh có nhiều vật chồng lấn. Theo tài liệu nghiên cứu (mục 4, mục 9 bảng Hybrid): các mô hình nền tảng hiện đại (Metric3D v2, UniDepthV2, Depth Anything V2) cho **zero-shot metric depth** khá tốt, nhưng vẫn có "trôi dạt tỷ lệ ở vùng viền ảnh" và cần tài nguyên tính toán đáng kể.

### 4.2 Vấn đề tỉ lệ khi không có LiDAR để neo

Phương án PRD trước (có LiDAR) dùng khoảng cách LiDAR tại vài điểm làm mỏ neo cho depth map tương đối. **Không có LiDAR, Lớp A (ground-plane) đóng vai trò mỏ neo thay thế:**

- Với các pixel mà Lớp A tính được khoảng cách tin cậy (vật chạm sàn, không bị che, pitch đã hiệu chỉnh bằng IMU) → dùng các giá trị này làm **điểm neo** để co giãn/hiệu chỉnh affine đầu ra của mạng depth (vốn thường chỉ đúng tới một phép biến đổi affine `Z_metric = a·Z_relative + b` đối với model chỉ cho relative depth, hoặc chỉ cần hiệu chỉnh độ lệch nhỏ nếu model đã là "metric" nhưng bị lệch theo camera/điều kiện ánh sáng).
- Nếu trong khung hình **không có điểm neo nào** (toàn bộ sàn bị che, ví dụ phòng chật) → hạ độ tin cậy toàn bộ output Lớp C của khung hình đó, không công bố số liệu mét tuyệt đối, chỉ giữ thứ tự xa/gần tương đối.

### 4.3 Lựa chọn mô hình — không chốt tên cụ thể

`[TBD — Q-03]` Tài liệu nghiên cứu liệt kê Depth Anything V2 (bản Small, ~24.8M tham số, chạy tốt qua OpenVINO/TensorRT) là ứng viên nhẹ nhất cho biên (edge). Vì tốc độ phát triển lĩnh vực này rất nhanh, **không chốt tên mô hình trong tài liệu** — tại thời điểm triển khai, so sánh lại các mô hình metric-depth nhẹ hiện có, ưu tiên: (a) có bản lượng tử hóa INT8/FP16 chạy được qua TensorRT trên Jetson, (b) có hỗ trợ "metric" (không chỉ relative) để giảm việc phải tự ước lượng affine neo tỉ lệ.

### 4.4 Chi phí tính toán

Theo tài liệu nghiên cứu (mục 15): cần FP16/INT8 trên Jetson qua TensorRT để đạt thời gian thực — nên chạy Lớp C ở tần số thấp hơn Lớp A/B (ví dụ 2–5 Hz thay vì mỗi frame), dùng kết quả Lớp A/B cho các frame xen giữa, vì Lớp A/B rẻ hơn nhiều bậc.

---

## 5. Lớp D — Motion stereo / VIO nhẹ dùng chuyển động robot + IMU riêng của camera

### 5.1 Nguyên lý

Theo tài liệu nghiên cứu (mục 10): _"monocular video thuần túy không thể tự giải quyết scale ambiguity"_ — quỹ đạo SLAM đơn kính (kiểu ORB-SLAM3) chỉ "up-to-scale" và bị trôi tỷ lệ theo thời gian, **trừ khi lai ghép với Visual-Inertial Odometry (VIO) hoặc Wheel Odometry**. Ở đây robot có cả hai nguồn khả dụng:

- **Wheel odometry** (từ encoder bánh dẫn động vi sai, nếu có trên robot/module này — `[TBD]` xác nhận module camera độc lập này có nhận được tín hiệu wheel odometry của robot hay không, vì bạn nói "cụm camera là độc lập") → cho quãng đường tịnh tiến trực tiếp, đúng vai trò mục 10.2 của tài liệu nghiên cứu.
- **IMU riêng của camera** (nếu trang bị) → cho tham chiếu xoay (gyro) và hướng trọng lực (accelerometer) **ngay tại điểm quan sát**, không qua sai số cánh tay đòn cơ khí như khi dùng IMU chính của robot.

Kết hợp hai nguồn này theo đúng công thức motion stereo đã trình bày trong `pcam5c_mono_module_PRD_SRS.md` (mục 6.1): `Z = f·B_virtual/d`, với `B_virtual` ước lượng từ wheel odometry, và **góc xoay dùng để rectify cặp keyframe lấy từ gyro riêng của camera** (chính xác hơn lấy từ EKF toàn robot, vì không có độ trễ/sai số truyền qua TF).

### 5.2 Khác biệt quan trọng nếu module camera THỰC SỰ độc lập (không có cả wheel odometry)

Nếu "độc lập" nghĩa là module camera **không nhận được bất kỳ tín hiệu nào từ robot** (kể cả wheel odometry), thì không còn nguồn đo tịnh tiến đáng tin cậy nào — chỉ còn IMU riêng của camera, mà **gia tốc kế không thể tích phân hai lần ra vị trí đủ chính xác** (trôi rất nhanh, đây là hạn chế vật lý nổi tiếng của IMU thuần túy, được chính tài liệu nghiên cứu ngầm xác nhận khi nói VIO cần "kết hợp" IMU chứ IMU đơn thuần không đủ). Trong trường hợp này:

- **Lớp D nên bị vô hiệu hóa hoặc hạ xuống vai trò rất phụ** (chỉ dùng gyro cho motion gating/bù rung ở Lớp A, không dùng để tính baseline ảo).
- `[TBD — Q-01, câu hỏi quan trọng nhất của tài liệu này]`: cần làm rõ với lead/nhóm phần cứng — "độc lập" có nghĩa là không có LiDAR, hay hoàn toàn không có bất kỳ tín hiệu nào (kể cả wheel odometry) từ robot? Câu trả lời quyết định Lớp D có khả thi hay không.

### 5.3 Khi khả thi

Nếu có wheel odometry (dù không có LiDAR): Lớp D hoạt động như mô tả ở PRD mono trước, với điểm cộng là góc xoay chính xác hơn nhờ gyro tại chỗ. Áp dụng khi robot tịnh tiến thực sự (không chỉ xoay tại chỗ), dùng để tinh chỉnh/kiểm tra chéo kết quả Lớp A/C ở khoảng cách xa hơn (nơi Lớp A nhạy với sai số góc, mục 2.4).

---

## 6. Lớp E — Phát hiện chướng ngại tổng quát không cần phân loại (free-space segmentation)

### 6.1 Vì sao cần lớp này riêng

Lớp B (known-size) và phần lớn mô hình depth/detection hiện đại (Lớp C) đều **thiên về vật thể đã có trong tập huấn luyện**. Với "chướng ngại" bất kỳ (hộp lạ, dây điện, vật rơi vãi) — đúng điều bạn hỏi ("xác định... chướng ngại hay không") — cách tiếp cận đáng tin cậy và rẻ nhất là **không cố phân loại vật thể, mà phân loại điểm ảnh "có phải là sàn hay không"**.

### 6.2 Cách làm (cổ điển, không bắt buộc deep learning)

- Phân vùng sàn bằng đặc trưng màu sắc/kết cấu đơn giản (sàn trong nhà thường đồng nhất màu/texture) — có thể dùng một mô hình phân đoạn nhị phân nhẹ ("floor vs non-floor") nếu cần độ bền vững cao hơn trước ánh sáng thay đổi.
- Với mỗi cột pixel, tìm hàng thấp nhất **không thuộc sàn** → đây là "điểm chạm đất nghi ngờ có vật cản" tại cột đó.
- Chiếu điểm này qua Homography của Lớp A → ra tọa độ (x, y) trên mặt sàn → tạo một "bản đồ chướng ngại" dạng top-down tương tự cách LiDAR 2D vẫn làm, nhưng bằng camera.

### 6.3 Ưu điểm trong bối cảnh không có LiDAR

Đây là kỹ thuật **gần nhất thay thế được vai trò "phát hiện vật cản bất kỳ" mà LiDAR vốn làm tốt** — không cần biết vật là gì, chỉ cần biết "có gì đó nhô lên khỏi sàn tại vị trí này". Kết hợp trực tiếp với Lớp A (dùng chung Homography), chi phí tính toán thấp.

### 6.4 Hạn chế

Thừa hưởng mọi điểm yếu của Lớp A (mục 2.5): sàn không phẳng, pitch dao động không bù được nếu thiếu IMU, vật trong suốt/phản chiếu mạnh (gương, sàn ướt) có thể bị phân loại sai là "sàn" hoặc ngược lại — tài liệu nghiên cứu liệt kê đây là "tử huyệt" chung của mọi phương pháp quang học (mục 14).

---

## 7. Bảng khả thi theo khoảng cách (điều chỉnh theo bối cảnh robot trong nhà)

Tài liệu nghiên cứu (mục 14) đưa ra bảng theo khoảng cách cho bối cảnh tổng quát (bao gồm cả ô tô tự hành); điều chỉnh lại cho bối cảnh robot trong nhà (0.3–3 m, giống phạm vi vận hành đã đặt ở các tài liệu PRD trước):

| Khoảng cách | Lớp nào đáng tin cậy nhất                                                       | Sai số kỳ vọng `[ASSUMPTION — cần đo thực tế]`                                                                                                                                                                                                                            |
| ----------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0.3–1 m     | Lớp B (known-size) nếu vật đủ gần để chiếm nhiều pixel; Lớp A nếu chạm sàn rõ   | Theo tài liệu nghiên cứu, cự ly 0.5–2 m có thể đạt sai số mm nếu điều kiện lý tưởng (keypoint dày đặc) — nhưng đó là bối cảnh thao tác tay robot (PnP+CAD), không áp dụng trực tiếp cho detection+ground-plane; với Lớp A/B ở cự ly này kỳ vọng thực tế hơn: sai số vài % |
| 1–2 m       | Lớp A (nền tảng chính) + Lớp C cross-check                                      | 2–5% theo tài liệu nghiên cứu cho bối cảnh "robot di động trong nhà", với điều kiện có "SLAM hoặc ground-plane phụ trợ để hiệu chỉnh" — đúng kiến trúc Lớp A+D đề xuất ở đây                                                                                              |
| 2–3 m       | Lớp A (nhạy cảm hơn với sai số góc θ, mục 2.4) + Lớp D nếu robot đang di chuyển | Cao hơn 1–2m, cần đo thực nghiệm; đây là biên giới hợp lý để đặt ngưỡng tin cậy tối thiểu                                                                                                                                                                                 |
| >3 m        | Không khuyến nghị dùng làm số liệu điều khiển né vật cản chính xác              | Theo tài liệu nghiên cứu, sai số tăng theo hàm mũ ngoài phạm vi này; chỉ nên dùng cho "có/không có vật thể" (Lớp E), không dùng cho khoảng cách chính xác                                                                                                                 |

---

## 8. Các kịch bản hỏng hóc cần xử lý tường minh (theo tài liệu nghiên cứu, mục 14)

| Kịch bản                                               | Ảnh hưởng tới lớp nào          | Cách xử lý đề xuất                                                                                                                                                        |
| ------------------------------------------------------ | ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Thiếu sáng / ban đêm                                   | Mọi lớp (quang học nói chung)  | Hạ độ tin cậy toàn hệ thống khi đo được độ sáng cảnh thấp hơn ngưỡng; cân nhắc đèn hỗ trợ nếu môi trường vận hành có lúc tối                                              |
| Bề mặt phản chiếu/trong suốt (sàn ướt, kính, gương)    | Lớp A, E (nhầm "sàn")          | Không có giải pháp quang học thuần túy triệt để; ghi nhận là giới hạn đã biết, dựa vào motion gating + cảm biến va chạm vật lý (bumper) làm lưới an toàn cuối cùng nếu có |
| Che khuất đáy vật (occlusion)                          | Lớp A (mất điểm chạm đất)      | Chuyển sang Lớp B/C, hạ độ tin cậy                                                                                                                                        |
| Sàn gồ ghề/dốc nhỏ, rung khi di chuyển                 | Lớp A, E                       | Bù bằng IMU riêng (mục 2.3) — đây là lý do IMU riêng cho cụm camera **có giá trị cao** trong thiết kế này                                                                 |
| Vật kích thước dị biệt (không giống trung bình đã học) | Lớp B, Lớp C (mô hình học sâu) | Luôn ưu tiên Lớp A khi vật chạm sàn (không phụ thuộc kích thước); với vật không chạm sàn và kích thước lạ, chấp nhận độ tin cậy thấp, không suy diễn liều lĩnh            |

---

## 9. Kế hoạch đánh giá (rút gọn, bổ sung cho tài liệu PRD mono)

| ID                                    | Thí nghiệm                                                                                                                             | Mục đích                                                                 |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| M1                                    | Hiệu chuẩn nội camera + đo `h_c, θ, φ` thực tế                                                                                         | Tham số nền cho Lớp A                                                    |
| M2                                    | Nếu có IMU riêng: hiệu chuẩn offset accelerometer/gyro, kiểm tra bộ lọc bù cho `θ(t), φ(t)` khi robot đứng yên vs di chuyển qua gờ nhỏ | Xác nhận mục 2.3 hoạt động đúng                                          |
| M3                                    | Đo sai số Lớp A theo khoảng cách (0.3–3 m), vật chạm sàn, so với ground-truth thước/laser                                              | Bảng MAE/RMSE theo Z, đối chiếu mục 7                                    |
| M4                                    | Đo sai số Lớp A khi robot di chuyển (rung thật) có/không bù IMU                                                                        | Định lượng lợi ích của IMU riêng (mục 2.3)                               |
| M5                                    | Đo sai số Lớp B cho vài lớp vật thể kích thước chuẩn                                                                                   | So sánh với Lớp A trên cùng vật (khi vật chạm sàn, dùng làm cross-check) |
| M6                                    | Thử nghiệm Lớp C (mô hình depth chọn tại thời điểm triển khai), đo hiệu quả neo tỉ lệ bằng Lớp A so với không neo                      | Xác nhận mục 4.2                                                         |
| M7 (chỉ nếu Lớp D khả thi — xem Q-01) | Đo chất lượng motion stereo dùng wheel odom + gyro riêng vs chỉ wheel odom                                                             | Định lượng lợi ích gyro riêng cho rectify                                |
| M8                                    | Đánh giá Lớp E trên vài vật "lạ" không thuộc tập lớp đã huấn luyện                                                                     | Recall phát hiện chướng ngại tổng quát                                   |

---

## 10. Câu hỏi cần làm rõ (quan trọng, ảnh hưởng trực tiếp tới kiến trúc)

| ID                         | Câu hỏi                                                                                                                                                                                                                                       |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Q-01 (quan trọng nhất)** | "Cụm camera độc lập, không được hỗ trợ bởi LiDAR" — có nghĩa là độc lập hoàn toàn với mọi tín hiệu robot (kể cả wheel odometry), hay chỉ riêng không có LiDAR? Câu trả lời quyết định Lớp D (mục 5) có khả thi hay phải loại bỏ.              |
| Q-02                       | Nếu có trang bị IMU riêng cho cụm camera: loại cảm biến cụ thể là gì (chỉ gyro, chỉ accelerometer, hay 6/9 trục đầy đủ)? Gắn cứng trực tiếp lên khối camera hay qua một giá đỡ có thể rung lắc độc lập?                                       |
| Q-03                       | Có ràng buộc về mô hình depth đơn mắt pretrained được phép dùng (giấy phép, kích thước model tối đa chạy được trên phần cứng) không, hay để quyết định lúc triển khai?                                                                        |
| Q-04                       | Giá trị `h_c` (chiều cao lắp) và `θ` (góc pitch) cụ thể là bao nhiêu — cần số liệu thật để tính bảng sai số định lượng thay vì `[ASSUMPTION]` ở mục 7?                                                                                        |
| Q-05                       | Có chấp nhận việc hệ thống trả về "độ tin cậy thấp, không đưa ra số liệu mét" trong các trường hợp thất bại (mục 8) thay vì luôn cố đưa ra một con số, hay cần một giá trị fallback mặc định cho các tầng điều khiển phía sau (Nav2/costmap)? |

---

## 11. Tham khảo

- `Monocular_3D_Perception.md` (tài liệu người dùng cung cấp) — toàn bộ cơ sở lý thuyết: pinhole model, ground-plane/homography, known-object-size, các mô hình metric depth nền tảng (Metric3D v2, UniDepthV2, Depth Anything V2), PnP/EPnP/SQPnP, VIO/wheel odometry cho SLAM đơn kính, phân tích lan truyền sai số `ΔZ ∝ Z²Δh`, bảng khả thi theo khoảng cách, các kịch bản hỏng hóc.
- `pcam5c_mono_module_PRD_SRS.md` — tài liệu PRD/SRS gốc cho phương án camera đơn (có giả định LiDAR fusion, nay được thay thế một phần bởi tài liệu này cho kịch bản không-LiDAR).
- `stereo_camera_module_PRD_SRS.md`, `RQ1_giai_phap_trigger_dong_ho.md` — tài liệu song song cho phương án 2 camera, dùng đối chiếu công thức lan truyền sai số và cấu trúc tài liệu.

_Hết tài liệu v0.1._
