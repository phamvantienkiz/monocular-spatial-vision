# KHUNG CÂU HỎI NGHIÊN CỨU (RQ PIPELINE), YÊU CẦU ĐÁNH GIÁ VÀ TIÊU CHÍ NGHIỆM THU MODULE CAMERA ĐƠN CHO MOBILE ROBOT

| Thuộc tính | Chi tiết kỹ thuật |
| :--- | :--- |
| **Dự án** | Mobile Robot LiDAR — Module Camera Đơn Pcam 5C (Monocular 3D Perception) |
| **Nền tảng phần cứng** | 1× Digilent Pcam 5C (OmniVision OV5640) + 1× Raspberry Pi 3 + 1× IMU MPU6050 + 1× Jetson AGX Xavier 16GB |
| **Hệ thống phần mềm** | Linux V4L2/libcamera, JetPack 5.x / TensorRT FP16, ROS 2 Foxy, Nav2 |
| **Tài liệu tham chiếu gốc** | Khung RQ Stereo (`resources/Mobile Robot/3DSpaceCamera/images/RQ-pipeline.jpg`) và PRD Module Stereo |
| **Mục đích tài liệu** | Xác lập chuỗi câu hỏi nghiên cứu định hướng (RQ Pipeline), quy định bộ yêu cầu kỹ thuật (FR & NFR), và thiết lập bộ tiêu chuẩn nghiệm thu định lượng (Acceptance Criteria / Decision Gates) làm chuẩn mực đo lường cho toàn bộ chu kỳ phát triển module. |
| **Vị trí lưu trữ** | `implementations/single-cam/ai/06_MONOCULAR_RQ_PIPELINE_AND_ACCEPTANCE_CRITERIA.md` |

---

## 1. Bảng Khung Câu Hỏi Nghiên Cứu (RQ Pipeline) Cho Camera Đơn

Kế thừa và chuyển đổi từ mô hình nghiên cứu Stereo Camera (`RQ-pipeline.jpg`), bài toán camera đơn loại bỏ việc đồng bộ hai camera độc lập và đo chiều sâu từ disparity song song. Thay vào đó, nó đối mặt với rào cản toán học cốt lõi: **Sự mất mát thang đo mét (Scale Ambiguity)** và **Sự lan truyền sai số góc nghiêng**.

