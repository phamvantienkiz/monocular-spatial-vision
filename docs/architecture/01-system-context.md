# 01 - System Context Architecture

> **Layer:** Architecture Layer (`docs/architecture/01-system-context.md`)  
> **Status:** Single Source of Truth — Living Architecture  

---

## 1. System Boundary & Scope Context

Hệ thống **Monocular Spatial Vision** là một hệ thống thị giác máy tính và nhận thức không gian 3D hoạt động trên biên (Edge AI Perception System) được thiết kế cho Mobile Robot trong nhà. Hệ thống nhận đầu vào quang học từ một camera đơn và dữ liệu góc nghiêng từ IMU, xử lý tính toán trên máy tính nhúng AI, và cung cấp đầu ra là tọa độ không gian 3D, cự ly thực và hộp bao 3D của các chướng ngại vật.

```mermaid
flowchart TD
    subgraph EXTERNAL_ENTITIES["Tác Nhân & Hệ Thống Ngoài"]
        USER["Người Vận Hành / Kỹ Sư Nghiên Cứu"]
        ROBOT_BASE["Khung Gầm Robot (STM32 Differential Drive)"]
        LIDAR_2D["Cảm Biến RPLIDAR S2E (2D Laser Scan)"]
        LASER_GT["Thước Đo Laser Quang Học (Ground Truth ±1.5mm)"]
    end

    subgraph SYSTEM_BOUNDARY["Hệ Thống Monocular Spatial Vision"]
        CAM_NODE["Cụm Thu Thập Dữ Liệu (Pcam 5C + Raspberry Pi 3 + MPU6050)"]
        AI_NODE["Bộ Não Tính Toán AI (NVIDIA Jetson AGX Xavier)"]
        EVAL_ENGINE["Module Đánh Giá Đối Chuẩn (Benchmark Engine)"]
    end

    subgraph DOWNSTREAM_CONSUMERS["Hệ Thống Tiêu Thụ Dữ Liệu"]
        NAV2["Navigation Stack (ROS 2 Nav2 Costmap)"]
        RVIZ["Giao Diện Trực Quan Hóa (RViz2 / Operator UI)"]
    end

    USER -->|Cấu hình & Kích hoạt| CAM_NODE
    USER -->|Nghiệm thu & Đánh giá| EVAL_ENGINE
    
    CAM_NODE -->|Luồng Hình Ảnh + Telemetry IMU| AI_NODE
    LIDAR_2D -.->|Tọa độ Laser Scan (Phase 3)| AI_NODE
    ROBOT_BASE -.->|Wheel Odometry (Phase 3)| AI_NODE

    AI_NODE -->|Tọa độ 3D Bounding Box & Depth Map| NAV2
    AI_NODE -->|Dữ liệu hiển thị Telemetry| RVIZ
    
    LASER_GT -.->|Khoảng cách chuẩn cơ sở| EVAL_ENGINE
    AI_NODE -->|Khoảng cách dự đoán (Prediction)| EVAL_ENGINE
```

---

## 2. External System Invariants & Interfaces

1. **Camera Sensor (Digilent Pcam 5C):**
   - Cảm biến OmniVision OV5640, giao tiếp MIPI CSI-2 2-lane.
   - Đầu ra ảnh gốc cấu hình tại $1280 \times 720$ @ $30\text{ FPS}$ hoặc $1920 \times 1080$ @ $15\text{ FPS}$.
2. **Auxiliary IMU (MPU6050):**
   - Giao tiếp I2C `/dev/i2c-1` trên Raspberry Pi 3, tần số đọc mẫu tối thiểu $50\text{Hz}$.
   - Trục đo gia tốc trùng phương với trục quang học để đo trực tiếp vector trọng lực $\vec{g}$.
3. **AI Compute Host (Jetson AGX Xavier):**
   - Nhận luồng ảnh và telemetry qua socket mạng nội bộ có dây (Gigabit Ethernet) giảm thiểu tối đa jitter.
4. **Ground Truth Instrument:**
   - Thước laser Bosch GLM chuyên dụng ($\pm 1.5\text{mm}$) cung cấp khoảng cách ground-truth đến tâm chân đế vật thể để tính $\text{AbsRel}$ và $\text{RMSE}$.
