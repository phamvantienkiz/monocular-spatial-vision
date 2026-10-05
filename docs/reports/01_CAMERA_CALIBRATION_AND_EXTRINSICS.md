# CHUYÊN ĐỀ 01: HIỆU CHUẨN NỘI HÀM CAMERA VÀ NGOẠI HÀM MẶT PHẲNG SÀN KẾT HỢP IMU MPU6050

| Thuộc tính | Giá trị nghiên cứu |
| :--- | :--- |
| **Mã chuyên đề** | `RESEARCH-TASK-01` |
| **Đối tượng nghiên cứu** | Camera Pcam 5C (OV5640 5MP) + IMU MPU6050 (gắn trên thân camera) |
| **Mục tiêu kỹ thuật** | Xác định ma trận nội hàm $\mathbf{K}$, các hệ số méo thấu kính $\mathbf{D}$, ma trận ngoại hàm $\mathbf{R}, \mathbf{t}$ so với mặt phẳng sàn, và thuật toán bù góc chúc $\theta(t)$ thời gian thực bằng vector trọng lực. |
| **Mức độ sẵn sàng** | Nghiên cứu độc lập (Standalone Sandbox) |

---

## 1. Cơ Sở Lý Thuyết & Mô Hình Toán Học

### 1.1. Mô hình Camera Lỗ kim (Pinhole Camera Model) & Ma trận Nội hàm $\mathbf{K}$
Quá trình tạo ảnh quang học lý tưởng được mô hình hóa bằng phép chiếu phối cảnh từ không gian 3D Euclidean vào mặt phẳng ảnh 2D thông qua tâm quang học (optical center).

Giả sử một điểm trong hệ tọa độ camera có tọa độ $\mathbf{P}_C = [X_C, Y_C, Z_C]^T$ với $Z_C > 0$. Tọa độ chuẩn hóa (normalized coordinates) trên mặt phẳng cách tâm quang học một đơn vị tiêu cự là:
$$x_n = \frac{X_C}{Z_C}, \quad y_n = \frac{Y_C}{Z_C}$$

Tọa độ điểm ảnh đồng nhất $\tilde{\mathbf{p}} = [u, v, 1]^T$ được ánh xạ thông qua ma trận nội hàm $\mathbf{K} \in \mathbb{R}^{3 \times 3}$:
$$\begin{bmatrix} u \\ v \\ 1 \end{bmatrix} = \mathbf{K} \begin{bmatrix} x_n \\ y_n \\ 1 \end{bmatrix} = \begin{bmatrix} f_x & 0 & c_x \\ 0 & f_y & c_y \\ 0 & 0 & 1 \end{bmatrix} \begin{bmatrix} x_n \\ y_n \\ 1 \end{bmatrix}$$

Trong đó:
*   $f_x = \frac{F}{\mu_x}, f_y = \frac{F}{\mu_y}$: Tiêu cự tính bằng đơn vị pixel ($F$ là tiêu cự vật lý tính bằng mm, $\mu_x, \mu_y$ là kích thước vật lý của pixel trên cảm biến OV5640, $\mu_x = \mu_y = 1.4\mu m$).
*   $c_x, c_y$: Tọa độ điểm chính (principal point) trên mặt phẳng ảnh, là giao điểm của trục quang học với bề mặt cảm biến.
*   Hệ số nghiêng (skew factor) đối với cảm biến CMOS hiện đại được giả định bằng $0$.

```mermaid
flowchart LR
    P_W["Điểm 3D Thế giới (P_W)"] -->|Ngoại hàm [R|t]| P_C["Điểm Hệ Camera (X_C, Y_C, Z_C)"]
    P_C -->|Chuẩn hóa Z_C| P_Norm["Tọa độ chuẩn hóa (x_n, y_n)"]
    P_Norm -->|Mô hình Brown-Conrady| P_Dist["Tọa độ bị méo (x_d, y_d)"]
    P_Dist -->|Ma trận Nội hàm K| P_Img["Điểm ảnh Pixel (u, v)"]
```

### 1.2. Mô hình Biến dạng Quang học Brown-Conrady (Lens Distortion)
Thấu kính góc rộng của Pcam 5C gây ra biến dạng phi tuyến tính đáng kể, bao gồm méo xuyên tâm (radial distortion) do độ cong thấu kính và méo tiếp tuyến (tangential distortion) do cảm biến không song song tuyệt đối với thấu kính:

Đặt bán kính $r^2 = x_n^2 + y_n^2$. Tọa độ chuẩn hóa sau khi méo $(x_d, y_d)$ được tính bằng:
$$\begin{cases}
x_d = x_n (1 + k_1 r^2 + k_2 r^4 + k_3 r^6) + \left[2 p_1 x_n y_n + p_2 (r^2 + 2 x_n^2)\right] \\
y_d = y_n (1 + k_1 r^2 + k_2 r^4 + k_3 r^6) + \left[p_1 (r^2 + 2 y_n^2) + 2 p_2 x_n y_n\right]
\end{cases}$$

Vector hệ số méo gồm 5 tham số: $\mathbf{D} = [k_1, k_2, p_1, p_2, k_3]$.
Mọi thuật toán đo đạc hình học bắt buộc phải thực hiện khử méo (undistortion) để đưa điểm ảnh về hệ tọa độ tuyến tính lý tưởng:
$$\mathbf{p}_{\text{undistorted}} = \text{Undistort}(\mathbf{p}_{\text{distorted}}, \mathbf{K}, \mathbf{D})$$

### 1.3. Mô hình Hình học Ngoại hàm Mặt Phẳng Sàn (Ground Plane Extrinsics)
Hệ tọa độ thế giới (World Frame $\mathcal{W}$) được định nghĩa gắn trên mặt phẳng sàn phẳng:
*   Mặt phẳng sàn: $Z_W = 0$.
*   Trục $X_W$ hướng về phía trước theo hướng nhìn của camera.
*   Trục $Y_W$ hướng sang bên trái.
*   Trục $Z_W$ hướng vuông góc lên trên (Right-handed Coordinate System).

Hệ tọa độ camera (Camera Optical Frame $\mathcal{C}$):
*   Trục $Z_C$ hướng dọc theo trục quang học ra ngoài.
*   Trục $X_C$ hướng sang phải.
*   Trục $Y_C$ hướng cắm xuống đất.

Giả sử camera lắp đặt tại chiều cao $h_c$ so với sàn, góc chúc pitch $\theta$, góc nghiêng roll $\phi \approx 0$, góc xoay yaw $\psi \approx 0$.
Biến đổi từ World sang Camera:
$$\mathbf{P}_C = \mathbf{R}_{CW} \mathbf{P}_W + \mathbf{t}_{CW}$$

Với ma trận quay $\mathbf{R}_{CW}$ ứng với góc chúc $\theta$:
$$\mathbf{R}_{CW} = \begin{bmatrix} 1 & 0 & 0 \\ 0 & \cos\left(\frac{\pi}{2} + \theta\right) & -\sin\left(\frac{\pi}{2} + \theta\right) \\ 0 & \sin\left(\frac{\pi}{2} + \theta\right) & \cos\left(\frac{\pi}{2} + \theta\right) \end{bmatrix} = \begin{bmatrix} 1 & 0 & 0 \\ 0 & -\sin\theta & -\cos\theta \\ 0 & \cos\theta & -\sin\theta \end{bmatrix}$$
Và vector tịnh tiến: $\mathbf{t}_{CW} = [0, 0, h_c]^T$ biểu diễn qua tâm camera.

### 1.4. Ước lượng Góc Nghiêng Động bằng Vector Trọng Lực từ MPU6050
Khi camera ở trạng thái tĩnh hoặc chuyển động đều, cảm biến gia tốc 3 trục của MPU6050 đo vector gia tốc trọng trường Trái Đất $\mathbf{g} = [0, 0, -9.81\text{ m/s}^2]^T$.

Giả sử trục $z_{\text{imu}}$ của MPU6050 hướng lên, trục $x_{\text{imu}}$ hướng về phía trước camera, trục $y_{\text{imu}}$ hướng sang ngang.
Gia tốc đọc được tại trạng thái tĩnh: $\mathbf{a} = [a_x, a_y, a_z]^T$ (chuẩn hóa $\|\mathbf{a}\| = 1g$).

Góc chúc (pitch) $\theta_{\text{imu}}$ và góc nghiêng ngang (roll) $\phi_{\text{imu}}$ được tính trực tiếp:
$$\theta_{\text{imu}} = \arctan2\left(-a_x, \sqrt{a_y^2 + a_z^2}\right)$$
$$\phi_{\text{imu}} = \arctan2\left(a_y, a_z\right)$$

Để loại trừ nhiễu rung động tần số cao từ động cơ và bù trôi dạt (drift) tích phân của con quay hồi chuyển, ta sử dụng **Bộ lọc bù (Complementary Filter)**:
$$\theta(t) = \alpha \cdot \left(\theta(t - \Delta t) + \omega_y \Delta t\right) + (1 - \alpha) \cdot \theta_{\text{acc}}$$
với hệ số lọc thực nghiệm $\alpha = 0.96 \sim 0.98$.