Chuỗi câu hỏi nghiên cứu (Research Questions - RQ) được sắp xếp tuần tự theo sự phụ thuộc nhân quả hình học và kiến trúc hệ thống:

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  RQ0    │ ──> │  RQ1    │ ──> │  RQ2    │ ──> │  RQ3    │ ──> │  RQ4    │ ──> │  RQ5    │
│ Hardware│     │ Sync &  │     │ Calib & │     │ 2D-to-3D│     │ TF &    │     │ Sensor  │
│ Driver  │     │ Telemetry     │ Metric  │     │ Bounding│     │ Semantic│     │ Fusion &│
│ Bringup │     │ Latency │     │ Depth   │     │ Box     │     │ Memory  │     │ Active  │
└─────────┘     └─────────┘     └─────────┘     └─────────┘     └─────────┘     └─────────┘
```

### Bảng Câu Hỏi Nghiên Cứu Tuần Tự (RQ Pipeline Matrix)

| Mã RQ | Câu hỏi nghiên cứu (Research Question) | Đầu ra phải đo được (Measurable Outputs) | Cổng quyết định (Decision Gate) |
| :---: | :--- | :--- | :--- |
| **RQ0** | Làm thế nào để kích hoạt driver nhân Linux V4L2 cho Pcam 5C (OV5640) trên Raspberry Pi 3 và truyền luồng video về Jetson AGX Xavier với băng thông và FPS ổn định? | • Trạng thái nhận diện `/dev/video0`<br>• FPS đo đạc thực tế tại độ phân giải $1280 \times 720$<br>• Tỉ lệ rớt khung hình (dropped-frame rate)<br>• Băng thông truyền dẫn (Mbps) | **Nếu không ra được `/dev/video0` hoặc FPS $< 20$:**<br>Kiểm tra cáp FFC 15-pin (đảo chiều tiếp xúc), cấu hình `dtoverlay=ov5640` trong boot config, phân bổ bộ nhớ GPU `gpu_mem=128`, chuyển từ định dạng thô YUYV sang nén phần cứng MJPEG/H.264. |
| **RQ1** | Làm thế nào đồng bộ thời gian (Time Synchronization) giữa luồng ảnh từ Pcam 5C với dữ liệu telemetry góc nghiêng của IMU MPU6050 trên Pi 3 và chuyển động của robot trên Jetson? | • Độ lệch thời gian $\Delta t$ giữa frame ảnh và mẫu IMU (ms)<br>• Jitter truyền thông mạng LAN giữa Pi 3 và Jetson<br>• Trôi dạt đồng hồ hệ thống (clock drift)<br>• Độ trễ toàn trình Glass-to-Jetson (Latency ms) | **Nếu $\Delta t > 20\text{ ms}$ hoặc Jitter $> 10\text{ ms}$:**<br>Đóng gói trực tiếp mẩu tin IMU vào header của frame ảnh ngay tại Pi 3 trước khi gửi socket TCP; kích hoạt giao thức đồng bộ đồng hồ PTP (IEEE 1588) hoặc Chrony qua mạng Ethernet có dây trực tiếp. |
| **RQ2** | Làm thế nào hiệu chuẩn nội hàm camera đơn và tái tạo khoảng cách hệ mét ($Z$) chính xác khi không có baseline stereo vật lý? | • Sai số tái chiếu nội hàm (Reprojection Error RMS)<br>• Độ ổn định góc chúc pitch $\theta$ và roll $\phi$ đo bằng MPU6050<br>• Sai số khoảng cách tuyệt đối và tương đối (MAE, RMSE, AbsRel theo các mốc từ $0.5\text{m} \rightarrow 5.0\text{m}$) | **Nếu AbsRel $> 5\%$ trong cự ly $0.5 - 2.5\text{m}$:**<br>Kiểm tra lại chiều cao lắp đặt cơ khí $h_c$; kiểm tra méo thấu kính ngoại vi; hiệu chuẩn lại bias tĩnh của gia tốc kế MPU6050; nếu do rung lắc, kích hoạt bộ lọc bù (Complementary Filter) $\theta(t)$. |
| **RQ3** | Làm thế nào kết hợp mạng phát hiện 2D / Instance Segmentation với hình học chiếu ngược để xác định tọa độ $(X, Y, Z)$, kích thước $(W, H, D)$ và 3D Bounding Box của vật thể? | • Sai lệch điểm chạm sàn $\Delta v_{\text{contact}}$ giữa 2D Bbox và Mask (px)<br>• Sai số kích thước vật lý $(W, H, D)$ so với thước đo chuẩn<br>• Tỉ lệ chồng lấp thể tích 3D (3D IoU / Volume Discrepancy)<br>• Tốc độ suy luận (Throughput FPS) trên Jetson Xavier | **Nếu điểm chạm sàn $v_{\text{contact}}$ bị trôi $> 5\text{ px}$ do bóng đổ hoặc chân ghế rỗng:**<br>Bắt buộc chuyển sang dùng mặt nạ phân đoạn thực thể (`YOLOv8n-seg` TensorRT) kết hợp thuật toán phân vị cạnh đáy; không dùng trung điểm cạnh đáy Bbox 2D thuần túy. |
| **RQ4** | Làm thế nào chuyển đổi vị trí 3D từ camera frame sang robot footprint/world frame và duy trì bộ nhớ ngữ nghĩa không gian (Semantic Spatial Memory)? | • Độ trôi dạt tọa độ vật cản trong `map` frame khi robot đứng yên và khi quay thân robot<br>• Tần số cập nhật TF Tree (Hz)<br>• Tỉ lệ gán nhãn đúng danh tính vật cản qua thời gian (ID Switch rate) | **Nếu tọa độ vật trong `map` bị nhảy giật khi robot quay:**<br>Kiểm tra timestamp của TF transform; áp dụng bộ lọc Kalman theo dõi quỹ đạo vật cản 3D (Extended Kalman Filter tracker); kiểm tra độ trễ của `/odometry/filtered`. |
| **RQ5** | Robot nên khai thác chuyển động bản thân (Motion Stereo) và hợp nhất đa cảm biến (LiDAR 2D RPLIDAR S2E) như thế nào để chủ động triệt tiêu Scale Ambiguity và hỗ trợ Nav2 tránh va chạm? | • Mức độ thu hẹp khoảng tin cậy sai số $\sigma_Z$ khi robot tịnh tiến<br>• Sai số khớp nối góc chiếu giữa tia LiDAR và Bounding Box trên ảnh<br>• Tỉ lệ phát hiện vật cản ngoài mặt phẳng quét LiDAR (obstacle recall rate)<br>• Thời gian phản ứng phanh an toàn của Nav2 | **Đây là phần Hợp nhất Đa Cảm biến (Sensor Fusion) ở Giai đoạn 2:**<br>Dùng LiDAR để khóa cứng khoảng cách $Z$ và chiều rộng $W$; dùng Camera đơn để nhận biết chiều cao $H$, nhận diện ngữ nghĩa và phát hiện chướng ngại vật lơ lửng trên/dưới tia quét 2D. |

---

## 2. Hệ Thống Yêu Cầu Kỹ Thuật (System Requirements Specification)

Để module camera đơn hoàn thiện và đủ tiêu chuẩn chuyển giao tích hợp vào Mobile Robot, hệ thống phải tuân thủ nghiêm ngặt hai nhóm yêu cầu: Yêu cầu chức năng (Functional Requirements - FR) và Yêu cầu phi chức năng (Non-Functional Requirements - NFR).

### 2.1. Yêu Cầu Chức Năng (Functional Requirements - FR)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            YÊU CẦU CHỨC NĂNG (FR)                               │
├───────────────┬─────────────────────────────────────────────────────────────────┤
│ FR-01: CAPTURE│ Thu nhận ảnh Pcam 5C độ phân giải 1280x720 @ 30 FPS trên Pi 3.  │
│ FR-02: TELEM  │ Thu thập dữ liệu gia tốc và góc nghiêng MPU6050 @ 100 Hz.       │
│ FR-03: STREAM │ Đóng gói và truyền luồng video + telemetry qua TCP LAN sang     │
│               │ Jetson với độ trễ < 40 ms.                                      │
│ FR-04: CALIB  │ Khử méo thấu kính Brown-Conrady và tự động cập nhật góc pitch.  │
│ FR-05: DETECT │ Nhận diện vật thể 2D và sinh mặt nạ phân đoạn thực thể.         │
│ FR-06: 3D-POS │ Ước lượng khoảng cách Z và tọa độ (X, Y, Z) trong camera frame. │
│ FR-07: 3D-BOX │ Ước lượng kích thước (W, H, D) và dựng 8 đỉnh 3D Bounding Box.  │
│ FR-08: ROS2-TF│ Xuất bản các topic ROS 2 chuẩn và chuyển đổi hệ tọa độ TF.      │
│ FR-09: COSTMAP│ Xuất đám mây điểm vật cản 3D cấp dữ liệu cho Nav2 Costmap.     │
└───────────────┴─────────────────────────────────────────────────────────────────┘
```

