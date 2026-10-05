# Software Requirements Specification (SRS) — Release 1

> **Layer:** Implementation Layer (`docs/implementation/release-1/srs.md`)  
> **Release:** Release 1 (Phase 1 Sandbox)  
> **Status:** Approved Baseline  

---

## 1. Functional Requirements (FR)

| Req ID | Requirement Statement | Priority | Verification Method |
| :--- | :--- | :--- | :--- |
| **FR-01** | Hệ thống `pi_capture_agent` phải mở được thiết bị `/dev/video0` (cảm biến OV5640) và cấu hình độ phân giải $1280 \times 720$ định dạng MJPEG hoặc YUYV. | **Must Have** | Kiểm tra `v4l2-ctl` và xuất ảnh frame đơn |
| **FR-02** | Hệ thống phải đọc dữ liệu gia tốc 3 trục từ cảm biến MPU6050 qua I2C với chu kỳ tối thiểu $20\text{ms}$ ($50\text{Hz}$) và tính toán góc pitch/roll tức thời. | **Must Have** | Log dữ liệu telemetry IMU liên tục |
| **FR-03** | Khung hình và dữ liệu telemetry phải được đóng gói vào Binary Frame Header chuẩn (Magic `0x5043`, timestamp nanosecond) và truyền qua TCP socket. | **Must Have** | Wireshark / Socket Packet Sniffer |
| **FR-04** | Node `mono_ingest` trên Jetson AGX Xavier phải tiếp nhận luồng dữ liệu, giải nén và lưu trữ vào hàng đợi đệm (Ring Buffer) có giới hạn độ dài 5 frame. | **Must Have** | Stress test không bị tràn bộ nhớ RAM |
| **FR-05** | Module `mono_calib` phải nạp tệp cấu hình YAML, tính toán ma trận xoay bù trừ góc nghiêng tức thời từ IMU: $R(\theta(t), \phi(t))$. | **Must Have** | Unit test hàm ma trận hình học |
| **FR-06** | Module `object2d_seg` phải thực thi suy luận YOLOv8-seg qua TensorRT FP16, xuất danh sách bounding box 2D và mặt nạ đa giác (segmentation mask). | **Must Have** | Đo mAP và thời gian suy luận trên Jetson |
| **FR-07** | Module `depth_engine` phải trích xuất điểm đáy tiếp xúc mặt sàn $(u_b, v_b)$ từ mặt nạ và tính cự ly $Z_{\text{ipm}}$ theo công thức chiếu phối cảnh ngược. | **Must Have** | So sánh giá trị cự ly với khoảng cách laser |
| **FR-08** | Module `object3d` phải tính toán tọa độ tâm $[X, Y, Z]$, kích thước vật lý $[L, W, H]$ và xuất ra topic ROS 2 `/perception/mono/objects_3d`. | **Must Have** | Kiểm tra `ros2 topic echo` |
| **FR-09** | Kịch bản `eval_benchmark.py` phải tự động so khớp tọa độ đo được với tệp dữ liệu Ground Truth Laser và xuất ra bảng chỉ số AbsRel, RMSE. | **Should Have** | Xuất báo cáo markdown tự động |

---

## 2. Non-Functional Requirements (NFR)

- **NFR-01 (Throughput):** Toàn bộ pipeline đạt tốc độ xử lý tối thiểu $15\text{ FPS}$ (khuyến nghị $\ge 25\text{ FPS}$) tại độ phân giải $1280 \times 720$.
- **NFR-02 (Memory Footprint):** Dung lượng RAM tiêu thụ trên Raspberry Pi 3 không vượt quá $250\text{ MB}$; trên Jetson AGX Xavier không vượt quá $4.5\text{ GB}$ VRAM.
- **NFR-03 (Fault Recovery):** Nếu kết nối mạng giữa Pi 3 và Jetson bị ngắt đột ngột, cả hai node phải tự động thử kết nối lại (auto-reconnect) trong vòng $3\text{ giây}$ mà không bị sập tiến trình.
