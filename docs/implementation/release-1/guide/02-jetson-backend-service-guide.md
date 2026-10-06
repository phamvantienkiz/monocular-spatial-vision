# Hướng Dẫn Kỹ Thuật: Jetson AGX Xavier Backend Service & Model Testing

> **Layer:** Implementation Layer (`docs/implementation/release-1/guide/02-jetson-backend-service-guide.md`)  
> **Release:** Release 1 (Phase 1 Sandbox)  
> **Target Hardware:** NVIDIA Jetson AGX Xavier (Headless Ubuntu 20.04/22.04 LTS)  
> **Design Pattern:** Tuân thủ triệt để [fastapi-backend-scaffold](file:///E:/UIT/monocular-spatial-vision/.agents/skills/fastapi-backend-scaffold/SKILL.md)  

---

## 1. Môi Trường Phát Triển: Dev Ở Đâu? Có Phải Code Trên Terminal Không?

> [!IMPORTANT]
> **Tuyệt đối không gõ mã nguồn bằng `nano` hay `vim` qua terminal SSH!**

### 1.1. Luồng làm việc chuẩn của Kỹ sư Hệ thống Nhúng (Embedded Dev Workflow)
1. **Viết code trên Laptop:** 
   - Sử dụng IDE hiện đại (VS Code, PyCharm, hoặc Antigravity) trên Laptop của bạn.
   - Sử dụng extension **VS Code Remote - SSH** kết nối trực tiếp vào Jetson AGX (`ssh jetson@192.168.1.20`). Bạn chỉnh sửa code, xem cây thư mục, format code và gỡ lỗi bằng giao diện đồ họa tiện lợi của Laptop, trong khi mã nguồn và trình biên dịch thực tế chạy trên Jetson.
   - Hoặc quản lý qua Git: Viết và commit trên Laptop $\to$ đẩy lên GitHub/GitLab $\to$ kéo về Jetson bằng `git pull`.

2. **Cách ly môi trường ảo (`.venv`) trên Jetson:**
   Tuân thủ nghiêm ngặt quy định tại [AGENTS.md](file:///E:/UIT/monocular-spatial-vision/AGENTS.md):
   ```bash
   # Đăng nhập SSH vào Jetson AGX Xavier
   ssh jetson@192.168.1.20
   
   cd ~/monocular-spatial-vision/backend
   
   # Khởi tạo môi trường ảo cục bộ (dùng uv hoặc python3 -m venv)
   python3 -m venv .venv
   source .venv/bin/activate
   
   # Nâng cấp pip và cài đặt phụ thuộc
   pip install --upgrade pip
   pip install fastapi uvicorn[standard] pydantic-settings numpy opencv-python-headless pyyaml rich
   
   # Cài đặt PyTorch & TensorRT theo phiên bản JetPack (được link từ hệ thống vào venv)
   # Lưu ý: JetPack đã cài sẵn TensorRT trong hệ thống, chỉ cần link vào .venv
   ```

---

## 2. Kiến Trúc Dịch Vụ Theo Chuẩn `fastapi-backend-scaffold`

Mã nguồn xử lý trung tâm trên Jetson được tổ chức theo kiến trúc phân tầng (Layered Architecture), phân tách độc lập giữa bộ nhận stream, mô hình AI, thuật toán hình học và tầng giao tiếp HTTP/WebSocket:

```mermaid
flowchart TD
    subgraph INGEST_LAYER ["1. Network Ingest Layer (Tầng Thu Nhận Mạng)"]
        TCP_SRV["TCP Socket Server (:9876)"]
        RING_BUF["Thread-Safe Ring Buffer (Max 5 frames)"]
    end

    subgraph SERVICE_LAYER ["2. Computational Service Layer (Tầng Nghiệp Vụ Tính Toán)"]
        TRT_SVC["ModelService (TensorRT YOLOv8-seg FP16)"]
        GEO_SVC["GeometryService (Ground Contact & IPM Solver)"]
        TRACK_SVC["Object3DService (3D Box & Metric Lifting)"]
    end

    subgraph API_LAYER ["3. Presentation & API Layer (Tầng Điều Khiển & Xuất Dữ Liệu)"]
        FASTAPI_APP["FastAPI Application (Uvicorn :8000)"]
        STREAM_EP["/api/v1/stream/live (MJPEG Stream Overlay)"]
        WS_EP["/api/v1/ws/telemetry (WebSocket Real-time JSON)"]
        ROS2_PUB["ROS 2 Node Publisher (/perception/mono/objects_3d)"]
        WEB_HUD["/hud (Static Operator Web Dashboard)"]
    end

    TCP_SRV -->|Unpack Binary Header| RING_BUF
    RING_BUF -->|Frame Tensor + Telemetry| TRT_SVC
    TRT_SVC -->|2D Box & Mask| GEO_SVC
    GEO_SVC -->|Ground Point (u,v) + Pitch θ| TRACK_SVC
    TRACK_SVC -->|3D Bounding Boxes| FASTAPI_APP
    FASTAPI_APP --> STREAM_EP
    FASTAPI_APP --> WS_EP
    FASTAPI_APP --> ROS2_PUB
    FASTAPI_APP --> WEB_HUD
```

---

## 3. Lấy Gì Để Test Mô Hình Khi Chưa Có Camera Thật? (Hardware Decoupling)

> [!TIP]
> Không bao giờ để tiến độ phát triển mô hình AI và thuật toán hình học bị phụ thuộc vào việc có camera Pcam 5C hay Raspberry Pi 3 đang kết nối!

### 3.1. Chế độ Kiểm Thử Ngoại Tuyến (Offline Static Testing)
Module `model_service` và `geometry_service` được thiết kế có thể chạy độc lập qua CLI với tập ảnh/video mẫu lưu sẵn trong `data/samples/`:

```bash
# Chạy suy luận trực tiếp trên ảnh tĩnh bằng Jetson
python -m app.cli --mode test-image \
  --image data/samples/lab_chair_person.jpg \
  --output data/debug/result_annotated.jpg \
  --weights weights/yolov8n-seg.engine
```

**Cách kiểm tra kết quả khi Jetson là Headless:**
- Script tự động in ra bảng tóm tắt định dạng CLI bằng thư viện `rich`:
  ```text
  ┌────┬─────────┬────────┬───────────────────┬──────────────┬──────────────┐
  │ ID │ Class   │ Score  │ Contact (u, v)    │ Distance Z   │ 3D Size [LWH]│
  ├────┼─────────┼────────┼───────────────────┼──────────────┼──────────────┤
  │ 1  │ person  │ 0.92   │ (642, 530) px     │ 1.84 m       │ 0.5x0.6x1.7 m│
  │ 2  │ chair   │ 0.88   │ (420, 610) px     │ 1.15 m       │ 0.6x0.6x0.8 m│
  └────┴─────────┴────────┴───────────────────┴──────────────┴──────────────┘
  Inference Time: 14.2 ms | IPM Solve: 0.8 ms | Total Latency: 15.0 ms (~66 FPS)
  ```
- File kết quả `result_annotated.jpg` được lưu tại `data/debug/` chứa ảnh đã vẽ sẵn:
  - Bounding Box 2D và mặt nạ phân đoạn màu sắc.
  - Chấm tròn đỏ `#EF4444` tại điểm tiếp xúc sàn.
  - Cự ly $Z$ ước tính hiển thị dạng text ngay trên đầu vật thể.

### 3.2. Bơm Stream Mẫu Từ Laptop Sang Jetson (Mock Stream Feeder)
Để kiểm tra tính ổn định của luồng TCP Ingest Socket trên Jetson trước khi Pi 3 sẵn sàng:
1. **Trên Laptop:** Chạy script phát lặp lại một video mẫu đóng gói theo đúng Binary Header chuẩn:
   ```bash
   python tools/laptop/mock_camera_streamer.py \
     --video test_recording.mp4 \
     --target-host 192.168.1.20 \
     --port 9876 \
     --fps 30
   ```
2. **Trên Jetson:** Khởi động Backend Service:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
3. **Kết quả:** Jetson tiếp nhận luồng như thể đang kết nối với camera thật, xử lý toàn bộ pipeline và sẵn sàng phục vụ hiển thị lên Web HUD.

---

## 4. Biên Dịch & Đánh Giá TensorRT Model Trên Jetson

1. **Xuất mô hình từ PyTorch sang ONNX (thực hiện trên Laptop hoặc Jetson):**
   ```bash
   yolo export model=yolov8n-seg.pt format=onnx imgsz=720,1280 dynamic=False
   ```

2. **Tối ưu hóa sang TensorRT FP16 Engine (chạy trực tiếp trên Jetson GPU):**
   ```bash
   /usr/src/tensorrt/bin/trtexec \
     --onnx=yolov8n-seg.onnx \
     --saveEngine=weights/yolov8n-seg.engine \
     --fp16 \
     --workspace=2048
   ```

3. **Kiểm tra hiệu năng phần cứng trên Jetson:**
   - Dùng lệnh `jtop` (Jetson Stats) trên một tab terminal khác để theo dõi nhiệt độ, mức tải GPU (%), và bộ nhớ VRAM sử dụng (phải thỏa tiêu chí $< 4.5\text{ GB}$).