*   **FR-01 (Thu nhận Hình ảnh):** Hệ thống trên Raspberry Pi 3 phải mở được thiết bị `/dev/video0`, thu nhận khung hình màu RGB/BGR từ cảm biến OV5640 ở độ phân giải tối thiểu $1280 \times 720$ với tốc độ ổn định $30\text{ FPS}$.
*   **FR-02 (Đo Lường Quán Tính):** Đọc liên tục 3 trục gia tốc $(a_x, a_y, a_z)$ và 3 trục vận tốc góc $(\omega_x, \omega_y, \omega_z)$ từ MPU6050 qua I2C với tần số tối thiểu $100\text{ Hz}$, tính toán góc chúc pitch $\theta$ và roll $\phi$.
*   **FR-03 (Truyền Dẫn Mạng Nội Bộ):** Truyền tải luồng khung hình đã nén và khối dữ liệu telemetry tương ứng sang Jetson AGX Xavier qua giao thức kết nối trực tiếp Ethernet TCP/UDP mà không làm tràn hàng đợi đệm (buffer overflow).
*   **FR-04 (Khử Méo & Bù Ngoại Hàm):** Jetson thực thi thuật toán khử méo ảnh dựa trên ma trận nội hàm $\mathbf{K}$ và vector hệ số méo $\mathbf{D}$; áp dụng góc pitch tức thời từ MPU6050 vào ma trận chiếu phối cảnh ngược.
*   **FR-05 (Nhận Diện Ngữ Nghĩa & Phân Đoạn):** Chạy mô hình học sâu (như `YOLOv8n-seg`) nhận diện các lớp chướng ngại vật trong nhà (người, ghế, bàn, balo, thùng carton, chai lọ...) và cung cấp mặt nạ nhị phân (binary mask).
*   **FR-06 (Ước Lượng Khoảng Cách Metric):** Xác định tọa độ điểm chạm sàn thấp nhất $v_{\text{contact}}$ và tính toán khoảng cách tiến $Z$, khoảng cách ngang $X$ và khoảng cách Euclidean $d$ theo đơn vị mét.
*   **FR-07 (Khôi Phục Thể Tích 3D):** Dựng khung hộp bao 3D bao gồm tâm $(X_C, Y_C, Z_C)$, kích thước ba chiều $(W, H, D)$ và góc xoay phương vị Yaw $\psi$.
*   **FR-08 (Giao Tiếp Chuẩn ROS 2):** Xuất bản dữ liệu định kỳ dưới dạng các thông điệp ROS 2 chuẩn:
    *   `/camera/image_raw` (`sensor_msgs/msg/Image`)
    *   `/camera/camera_info` (`sensor_msgs/msg/CameraInfo`)
    *   `/perception/detections_3d` (`vision_msgs/msg/Detection3DArray`)
    *   `/perception/markers_3d` (`visualization_msgs/msg/MarkerArray`)
