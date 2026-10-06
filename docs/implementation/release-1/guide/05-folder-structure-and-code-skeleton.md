# Cấu Trúc Mã Nguồn & Tổ Chức Dịch Vụ (Folder Structure & Code Skeleton)

> **Layer:** Implementation Layer (`docs/implementation/release-1/guide/05-folder-structure-and-code-skeleton.md`)  
> **Release:** Release 1 (Phase 1 Sandbox)  
> **Mô hình kiến trúc:** Modular Microservices, tuân thủ chặt chẽ tiêu chuẩn [fastapi-backend-scaffold](file:///E:/UIT/monocular-spatial-vision/.agents/skills/fastapi-backend-scaffold/SKILL.md) và [AGENTS.md](file:///E:/UIT/monocular-spatial-vision/AGENTS.md).  

---

## 1. Bản Đồ Thư Mục Toàn Dự Án (Master Repository Layout)

```
monocular-spatial-vision/
│
├── .agents/                               # Cấu hình AI Agent & Skills
├── docs/                                  # HỆ THỐNG TÀI LIỆU KIẾN TRÚC & TRIỂN KHAI
│   ├── business/                          # BRD, Roadmap, Stakeholders
│   ├── architecture/                      # Nguồn chân lý kiến trúc 14 chương
│   └── implementation/release-1/          # Hồ sơ nghiệm thu PRD, SRS, Story Backlog
│       ├── guide/                         # [HƯỚNG DẪN THỰC THI & KỸ THUẬT CHI TIẾT]
│       │   ├── 00-overview-and-dev-workflow.md
│       │   ├── 01-pi3-capture-and-streaming-guide.md
│       │   ├── 02-jetson-backend-service-guide.md
│       │   ├── 03-web-hud-and-laptop-inspection.md
│       │   ├── 04-step-by-step-integration-and-testing-plan.md
│       │   ├── 05-folder-structure-and-code-skeleton.md
│       │   └── README.md
│
├── configs/                               # CẤU HÌNH HỆ THỐNG & HIỆU CHUẨN
│   ├── calib_pcam5c.yaml                  # Ma trận K, hệ số méo, chiều cao hc, pitch tĩnh
│   ├── capture_pi.yaml                    # Cấu hình V4L2 và địa chỉ socket đích trên Pi 3
│   └── perception_jetson.yaml             # Cấu hình TensorRT, ngưỡng nhận diện, port API
│
├── services/
│   │
│   ├── pi_capture_agent/                  # [SERVICE 1: RASPBERRY PI 3]
│   │   ├── .venv/                         # Môi trường ảo riêng trên Pi 3 (KHÔNG commit)
│   │   ├── pyproject.toml                 # Khai báo phụ thuộc: opencv, smbus2, pyyaml
│   │   ├── README.md                      # Hướng dẫn chạy và test cục bộ trên Pi 3
│   │   └── pi_capture_agent/
│   │       ├── __init__.py
│   │       ├── cli.py                     # Entrypoint: --mode snapshot/preview/test-imu/stream
│   │       ├── camera.py                  # Driver V4L2 OV5640, buffer capture
│   │       ├── imu.py                     # Đọc MPU6050 qua I2C (smbus2), tính pitch/roll
│   │       ├── packer.py                  # Đóng gói Binary Header 36 bytes Big-Endian
│   │       └── streamer.py                # TCP Client socket có exponential backoff reconnect
│   │
│   └── backend/                           # [SERVICE 2: JETSON AGX XAVIER] (Chuẩn fastapi-backend-scaffold)
│       ├── .venv/                         # Môi trường ảo riêng trên Jetson (KHÔNG commit)
│       ├── pyproject.toml                 # Khai báo phụ thuộc PEP 621 (FastAPI, Uvicorn...)
│       ├── .env.example                   # Biến môi trường mẫu
│       ├── README.md                      # Hướng dẫn khởi động service và test
│       ├── logs/                          # Runtime logs (.gitkeep)
│       ├── tests/                         # Pytest unit & integration tests
│       │   ├── conftest.py
│       │   ├── api/v1/test_endpoints.py
│       │   └── services/test_geometry.py
│       │
│       └── app/                           # Mã nguồn cốt lõi FastAPI Backend
│           ├── main.py                    # Khởi tạo FastAPI, Lifespan (Socket Server + TRT warm-up)
│           │
│           ├── core/                      # Cấu hình & Logging hệ thống
│           │   ├── config.py              # Pydantic Settings đọc từ .env và configs/
│           │   └── logging.py             # Cấu hình log xoay vòng có cấu trúc
│           │
│           ├── middlewares/               # Tầng middleware xử lý toàn cục
│           │   ├── __init__.py            # Đăng ký tập trung các middleware
│           │   ├── request_id.py          # Gắn X-Request-ID cho mỗi request
│           │   ├── logging.py             # Log request/response timing
│           │   ├── error_handler.py       # Bắt ngoại lệ an toàn, trả về JSON 500
│           │   └── cors.py                # Cấu hình CORS mở cho Laptop truy cập
│           │
│           ├── schemas/                   # Pydantic Schemas (Dữ liệu vào/ra)
│           │   ├── telemetry.py           # Schema IMU, Latency, FPS
│           │   ├── detection.py           # Schema 2D Mask, 3D Bounding Box
│           │   └── benchmark.py           # Schema đối chuẩn Laser Ground Truth
│           │
│           ├── services/                  # TẦNG NGHIỆP VỤ & TÍNH TOÁN CỐT LÕI
│           │   ├── ingest_service.py      # TCP Socket Server daemon nhận stream, RingBuffer
│           │   ├── model_service.py       # YOLOv8-seg TensorRT engine runner (có mock fallback)
│           │   ├── geometry_service.py    # IPM Ground Contact Solver & 3D Box Lifting
│           │   ├── ros2_service.py        # ROS 2 Publisher node (khi chạy trong ROS environment)
│           │   └── benchmark_service.py   # So khớp khoảng cách laser, tính AbsRel, RMSE
│           │
│           ├── api/v1/                    # TẦNG CONTROLLER / ROUTER
│           │   ├── router.py              # Tổng hợp tất cả router con v1
│           │   └── endpoints/
│           │       ├── stream.py          # GET /api/v1/stream/live (MJPEG overlay stream)
│           │       ├── telemetry.py       # GET /api/v1/telemetry & WS /api/v1/ws/telemetry
│           │       ├── benchmark.py       # POST /api/v1/benchmark/record
│           │       └── system.py          # GET /health, GET /api/v1/system/status
│           │
│           └── static/hud/                # FRONTEND OPERATOR WEB HUD (Phục vụ Laptop)
│               ├── index.html             # Giao diện hiển thị trực quan không cần build
│               ├── app.js                 # WebSocket client, vẽ BEV 2D Canvas, Laser form
│               └── style.css              # Phong cách hiển thị dark-mode chuyên nghiệp
│
├── tools/                                 # BỘ CÔNG CỤ DÀNH CHO DEVELOPER TRÊN LAPTOP
│   ├── laptop/
│   │   ├── mock_ingest_server.py          # Laptop nhận stream từ Pi 3 để test Pi độc lập
│   │   ├── mock_camera_streamer.py        # Laptop bơm video mẫu sang Jetson để test AI độc lập
│   │   ├── camera_calibration.py          # Kịch bản bàn cờ hiệu chuẩn tìm ma trận K
│   │   └── live_hud_viewer.py             # Cửa sổ OpenCV desktop xem stream từ Jetson
│   └── benchmark/
│       └── eval_laser.py                  # Script tự động xuất bảng so sánh Markdown
│
├── data/                                  # DỮ LIỆU KIỂM THỬ NGOẠI TUYẾN
│   ├── samples/                           # Ảnh/video mẫu chụp từ Pcam 5C dùng cho mock
│   └── debug/                             # Nơi lưu snapshot kiểm tra (bị git ignore)
│
├── weights/                               # TRỌNG SỐ MÔ HÌNH AI (.gitkeep, bị git ignore)
│   ├── yolov8n-seg.pt                     # Trọng số PyTorch gốc
│   ├── yolov8n-seg.onnx                   # Trọng số ONNX trung gian
│   └── yolov8n-seg.engine                 # Trọng số TensorRT FP16 tối ưu hóa cho Jetson
│
├── AGENTS.md                              # Tệp quy chuẩn điều khiển AI Agent
├── README.md                              # Giới thiệu dự án
└── LICENSE                                # Bản quyền ASIC Lab, UIT
```

---

## 2. Đặc Tả Tệp Cấu Hình Phụ Thuộc (pyproject.toml)

### 2.1. Phía Pi 3 (`services/pi_capture_agent/pyproject.toml`)
Sử dụng gói nhẹ, không chứa thư viện AI:
```toml
[project]
name = "pi-capture-agent"
version = "0.1.0"
description = "Raspberry Pi 3 Pcam 5C capture and IMU streaming agent"
requires-python = ">=3.9"
dependencies = [
    "opencv-python-headless>=4.5.0",
    "smbus2>=0.4.0",
    "pyyaml>=6.0",
    "numpy>=1.21.0"
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0"
]
```

### 2.2. Phía Jetson (`services/backend/pyproject.toml`)
Tuân thủ chuẩn [fastapi-backend-scaffold](file:///E:/UIT/monocular-spatial-vision/.agents/skills/fastapi-backend-scaffold/SKILL.md):
```toml
[project]
name = "monocular-spatial-backend"
version = "0.1.0"
description = "Jetson AGX Xavier FastAPI Backend for Monocular 3D Perception"
requires-python = ">=3.8"
dependencies = [
    "fastapi>=0.100.0",
    "uvicorn[standard]>=0.22.0",
    "pydantic-settings>=2.0.0",
    "numpy>=1.21.0",
    "opencv-python-headless>=4.5.0",
    "pyyaml>=6.0",
    "rich>=13.0.0"
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "httpx>=0.24.0",
    "ruff>=0.1.0"
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

---

## 3. Quản Lý Môi Trường Biệt Lập (uv hoặc pip)

Theo nguyên tắc bất biến tại [AGENTS.md](file:///E:/UIT/monocular-spatial-vision/AGENTS.md):
- **Trên máy có `uv` (Laptop hoặc Jetson đã cài `uv`):**
  ```bash
  uv venv .venv
  source .venv/bin/activate
  uv pip install -e ".[dev]"
  ```
- **Trên máy dùng `pip` tiêu chuẩn (Raspberry Pi 3 hoặc Jetson cơ bản):**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -e ".[dev]"
  ```
Mọi lệnh chạy thực thi mã nguồn (`pytest`, `uvicorn`, `python -m ...`) **bắt buộc phải thực hiện sau khi `.venv` đã được kích hoạt**.