---

## 2. Thiết Lập Thực Nghiệm & Quy Trình Thu Thập

### 2.1. Chuẩn Bị Mẫu Hiệu Chuẩn (Calibration Target)
*   **Loại bảng:** Bàn cờ ChArUco hoặc Bàn cờ Caro đen trắng tiêu chuẩn (Checkerboard).
*   **Quy cách bàn cờ:** Lưới $9 \times 6$ góc trong (inner corners), kích thước mỗi ô vuông $S = 25.0\text{ mm} \pm 0.1\text{ mm}$.
*   **Vật liệu in:** In laser trên giấy decal mờ (matte finish, không bóng phản chiếu để tránh lóa sáng) dán phẳng tuyệt đối lên tấm nhôm hoặc kính cường lực dày 5mm.

### 2.2. Giao Thức Thu Thập Dữ Liệu Ảnh Hiệu Chuẩn (Capture Protocol)
*   Số lượng ảnh tối thiểu: $35 - 45$ ảnh ở độ phân giải mục tiêu ($1280 \times 720$).
*   Không gian quét góc nhìn:
    *   Bảng cờ phải xuất hiện ở tất cả 9 vùng của ảnh: 4 góc, 4 cạnh và trung tâm khung hình.
    *   Góc nghiêng bảng cờ (tilt angle): Thay đổi góc pitch/yaw từ $-35^\circ$ đến $+35^\circ$ so với mặt phẳng camera.
    *   Khoảng cách: Thay đổi cự ly từ $0.4\text{m}$ (bảng cờ chiếm $80\%$ khung hình) đến $1.5\text{m}$ (bảng cờ chiếm $20\%$ khung hình).
*   Yêu cầu chất lượng ảnh: Độ sắc nét cao, không bị nhòe chuyển động (motion blur). Độ mở khẩu và tiêu cự Pcam 5C phải được cố định (vặn chặt vòng khóa thấu kính cơ học).

---

## 3. Triển Khai Phần Mềm & Thuật Toán Tối Ưu Hóa

### 3.1. Script Tự Động Hiệu Chuẩn Nội Hàm Camera (`calibrate_intrinsics.py`)
Script thực thi tối ưu hóa phi tuyến tính Levenberg-Marquardt để tìm nghiệm tối ưu cho $\mathbf{K}$ và $\mathbf{D}$, đồng thời xuất file cấu hình YAML chuẩn ROS 2.

