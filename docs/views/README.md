# Centralized HTML Visual Views Directory (`docs/views/`)

> **Layer:** Centralized Visual Views Layer (`docs/views/`)  
> **Status:** Standardized Directory Index  
> **Reference:** [documentation/SKILL.md (Section 10)](file:///E:/UIT/monocular-spatial-vision/.agents/skills/documentation/SKILL.md#L204-L245)

---

## 1. Purpose & Separation of Concerns

Thư mục `docs/views/` là **nơi lưu trữ tập trung duy nhất** cho toàn bộ các bản vẽ HTML/SVG tương tác, dashboard giám sát độc lập, mockups, và các sơ đồ kiến trúc trực quan dạng standalone của dự án Monocular Spatial Vision.

Cơ chế này đảm bảo sự phân tách tuyệt đối giữa tài liệu phân tích kỹ thuật và các giao diện hiển thị:
- **Tài liệu cốt lõi (`docs/business/`, `docs/architecture/`, `docs/implementation/`):** Tuân thủ tiêu chuẩn **Pure Markdown 100%**. Mọi sơ đồ bên trong tài liệu cốt lõi bắt buộc dùng cú pháp Mermaid chuẩn (`flowchart`, `sequenceDiagram`, `stateDiagram-v2`, `classDiagram`, `erDiagram`) hoặc bảng Markdown. Tuyệt đối không nhúng mã HTML/CSS/JS (`<script>`, `<style>`, `<div>`, `<canvas>`), không chèn chuỗi base64 image hoặc vứt các file ảnh rác vào thư mục tài liệu.
- **Bản vẽ trực quan (`docs/views/`):** Chứa các file HTML/SVG độc lập, có thể mở trực tiếp trên trình duyệt web, có tính tương tác cao (pan/zoom, toggle layers, visual inspection). Các tài liệu Markdown cốt lõi có thể tạo liên kết tham chiếu tới các view này:
  ```markdown
  > [!NOTE]
  > Để xem sơ đồ trực quan tương tác của topo hệ thống, xem [System Topology View](../../views/02-system-topology-view.html).
  ```

---

## 2. On-Demand Generation Invariant

> ⛔ **QUY TẮC BẤT BIẾN:** Các kỹ năng phân tích và lập tài liệu (`documentation`, `product-requirements`, `system-design`, `user-story-ac-writer`) **KHÔNG BAO GIỜ** tự động sinh các file HTML view trong quá trình làm việc thông thường nhằm tránh lãng phí context và phát sinh overhead.

Các file HTML trong `docs/views/` **CHỈ ĐƯỢC PHÉP TẠO RA** khi có yêu cầu rõ ràng, tường minh từ người dùng (ví dụ: *"hãy vẽ file HTML view trực quan cho kiến trúc này"*, *"tạo sơ đồ tương tác pan-zoom"*).

---

## 3. Delegation to Specialist Visual Skills

Khi người dùng yêu cầu tạo HTML view, Agent lấy thông tin từ tài liệu Markdown nguồn trong `docs/` (Nguồn chân lý duy nhất) và kích hoạt kỹ năng chuyên biệt tương ứng:

| Dạng Bản Vẽ Cần Sinh | Kỹ Năng Chuyên Trách Ủy Thác | Đầu Ra File Mẫu Trong `docs/views/` |
| :--- | :--- | :--- |
| **Sơ đồ Kiến trúc / Topo / C4 / Sequence có style** | `diagram-design` / `html-diagram` | `02-high-level-topology-view.html` |
| **Mô phỏng Giao diện / HUD Telemetry / Dashboard** | `design-artifact` / `html` / `html-prototype` | `operator-hud-view.html` |
| **Bản đồ Lộ trình & Timeline Kế hoạch Phối cảnh** | `html-plan` | `product-roadmap-view.html` |
| **Mô hình Khung dây Không gian 3D tương tác** | `3dviz-pro-max` | `3d-spatial-scene-view.html` |

---

## 4. Current Views Catalog

Danh mục các bản vẽ trực quan tương tác đã được sinh và kiểm chứng độc lập:

| File Name | Description & Visual Skills Used | Source Documents | Generated Date |
| :--- | :--- | :--- | :--- |
| [index.html](file:///E:/UIT/monocular-spatial-vision/docs/views/index.html) | **Master Explorer Portal:** Cổng điều hướng tập trung toàn bộ hệ thống, tích hợp tìm kiếm nhanh, lọc phân lớp và tổng quan số liệu. *(design-artifact, ui-ux-pro-max)* | Toàn bộ `docs/` | 2026-10-05 |
| [01-business-roadmap-view.html](file:///E:/UIT/monocular-spatial-vision/docs/views/01-business-roadmap-view.html) | **Lộ Trình & Nghiệp Vụ:** Timeline 4 giai đoạn, thẻ chỉ số KPI/ROI, ma trận RACI 6 nhóm stakeholders và từ điển Glossary tương tác. *(html-plan, design-artifact)* | `docs/business/{brd, roadmap, glossary, stakeholders}.md` | 2026-10-05 |
| [02-system-architecture-view.html](file:///E:/UIT/monocular-spatial-vision/docs/views/02-system-architecture-view.html) | **Kiến Trúc Hệ Thống & Topo:** Sơ đồ Topo tương tác click để xem chi tiết node, bộ soi nhị phân Binary Frame Header 36-byte, ma trận ROS 2 Topics và ADR-001. *(html-diagram, ui-styling)* | `docs/architecture/{01..05, 07..10, adr/ADR-001}.md` | 2026-10-05 |
| [03-ai-perception-pipeline-view.html](file:///E:/UIT/monocular-spatial-vision/docs/views/03-ai-perception-pipeline-view.html) | **Pipeline AI & Mô Phỏng IPM:** Chuỗi xử lý 7 bước, bộ mô phỏng tính toán cự ly hình học và tia chiếu Ray Tracing thời gian thực trên Canvas, chứng minh 4 giả thuyết H1-H4. *(html-diagram, design-artifact)* | `docs/architecture/06-ai.md`, `docs/reports/{01..04}.md` | 2026-10-05 |
| [04-research-synthesis-report-view.html](file:///E:/UIT/monocular-spatial-vision/docs/views/04-research-synthesis-report-view.html) | **Báo Cáo Nghiên Cứu & Cổng RQ:** Khung câu hỏi RQ0-RQ5, cẩm nang xử lý cổng quyết định thất bại, so sánh 3 ứng viên Depth và dữ liệu đối chuẩn laser Bosch. *(html, design-artifact)* | `docs/reports/{00..06}.md` | 2026-10-05 |
| [05-operator-hud-prototype-view.html](file:///E:/UIT/monocular-spatial-vision/docs/views/05-operator-hud-prototype-view.html) | **Prototype HUD & Khung Dây 3D:** Khung nhìn quang học 1280x720 giả lập với hộp bao 3D wireframe, radar quét BEV 2D, điều khiển Pitch/Roll động và giám sát telemetry. *(html-prototype, html-wireframe, ui-ux-pro-max)* | `docs/architecture/{11..14}.md`, `docs/implementation/frontend` | 2026-10-05 |
