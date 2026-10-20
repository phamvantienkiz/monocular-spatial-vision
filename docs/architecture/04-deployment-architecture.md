# 04 - Deployment & Infrastructure Architecture

> **Layer:** Architecture Layer (`docs/architecture/04-deployment-architecture.md`)  
> **Status:** Single Source of Truth — Living Architecture  

---

## 1. Physical & Network Topology

```mermaid
flowchart LR
    subgraph RIG["Khung Thí Nghiệm & Thu Thập"]
        OV["OmniVision OV5640 (Pcam 5C)"] -->|MIPI CSI-2 15-pin| PI3["Raspberry Pi 3 Model B+<br/>IP: 192.168.1.10"]
        MPU["MPU6050 (I2C)"] -->|SDA/SCL Pins 3,5| PI3
    end

    subgraph NETWORK["Mạng Cục Bộ"]
        SW["Gigabit Ethernet Switch (Cat6 UTP)"]
    end

    subgraph BRAIN["Cụm Tính Toán AI Trung Tâm"]
        JET["Jetson AGX Xavier 16GB<br/>IP: 192.168.1.20"]
    end

    subgraph MON["Trạm Giám Sát & Benchmark"]
        PC["Laptop / Dev PC (RViz2)<br/>IP: 192.168.1.100"]
    end

    PI3 <-->|"100 Mbps Eth (Jetson / Laptop USB Type-C Hub)\nhoặc Wi-Fi 802.11n (Laptop Test)"| SW
    JET <-->|1000 Mbps Eth| SW
    PC <-->|"Wi-Fi (--mode preview/stream)\nhoặc USB Type-C to Ethernet Hub"| SW
```

### 1.1. Dual-Mode Network Transport Invariant (Wi-Fi & Wired Ethernet)
Cả phiên bản Python (`services/pi_capture_agent/`) lẫn phiên bản C/C++ (`services/pi_capture_agent_cpp/`) trên Raspberry Pi 3 đều **bắt buộc duy trì đồng thời 2 giao thức truyền dẫn vật lý và cách thức kiểm thử**:
1. **Wi-Fi (`wlan0`):** Phục vụ kiểm thử không dây tiện lợi với Laptop qua cả chế độ xem trực tiếp trên trình duyệt (`--mode preview`, cổng HTTP `8080`) và chế độ truyền luồng nhị phân (`--mode stream`, cổng TCP `9876`).
2. **Cổng Ethernet (`eth0`):**
   - **Kiểm thử có dây với Laptop:** Kết nối cáp RJ45 từ Pi 3 qua **Hub chuyển đổi USB Type-C sang Ethernet** cắm vào Laptop (hỗ trợ Zero-Friction Networking qua dải IP Link-Local APIPA `169.254.x.x`, mDNS `raspberrypi.local`, hoặc `--host <IP>` động mà không ép đổi Static IP của Laptop).
   - **Tích hợp thực tế trên Robot:** Kết nối cáp RJ45 từ Pi 3 trực tiếp sang cổng Ethernet của **Jetson AGX Xavier (`192.168.1.20:9876`)**.

---

## 2. Node Computing Environments & Runtime Stacks

### 2.1. Node 1: Raspberry Pi 3 Model B/B+
- **Hệ điều hành:** Raspberry Pi OS Lite (64-bit hoặc 32-bit tối ưu kernel V4L2).
- **Driver:** Cấu hình Device Tree Overlay cho cảm biến OV5640 (`dtoverlay=ov5640` hoặc V4L2 subdevice driver).
- **Thư viện phụ trợ:** `smbus2` (giao tiếp MPU6050 qua I2C), `opencv-python-headless` (hoặc `libcamera-apps`).
- **Dịch vụ hệ thống:** `pi-capture.service` (Systemd daemon tự khởi chạy khi bật nguồn).

### 2.2. Node 2: NVIDIA Jetson AGX Xavier 16GB
- **Carrier Board:** Auvidea X221-AI hoặc DevKit chuẩn.
- **Hệ điều hành:** Ubuntu 20.04 LTS (JetPack 5.1.x / L4T 35.x) hoặc Ubuntu 22.04 LTS (JetPack 6.x).
- **Tăng tốc phần cứng:**
  - CUDA 11.4 / 12.x
  - cuDNN 8.6+
  - TensorRT 8.5+
- **Môi trường cách ly:** Bắt buộc sử dụng Python Virtualenv cục bộ (`.venv`) hoặc Docker container có GPU runtime (`nvidia-container-toolkit`).
- **ROS 2:** ROS 2 Foxy Fitzroy (Ubuntu 20.04) hoặc Humble Hawksbill (Ubuntu 22.04) với FastDDS rmw.

---

## 3. Communication Latency Budget & Bandwidth

| Phân đoạn truyền dẫn | Giao thức | Băng thông dự kiến | Độ trễ mục tiêu |
| :--- | :--- | :--- | :--- |
| Pcam 5C $\rightarrow$ Pi 3 Memory | MIPI CSI-2 2-lane | $\approx 1.0\text{ Gbps}$ | $< 5\text{ms}$ |
| Pi 3 $\rightarrow$ Jetson AGX (Frame stream) | TCP / UDP Socket (MJPEG/H.264) | $15 - 35\text{ Mbps}$ | $< 15\text{ms}$ |
| Ingest Buffer $\rightarrow$ TensorRT Inference | GPU Unified Memory / pinned memory | N/A | $25 - 35\text{ms}$ |
| Object3D Engine $\rightarrow$ ROS 2 DDS Topic | FastDDS Shared Memory (Intra-process) | N/A | $< 2\text{ms}$ |
| **Tổng độ trễ từ cảm biến tới 3D Bounding Box** | **End-to-End Pipeline** | N/A | $\le 60\text{ms}$ ($\ge 16.6\text{ FPS}$) |