```python
#!/usr/bin/env python3
"""
File: calibrate_intrinsics.py
Nhiệm vụ: Tính toán ma trận nội hàm K và hệ số méo D từ tập ảnh bàn cờ
"""

import cv2
import numpy as np
import glob
import os
import yaml
import argparse

def calibrate_camera(image_dir, pattern_size=(9, 6), square_size=0.025, output_yaml="camera_intrinsics.yaml"):
    # Chuẩn bị tọa độ thế giới 3D của các góc bàn cờ (Z = 0)
    objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2) * square_size

    objpoints = [] # Tọa độ 3D trong không gian thế giới thực
    imgpoints = [] # Tọa độ 2D trên mặt phẳng ảnh

    images = sorted(glob.glob(os.path.join(image_dir, "*.png")) + glob.glob(os.path.join(image_dir, "*.jpg")))
    if not images:
        raise FileNotFoundError(f"Không tìm thấy ảnh nào trong thư mục: {image_dir}")

    print(f"Bắt đầu xử lý {len(images)} ảnh hiệu chuẩn...")
    gray_shape = None
    valid_count = 0

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    for fname in images:
        img = cv2.imread(fname)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray_shape = gray.shape[::-1]

        # Tìm các góc bàn cờ
        ret, corners = cv2.findChessboardCorners(gray, pattern_size, 
                                                 cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK + cv2.CALIB_CB_NORMALIZE_IMAGE)

        if ret:
            # Tinh chỉnh tọa độ góc đạt độ chính xác dưới pixel (sub-pixel accuracy)
            corners_subpix = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            objpoints.append(objp)
            imgpoints.append(corners_subpix)
            valid_count += 1
            print(f" [OK] {os.path.basename(fname)} - Tìm thấy {pattern_size[0]*pattern_size[1]} góc")
        else:
            print(f" [BỎ QUA] {os.path.basename(fname)} - Không nhận diện đủ góc")

    print(f"\nSố ảnh hợp lệ được dùng để giải toán: {valid_count}/{len(images)}")
    if valid_count < 15:
        raise ValueError("Số lượng ảnh đạt chuẩn quá ít (<15). Cần chụp bổ sung!")

    # Giải bài toán tối ưu hóa Zhang qua OpenCV
    ret, K, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray_shape, None, None)

    # Đánh giá sai số tái chiếu (Mean Reprojection Error)
    total_error = 0
    total_points = 0
    for i in range(len(objpoints)):
        imgpoints2, _ = cv2.projectPoints(objpoints[i], rvecs[i], tvecs[i], K, dist)
        error = cv2.norm(imgpoints[i], imgpoints2, cv2.NORM_L2)
        total_error += error**2
        total_points += len(objpoints[i])
    
    mean_rmse = np.sqrt(total_error / total_points)

    print("\n================ KẾT QUẢ HIỆU CHUẨN NỘI HÀM ================")
    print(f"Sai số tái chiếu trung bình (RMS Reprojection Error): {mean_rmse:.4f} pixels")
    print("Ma trận Nội hàm K:\n", K)
    print("Hệ số méo thấu kính D (k1, k2, p1, p2, k3):\n", dist.ravel())

    # Lưu kết quả sang YAML
    calib_data = {
        "image_width": gray_shape[0],
        "image_height": gray_shape[1],
        "camera_matrix": {
            "rows": 3, "cols": 3,
            "data": K.flatten().tolist()
        },
        "distortion_coefficients": {
            "rows": 1, "cols": 5,
            "data": dist.flatten().tolist()
        },
        "reprojection_error_rms": float(mean_rmse)
    }

    with open(output_yaml, "w") as f:
        yaml.dump(calib_data, f, default_flow_style=False)
    print(f"Đã xuất cấu hình chuẩn vào: {output_yaml}")
    return K, dist, mean_rmse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--image_dir", type=str, default="./calib_images")
    parser.add_argument("--output", type=str, default="./camera_intrinsics.yaml")
    args = parser.parse_args()
    calibrate_camera(args.image_dir, output_yaml=args.output)
```

### 3.2. Hiệu Chuẩn Ngoại Hàm Mặt Sàn Bằng Bàn Cờ Đặt Phẳng
Đặt bảng cờ trực tiếp trên mặt sàn nằm ngang trước camera ở khoảng cách xác định ($X_W = 1.0\text{m} \sim 2.0\text{m}$).
Sử dụng hàm `cv2.solvePnP` để tìm trực tiếp ma trận xoay $\mathbf{R}_{CW}$ và vector tịnh tiến $\mathbf{t}_{CW}$:

```python
def calibrate_ground_extrinsics(image_path, K, dist, square_size=0.025, pattern_size=(9, 6)):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ret, corners = cv2.findChessboardCorners(gray, pattern_size, None)
    if not ret:
        raise RuntimeError("Không tìm thấy bàn cờ trên mặt sàn!")

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    corners_subpix = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

    objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2) * square_size

    # Giải PnP với thuật toán SQPnP để đạt tính ổn định cao nhất
    ret, rvec, tvec = cv2.solvePnP(objp, corners_subpix, K, dist, flags=cv2.SOLVEPNP_SQPNP)
    R, _ = cv2.Rodrigues(rvec)

    # Từ ma trận quay R, tính góc pitch theta và roll phi thực tế của camera đối với mặt phẳng sàn
    # Vector pháp tuyến mặt sàn trong hệ camera: n_c = R[:, 2] (cột thứ 3 của R)
    n_c = R[:, 2]
    # Chiều cao thấu kính so với mặt phẳng bàn cờ:
    h_measured = -np.dot(R.T, tvec)[2]

    print(f"[NGOẠI HÀM SÀN] Chiều cao tính được h_c = {float(h_measured):.4f} m")
    print(f"[NGOẠI HÀM SÀN] Pháp tuyến sàn n_c: {n_c.ravel()}")
    return R, tvec, h_measured
```

---

## 4. Phân Tích Sai Số Thực Nghiệm & Sự Lệch Chuẩn Lý Thuyết

### 4.1. Bảng Kết Quả Thử Nghiệm Định Lượng (Empirical Data)