*   **FR-09 (Hỗ Trợ Tránh Vật Cản Nav2):** Tạo luồng dữ liệu đám mây điểm `/perception/obstacle_pointcloud` (`sensor_msgs/msg/PointCloud2`) đại diện cho các bề mặt vật cản 3D để đưa vào lớp chướng ngại vật (Voxel Costmap Layer) của Nav2.

---

### 2.2. Yêu Cầu Phi Chức Năng (Non-Functional Requirements - NFR)

| Mã NFR | Tên yêu cầu phi chức năng | Chỉ số định lượng (Target Metric) | Phương pháp kiểm tra & Đo lường |
| :---: | :--- | :--- | :--- |
| **NFR-01** | **Tốc độ xử lý (Throughput)** | $\ge 25\text{ FPS}$ cho tầng trích xuất điểm;<br>$\ge 20\text{ FPS}$ cho toàn bộ pipeline hoàn chỉnh (Detect + Mask + 3D Box) | Đo thời gian xử lý trung bình qua 1,000 frames liên tiếp trên Jetson Xavier (chế độ nguồn 30W/MAXN). |
| **NFR-02** | **Độ trễ toàn trình (Latency)** | $\le 50\text{ ms}$ (từ thời điểm cảm biến phơi sáng đến khi xuất thông điệp ROS 2) | So sánh timestamp nanosecond giữa thời điểm chụp ảnh trên Pi 3 và thời điểm publish topic trên Jetson. |
| **NFR-03** | **Chiếm dụng tài nguyên GPU/CPU** | • GPU VRAM $\le 2.0\text{ GB}$ (trên 16GB tổng)<br>• Tải CPU Jetson $\le 35\%$ tổng 8 nhân Carmel<br>• Tải CPU Pi 3 $\le 60\%$ tổng 4 nhân Cortex-A53 | Giám sát bằng công cụ `jtop` trên Jetson và `htop` trên Raspberry Pi 3 trong suốt quá trình chạy thực tế. |
| **NFR-04** | **Độ ổn định truyền thông (Network)** | • Tỉ lệ rớt frame (Dropped Frames) $\le 0.2\%$<br>• Jitter truyền nhận $\le 5.0\text{ ms}$ | Ghi log truyền nhận qua socket mạng LAN trong phiên thử nghiệm liên tục 60 phút. |
| **NFR-05** | **Tính bền bỉ (Reliability & Uptime)**| Hoạt động liên tục $\ge 3\text{ giờ}$ không xảy ra crash, rò rỉ bộ nhớ (leak $< 10\text{ MB/giờ}$) | Kiểm tra dung lượng RAM hệ thống định kỳ mỗi 15 phút bằng script tự động. |
| **NFR-06** | **Tính tái lập khoa học (Reproducibility)**| Mọi tham số cấu hình, model weights, calibration YAML được quản lý phiên bản rõ ràng | Lưu trữ mã băm Git commit hash, file cấu hình ROS 2 parameters và file log raw dataset (`.rosbag2`). |

