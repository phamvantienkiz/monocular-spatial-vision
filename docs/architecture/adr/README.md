# Architecture Decision Records (ADR) Index

> **Layer:** Architecture Layer (`docs/architecture/adr/README.md`)  
> **Status:** Living Ledger of Technical Decisions  

---

## 1. What is an ADR?

Mỗi Architecture Decision Record (ADR) ghi lại một quyết định kiến trúc quan trọng, bao gồm bối cảnh, các giải pháp thay thế được cân nhắc, và cấu trúc đánh đổi **Solves / Worsens / Change it when**.

---

## 2. ADR Ledger

| ADR ID | Decision Title | Status | Date | Decision Summary |
| :--- | :--- | :--- | :--- | :--- |
| [ADR-001](file:///E:/UIT/monocular-spatial-vision/docs/architecture/adr/ADR-001.md) | Phân Tách Sandbox Nghiên Cứu Độc Lập & Lựa Chọn Kiến Trúc Camera Đơn Pcam 5C | **Accepted** | 2026-10-01 | Phân tách giai đoạn 1 thành Sandbox độc lập; chuyển từ Stereo sang Camera Đơn + IMU MPU6050 để khử ghép kênh sai số. |
| *ADR-002* | *Lựa Chọn Chiến Lược Đo Sâu Đơn Mắt Chính Thức (TBD)* | *Proposed* | Phase 2 | So sánh giữa Motion Stereo, Metric Depth Net và LiDAR Projection Fusion. |

---

## 3. ADR Structure Standard

Mọi ADR mới phải tuân theo cấu trúc chuẩn:
1. **Title & Status:** Proposed, Accepted, Deprecated, Superseded.
2. **Context & Problem Statement:** Lý do phát sinh vấn đề và bối cảnh kỹ thuật.
3. **Decision:** Quyết định được chọn.
4. **Trade-offs Framework:**
   - *Solves:* Giải quyết được những vấn đề gì?
   - *Worsens:* Phát sinh đánh đổi, gánh nặng hoặc nhược điểm gì mới?
   - *Change it when:* Khi nào thì quyết định này cần được xem xét lại hoặc thay thế?
5. **System Invariants Impacted:** Các tài liệu trong `docs/architecture/` bị ảnh hưởng.
