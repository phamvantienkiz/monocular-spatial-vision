# Sổ Cái Backlog (Story Index) — Release 1c: C/C++ Native Standalone Sandbox

> **Layer:** Implementation Layer (`docs/implementation/release-1c/backlogc/mono-perception-c-story-index.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Status:** Active Ledger  

---

## 1. Backlog Stories Registry (Danh Mục User Stories)

| Story ID | Story Title (Tên User Story) | Priority | Status | Architecture Guardrails Cited |
| :--- | :--- | :---: | :---: | :--- |
| [US-C01](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/backlogc/storiesc/US-C01.md) | Thu nhận V4L2 MMAP trực tiếp & Nén ảnh TurboJPEG ARM NEON | **Must Have** | Backlog | `04-deployment`, `05-data`, `09-design`, `10-folder` |
| [US-C02](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/backlogc/storiesc/US-C02.md) | Đọc IMU qua Linux I2C ioctl & RingBuffer Streamer đa luồng | **Must Have** | Backlog | `03-service`, `05-data`, `08-integration`, `09-design` |
| [US-C03](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/backlogc/storiesc/US-C03.md) | Quản lý phụ thuộc cô lập bằng uv + Conan 2.0 & Safe Native Build Harness | **Must Have** | Backlog | `04-deployment`, `09-design`, `10-folder`, `AGENTS.md` |

---

## 2. Sprint Execution Rules for AI Coding Agents

1. **Guardrails Compliance:** Không bao giờ viết code trực tiếp nếu không đọc kỹ mục Architecture Guardrails trong từng User Story.
2. **Acceptance Criteria Verification:** Phải chạy script kiểm thử tự động xác nhận 100% tiêu chí Given-When-Then trong AC trước khi đóng Story.
3. **Traceability:** Mọi commit git phải gắn liền với mã định danh Story (ví dụ: `feat(US-C01): implement zero-copy v4l2 mmap and turbojpeg neon`).
4. **Zero System Pollution:** Mọi bản build thử nghiệm hoặc cài đặt package đều phải giữ nguyên vẹn trong `.venv`, `.conan/` và `build/` của repo.
