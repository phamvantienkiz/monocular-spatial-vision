# Release 1c: Hướng Dẫn Thiết Lập Môi Trường C++ Cô Lập (`.venv` + `.conan`) Trên Pi 3

> **Layer:** Implementation Layer (`docs/implementation/release-1c/guidec/01-pi3-c-environment-and-conan-setup.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Status:** Approved Baseline — Practical Engineering Standard (Audit-Remediated)  

---

## 1. Kiểm Tra Điều Kiện Phần Cứng & Hệ Điều Hành

Môi trường thực thi tiêu chuẩn là **Raspberry Pi 3 Model B hoặc B+** chạy hệ điều hành **Raspberry Pi OS (64-bit hoặc 32-bit Debian Bullseye/Bookworm)**.

Trước khi tiến hành, kiểm tra sự hiện diện của trình biên dịch cơ bản và công cụ `media-ctl`:
```bash
gcc --version
g++ --version
cmake --version      # Yêu cầu >= 3.18 (có sẵn mặc định trên cả Debian Bullseye & Bookworm)
media-ctl --version  # Công cụ cấu hình đường ống CSI-2 bcm2835-unicam
```
> [!NOTE]
> Các gói này là công cụ hệ thống cơ bản có sẵn trên Raspberry Pi OS. Dự án tuân thủ nghiêm ngặt quy tắc **Zero System Pollution (`AGENTS.md` Mục 3)**: tuyệt đối không cài đặt các thư viện phát triển ứng dụng (`libturbojpeg0-dev`, `libyaml-cpp-dev`, ...) vào môi trường toàn cục của hệ điều hành và không sửa đổi các tệp cấu hình toàn cục trong `/etc/*`.

---

## 2. Kiểm Soát Bộ Nhớ RAM Khi Biên Dịch Trên Pi 3 (Không Chỉnh Sửa `/etc/dphys-swapfile`)

Bộ nhớ RAM vật lý của Pi 3 có dung lượng **1GB (1024MB)**. Nếu chạy trình biên dịch `g++` không giới hạn số luồng (`make -j` hoặc `cmake --build build` mặc định chạy 4 luồng), tổng mức tiêu thụ RAM có thể vượt quá 1GB và kích hoạt `OOM Killer`. However, việc ép buộc chỉnh sửa tệp hệ thống `/etc/dphys-swapfile` lên `2048MB` trên thẻ nhớ microSD sẽ vi phạm quy tắc cô lập môi trường (`AGENTS.md` Rule 3) và gây hiện tượng ghi xóa liên tục (SD card thrashing) làm hỏng thẻ nhớ.

**Giải pháp chuẩn của Release 1c:**
1. **Khóa cứng tối đa 2 luồng biên dịch (`-j2` và `tools.build:jobs=2`):** Với dự án `pi_capture_agent_cpp` gồm 7 tệp `.cpp` nhẹ, giới hạn 2 luồng giữ mức sử dụng RAM đỉnh dưới **$550\text{MB}$**, biên dịch hoàn tất trong $20 - 35\text{ giây}$ ngay trong 1GB RAM vật lý mà **không cần can thiệp `/etc/dphys-swapfile`**.
2. Kiểm tra dung lượng RAM trống trước khi build:
   ```bash
   free -m
   ```
   *(Đảm bảo cột `available` đạt $\ge 550\text{MB}$; nếu đang mở giao diện Desktop nặng trên Pi 3, khuyến nghị chuyển sang chế độ CLI Headless để giải phóng RAM).*

---

## 3. Khởi Tạo Môi Trường Ảo Cô Lập & Cài Đặt Conan 2.0

Sử dụng trình quản lý `uv` tại thư mục gốc của dự án để tạo môi trường Python cục bộ đóng vai trò làm vỏ bọc thực thi cho công cụ `conan`:

```bash
# 1. Di chuyển vào thư mục gốc của dự án
cd ~/workspaces/monocular-spatial-vision

# 2. Khởi tạo môi trường ảo .venv cục bộ (nếu chưa có)
uv venv .venv

# 3. Cài đặt Conan 2.0 nội bộ vào .venv
uv pip install conan

# 4. Kích hoạt môi trường
source .venv/bin/activate

# 5. Xác nhận conan đã được cài vào .venv chứ không phải toàn cục
which conan
# Kết quả mong đợi: /home/pi/workspaces/monocular-spatial-vision/.venv/bin/conan
```

---

## 4. Cấu Hình Cache Cục Bộ `CONAN_HOME` & Tinh Chỉnh Profile Pi 3

Theo mặc định, Conan sẽ tạo thư mục cache tại thư mục người dùng `~/.conan2`. Để thỏa mãn 100% nguyên tắc **Zero System Pollution**, ta cấu hình để cache nằm ngay trong thư mục gốc của repo (`.conan/`):

```bash
# 1. Thiết lập biến môi trường CONAN_HOME trỏ vào thư mục gốc repo
export CONAN_HOME="$(pwd)/.conan"

# 2. Tự động nhận diện cấu hình phần cứng Pi 3
uv run conan profile detect --force
```

### Giới Hạn Luồng Biên Dịch Trong Conan Profile (`tools.build:jobs=2`)
Khi Conan cần build thư viện từ source code (như `libjpeg-turbo`), cần khóa cứng số luồng build tối đa là 2 trong file profile cục bộ `.conan/profiles/default`:

```bash
cat << 'EOF' >> "$CONAN_HOME/profiles/default"

[conf]
tools.build:jobs=2
EOF
```

---

## 5. Giải Quyết Phụ Thuộc Tại `services/pi_capture_agent_cpp/`

Tệp `services/pi_capture_agent_cpp/conanfile.txt` được định nghĩa như sau:

```ini
[requires]
libjpeg-turbo/3.0.2
nlohmann_json/3.11.3
yaml-cpp/0.8.0

[generators]
CMakeDeps
CMakeToolchain

[layout]
cmake_layout
```

Di chuyển vào thư mục dịch vụ C++ và chạy lệnh cài đặt phụ thuộc vào thư mục `build/`:
```bash
cd ~/workspaces/monocular-spatial-vision/services/pi_capture_agent_cpp
uv run conan install . --output-folder=build --build=missing -s build_type=Release
```

Sau khi lệnh trên hoàn tất, toàn bộ thư viện `libjpeg-turbo` (kèm tập lệnh SIMD ARM NEON), `nlohmann_json` và `yaml-cpp` đã được đóng gói cô lập 100% bên trong workspace, sẵn sàng cho bước biên dịch CMake.
