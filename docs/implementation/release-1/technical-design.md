# Technical Design — Release 1 Pipeline

> **Layer:** Implementation Layer (`docs/implementation/release-1/technical-design.md`)  
> **Release:** Release 1 (Phase 1 Sandbox)  
> **Status:** Approved Baseline  

---

## 1. Frame Processing Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant HW_CAM as Pcam 5C (OV5640)
    participant HW_IMU as IMU MPU6050
    participant PI_AGENT as pi_capture_agent (Pi 3)
    participant INGEST as mono_ingest (Jetson AGX)
    participant PERCEPT as Perception Engine (TRT + IPM)
    participant ROS_PUB as ROS 2 Publisher

    loop Every Frame (~33ms @ 30 FPS)
        HW_CAM->>PI_AGENT: Khung hình thô (MIPI CSI-2)
        HW_IMU->>PI_AGENT: Đọc gia tốc ax, ay, az (I2C)
        PI_AGENT->>PI_AGENT: Tính pitch, roll & đóng gói Binary Header
        PI_AGENT->>INGEST: Truyền Packet (Header + Image bytes) qua TCP Socket
        
        INGEST->>INGEST: Kiểm tra Magic 0x5043, giải nén Ring Buffer
        INGEST->>PERCEPT: Chuyển Tensor ảnh & telemetry sang GPU
        
        activate PERCEPT
        PERCEPT->>PERCEPT: YOLOv8-seg suy luận 2D BBox & Masks (TensorRT)
        PERCEPT->>PERCEPT: Trích xuất đáy mặt nạ & tính IPM Z_ground với pitch bù trừ
        PERCEPT->>PERCEPT: Tính toán tọa độ 3D [X, Y, Z] & kích thước [L, W, H]
        deactivate PERCEPT
        
        PERCEPT->>ROS_PUB: Xuất Detection3DArray & Image Markers
        ROS_PUB-->>INGEST: Báo nhận hoàn tất frame
    end
```

---

## 2. Activity Swimlane for Ground Contact Point Extraction

```mermaid
flowchart TD
    START(["Khởi đầu: Nhận Mask 2D của vật thể"]) --> GET_PTS["Trích xuất tập hợp các tọa độ pixel (u, v) thuộc Mask"]
    GET_PTS --> FIND_MAX_V["Tìm giá trị v_max (tọa độ pixel thấp nhất gần đáy ảnh)"]
    FIND_MAX_V --> FILTER_ROW["Lọc các pixel có v nằm trong dải [v_max - 2px, v_max]"]
    FILTER_ROW --> COMP_MEDIAN["Lấy trung vị hoành độ u_contact = median(u_row)"]
    COMP_MEDIAN --> CHECK_NOISE{"Kiểm tra đổ bóng (Shadow Rejection)?"}
    
    CHECK_NOISE -->|Vượt ngưỡng gradient màu| REFINE["Hiệu chỉnh điểm tiếp xúc loại trừ vùng bóng đổ"]
    CHECK_NOISE -->|Bình thường| ACCEPT["Chấp nhận điểm tiếp xúc (u_contact, v_max)"]
    REFINE --> ACCEPT
    
    ACCEPT --> COMPUTE_IPM["Đưa vào công thức IPM khôi phục cự ly Z_ground"]
    COMPUTE_IPM --> END(["Kết thúc: Xuất cự ly Z"])
```
