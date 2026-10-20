# QA Test Plan & Test Cases — Release 1c (C/C++ Native)

> **Layer:** Implementation Layer (`docs/implementation/release-1c/qac/test-cases.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Status:** Approved Baseline  

---

## 1. Mục Tiêu & Phương Pháp Đo Đạc Định Lượng

Bộ kiểm thử chất lượng Release 1c tập trung vào 4 khía cạnh trọng tâm:
1. **Hiệu năng thời gian thực (Throughput & Latency):** Xác nhận đạt $\ge 25\text{ FPS}$ ổn định tại $1280 \times 720$.
2. **Hiệu quả tài nguyên (CPU & Memory Footprint):** Đảm bảo không quá tải 4 nhân Cortex-A53 và không chiếm quá $35\text{MB}$ RAM.
3. **Độ ổn định truyền dẫn & Khả năng phục hồi (Resilience):** Triệt tiêu hiện tượng lag hiển thị và tự động kết nối lại khi mạng đứt.
4. **Kiểm toán môi trường (Zero-Pollution & Memory Leak):** Không rò rỉ bộ nhớ và không làm ô nhiễm hệ thống toàn cục.

---

## 2. Ma Trận Test Cases Định Lượng C/C++ Native

| Test Case ID | Tên Bài Kiểm Thử | Mục Tiêu & Phạm Vi | Tiêu Chuẩn Đạt (Pass/Fail Criteria) | Giao Thức & Lệnh Thực Thi |
| :--- | :--- | :--- | :--- | :--- |
| **TC-CPP-01** | Độ trễ bắt hình V4L2 MMAP | $1280 \times 720$ UYVY @ $30\text{ FPS}$ | $\text{Avg Grab Time} \le \mathbf{3.5\text{ ms}}$ | Lệnh `--mode test-perf --frames 100`, đo thời gian `VIDIOC_DQBUF`. |
| **TC-CPP-02** | Độ trễ nén TurboJPEG ARM NEON | $1280 \times 720$, Quality 70, FastDCT | $\text{Avg Encode Time} \le \mathbf{11.0\text{ ms}}$ | Đo thời gian gọi C API `tjCompress2()` trên 500 frames liên tục. |
| **TC-CPP-03** | Tốc độ khung hình toàn chu trình Pi 3 | Bắt hình $\to$ Nén $\to$ Đóng Header 40B | Thông lượng $\ge \mathbf{25.0\text{ FPS}}$ (Kỳ vọng $30\text{ FPS}$) | Benchmark chế độ pipeline đa luồng trong 60 giây. |
| **TC-CPP-04** | Mức chiếm dụng CPU trên Raspberry Pi 3 | Toàn bộ tiến trình C++ khi đang stream | Tổng tải CPU trên 4 nhân $\le \mathbf{25.0\%}$ | Lệnh `pidstat -p [PID] 1 30` hoặc `htop` ghi nhận trung bình. |
| **TC-CPP-05** | Dấu ấn bộ nhớ RAM (Resident Set Size) | Đo bộ nhớ thường trú của tiến trình | $\text{RSS} \le \mathbf{35.0\text{ MB}}$ RAM | Đọc `/proc/[pid]/status` trường `VmRSS` sau 30 phút stream. |
| **TC-CPP-06** | Độ trễ hiển thị hình ảnh (Visual Latency) | Từ lúc vật thể chuyển động tới màn hình | Độ trễ cảm nhận $\le \mathbf{30.0\text{ ms}}$ | So sánh đối chiếu khung hình video bằng đồng hồ milli-giây. |
| **TC-CPP-07** | Khả năng tự phục hồi mạng (Auto-Reconnect) | Rút dây mạng Ethernet hoặc ngắt server | Tự động kết nối lại trong vòng $\le \mathbf{2.0\text{ s}}$ | Ngắt socket server 5 giây rồi mở lại; tiến trình C++ tự bắt lại stream. |
| **TC-CPP-08** | Kiểm toán rò rỉ bộ nhớ (Memory Leak Audit) | Chạy liên tục 1000 frames với Valgrind | `definitely lost: 0 bytes in 0 blocks` | Chạy lệnh `valgrind --tool=memcheck --leak-check=full`. |
| **TC-CPP-09** | Kiểm toán cô lập môi trường (Zero-Pollution) | Kiểm tra thư mục hệ thống trước và sau | Không có bất kỳ file mới nào tại `/usr/local/` | So sánh snapshot `ls -la /usr/local/bin` và `git status --ignored`. |

---

## 3. Biên Bản Nghiệm Thu Release 1c

Một bản build C++ chỉ được phép phê duyệt nghiệm thu đưa vào vận hành trên robot khi đạt **100% trạng thái Passed** trên cả 9 bài kiểm thử định lượng ở bảng trên.
