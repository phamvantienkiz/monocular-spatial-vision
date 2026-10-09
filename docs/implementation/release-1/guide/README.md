# Release 1 Documentation Index — Practical Implementation Guide

> **Layer:** Implementation Layer (`docs/implementation/release-1/guide/README.md`)  
> **Release:** Release 1 (Phase 1 Sandbox)  
> **Status:** Official Implementation Guide for Engineering  

---

## 1. Giới Thiệu Bộ Tài Liệu Triển Khai Thực Chiến Release 1

Bộ tài liệu này được thiết kế để giải quyết toàn bộ bài toán kỹ thuật thực địa trong môi trường nhúng, phân định rõ ràng vai trò của **Laptop của Developer**, **Raspberry Pi 3 (Capture Node)** và **Jetson AGX Xavier (AI & Geometry Backend)**.

Bộ tài liệu thay thế các hướng dẫn lý thuyết chung chung bằng quy trình phát triển, kiểm nghiệm ngoại tuyến, cô lập phần cứng và giám sát trực quan thời gian thực.

---

## 2. Danh Mục Các Chuyên Đề Kỹ Thuật

| Chuyên đề | Tệp tài liệu | Tóm tắt nội dung chính |
| :--- | :--- | :--- |
| **00. Tổng quan & Luồng Dev** | [00-overview-and-dev-workflow.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/guide/00-overview-and-dev-workflow.md) | Sơ đồ luồng 3 thực thể (Laptop - Pi 3 - Jetson), giải đáp cốt lõi 3 câu hỏi thực địa |
| **01. Raspberry Pi 3 Capture** | [01-pi3-capture-and-streaming-guide.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/guide/01-pi3-capture-and-streaming-guide.md) | Đấu nối Pcam 5C & MPU6050, driver OV5640, test độc lập trên Pi, stream về Laptop |
| **02. Jetson Backend Service** | [02-jetson-backend-service-guide.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/guide/02-jetson-backend-service-guide.md) | Dev qua Remote-SSH, chuẩn FastAPI Scaffold, test TensorRT bằng video mẫu offline |
| **03. Web HUD & Giám sát** | [03-web-hud-and-laptop-inspection.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/guide/03-web-hud-and-laptop-inspection.md) | Giải pháp xem trực quan khi Jetson headless: MJPEG stream, WebSocket, BEV Canvas trên Laptop |
| **04. Kế hoạch Tích hợp 6 Bước** | [04-step-by-step-integration-and-testing-plan.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/guide/04-step-by-step-integration-and-testing-plan.md) | Quy trình 6 nấc thang: Unit test Laptop $\to$ Test Pi $\to$ Test Jetson $\to$ Ghép nối $\to$ Đo laser |
| **05. Cấu trúc Mã nguồn** | [05-folder-structure-and-code-skeleton.md](file:///D:/ASICLAB/monocular-spatial-vision/docs/implementation/release-1/guide/05-folder-structure-and-code-skeleton.md) | Bố cục thư mục `services/`, `backend/`, `tools/`, cấu hình `pyproject.toml` và `.venv` |
| **06. Hướng dẫn Bring-up Pi 3 & Laptop** | [06-pi3-step-by-step-bringup-and-verification-guide.md](file:///D:/ASICLAB/monocular-spatial-vision/docs/implementation/release-1/guide/06-pi3-step-by-step-bringup-and-verification-guide.md) | Hướng dẫn chi tiết từng bước: Git clone, cài đặt `uv`, tạo `.venv`, test IMU/Cam và giám sát qua Web HUD/Laptop |


---

## 3. Liên Kết Đến Các Hồ Sơ Nghiệm Thu
- [docs/implementation/release-1/prd.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/prd.md) — PRD và 4 chỉ số KPIs (AC-01 đến AC-04).
- [docs/implementation/release-1/srs.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/srs.md) — 9 yêu cầu chức năng (FR-01 đến FR-09) và 3 yêu cầu phi chức năng.
- [docs/implementation/release-1/qa/test-cases.md](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/qa/test-cases.md) — Ma trận kiểm thử đo đối chuẩn bằng thước laser Bosch GLM.
