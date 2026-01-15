"""Coordinate transformations for waypoint navigation.

Handles:
- ENU → NWU coordinate conversion
- Tool offset transformations
- Waypoint loading from CSV files
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from farm_ng_core_pybind import Isometry3F64, Pose3F64, Rotation3F64

logger = logging.getLogger(__name__)


class CoordinateTransforms:
    """Handle all coordinate transformations."""

    def __init__(self, tool_config: dict) -> None:
        """Initialize with tool offset.

        Args:
            tool_config: Tool configuration dict with offset_x, offset_y, offset_z
        """
        self.robot_from_tool = self._create_tool_offset(tool_config)

    def _create_tool_offset(self, config: dict) -> Pose3F64:
        """Create robot_from_tool transformation.

        Args:
            config: Tool configuration dict

        Returns:
            Pose3F64 representing the tool offset from robot center
        """
        return Pose3F64(
            a_from_b=Isometry3F64(
                [config["offset_x"], config["offset_y"], config["offset_z"]],
                Rotation3F64(),
            ),
            frame_a="robot",
            frame_b="tool",
        )

    def load_waypoints_from_csv(
        self, csv_path: Path, last_row_index: int
    ) -> dict[int, Pose3F64]:
        """Load ENU waypoints from CSV, convert to NWU hole positions.

        Args:
            csv_path: Path to CSV file with waypoint data
            last_row_index: Index of last waypoint in current row (for heading inference)

        Returns:
            Dictionary mapping waypoint_index → world_from_hole pose
        """
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip().str.lower()

        # ENU → NWU conversion
        # ENU: X=East, Y=North, Z=Up
        # NWU: X=North, Y=West, Z=Up
        # Therefore: NWU_X = ENU_Y, NWU_Y = -ENU_X
        north = df["dy"].astype(float).to_numpy()
        west = (-df["dx"].astype(float)).to_numpy()

        # Heading inference
        if "yaw_deg" in df.columns:
            yaw = np.deg2rad(df["yaw_deg"].astype(float).to_numpy())
        else:
            yaw = self._infer_yaw_from_path(north, west, last_row_index)

        # Build poses
        poses = {}
        zero_tangent = np.zeros((6, 1), dtype=np.float64)

        for i, (n, w, th) in enumerate(zip(north, west, yaw), start=1):
            iso = Isometry3F64(
                np.array([n, w, 0.0], dtype=np.float64), Rotation3F64.Rz(float(th))
            )
            poses[i] = Pose3F64(
                a_from_b=iso,
                frame_a="world",
                frame_b="hole",
                tangent_of_b_in_a=zero_tangent,
            )

        logger.info(f"Loaded {len(poses)} waypoints from {csv_path}")
        return poses

    def transform_holes_to_robot_targets(
        self, hole_poses: dict[int, Pose3F64]
    ) -> dict[int, Pose3F64]:
        """Transform hole positions to robot navigation targets.

        The robot must position itself such that the tool (dipbob/chute) is over the hole.
        This requires: world_from_robot = world_from_hole * hole_from_robot

        Args:
            hole_poses: Dictionary of hole positions in world frame

        Returns:
            Dictionary of robot navigation targets in world frame
        """
        robot_poses = {}

        for idx, hole_pose in hole_poses.items():
            world_from_hole = Pose3F64(
                a_from_b=hole_pose.a_from_b,
                frame_a="world",
                frame_b="hole",
                tangent_of_b_in_a=hole_pose.tangent_of_b_in_a,
            )

            # Inverse of robot_from_tool gives us hole_from_robot
            hole_from_robot = self.robot_from_tool.inverse()
            hole_from_robot.frame_a = "hole"
            hole_from_robot.frame_b = "robot"

            # Compose: world_from_robot = world_from_hole * hole_from_robot
            world_from_robot = world_from_hole * hole_from_robot
            robot_poses[idx] = world_from_robot

        return robot_poses

    def _infer_yaw_from_path(
        self, north: np.ndarray, west: np.ndarray, last_row_index: int
    ) -> np.ndarray:
        """Infer heading from path direction using forward difference.

        Args:
            north: Array of north coordinates
            west: Array of west coordinates
            last_row_index: Index of last waypoint in row (uses backward difference)

        Returns:
            Array of yaw angles in radians
        """
        yaw = np.zeros_like(north)

        if len(north) > 1:
            dn = np.diff(north)
            dw = np.diff(west)

            # Forward difference for most waypoints
            yaw[:-1] = np.arctan2(dw, dn)

            # Backward difference for last waypoint
            yaw[-1] = np.arctan2(west[-1] - west[-2], north[-1] - north[-2])

            # Special: last row waypoint uses backward (approach direction)
            if last_row_index > 0 and last_row_index <= len(north):
                idx = last_row_index - 1
                if idx > 0:
                    yaw[idx] = np.arctan2(
                        west[idx] - west[idx - 1], north[idx] - north[idx - 1]
                    )

        return yaw
