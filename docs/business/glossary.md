# Domain Glossary & Ubiquitous Language — Monocular Spatial Vision

> **Layer:** Business Layer (`docs/business/glossary.md`)  
> **Project:** Monocular Spatial Vision  
> **Purpose:** Thống nhất định nghĩa ngôn ngữ chung (Ubiquitous Language) giữa nhóm nghiên cứu, kỹ sư phần mềm, và các AI Agent.  

---

## 1. Domain Terminology

| Thuật ngữ | Ký hiệu / Tên tiếng Anh | Định nghĩa & Bối cảnh sử dụng |
| :--- | :--- | :--- |
| **Monocular Vision** | Camera đơn | Hệ thống thị giác chỉ sử dụng một ống kính quang học duy nhất, không có độ đo chiều sâu hình học lập thể trực tiếp. |
| **Pcam 5C** | Digilent Pcam 5C | Module camera 5 megapixel trang bị cảm biến OmniVision OV5640, giao tiếp qua cáp MIPI CSI-2 15 chân. |
| **IPM** | Inverse Perspective Mapping | Thuật toán chiếu phối cảnh ngược từ không gian ảnh 2D xuống mặt phẳng sàn giả định để khôi phục cự ly $Z$ thực tế. |
| **Metric Depth** | Độ sâu theo thang đo mét | Độ sâu thực có đơn vị vật lý (mét) thay vì độ sâu tương đối (Relative Depth) chỉ biểu thị quan hệ trước/sau giữa các pixel. |
| **Scale Ambiguity** | Sự mơ hồ về tỉ lệ | Bản chất toán học của camera đơn: một vật thể nhỏ ở gần tạo ra hình ảnh chiếu trên cảm biến giống hệt vật thể lớn ở xa nếu không có thông tin neo tỉ lệ (Scale Anchor). |
| **Ground Contact Point** | Điểm tiếp xúc mặt sàn | Tọa độ pixel $(u, v)$ tại đáy của đối tượng tiếp giáp với mặt phẳng sàn, dùng làm đầu vào cho công thức tính toán IPM. |
| **3D Bounding Box** | Hộp bao 3D | Khối hộp chữ nhật không gian xác định bởi tâm $(X, Y, Z)$, kích thước $(L, W, H)$, và hướng quay (yaw angle $\theta_y$) bao bọc vật thể thực. |
| **Intrinsics** | Thông số nội suy camera | Ma trận $K$ bao gồm tiêu cự $(f_x, f_y)$, điểm chính $(c_x, c_y)$, và các hệ số méo thấu kính $(k_1, k_2, p_1, p_2)$. |
| **Extrinsics** | Thông số ngoại quan camera | Ma trận biến đổi $[R \mid T]$ mô tả vị trí và góc quay của camera so với hệ quy chiếu chuẩn (mặt sàn, robot base_footprint, hoặc LiDAR). |
| **Pitch Angle** | Góc chúc ($\theta$) | Góc nghiêng của trục quang học camera so với mặt phẳng nằm ngang song song với sàn. |
| **Roll Angle** | Góc nghiêng ngang ($\phi$) | Góc xoay của camera quanh trục quang học (thường được căn chỉnh cơ khí triệt tiêu $\approx 0$). |
| **AbsRel** | Absolute Relative Error | Chỉ số đánh giá sai số tương đối tuyệt đối: $\frac{1}{N} \sum \frac{\|d_{\text{pred}} - d_{\text{gt}}\|}{d_{\text{gt}}}$. |
| **RMSE** | Root Mean Square Error | Căn bậc hai của sai số bình phương trung bình: $\sqrt{\frac{1}{N} \sum (d_{\text{pred}} - d_{\text{gt}})^2}$. |
| **Ground Truth (GT)** | Dữ liệu tham chiếu chuẩn | Tọa độ và khoảng cách thực tế đo bằng thước laser quang học chuyên dụng ($\pm 1.5\text{mm}$). |
| **Standalone Sandbox** | Môi trường kiểm thử độc lập | Cấu hình thử nghiệm tĩnh trên giá đỡ thí nghiệm, tách biệt khỏi các sai số cơ khí và odometry của robot. |
