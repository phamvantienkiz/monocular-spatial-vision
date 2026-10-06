"""Geometry Service: Ground contact extraction, IPM distance, and 3D bounding box lifting.

TODO for Students:
- Implement extract_ground_contact_point(mask, bbox):
  Find lowest non-zero row v_max, take horizontal median u_contact = median(u_row).
  Filter shadow pixels if gradient exceeds threshold.
- Implement compute_ipm_distance(v_contact, cy, fy, h_c, pitch_rad):
  alpha_v = arctan((v_contact - cy) / fy)
  Z_ground = h_c / tan(pitch_rad + alpha_v)
  Handle horizon boundary conditions (denominator <= 0).
- Implement compute_3d_box(bbox_2d, Z_ground, K, class_name):
  Back-project 2D box corners to 3D metric coordinates [X, Y, Z] and size [L, W, H].
"""

import math
import logging
from typing import Tuple, Optional
import numpy as np

logger = logging.getLogger("monocular_backend.geometry")


class GeometryService:
    """Solves monocular 3D spatial properties using pinhole geometry and IPM."""

    def __init__(self, fx: float = 920.0, fy: float = 920.0, cx: float = 640.0, cy: float = 360.0, h_c: float = 0.285):
        self.fx = fx
        self.fy = fy
        self.cx = cx
        self.cy = cy
        self.h_c = h_c

    def extract_ground_contact_point(self, mask: np.ndarray, bbox: Tuple[float, float, float, float]) -> Tuple[int, int]:
        """Extracts bottom ground contact pixel (u, v) from object segmentation mask."""
        # TODO: Implement ground contact extraction and shadow rejection
        x1, y1, x2, y2 = bbox
        return int((x1 + x2) / 2), int(y2)

    def compute_ipm_distance(self, v_contact: int, pitch_rad: float) -> Optional[float]:
        """Computes metric distance Z_ground to bottom contact point using IPM.

        Formula:
            alpha_v = arctan((v_contact - cy) / fy)
            Z = h_c / tan(pitch_rad + alpha_v)
        """
        # TODO: Implement robust IPM solver with tilt compensation
        angle_elev = math.atan((v_contact - self.cy) / self.fy)
        total_angle = pitch_rad + angle_elev
        if total_angle <= 0.001:
            return None  # Above or on horizon
        return self.h_c / math.tan(total_angle)

    def lift_to_3d_box(
        self,
        bbox_xyxy: Tuple[float, float, float, float],
        distance_z: float,
        pitch_rad: float,
    ) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """Lifts 2D bounding box and ground distance Z into 3D position [X, Y, Z] and size [L, W, H]."""
        # TODO: Implement 3D box reconstruction
        x1, y1, x2, y2 = bbox_xyxy
        u_center = (x1 + x2) / 2.0
        X = ((u_center - self.cx) * distance_z) / self.fx
        Y = 0.0  # Ground plane level
        Z = distance_z
        return (X, Y, Z), (0.5, 0.5, 1.5)
