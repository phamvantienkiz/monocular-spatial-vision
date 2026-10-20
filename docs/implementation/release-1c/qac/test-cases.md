# QA Test Plan & Test Cases — Release 1c (C/C++ Native)

> **Layer:** Implementation Layer (`docs/implementation/release-1c/qac/test-cases.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Status:** Approved Baseline (Audit-Remediated)  

---

## 1. Mục Tiêu & Phương Pháp Đo Đạc Định Lượng

Bộ kiểm thử chất lượng Release 1c tập trung vào 5 khía cạnh trọng tâm:
1. **Hiệu năng thời gian thực (Throughput & Active CPU Latency):** Xác nhận đạt chuẩn $30.0\text{ FPS}$ theo nhịp VSYNC phần cứng ($33.33\text{ms}$/frame) tại $1280 \times 720$, với tổng thời gian CPU hoạt động (NEON De-interleave + `tjCompressFromYUV`) $\le 12.0\text{ms}$/frame.
2. **Bảo toàn 100% Giao thức Truyền dẫn (Wi-Fi & Ethernet) và 6 Chế độ CLI:** Kiểm chứng đầy đủ việc dùng **Wi-Fi** để test không dây với Laptop (`--mode preview` & `--mode stream`), dùng **dây Ethernet qua Hub chuyển đổi USB Type-C** để test có dây với Laptop, và dùng **cổng Ethernet** để tích hợp thực tế với **Jetson AGX Xavier**.
3. **Hiệu quả tài nguyên (CPU & Memory Footprint):** Đảm bảo không quá tải 4 nhân Cortex-A53 ($\le 25\%$) và không chiếm quá $35\text{MB}$ RAM.
4. **Độ ổn định truyền dẫn & Khả năng phục hồi (Resilience):** Triệt tiêu hiện tượng lag hiển thị bằng Triple-Buffer Drop-Stale, gửi nguyên tử `send_all()` không làm lệch byte đồng bộ `0x5043`, và tự động kết nối lại khi mạng đứt.
5. **Kiểm toán môi trường (Zero-Pollution & Memory Leak):** Không rò rỉ bộ nhớ, không vi phạm Strict Aliasing dưới `-O3`, và không can thiệp bất kỳ tệp hệ thống nào (`/etc/dphys-swapfile`, `/usr/local/`, `~/.conan2`).

---

## 2. Ma Trận Test Cases Định Lượng C/C++ Native

| Test Case ID | Tên Bài Kiểm Thử | Mục Tiêu & Phạm Vi | Tiêu Chuẩn Đạt (Pass/Fail Criteria) | Giao Thức & Lệnh Thực Thi |
| :--- | :--- | :--- | :--- | :--- |
| **TC-CPP-01** | Đồng bộ `media-ctl`, `v4l-subdev0` & Tách kênh NEON `vld2_u8` | $1280 \times 720$ UYVY $\to$ YUV422P @ $30\text{ FPS}$, trả ngay `VIDIOC_QBUF` | `VIDIOC_STREAMON` không lỗi `-EPIPE`; `VFLIP=1` hoạt động trên `/dev/v4l-subdev0`; $\text{NEON Time} \le \mathbf{2.0\text{ ms}}$ | Lệnh `--mode diag`, `--mode snapshot` và `--mode test-perf --frames 100`. |
| **TC-CPP-02** | Độ trễ nén `tjCompressFromYUV` ARM NEON | $1280 \times 720$ `YUV422P`, `TJSAMP_422`, Quality 70, `TJFLAG_FASTDCT` | $\text{Avg Encode Time} \le \mathbf{10.0\text{ ms}}$ (Tổng Active CPU $\le \mathbf{12.0\text{ ms}}$) | Đo thời gian gọi C API `tjCompressFromYUV()` trên 500 frames liên tục. |
| **TC-CPP-03** | Tốc độ khung hình toàn chu trình Pi 3 | `poll(POLLIN)` $\to$ `DQBUF` $\to$ NEON $\to$ `QBUF` $\to$ Encode $\to$ Header 40B | Thông lượng đạt chuẩn $\mathbf{29.5 - 30.0\text{ FPS}}$ (100 frames trong $\approx 3.33\text{s}$, 0 dropped) | Benchmark chế độ pipeline đa luồng trong 60 giây. |
| **TC-CPP-04** | Mức chiếm dụng CPU trên Raspberry Pi 3 | Toàn bộ tiến trình C++ khi đang stream 720p@30FPS | Tổng tải CPU trên 4 nhân Cortex-A53 $\le \mathbf{25.0\%}$ | Lệnh `pidstat -p [PID] 1 30` hoặc `htop` ghi nhận trung bình. |
| **TC-CPP-05** | Dấu ấn bộ nhớ RAM (Resident Set Size) | Đo bộ nhớ thường trú của tiến trình | $\text{RSS} \le \mathbf{35.0\text{ MB}}$ RAM | Đọc `/proc/[pid]/status` trường `VmRSS` sau 30 phút stream. |
| **TC-CPP-06** | Độ trễ hiển thị & Triple-Buffer Drop-Stale | Từ lúc vật thể chuyển động tới màn hình khi mạng nghẽn | Độ trễ hiển thị $\le \mathbf{30.0\text{ ms}}$; không ghi đè gói đang gửi trong `send_all()` | Giả lập bóp băng thông mạng và kiểm tra đồng hồ milli-giây + tính toàn vẹn JPEG. |
| **TC-CPP-07A** | Kiểm thử không dây qua **Wi-Fi (`wlan0`)** với Laptop | Cả 2 chế độ `--mode preview` (`:8080`) và `--mode stream` (`:9876`) qua Wi-Fi | Web HUD `:8080/preview` hiển thị mượt MJPEG + IMU; `scripts/mock_ingest_server.py` nhận stream ổn định không trễ tích lũy | Chạy `--mode preview --port 8080` và `--mode stream --host <LAPTOP_WIFI_IP> --port 9876`. |
| **TC-CPP-07B** | Kiểm thử có dây qua **Ethernet + Hub chuyển đổi USB Type-C** với Laptop | Cắm dây RJ45 từ Pi 3 qua Hub Type-C vào Laptop (Zero-Friction APIPA/mDNS/DHCP) | Không cần đổi Static IP thủ công trên Laptop; đạt $\mathbf{29.5 - 30.0\text{ FPS}}$ @ $1280 \times 720$ trên cả `preview` và `stream` | Chạy `uv run python scripts/mock_ingest_server.py` trên Laptop và `--mode stream --host <LAPTOP_TYPEC_IP>` trên Pi 3. |
| **TC-CPP-07C** | Tích hợp thực tế qua **cổng Ethernet** với **Jetson AGX Xavier** & Auto-Reconnect | Kết nối RJ45 trực tiếp tới `192.168.1.20:9876`; rút/cắm cáp mạng đột ngột | Đạt $30.0\text{ FPS}$ 3D BBox trên Jetson; khi rút/cắm cáp tự động phục hồi trong $\le \mathbf{2.0\text{ s}}$, `0` lỗi lệch khung (`0x5043`) | Ngắt cáp Ethernet hoặc tắt server 5 giây rồi mở lại; tiến trình C++ tự bắt lại stream. |
| **TC-CPP-08** | Kiểm toán rò rỉ bộ nhớ & Strict Aliasing (`-O3`) | Chạy Unit Test (`test_header_packer`) và 1000 frames với Valgrind / UBSan | `definitely lost: 0 bytes`; `pitch_deg`/`roll_deg` giải mã chính xác $100\%$ dưới cờ `-O3` | Chạy `ctest --test-dir build` và `valgrind --tool=memcheck --leak-check=full`. |
| **TC-CPP-09** | Kiểm toán cô lập môi trường (Zero-Pollution) | Kiểm tra hệ thống trước và sau khi build bằng `uv` + `Conan` | Không sửa `/etc/dphys-swapfile`, không tạo `~/.conan2` hay file mới tại `/usr/local/` | So sánh `git status --ignored`, `ls -la ~` và `md5sum /etc/dphys-swapfile`. |

---

## 3. Biên Bản Nghiệm Thu Release 1c

Một bản build C++ chỉ được phép phê duyệt nghiệm thu đưa vào vận hành trên robot khi đạt **100% trạng thái Passed** trên toàn bộ các bài kiểm thử định lượng ở bảng trên (bao gồm cả kiểm thử qua Wi-Fi, kiểm thử qua dây Ethernet với Hub chuyển đổi USB Type-C trên Laptop, và tích hợp Ethernet trực tiếp với Jetson AGX Xavier).
