# Release 1c: Hướng Dẫn Thiết Lập Môi Trường C++ Cô Lập & Swap 2GB Trên Pi 3

> **Layer:** Implementation Layer (`docs/implementation/release-1c/guidec/01-pi3-c-environment-and-conan-setup.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Status:** Approved Baseline — Practical Engineering Standard  

---

## 1. Kiểm Tra Điều Kiện Phần Cứng & Hệ Điều Hành

Môi trường thực thi tiêu chuẩn là **Raspberry Pi 3 Model B hoặc B+** chạy hệ điều hành **Raspberry Pi OS Lite (64-bit hoặc 32-bit Debian Bullseye/Bookworm)**.

Trước khi tiến hành, kiểm tra sự hiện diện của trình biên dịch cơ bản:
```bash
gcc --version
g++ --version
cmake --version
```
> [!NOTE]
> Các gói này là công cụ hệ thống tối thiểu có sẵn của bản phân phối Linux (`build-essential`). Dự án không yêu cầu cài đặt bất kỳ thư viện phát triển bên ngoài (`-dev`) nào vào hệ điều hành.

---

## 2. Cấu Hình Bộ Nhớ Swap 2048MB (Bước Sống Còn Chống Treo Máy)

Bộ nhớ RAM vật lý của Pi 3 chỉ có đúng **1GB (1024MB)**. Mặc định hệ điều hành chỉ cấp **100MB** swap file. Khi biên dịch mã C++ hiện đại (với các thư viện nén, toán học hoặc JSON), trình biên dịch `g++` có thể tiêu tốn từ $400\text{MB} - 800\text{MB}$ RAM cho mỗi luồng. Nếu không có swap đủ lớn, nhân Linux sẽ kích hoạt cơ chế `OOM Killer` làm sập tiến trình hoặc treo cứng toàn bộ hệ thống.

Thực hiện tăng dung lượng swap:
```bash
# 1. Dừng dịch vụ swap tạm thời
sudo dphys-swapfile swapoff

# 2. Mở file cấu hình swap
sudo nano /etc/dphys-swapfile

# 3. Tìm dòng CONF_SWAPSIZE và sửa thành:
CONF_SWAPSIZE=2048

# 4. Tạo lại file swap với dung lượng mới
sudo dphys-swapfile setup

# 5. Kích hoạt lại swap
sudo dphys-swapfile swapon

# 6. Kiểm tra xác nhận bộ nhớ ảo sẵn sàng
free -m
```
*Kết quả mẫu hiển thị đúng:*
```text
               total        used        free      shared  buff/cache   available
Mem:             922         115         580          12         226         740
Swap:           2047           0        2047
```

---

## 3. Khởi Tạo Môi Trường Ảo Cô Lập & Cài Đặt Conan 2.0

Chúng ta sử dụng trình quản lý `uv` để tạo môi trường Python cục bộ đóng vai trò làm vỏ bọc thực thi cho công cụ `conan`:

```bash
# 1. Di chuyển vào thư mục dự án
cd ~/workspaces/monocular-spatial-vision

# 2. Khởi tạo môi trường ảo .venv cục bộ
uv venv

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

Theo mặc định, Conan sẽ tạo thư mục cache tại thư mục người dùng `~/.conan2`. Để thỏa mãn 100% nguyên tắc **Zero System Pollution**, ta cấu hình để cache nằm ngay trong repo:

```bash
# 1. Thiết lập biến môi trường CONAN_HOME trong terminal hiện tại
export CONAN_HOME="$(pwd)/.conan"

# (Tùy chọn) Lưu biến vào file môi trường cục bộ để tự động nạp khi activate:
echo 'export CONAN_HOME="$(pwd)/.conan"' >> .venv/bin/activate

# 2. Tự động nhận diện cấu hình phần cứng Pi 3
uv run conan profile detect --force
```

### Giới Hạn Luồng Biên Dịch Trong Conan Profile
Khi Conan cần build thư viện từ source code (như `libjpeg-turbo`), nó có thể tự động chạy đa luồng tối đa làm tràn RAM. Cần giới hạn số luồng build trong file profile:

```bash
# Mở file profile mặc định của Conan
nano .conan/profiles/default
```
Thêm vào cuối file dòng cấu hình giới hạn tối đa 2 luồng:
```ini
[conf]
tools.build:jobs=2
```

---

## 5. Tệp Khai Báo Phụ Thuộc `conanfile.txt` Chuẩn

Tệp `conanfile.txt` tại thư mục dự án được định nghĩa như sau:

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

Khi chạy lệnh sau, Conan sẽ tải mã nguồn, tự động biên dịch và sinh toolchain chuẩn vào thư mục `build/`:
```bash
export CONAN_HOME="$(pwd)/.conan"
uv run conan install . --build=missing -s build_type=Release
```

Sau khi lệnh trên hoàn tất, bạn đã có một môi trường C++ hoàn hảo, độc lập $100\%$ và sẵn sàng biên dịch mã nguồn native trên Raspberry Pi 3.