---

## 3. Bộ Tiêu Chí Nghiệm Thu Toàn Diện (Acceptance Criteria & Decision Gates)

Hệ thống nghiệm thu được phân cấp thành **6 Cổng Quyết Định (Decision Gates G0 – G5)**. Mỗi gate là một điều kiện tiên quyết (Prerequisite): **Nếu không vượt qua gate cấp thấp, nghiêm cấm chuyển sang phát triển hoặc đánh giá gate cấp cao hơn.**

```
   [G0: Hardware & Driver] ──> PASS ──> [G1: Network & Sync] ──> PASS
                                                                  │
┌─────────────────────────────────────────────────────────────────┘
│
└──> [G2: Calibration & IPM] ──> PASS ──> [G3: 2D/3D Perception] ──> PASS
                                                                      │
┌─────────────────────────────────────────────────────────────────────┘
│
└──> [G4: ROS 2 TF & Tracking] ──> PASS ──> [G5: Nav2 Integration] ──> [READY FOR ROBOT]
```

### 3.1. Bảng Tiêu Chí Nghiệm Thu Định Lượng Từng Cổng (Gate Details)

| Cổng (Gate) | Tên Cổng Nghiệm Thu | Tiêu chí Định lượng Đạt chuẩn (Pass Criteria) | Tiêu chí Không đạt (Fail Criteria) | Hành động khắc phục khi Fail |
| :---: | :--- | :--- | :--- | :--- |
| **GATE 0** | **Kiểm định Phần cứng & Driver Pcam 5C** | • `dmesg` báo nhận diện chip OV5640 thành công.<br>• Xuất hiện node `/dev/video0`.<br>• Chụp được ảnh sắc nét $1280 \times 720$.<br>• Tốc độ stream tại chỗ trên Pi 3 đạt $\ge 25\text{ FPS}$. | • Không nhận diện thiết bị I2C/CSI.<br>• Màn hình đen hoặc sọc nhiễu.<br>• FPS trồi sụt dưới $15\text{ FPS}$. | • Kiểm tra lại chiều cắm cáp FFC (tiếp xúc mặt kim loại).<br>• Thử lại với `dtoverlay=ov5640` trong boot config.<br>• Kiểm tra sụt áp nguồn 5V cấp cho Pi 3. |
| **GATE 1** | **Kiểm định Mạng LAN & Đồng bộ Telemetry** | • Trễ truyền mạng một chiều $\le 15\text{ ms}$.<br>• Tỉ lệ rớt gói tin ảnh $\le 0.5\%$.<br>• Dữ liệu gia tốc MPU6050 gắn kèm timestamp đồng bộ với frame ảnh sai lệch $\Delta t \le 10\text{ ms}$. | • Độ trễ mạng $> 40\text{ ms}$.<br>• Mất kết nối TCP ngẫu nhiên.<br>• Dữ liệu IMU bị treo hoặc không cập nhật. | • Thay thế cáp mạng Cat6 chuẩn; đặt IP tĩnh.<br>• Bật cờ `TCP_NODELAY` trong socket script.<br>• Tách luồng đọc IMU thành thread độc lập có khóa lock. |
| **GATE 2** | **Nghiệm thu Hiệu chuẩn & Chiếu Phối Cảnh Sàn** | • Sai số tái chiếu nội hàm $\text{RMS} \le 0.35\text{ px}$.<br>• Sai số đo góc tĩnh MPU6050 $\le 0.2^\circ$.<br>• Sai số đo khoảng cách IPM ở cự ly $1.0\text{m} - 2.0\text{m}$: $\text{AbsRel} \le 2.0\%$. | • RMS Reprojection $> 0.50\text{ px}$.<br>• Ước lượng khoảng cách tại $2.0\text{m}$ bị lệch $> 10\text{ cm}$ ($\text{AbsRel} > 5\%$). | • Thu thập lại tập ảnh bàn cờ (tối thiểu 30 ảnh bao phủ 4 góc rìa ảnh).<br>• Đo đạc lại chiều cao cơ khí $h_c$ bằng thước thép chính xác.<br>• Bù trừ độ lệch bias tĩnh của MPU6050. |
| **GATE 3** | **Nghiệm thu Nhận thức 2D/3D & Hộp Giới Hạn** | • $\text{mAP@50} \ge 0.70$ trên tập vật cản chuẩn.<br>• Tốc độ suy luận trên Jetson $\ge 25\text{ FPS}$.<br>• Điểm tiếp xúc sàn $v_{\text{contact}}$ không bị lệch do bóng đổ ($\le 2\text{ px}$).<br>• Sai số chiều cao vật $H$ ở cự ly $\le 2.5\text{m}$: $\le 5.0\%$. | • Bounding box 2D gom cả bóng đổ trên sàn làm sai lệch khoảng cách $> 15\%$.<br>• Tốc độ suy luận $< 15\text{ FPS}$. | • Bắt buộc dùng `YOLOv8n-seg` xuất Engine TensorRT FP16.<br>• Áp dụng thuật toán trích xuất phân vị đáy mặt nạ (95th percentile).<br>• Hạ độ phân giải suy luận xuống $640 \times 640$. |
| **GATE 4** | **Nghiệm thu Chuyển Đổi Hệ Tọa Độ & Theo Dõi** | • Xuất bản đầy đủ topic `/perception/detections_3d` chuẩn ROS 2.<br>• Cây TF liên kết liền mạch từ `map` $\rightarrow$ `base_footprint` $\rightarrow$ `camera_link` $\rightarrow$ `camera_optical_frame`.<br>• Vị trí vật cản trong `map` frame không bị trôi dạt $> 5\text{ cm}$ khi xoay robot. | • Cây TF bị đứt gãy hoặc báo thiếu transform.<br>• Tọa độ vật thể bị nhảy giật loạn xạ khi robot di chuyển. | • Kiểm tra lại timestamp của thông điệp TF (dùng chung clock ROS của Jetson).<br>• Tích hợp bộ lọc Kalman 3D làm mượt tọa độ tâm $(X, Y, Z)$ theo thời gian. |
| **GATE 5** | **Nghiệm thu Tích Hợp Hệ Thống Tránh Vật Cản Nav2** | • Đám mây điểm `/perception/obstacle_pointcloud` được chèn thành công vào Local Costmap của Nav2.<br>• Robot tự động dừng lại hoặc né tránh vật cản lơ lửng (không nhìn thấy bởi LiDAR 2D) ở cự ly an toàn $\ge 0.40\text{ m}$. | • Nav2 không nhận diện được vật cản từ camera.<br>• Robot đâm va vào vật cản ở độ cao ngoài mặt phẳng quét LiDAR. | • Kiểm tra cấu hình lớp Voxel Layer trong `nav2_params_v2.yaml`.<br>• Điều chỉnh ngưỡng Raytrace và Obstacle Range trong Costmap.<br>• Tinh chỉnh góc mở FOV của camera trong cấu hình sensor costmap. |

