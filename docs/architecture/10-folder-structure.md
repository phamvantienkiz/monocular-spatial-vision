# 10 - Repository Folder Structure Invariants

> **Layer:** Architecture Layer (`docs/architecture/10-folder-structure.md`)  
> **Status:** Single Source of Truth — Living Architecture  

---

## 1. Master Repository Directory Layout

Cấu trúc thư mục của repository `monocular-spatial-vision` được quy định bất biến như sau:

```
monocular-spatial-vision/
│
├── .agents/                           ← Cấu hình AI Agent, MCP server & Bộ Skills
│   └── skills/                        ← Tập hợp các skills chuyên sâu (clean-code, system-design...)
│
├── docs/                              ← HỆ THỐNG TÀI LIỆU KIẾN TRÚC 3 TẦNG
│   ├── business/                      ← Tầng 1: Mục tiêu kinh doanh & nghiệp vụ (BRD, Roadmap)
│   ├── architecture/                  ← Tầng 2: Nguồn chân lý duy nhất & Bất biến hệ thống
│   │   └── adr/                       ← Sổ cái quyết định kiến trúc (ADR-xxx)
│   ├── implementation/                ← Tầng 3: Tài liệu bàn giao theo Release/Sprint
│   │   └── release-1/                 ← Giai đoạn 1: Standalone Sandbox
│   │       ├── backlog/               ← Sổ cái Backlog & User Stories có Guardrails
│   │       │   └── stories/
│   │       ├── api/                   ← Đặc tả endpoint / topics của release
│   │       ├── frontend/              ← Đặc tả màn hình / UI telemetry của release
│   │       └── qa/                    ← Kế hoạch kiểm thử & Test cases
│   ├── views/                         ← Nơi lưu trữ duy nhất các bản vẽ HTML/SVG Standalone
│   ├── reports/                       ← Báo cáo nghiên cứu hàn lâm & hồ sơ kỹ thuật chuyên sâu
│   └── research/                      ← Dữ liệu nghiên cứu phác thảo ban đầu
│
├── configs/                           ← Tệp cấu hình hệ thống, YAML calibration
│   ├── calib_pcam5c.yaml              # Ma trận K, hệ số méo, chiều cao và góc pitch
│   ├── capture_pi.yaml                # Cấu hình V4L2 và port socket của Pi 3
│   └── perception_jetson.yaml         # Trọng số model YOLOv8-seg, TensorRT FP16 config
│
├── mono_perception/                   ← MÃ NGUỒN CỐT LÕI (PYTHON / ROS 2 PACKAGES)
│   ├── pi_capture_agent/              # Mã nguồn chạy trên Raspberry Pi 3
│   ├── mono_ingest/                   # Node tiếp nhận luồng dữ liệu mạng & buffer
│   ├── mono_calib/                    # Thư viện xử lý ma trận và biến đổi hình học
│   ├── depth_engine/                  # Thư viện tính IPM & suy luận Metric Depth
│   ├── object3d/                      # Thư viện tính toán 3D Bounding Box
│   └── nodes/                         # ROS 2 entrypoint nodes (mono_spatial_node)
│
├── tests/                             ← KIỂM THỬ ĐỘC LẬP
│   ├── unit/                          # Kiểm thử đơn vị các hàm thuần túy (IPM, Geometry)
│   ├── integration/                   # Kiểm thử kết nối socket, pipeline suy luận
│   └── benchmark/                     # Kiểm thử so sánh dữ liệu với thước Laser Ground Truth
│
├── tools/                             # Các kịch bản tiện ích (Calibration tool, Viewer)
├── tasks/                             # Quản lý tác vụ AI Agent (todo.md, lessons.md)
├── AGENTS.md                          # Tệp kiểm soát chính của Antigravity Agent
├── README.md                          # Giới thiệu tổng quan & bản quyền
└── LICENSE                            # Bản quyền thuộc ASIC Lab, UIT
```

---

## 2. Invariant Rules for File Placement

1. **Pure Markdown Invariant:** Mọi tài liệu nằm trong `docs/business/`, `docs/architecture/`, `docs/implementation/` phải là file Markdown thuần (`.md`).
2. **Centralized HTML Views Invariant:** Mọi bản vẽ tương tác HTML/SVG standalone bắt buộc phải đặt tại `docs/views/`.
3. **No Code in Docs:** Tuyệt đối không lưu trữ các file mã nguồn thực thi (`.py`, `.sh`, `.cpp`) bên trong thư mục `docs/`. Mọi mã nguồn phải nằm trong `mono_perception/`, `tools/` hoặc `tests/`.
4. **Configuration Centralization:** Mọi tham số phần cứng (chiều cao camera, ma trận nội suy, port mạng) phải nằm trong thư mục `configs/`, không được hardcode trong mã nguồn.
