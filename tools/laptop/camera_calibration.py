"""Camera Calibration Script using Checkerboard Pattern.

Computes pinhole intrinsic matrix K and distortion coefficients
from a directory of calibration images.

Usage:
    python tools/laptop/camera_calibration.py --images data/calib_images/ --rows 6 --cols 9 --square-size 0.025
"""

import argparse
import glob
import cv2
import numpy as np
import yaml


def calibrate(images_dir: str, pattern_rows: int, pattern_cols: int, square_size: float, output_yaml: str):
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    objp = np.zeros((pattern_rows * pattern_cols, 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern_cols, 0:pattern_rows].T.reshape(-1, 2) * square_size

    objpoints = []
    imgpoints = []

    images = glob.glob(f"{images_dir}/*.jpg") + glob.glob(f"{images_dir}/*.png")
    if not images:
        print(f"[!] No images found in {images_dir}")
        return

    print(f"[*] Processing {len(images)} calibration images...")
    gray_shape = None

    for fname in images:
        img = cv2.imread(fname)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray_shape = gray.shape[::-1]

        ret, corners = cv2.findChessboardCorners(gray, (pattern_cols, pattern_rows), None)
        if ret:
            objpoints.append(objp)
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            imgpoints.append(corners2)

    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray_shape, None, None)

    print("\n=== CALIBRATION RESULT ===")
    print(f"RMS Re-projection error: {ret:.4f}")
    print(f"Camera Matrix K:\n{mtx}")
    print(f"Distortion coefficients:\n{dist.ravel()}")

    calib_data = {
        "camera": {
            "intrinsics": {
                "fx": float(mtx[0, 0]),
                "fy": float(mtx[1, 1]),
                "cx": float(mtx[0, 2]),
                "cy": float(mtx[1, 2]),
            },
            "distortion_coefficients": dist.ravel().tolist(),
        }
    }

    with open(output_yaml, "w") as f:
        yaml.dump(calib_data, f, default_flow_style=False)
    print(f"[+] Saved intrinsic parameters to {output_yaml}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pinhole Camera Calibration Tool")
    parser.add_argument("--images", default="data/samples", help="Directory containing checkerboard photos")
    parser.add_argument("--rows", type=int, default=6, help="Interior checkerboard rows")
    parser.add_argument("--cols", type=int, default=9, help="Interior checkerboard columns")
    parser.add_argument("--square-size", type=float, default=0.025, help="Square size in meters")
    parser.add_argument("--output", default="configs/calib_pcam5c.yaml", help="Output YAML config")
    args = parser.parse_args()
    calibrate(args.images, args.rows, args.cols, args.square_size, args.output)