---

## 4. Kịch Bản & Quy Trình Kiểm Thử Thực Địa (Verification Testbed)

Để đảm bảo các kết quả nghiệm thu có giá trị khoa học và khách quan, toàn bộ quá trình đánh giá phải tuân theo quy trình chuẩn hóa:

### 4.1. Thiết Bị Đo Chuẩn Đối Chiếu (Ground Truth Instruments)
1.  **Thước Đo Laser Quang Học:** Bosch GLM 50-27 CG Professional (Độ chính xác $\pm 1.5\text{ mm}$, chuẩn công nghiệp).
2.  **Thước Cặp Cơ Khí/Điện Tử:** Mitutoyo 150mm (Độ chính xác $\pm 0.02\text{ mm}$) dùng đo kích thước vật thể chuẩn.
3.  **Thước Đo Góc Nghiêng Điện Tử:** Bọt thủy kỹ thuật số (Độ chính xác $\pm 0.05^\circ$) đối chuẩn góc pitch camera.
4.  **Lưới Tọa Độ Mặt Sàn:** Kẻ vạch định vị $0.5\text{m} \times 0.5\text{m}$ trên nền sàn gạch phẳng phòng lab.

### 4.2. Bộ Vật Cản Thử Nghiệm Chuẩn (Standard Obstacle Benchmark Suite)

