"""Dual-camera vision system with EventService integration.

This module manages the forward and downward cameras for hole detection
and alignment. It integrates with the farm-ng EventService to receive
camera streams and runs YOLO detection.
"""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import cv2
import numpy as np
from farm_ng.core.event_service_pb2 import SubscribeRequest
from farm_ng.core.uri_pb2 import Uri

from .camera_calibration import CameraCalibration
from .depth_utils import get_depth_at_point
from .detector import YOLODetector
from .filters import DetectionAverager

if TYPE_CHECKING:
    from farm_ng.core.event_client import EventClient
    from farm_ng_core_pybind import Pose3F64

logger = logging.getLogger(__name__)


class VisionSystem:
    """Dual-camera vision system with EventService integration."""

    def __init__(
        self,
        oak0_client: EventClient,  # Downward camera
        oak1_client: EventClient,  # Forward camera
        forward_config: dict,
        downward_config: dict,
    ) -> None:
        """Initialize vision system.

        Args:
            oak0_client: Downward camera service client
            oak1_client: Forward camera service client
            forward_config: Forward camera configuration
            downward_config: Downward camera configuration
        """
        # Clients
        self.oak0 = oak0_client
        self.oak1 = oak1_client

        # Detectors
        self.forward_detector = YOLODetector(
            forward_config["model_path"], forward_config.get("min_confidence", 0.7)
        )
        self.downward_detector = YOLODetector(
            downward_config["model_path"], downward_config.get("min_confidence", 0.7)
        )

        # Calibrations
        self.forward_cal = CameraCalibration(oak1_client, forward_config)
        self.downward_cal = CameraCalibration(oak0_client, downward_config)

        # Averaging
        self.averager = DetectionAverager()

        logger.info("Vision system initialized")

    async def initialize(self) -> None:
        """Load camera calibrations."""
        await self.forward_cal.load_calibration()
        await self.downward_cal.load_calibration()
        logger.info("Camera calibrations loaded")

    async def detect_hole_forward(
        self,
        search_center: Pose3F64,
        search_radius_m: float = 1.0,
        timeout_s: float = 10.0,
    ) -> Pose3F64 | None:
        """Detect hole using forward camera (oak/1).

        Args:
            search_center: Expected hole position for validation
            search_radius_m: Search radius around center
            timeout_s: Detection timeout

        Returns:
            Refined hole position or None if not detected
        """
        logger.info("Starting forward hole detection...")
        start_time = asyncio.get_event_loop().time()
        self.averager.clear()

        # Subscribe to RGB stream from oak/1
        rgb_sub = SubscribeRequest(uri=Uri(path="/rgb", query="service_name=oak/1"))

        detection_count = 0

        try:
            async for event, msg in self.oak1.subscribe(rgb_sub, decode=True):
                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout_s:
                    logger.warning("Vision detection timeout")
                    return None

                # Decode frame
                rgb = cv2.imdecode(
                    np.frombuffer(msg.image_data, dtype="uint8"), cv2.IMREAD_COLOR
                )

                # Run detection
                detections = self.forward_detector.detect(rgb)

                if not detections:
                    continue

                # Get best detection
                best = max(detections, key=lambda d: d.confidence)
                detection_count += 1

                # For now, add to averager (full 3D projection requires depth)
                # TODO: Integrate disparity stream for 3D projection
                self.averager.add(
                    best.x_norm + best.width_norm / 2,
                    best.y_norm + best.height_norm / 2,
                    best.confidence,
                    asyncio.get_event_loop().time(),
                )

                # Check if we have enough detections
                avg = self.averager.get_average()
                if avg and len(self.averager.buffer) >= 3:
                    logger.info(
                        f"Hole detected with {detection_count} samples: "
                        f"conf={avg[2]:.2f}"
                    )
                    # TODO: Convert averaged 2D position to 3D pose
                    # For now, return search_center as fallback
                    return search_center

        except Exception as e:
            logger.error(f"Error in forward detection: {e}", exc_info=True)
            return None

        return None

    async def align_tool_downward(
        self, tolerance_m: float = 0.02, timeout_s: float = 10.0
    ) -> bool:
        """Use downward camera (oak/0) for final alignment check.

        Args:
            tolerance_m: Alignment tolerance in meters
            timeout_s: Timeout for alignment check

        Returns:
            True if aligned within tolerance
        """
        logger.info("Checking tool alignment with downward camera...")
        start_time = asyncio.get_event_loop().time()

        # Subscribe to RGB stream from oak/0
        rgb_sub = SubscribeRequest(uri=Uri(path="/rgb", query="service_name=oak/0"))

        try:
            async for event, msg in self.oak0.subscribe(rgb_sub, decode=True):
                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout_s:
                    logger.warning("Alignment check timeout")
                    return False

                # Decode frame
                rgb = cv2.imdecode(
                    np.frombuffer(msg.image_data, dtype="uint8"), cv2.IMREAD_COLOR
                )

                # Detect hole
                detections = self.downward_detector.detect(rgb)

                if not detections:
                    continue

                best = max(detections, key=lambda d: d.confidence)

                # Check if centered
                center_x = best.x_norm + best.width_norm / 2
                center_y = best.y_norm + best.height_norm / 2

                # Image center is 0.5, 0.5
                error_x = abs(center_x - 0.5)
                error_y = abs(center_y - 0.5)

                # Convert to metric error (approximate)
                # TODO: Use proper camera FOV and depth
                fov_width_m = 0.5  # Approximate downward FOV
                metric_error = max(error_x, error_y) * fov_width_m

                logger.debug(f"Alignment error: {metric_error:.3f}m")

                if metric_error < tolerance_m:
                    logger.info("Tool aligned over hole")
                    return True

        except Exception as e:
            logger.error(f"Error in alignment check: {e}", exc_info=True)
            return False

        return False
