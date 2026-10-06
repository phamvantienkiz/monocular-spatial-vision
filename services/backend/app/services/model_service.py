"""Model Service: TensorRT / ONNX YOLOv8-seg inference engine.

TODO for Students:
- Load TensorRT engine (.engine) on Jetson AGX GPU.
- Implement fallback to ONNX Runtime or Mock detector when running on Laptop.
- Preprocess image: Letterbox resizing to model input shape, normalize [0, 1].
- Execute TRT execution context inference asynchronously.
- Postprocess: NMS (Non-Maximum Suppression), extract 2D boxes and polygon masks.
"""

import logging
from typing import List, Dict, Any
import numpy as np

logger = logging.getLogger("monocular_backend.model")


class ModelService:
    """YOLOv8-seg TensorRT perception model wrapper."""

    def __init__(self, engine_path: str, conf_thresh: float = 0.50):
        self.engine_path = engine_path
        self.conf_thresh = conf_thresh
        self._is_loaded = False

    def load_model(self) -> bool:
        """Loads TensorRT engine or fallback mock."""
        logger.info("Loading model engine from %s...", self.engine_path)
        # TODO: Implement TensorRT runtime engine deserialization
        self._is_loaded = True
        return True

    def infer(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Runs segmentation inference on a single BGR image.

        Returns:
            List[Dict[str, Any]]: List of detections, each containing:
                - 'class_id': int
                - 'class_name': str
                - 'confidence': float
                - 'bbox_xyxy': [x1, y1, x2, y2]
                - 'mask': binary mask np.ndarray (same shape as input or polygon points)
        """
        # TODO: Implement inference and mask post-processing
        return []
