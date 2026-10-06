# QA Test Plan & Test Cases — Release 1 Sandbox

> **Layer:** Implementation Layer (`docs/implementation/release-1/qa/test-cases.md`)  
> **Release:** Release 1 (Phase 1 Sandbox)  
> **Status:** Approved Baseline  

---

## 1. Test Strategy & Ground-Truth Verification Rig

Mọi bài kiểm thử độ chính xác định lượng đều được thực hiện trên giá đỡ thí nghiệm chuẩn tại phòng lab ASIC:
1. Đặt mục tiêu kiểm thử (người, ghế tiêu chuẩn, hộp carton có kích thước đã đo đạc bằng thước kẹp cơ khí) tại các mốc cự ly xác định trên sàn: $0.5\text{m}, 1.0\text{m}, 1.5\text{m}, 2.0\text{m}, 2.5\text{m}, 3.0\text{m}$.
2. Dùng thước đo laser Bosch GLM ($\pm 1.5\text{mm}$) chiếu từ tâm giá đỡ camera tới điểm tiếp xúc mặt đất của vật thể để ghi nhận khoảng cách thực $d_{\text{gt}}$.
3. Thu nhận giá trị dự đoán $d_{\text{pred}}$ từ hệ thống và tính toán sai số.

---

## 2. Quantitative Benchmark Test Cases

| Test Case ID | Test Description | Target Range | Pass/Fail Criteria | Execution Protocol |
| :--- | :--- | :--- | :--- | :--- |
| **TC-IPM-01** | Độ chính xác cự ly tĩnh tại khoảng cách gần | $0.5\text{m} - 1.5\text{m}$ | $\text{AbsRel} \le 3.0\%$ | 30 mẫu đo liên tục trên 3 loại vật cản |
| **TC-IPM-02** | Độ chính xác cự ly tĩnh tại khoảng cách trung bình | $1.5\text{m} - 3.0\text{m}$ | $\text{AbsRel} \le 5.0\%$ | 30 mẫu đo liên tục trên 3 loại vật cản |
| **TC-TILT-01** | Khả năng miễn nhiễm với góc nghiêng động (IMU compensation) | $1.0\text{m} - 2.5\text{m}$ | Tăng sai số $\le 1.0\%$ khi nghiêng $\pm 5^\circ$ | Nghiêng cưỡng bức giá đỡ cơ khí và đo đối chiếu |
| **TC-LAT-01** | Độ trễ toàn chu trình từ cảm biến tới 3D BBox | Toàn dải | End-to-end Latency $\le 60\text{ms}$ ($\ge 16.6\text{ FPS}$) | Timestamp profiling từ header Pi tới Jetson output |
| **TC-NET-01** | Độ ổn định truyền stream mạng Ethernet | Toàn dải | Frame Drop Rate $< 0.1\%$ trong 30 phút | Socket sniffer và đếm `frame_id` nhảy cóc |
| **TC-BOX-01** | Sai số ước lượng kích thước vật lý 3D $[L, W, H]$ | $1.0\text{m} - 2.0\text{m}$ | Sai số kích thước $\le 10.0\%$ | So sánh với kích thước thực tế đo bằng thước dây |