| ID Vật thể | Tên vật thể kiểm thử | Kích thước chuẩn $W \times H \times D$ (m) | Đặc tính hình học & Thách thức thị giác |
| :---: | :--- | :---: | :--- |
| **OBJ-01** | Thùng Carton Chuẩn Khối Hộp | $0.300 \times 0.250 \times 0.200$ | Khối đặc, biên phẳng, kiểm tra khả năng tách cạnh và khôi phục 3D box. |
| **OBJ-02** | Ghế Xoay Văn Phòng 5 Chân | $0.580 \times 0.860 \times 0.540$ | Chân rỗng, có bóng râm lớn dưới đáy; kiểm tra năng lực chống bóng đổ của Mask. |
| **OBJ-03** | Chai Nước Đặt Đứng | $0.075 \times 0.245 \times 0.075$ | Kích thước nhỏ; kiểm tra độ phân giải góc và sai số cự ly gần ($0.5\text{m} - 1.5\text{m}$). |
| **OBJ-04** | Balo / Cặp Sách Đặt Dưới Sàn | $0.320 \times 0.450 \times 0.180$ | Bề mặt mềm không định hình; kiểm tra độ vững chắc của thuật toán phân đoạn. |
| **OBJ-05** | Người Đi Bộ (Bàn chân & Cơ thể) | $0.450 \times 1.700 \times 0.280$ | Vật cản động (Dynamic obstacle); kiểm tra độ an toàn điều hướng cho con người. |
| **OBJ-06** | Mặt Bàn / Rào Cản Lơ Lửng | $0.800 \times 0.050 \times 0.600$ (treo cao 0.45m) | **Vật thể không chạm sàn**; LiDAR 2D không quét tới; kiểm tra thuật toán Metric Depth. |

---

## 5. Mẫu Biên Bản Nghiệm Thu Kỹ Thuật (Verification Scorecard Template)

