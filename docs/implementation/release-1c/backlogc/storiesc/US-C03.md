# US-C03: Quản Lý Phụ Thuộc Cô Lập Bằng `uv` + `Conan 2.0` & Safe Native Build Harness (`-j2`)

> **Layer:** Implementation Layer (`docs/implementation/release-1c/backlogc/storiesc/US-C03.md`)  
> **Release:** Release 1c (C/C++ Native Edge Capture & Perception Pipeline)  
> **Story ID:** US-C03  
> **Status:** Ready for Development (Audit-Remediated)  

---

## 1. User Story

**Là một** Kỹ sư DevOps & Kiến Trúc Hệ Thống (DevOps & Systems Architect),  
**Tôi muốn** thiết lập quy trình quản lý thư viện C++ bằng `Conan 2.0` được cài đặt cô lập trong môi trường ảo `.venv` của `uv`, với cache `CONAN_HOME` nằm trọn trong thư mục dự án và harness biên dịch CMake (`cmake_minimum_required(VERSION 3.18)`) giới hạn tối đa 2 luồng (`-j2`) mà không cần can thiệp file cấu hình hệ thống `/etc/dphys-swapfile`,  
**Để** thỏa mãn $100\%$ nguyên tắc Zero System Pollution tại `AGENTS.md`, tương thích với cả Debian Bullseye lẫn Bookworm trên Raspberry Pi 3, và loại bỏ nguy cơ tràn RAM (OOM) khi biên dịch mã nguồn C++.

---

## 2. Acceptance Criteria (Given-When-Then)

### Kịch bản 1: Cài đặt Conan trong môi trường ảo cô lập (`.venv`)
- **Given:** Máy tính Raspberry Pi 3 hoặc Laptop đã có sẵn `uv`.
- **When:** Kỹ sư chạy lệnh `uv venv .venv` và `uv pip install conan`.
- **Then:**
  1. Thư mục `.venv` được tạo cục bộ trong root workspace.
  2. Binary `conan` nằm trong `.venv/bin/conan`, hoàn toàn không có gói nào được cài vào Python global hệ điều hành (`/usr/local/lib/python*`).

### Kịch bản 2: Cấu hình `CONAN_HOME` cục bộ và giải quyết phụ thuộc tại `services/pi_capture_agent_cpp/`
- **Given:** Biến môi trường `CONAN_HOME` được export trỏ vào `${REPO_ROOT}/.conan`.
- **When:** Kỹ sư di chuyển vào `services/pi_capture_agent_cpp/` và chạy lệnh `uv run conan install . --output-folder=build --build=missing -s build_type=Release`.
- **Then:**
  1. Tất cả recipe, package binary của `libjpeg-turbo/3.0.2`, `nlohmann_json/3.11.3`, `yaml-cpp/0.8.0` được tải và lưu trọn trong thư mục `.conan/p/` của repo.
  2. Thư mục `~/.conan2` của user không bị tạo ra hoặc không bị ghi bất kỳ file nào.
  3. Tệp `conan_toolchain.cmake` được sinh ra chính xác bên trong `services/pi_capture_agent_cpp/build/`.

### Kịch bản 3: Biên dịch CMake an toàn (`VERSION 3.18`, `-j2`) không chạm vào `/etc/*`
- **Given:** Hệ điều hành Raspberry Pi OS nguyên bản (CMake $\ge 3.18$), hoàn toàn không chỉnh sửa `/etc/dphys-swapfile`.
- **When:** Tại thư mục `services/pi_capture_agent_cpp/`, chạy lệnh cấu hình `cmake -B build -DCMAKE_TOOLCHAIN_FILE=build/build/Release/generators/conan_toolchain.cmake -DCMAKE_BUILD_TYPE=Release` và biên dịch bằng `cmake --build build -j2`.
- **Then:**
  1. Trình biên dịch `g++` chỉ chạy tối đa 2 luồng song song, mức chiếm dụng RAM đỉnh không vượt quá $650\text{MB}$ (an toàn tuyệt đối trong 1GB RAM vật lý của Pi 3).
  2. Toàn bộ tiến trình biên dịch hoàn tất $100\%$ thành công, sinh ra file thực thi `services/pi_capture_agent_cpp/build/pi_capture_agent_cpp` và bộ test `test_header_packer` mà không bị kích hoạt OOM Killer.

### Kịch bản 4: Kiểm toán không để lại rác (Zero-Pollution Audit)
- **Given:** Quá trình build và chạy thử nghiệm đã hoàn tất.
- **When:** Kỹ sư thực hiện xóa 3 thư mục cục bộ `rm -rf .venv .conan services/pi_capture_agent_cpp/build`.
- **Then:** Toàn bộ hệ điều hành trở về trạng thái nguyên bản sạch sẽ ban đầu, không có bất kỳ file cấu hình `/etc/*`, thư viện toàn cục hay biến môi trường nào bị lưu lại trên máy.

---

## 3. ARCHITECTURE GUARDRAILS FOR CODING AGENT

> ⛔ **BẮT BUỘC TUÂN THỦ:** Trước khi viết hoặc sửa đổi mã nguồn, AI Coding Agent phải đối chiếu các ràng buộc kiến trúc sau:

1. **Tuân Thủ Nghiêm Ngặt Quy Định Cách Ly Môi Trường (`AGENTS.md` Rule 3):**
   - Đối chiếu: [AGENTS.md - Mục 3: Environment Isolation & Script Execution Rules](file:///E:/UIT/monocular-spatial-vision/AGENTS.md).
   - *Ràng buộc:* Nghiêm cấm chạy bare `pip install conan`, `sudo apt install libturbojpeg0-dev` hay bắt buộc sửa `/etc/dphys-swapfile`. Mọi phụ thuộc C++ phải khai báo trong `services/pi_capture_agent_cpp/conanfile.txt`.
2. **Quy Tắc Biên Dịch Native Trên Phần Cứng Giới Hạn:**
   - Đối chiếu: [docs/architecture/04-deployment-architecture.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/04-deployment-architecture.md).
   - *Ràng buộc:* Không bao giờ được phép để lệnh `make` hoặc `cmake --build` chạy không có cờ giới hạn (`-j1` hoặc `-j2`) trên Pi 3. `CMakeLists.txt` phải đặt `cmake_minimum_required(VERSION 3.18)` để tương thích ngay với CMake mặc định trên Debian Bullseye/Bookworm.
3. **Cấu Trúc Tệp Khai Báo Phụ Thuộc:**
   - Đối chiếu: [docs/architecture/10-folder-structure.md](file:///E:/UIT/monocular-spatial-vision/docs/architecture/10-folder-structure.md).
   - *Ràng buộc:* File `conanfile.txt` và `CMakeLists.txt` đặt tại `services/pi_capture_agent_cpp/`, đồng bộ nhất quán giữa mọi tài liệu hướng dẫn trong `guidec/`.
