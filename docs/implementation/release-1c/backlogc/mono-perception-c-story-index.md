# Sổ Cái Backlog (Story Index) — Release 1c: C/C++ Native Standalone Sandbox

> **Layer:** Implementation Layer (`docs/implementation/release-1c/backlogc/mono-perception-c-story-index.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Status:** Active Ledger (Audit-Remediated)  

---

## 1. Backlog Stories Registry (Danh Mục User Stories)

| Story ID | Story Title (Tên User Story) | Priority | Status | Architecture Guardrails Cited |
| :--- | :--- | :---: | :---: | :--- |
| [US-C01](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/backlogc/storiesc/US-C01.md) | Thu nhận V4L2 MMAP (`media-ctl` + `v4l-subdev0`), Tách Kênh NEON `vld2_u8` & Nén Ảnh `tjCompressFromYUV` | **Must Have** | Backlog | `04-deployment`, `05-data`, `09-design`, `10-folder` |
| [US-C02](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/backlogc/storiesc/US-C02.md) | Đọc IMU I2C, Triple-Buffer Drop-Stale & Truyền Dẫn Kép Wi-Fi / Ethernet (`--mode preview` & `--mode stream`) | **Must Have** | Backlog | `03-service`, `05-data`, `08-integration`, `09-design` |
| [US-C03](file:///E:/UIT/monocular-spatial-vision/docs/implementation/release-1c/backlogc/storiesc/US-C03.md) | Quản lý phụ thuộc cô lập bằng `uv` + `Conan 2.0` & Safe Native Build Harness (`-j2`) | **Must Have** | Backlog | `04-deployment`, `09-design`, `10-folder`, `AGENTS.md` |

---

## 2. Sprint Execution Rules for AI Coding Agents

1. **Guardrails Compliance:** Không bao giờ viết code trực tiếp nếu không đọc kỹ mục Architecture Guardrails trong từng User Story.
2. **Full Parity With Python Modes & Transports:** Bản C++ bắt buộc phải hỗ trợ đủ 6 chế độ CLI (`diag`, `snapshot`, `test-imu`, `preview`, `stream`, `test-perf`) và hoạt động trơn tru trên cả **Wi-Fi (`wlan0`)** lẫn **Ethernet (`eth0` qua Hub chuyển đổi USB Type-C sang RJ45 với Laptop hoặc nối thẳng Jetson AGX Xavier)**.
3. **Acceptance Criteria Verification:** Phải chạy script kiểm thử tự động xác nhận 100% tiêu chí Given-When-Then trong AC trước khi đóng Story.
4. **Traceability:** Mọi commit git phải gắn liền với mã định danh Story (ví dụ: `feat(US-C01): implement v4l2 mmap neon deinterleave and turbojpeg yuv422p`).
5. **Zero System Pollution:** Mọi bản build thử nghiệm hoặc cài đặt package đều phải giữ nguyên vẹn trong `.venv`, `.conan/` và `services/pi_capture_agent_cpp/build/` của repo; tuyệt đối không chỉnh sửa các tệp cấu hình toàn cục của hệ điều hành (`/etc/*`).