Khi tiến hành đánh giá thực tế trước hội đồng hoặc bàn giao module, nhóm nghiên cứu sẽ điền và ký xác nhận theo biểu mẫu chuẩn sau:

```
========================================================================================
            BIÊN BẢN NGHIỆM THU ĐÁNH GIÁ MODULE CAMERA ĐƠN (PCAM 5C)
========================================================================================
Ngày đánh giá: ...../...../2026                 Địa điểm: Lab ASIC / Mobile Robot Sandbox
Thành viên đánh giá: ...................................................................
Phiên bản phần mềm (Git Hash): .................... Trọng số Model: ....................
----------------------------------------------------------------------------------------
KẾT QUẢ ĐÁNH GIÁ TỪNG CỔNG (GATES):

[ ] GATE 0 (Hardware & Driver):
    - Nhận diện /dev/video0:       [ ] PASS    [ ] FAIL   (Ghi chú: ...................)
    - FPS Video Stream thực tế:    .......... FPS         (Yêu cầu: >= 25 FPS)

[ ] GATE 1 (Network & Telemetry Sync):
    - Trễ truyền mạng một chiều:   .......... ms          (Yêu cầu: <= 15 ms)
    - Tỉ lệ rớt frame (Drop rate): .......... %           (Yêu cầu: <= 0.5%)
    - Đồng bộ mẩu tin IMU:         [ ] PASS    [ ] FAIL

[ ] GATE 2 (Calibration & IPM Distance Precision):
    - Reprojection Error RMS:      .......... px          (Yêu cầu: <= 0.35 px)
    - AbsRel tại 1.0m:             .......... %           (Yêu cầu: <= 2.0%)
    - AbsRel tại 2.0m:             .......... %           (Yêu cầu: <= 2.0%)
    - AbsRel tại 3.0m:             .......... %           (Yêu cầu: <= 5.0%)

[ ] GATE 3 (2D/3D Perception & Bounding Box):
    - Tốc độ suy luận (Throughput):.......... FPS         (Yêu cầu: >= 20 FPS)
    - Xử lý bóng đổ (Shadow test): [ ] PASS    [ ] FAIL
    - Sai số chiều cao H (tại 2m): .......... %           (Yêu cầu: <= 5.0%)

[ ] GATE 4 (ROS 2 Interface & TF Transform):
    - Xuất bản topic chuẩn:        [ ] PASS    [ ] FAIL
    - Độ ổn định TF khi robot quay:.......... cm          (Yêu cầu: <= 5 cm)

[ ] GATE 5 (Nav2 Costmap Integration):
    - Chèn đám mây điểm PointCloud2:[ ] PASS   [ ] FAIL
    - Tự động phanh tránh vật treo:[ ] PASS    [ ] FAIL   (Cự ly phanh: ........ m)
----------------------------------------------------------------------------------------
KẾT LUẬN CHUNG:
    [ ] ĐẠT CHUẨN TOÀN DIỆN (Sẵn sàng tích hợp sang Giai đoạn 2 trên Mobile Robot)
    [ ] CẦN KHẮC PHỤC (Nêu rõ Gate chưa đạt và hành động xử lý)

Chữ ký Trưởng nhóm Nghiên cứu                         Chữ ký Giám sát Kỹ thuật
(Ký và ghi rõ họ tên)                                 (Ký và ghi rõ họ tên)
========================================================================================
```

---

## 6. Tổng Kết

Tài liệu này xác lập bộ khung chuẩn mực kỹ thuật và nghiên cứu khoa học cho toàn bộ quá trình phát triển module camera đơn Pcam 5C. Việc phân định rõ từng câu hỏi nghiên cứu (RQ), đầu ra định lượng và cổng quyết định (Decision Gates) giúp loại bỏ tính chủ quan, đảm bảo mọi cải tiến thuật toán đều được kiểm chứng bằng số liệu thực nghiệm minh bạch trước khi tích hợp vào hệ thống Mobile Robot tự hành.
