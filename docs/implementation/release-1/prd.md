# Release 1 PRD — Standalone Monocular 3D Perception Sandbox

> **Layer:** Implementation Layer (`docs/implementation/release-1/prd.md`)  
> **Release:** Release 1 (Phase 1 Sandbox)  
> **Target Date:** Q4 2026  
> **Status:** Approved Baseline  

---

## 1. Release Goals & Scope Definition

Release 1 thiết lập môi trường kiểm chứng độc lập (Standalone Research Sandbox) trên giá đỡ cơ khí tĩnh với mục tiêu hoàn thiện chu trình thu nhận, xử lý AI và xuất tọa độ 3D từ một camera đơn Pcam 5C kết hợp IMU MPU6050.

### In-Scope Features
1. **Pcam 5C Driver & Stream:** Kiểm chứng driver V4L2 OV5640 trên Pi 3, stream ảnh $1280 \times 720$ @ $30\text{ FPS}$ sang Jetson AGX Xavier.
2. **IMU Telemetry Sync:** Đọc gia tốc MPU6050, tính góc pitch/roll thời gian thực và đóng gói vào header nhị phân.
3. **Camera Calibration:** Hiệu chuẩn thấu kính pinhole, xác định ma trận $K$ và ma trận xoay biến đổi xuống mặt sàn.
4. **2D Perception Engine:** Tích hợp mô hình YOLOv8-seg (TensorRT FP16) phát hiện người, bàn, ghế và trích xuất mặt nạ tiếp xúc sàn.
5. **IPM Distance & 3D BBox:** Tính cự ly tiếp xúc sàn $Z_{\text{ground}}$, tọa độ $[X, Y, Z]$ và hộp bao 3D Bounding Box.
6. **Laser Benchmark Protocol:** So sánh đối chuẩn tự động với số liệu đo từ thước Laser Bosch GLM ($\pm 1.5\text{mm}$).

---

## 2. Release Acceptance Criteria & KPIs

- **AC-01 (Stream Stability):** Tỷ lệ rớt khung hình (Packet Drop Rate) qua mạng Ethernet có dây $< 0.1\%$ trong 30 phút chạy liên tục.
- **AC-02 (Ground Contact Accuracy):** Sai số cự ly tiếp xúc sàn $\text{AbsRel} \le 5.0\%$ cho các vật thể nằm trong phạm vi $0.5\text{m} - 3.0\text{m}$.
- **AC-03 (End-to-End Latency):** Độ trễ từ lúc chụp khung hình tại Pi 3 đến khi xuất ra 3D Bounding Box trên Jetson AGX Xavier $\le 60\text{ms}$ ($\ge 16.6\text{ FPS}$).
- **AC-04 (Tilt Immunity):** Khi nghiêng giả lập giá đỡ một góc $\pm 5^\circ$, sai số khoảng cách sau khi bù trừ IMU tăng không quá $1.0\%$.
