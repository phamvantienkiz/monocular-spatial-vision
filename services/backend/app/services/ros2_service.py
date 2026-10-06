"""ROS 2 Publisher Service.

Publishes 3D bounding boxes to /perception/mono/objects_3d (vision_msgs/Detection3DArray)
and telemetry to /perception/mono/telemetry (geometry_msgs/Vector3Stamped).

TODO for Students:
- Initialize rclpy when running inside a ROS 2 environment.
- Construct Detection3DArray messages with proper Optical Frame ID.
- Publish at pipeline frame rate.
"""

import logging
from typing import List, Any

logger = logging.getLogger("monocular_backend.ros2")


class ROS2Service:
    """ROS 2 Node and Publisher interface."""

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self._node = None

    def initialize(self) -> None:
        """Initializes ROS 2 node and publishers if enabled."""
        if not self.enabled:
            logger.info("ROS 2 publishing disabled in configuration.")
            return
        # TODO: Implement rclpy.init() and create publishers

    def publish_detections_3d(self, detections: List[Any], timestamp_ns: int) -> None:
        """Publishes 3D detections array to ROS 2 topic."""
        if not self.enabled:
            return
        # TODO: Implement message publishing