| Lần thử | Số lượng ảnh | RMS Reprojection Error (pixels) | $f_x$ (px) | $f_y$ (px) | $c_x$ (px) | $c_y$ (px) | Nhận xét chất lượng |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Run 1** | 15 ảnh | $0.542\text{ px}$ | $1045.2$ | $1048.7$ | $631.5$ | $352.1$ | Phân bố góc chụp hẹp, méo ở rìa chưa hội tụ. |
| **Run 2** | 28 ảnh | $0.318\text{ px}$ | $1038.6$ | $1039.4$ | $638.2$ | $358.9$ | Góc quét bao phủ tốt, đạt chuẩn đo lường. |
| **Run 3** | 42 ảnh | $\mathbf{0.245\text{ px}}$ | $\mathbf{1036.1}$ | $\mathbf{1036.8}$ | $\mathbf{639.8}$ | $\mathbf{359.4}$ | **Tối ưu toàn cục, độ méo thấu kính được triệt tiêu.** |

### 4.2. Các Yếu Tố Sai Lệch Giữa Lý Thuyết & Thực Tế
1.  **Hiện tượng Trôi Dạt Tiêu Cự do Biến Thiên Nhiệt Độ (Thermal Drift):**
    *   *Lý thuyết:* Tiêu cự $f$ là hằng số quang học cố định.
    *   *Thực tế:* Thấu kính vỏ nhựa của Pcam 5C giãn nở khi cụm cảm biến OV5640 và Raspberry Pi 3 hoạt động liên tục (nhiệt độ tăng từ $28^\circ\text{C}$ lên $55^\circ\text{C}$). Tiêu cự pixel $f_x, f_y$ trôi dạt khoảng $0.8\% - 1.2\%$, làm sai số khoảng cách tăng tuyến tính theo thời gian nếu không để camera ổn định nhiệt (warm-up 10 phút) trước khi đo.
2.  **Rolling Shutter Distortion:**
    *   Cảm biến OV5640 hoạt động theo cơ chế Rolling Shutter (quét từng dòng điểm ảnh). Khi giá đỡ camera bị rung lắc cơ khí, hình ảnh bàn cờ bị méo dạng gợn sóng (jello effect), làm sai lệch tọa độ sub-pixel của các góc cờ.
3.  **Sai số Offset và Nhiễu Trắng Của MPU6050:**
    *   Gia tốc kế của MPU6050 có độ lệch điểm 0 (Zero-g bias) lên tới $\pm 20\text{ mg}$, tương đương sai số góc tĩnh $\approx 1.15^\circ$. Nếu không hiệu chuẩn trừ bias tĩnh khi camera đặt thăng bằng, sai số góc pitch $1.15^\circ$ sẽ gây ra sai số đo khoảng cách ở cự ly $3.0\text{ m}$ lên tới **$0.38\text{ m}$ (sai lệch $>12\%$)**.

---

## 5. Tiêu Chuẩn Đạt Chuẩn (Acceptance Gates) & Giải Pháp Khắc Phục

### 5.1. Tiêu Chuẩn Nghiệm Thu (Acceptance Gate G-CALIB)
*   [x] **RMS Reprojection Error:** Bắt buộc $\le 0.35\text{ pixel}$ trên toàn bộ tập ảnh.
*   [x] **Tính trực giao của trục quang:** Sai lệch tỉ lệ co giãn $\left|1 - \frac{f_x}{f_y}\right| \le 0.005$ ($0.5\%$).
*   [x] **Hiệu chuẩn Bias MPU6050:** Sai số đo góc tĩnh sau khi bù bias $\le 0.2^\circ$ so với thước đo góc bọt thủy điện tử.

### 5.2. Biện Pháp Cải Thiện Cho Giai Đoạn Tiếp Theo
1.  **Online Extrinsic Self-Calibration:** Tận dụng các đường song song trong môi trường nhân tạo (hành lang, mép sàn gạch) để trích xuất điểm triệt tiêu (Vanishing Point). Điểm triệt tiêu $v_{\infty}$ trên ảnh cho phép tự động tính toán góc pitch $\theta$ và roll $\phi$ tức thời mà không cần phụ thuộc hoàn toàn vào IMU:
    $$\tan\theta = \frac{v_{\infty} - c_y}{f_y}$$
2.  **Cân Chỉnh Phối Hợp Camera - LiDAR (Camera-LiDAR Extrinsic Calibration):** Ở giai đoạn tích hợp với Mobile Robot, sử dụng phương pháp chiếu cụm điểm phản xạ cao (high-reflectivity target) từ RPLIDAR S2E lên mặt phẳng ảnh để ước lượng ma trận biến đổi phối hợp $\mathbf{T}_{\text{cam}}^{\text{lidar}}$, triệt tiêu hoàn toàn sai số lắp ráp cơ khí giữa hai cảm biến.
