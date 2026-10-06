# Release 1 Master Index — Standalone Monocular 3D Perception Sandbox

> **Layer:** Implementation Layer (`docs/implementation/release-1/README.md`)  
> **Release:** Release 1 (Phase 1 Sandbox)  
> **Status:** Active Baseline  

---

## 1. Cấu Trúc Tài Liệu Nghiệm Thu & Triển Khai Release 1

Thư mục `docs/implementation/release-1/` chứa toàn bộ hồ sơ kỹ thuật, yêu cầu chức năng, backlog phát triển và bộ hướng dẫn triển khai thực địa cho Release 1:

### 1.1. Hồ Sơ Yêu Cầu & Thiết Kế Kỹ Thuật (Specifications)
- [prd.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/prd.md): Định nghĩa mục tiêu Release 1, phạm vi in-scope, Acceptance Criteria & KPIs cấp release.
- [srs.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/srs.md): Đặc tả 9 yêu cầu chức năng (FR-01 → FR-09) và 3 yêu cầu phi chức năng (NFR-01 → NFR-03).
- [technical-design.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/technical-design.md): Sơ đồ tuần tự xử lý frame (Sequence) và luồng trích xuất điểm tiếp xúc đáy (Activity).
- [migration.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/migration.md): Hướng dẫn thiết lập môi trường biệt lập (`uv`/`venv`) và cân chỉnh cơ khí.
- [api/v1.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/api/v1.md): Giao thức socket streaming nhị phân và chuẩn các topic ROS 2 v1.
- [frontend/ui-spec.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/frontend/ui-spec.md): Đặc tả giao diện Operator Telemetry HUD & hiển thị BEV.
- [qa/test-cases.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/qa/test-cases.md): Kế hoạch kiểm thử chất lượng và ma trận Benchmark Test Cases.
- [backlog/mono-perception-story-index.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/backlog/mono-perception-story-index.md): Sổ cái Backlog (User Stories US-001 đến US-005) kèm Architecture Guardrails.

---

### 1.2. Bộ Hướng Dẫn Thực Thi Thực Địa ([`guide/`](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/guide/))

Bộ hướng dẫn kỹ thuật chi tiết giúp developer kết nối laptop, kiểm nghiệm máy tính nhúng headless và tích hợp từng bước:

| Tệp hướng dẫn | Nội dung trọng tâm |
| :--- | :--- |
| [00-overview-and-dev-workflow.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/guide/00-overview-and-dev-workflow.md) | Phân định kiến trúc 3 thực thể (Laptop - Pi 3 - Jetson AGX) và giải quyết 3 bài toán thực địa |
| [01-pi3-capture-and-streaming-guide.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/guide/01-pi3-capture-and-streaming-guide.md) | Đấu nối Pcam 5C & MPU6050, driver OV5640, chụp ảnh ra file, stream kiểm thử về Laptop |
| [02-jetson-backend-service-guide.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/guide/02-jetson-backend-service-guide.md) | Dev qua Remote-SSH, chuẩn FastAPI Scaffold, test TensorRT bằng video mẫu offline |
| [03-web-hud-and-laptop-inspection.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/guide/03-web-hud-and-laptop-inspection.md) | Web HUD (MJPEG + WebSocket + BEV Canvas), giám sát Jetson headless trực tiếp từ Laptop |
| [04-step-by-step-integration-and-testing-plan.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/guide/04-step-by-step-integration-and-testing-plan.md) | Lộ trình kiểm thử 6 bước tuần tự (Laptop Unit Test $\to$ Pi Test $\to$ Jetson Test $\to$ E2E $\to$ Laser) |
| [05-folder-structure-and-code-skeleton.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/guide/05-folder-structure-and-code-skeleton.md) | Cấu trúc thư mục module dịch vụ hoàn chỉnh, cấu hình `pyproject.toml` và `.venv` |
| [README.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/guide/README.md) | Bản đồ mục lục chuyên đề hướng dẫn triển khai thực tế |
