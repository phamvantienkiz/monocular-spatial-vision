# Sổ Cái Backlog (Story Index) — Release 1: Standalone Sandbox

> **Layer:** Implementation Layer (`docs/implementation/release-1/backlog/mono-perception-story-index.md`)  
> **Release:** Release 1 (Phase 1 Sandbox)  
> **Status:** Active Ledger  

---

## 1. Backlog Stories Registry

| Story ID | Story Title | Priority | Status | Architecture Guardrails Cited |
| :--- | :--- | :--- | :--- | :--- |
| [US-001](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/backlog/stories/US-001.md) | Thu nhận ảnh Pcam 5C & Đóng gói Telemetry IMU qua Socket mạng | **Must Have** | Backlog | `04-deployment`, `05-data`, `09-design`, `10-folder` |
| [US-002](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1/backlog/stories/US-002.md) | Tính toán Cự ly Tiếp xúc Mặt sàn bằng IPM có Bù trừ Góc Nghiêng | **Must Have** | Backlog | `05-data`, `06-ai`, `09-design`, `10-folder` |
| *US-003* | *Tích hợp YOLOv8-seg TensorRT FP16 trích xuất đáy mặt nạ đối tượng* | *Must Have* | Backlog | `06-ai`, `09-design` |
| *US-004* | *Khôi phục Kích thước Vật lý và Xuất Hộp Bao 3D Bounding Box* | *Must Have* | Backlog | `05-data`, `06-ai`, `08-integration` |
| *US-005* | *Kịch bản Đo Đối Chuẩn Tự Động với Thước Laser Ground Truth* | *Should Have* | Backlog | `02-high-level`, `05-data` |

---

## 2. Sprint Execution Rules for AI Coding Agents

1. **Guardrails Compliance:** Không bao giờ viết code trực tiếp nếu không đọc kỹ mục Architecture Guardrails trong từng User Story.
2. **Acceptance Criteria Verification:** Phải chạy script kiểm thử tự động xác nhận 100% tiêu chí Given-When-Then trong AC trước khi đóng Story.
3. **Traceability:** Mọi commit git phải gắn liền với mã định danh Story (ví dụ: `feat(US-001): implement binary frame packer`).
