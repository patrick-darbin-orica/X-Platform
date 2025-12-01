"""Camera calibration and coordinate transformations."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from farm_ng.oak import oak_pb2
from farm_ng_core_pybind import Isometry3F64, Pose3F64, Rotation3F64
from google.protobuf.empty_pb2 import Empty

if TYPE_CHECKING:
    from farm_ng.core.event_client import EventClient

logger = logging.getLogger(__name__)


class CameraCalibration:
    """Manage camera intrinsics and extrinsics."""

    def __init__(self, oak_client: EventClient, config: dict) -> None:
        """Initialize camera calibration.

        Args:
            oak_client: Oak camera service client
            config: Camera configuration dict with offset and pitch
        """
        self.oak_client = oak_client
        self.config = config

        # Will be populated by load_calibration()
        self.intrinsics: dict | None = None
        self.robot_from_camera: Pose3F64 | None = None

    async def load_calibration(self) -> None:
        """Load intrinsics from camera and extrinsics from config."""
        # Get intrinsics from oak service
        cal: oak_pb2.OakCalibration = await self.oak_client.request_reply(
            "/calibration", Empty(), decode=True
        )

        # Extract intrinsic matrix
        cam_data = cal.camera_data[0]
        self.intrinsics = {
            "fx": cam_data.intrinsic_matrix[0],
            "fy": cam_data.intrinsic_matrix[4],
            "cx": cam_data.intrinsic_matrix[2],
            "cy": cam_data.intrinsic_matrix[5],
            "distortion": np.array(cam_data.distortion_coeff),
        }

        # Build robot_from_camera transformation
        tx = self.config["offset_x"]
        ty = self.config["offset_y"]
        tz = self.config["offset_z"]
        pitch_deg = self.config.get("pitch_deg", 0.0)

        # Camera axis alignment (DepthAI → NWU)
        # DepthAI: X=Right, Y=Down, Z=Forward
        # NWU: X=North/Forward, Y=West/Left, Z=Up
        R_align = Rotation3F64.Rx(np.radians(-90)) * Rotation3F64.Ry(np.radians(90))

        # Camera tilt (pitch down is negative in robot frame)
        R_tilt = Rotation3F64.Rx(np.radians(-pitch_deg))

        # Combined rotation
        R_total = R_align * R_tilt

        self.robot_from_camera = Pose3F64(
            a_from_b=Isometry3F64([tx, ty, tz], R_total),
            frame_a="robot",
            frame_b="camera",
        )

        logger.info(f"Camera calibration loaded: fx={self.intrinsics['fx']:.1f}")

    def pixel_to_camera_coords(
        self,
        x_norm: float,
        y_norm: float,
        depth_mm: float,
        img_w: int,
        img_h: int,
    ) -> np.ndarray:
        """Backproject pixel + depth to 3D camera coordinates.

        Args:
            x_norm: Normalized x coordinate (0-1)
            y_norm: Normalized y coordinate (0-1)
            depth_mm: Depth in millimeters
            img_w: Image width in pixels
            img_h: Image height in pixels

        Returns:
            3D point in camera frame (meters)
        """
        if self.intrinsics is None:
            raise RuntimeError("Calibration not loaded")

        u = x_norm * img_w
        v = y_norm * img_h

        z = depth_mm / 1000.0
        x = (u - self.intrinsics["cx"]) * z / self.intrinsics["fx"]
        y = (v - self.intrinsics["cy"]) * z / self.intrinsics["fy"]

        return np.array([x, y, z], dtype=float)

    def camera_to_robot(self, p_cam: np.ndarray) -> Pose3F64:
        """Transform camera detection to robot frame.

        Args:
            p_cam: 3D point in camera frame

        Returns:
            Pose in robot frame
        """
        if self.robot_from_camera is None:
            raise RuntimeError("Calibration not loaded")

        camera_from_object = Pose3F64(
            a_from_b=Isometry3F64(p_cam.tolist(), Rotation3F64()),
            frame_a="camera",
            frame_b="object",
        )
        return self.robot_from_camera * camera_from_object
