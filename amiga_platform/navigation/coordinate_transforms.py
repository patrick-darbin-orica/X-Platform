"""Coordinate transformations for waypoint navigation.

Handles:
- ENU → NWU coordinate conversion
- Lat/lon (WGS84) → NWU local metric frame conversion
- Tool offset transformations
- Waypoint loading from CSV files (ENU, NWU, or LATLONG)
"""
from __future__ import annotations

import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd
from farm_ng_core_pybind import Isometry3F64, Pose3F64, Rotation3F64

logger = logging.getLogger(__name__)


class CoordinateTransforms:
    """Handle all coordinate transformations."""

    def __init__(self) -> None:
        """Initialize coordinate transforms.

        Tool offsets are applied on-demand via apply_tool_offset(), not at init.
        """
        pass

    def apply_tool_offset(self, hole_pose: Pose3F64, tool_config: dict) -> Pose3F64:
        """Apply tool offset to a hole position to get robot navigation target.

        The robot must position itself such that the tool is over the hole.
        This requires: world_from_robot = world_from_hole * hole_from_robot

        Args:
            hole_pose: Hole position in world frame
            tool_config: Tool configuration dict with offset_x, offset_y, offset_z

        Returns:
            Robot navigation target in world frame (where robot should be
            so that the tool is positioned over the hole)
        """
        # Create tool offset transformation
        robot_from_tool = Pose3F64(
            a_from_b=Isometry3F64(
                [tool_config["offset_x"], tool_config["offset_y"], tool_config["offset_z"]],
                Rotation3F64(),
            ),
            frame_a="robot",
            frame_b="tool",
        )

        world_from_hole = Pose3F64(
            a_from_b=hole_pose.a_from_b,
            frame_a="world",
            frame_b="hole",
            tangent_of_b_in_a=hole_pose.tangent_of_b_in_a,
        )

        # Inverse of robot_from_tool gives us hole_from_robot
        hole_from_robot = robot_from_tool.inverse()
        hole_from_robot.frame_a = "hole"
        hole_from_robot.frame_b = "robot"

        # Compose: world_from_robot = world_from_hole * hole_from_robot
        world_from_robot = world_from_hole * hole_from_robot
        return world_from_robot

    @staticmethod
    def latlong_to_nwu(
        reference_lat: float,
        reference_lon: float,
        target_latlons: np.ndarray,
    ) -> np.ndarray:
        """Convert absolute lat/lon coordinates to NWU metric frame.

        All targets are expressed in metres relative to the reference point,
        which should be the robot's GPS position at filter initialisation so
        the output aligns with the filter's world frame.

        The function implements a flat-Earth (equirectangular) approximation
        valid for distances up to a few kilometres.

        Args:
            reference_lat: Reference latitude in decimal degrees (robot start)
            reference_lon: Reference longitude in decimal degrees (robot start)
            target_latlons: (N, 2) array of [lat, lon] in decimal degrees

        Returns:
            (N, 2) array of [north_m, west_m] — NWU X and Y respectively
        """
        R = 6378137.0  # WGS-84 equatorial radius in metres
        lat1_rad = math.radians(reference_lat)
        lon1_rad = math.radians(reference_lon)

        target_rad = np.radians(target_latlons)
        dlat = target_rad[:, 0] - lat1_rad
        dlon = target_rad[:, 1] - lon1_rad

        # Equirectangular projection
        north = R * dlat
        east = R * dlon * np.cos((lat1_rad + target_rad[:, 0]) / 2)
        west = -east  # NWU Y axis points West

        return np.column_stack((north, west))

    def load_waypoints_from_csv(
        self,
        csv_path: Path,
        last_row_index: int,
        coordinate_system: str = "ENU",
        reference_lat: float | None = None,
        reference_lon: float | None = None,
    ) -> dict[int, Pose3F64]:
        """Load waypoints from CSV and convert to NWU hole positions.

        Supported coordinate systems:
        - ``"ENU"``: CSV has ``dx`` (East) and ``dy`` (North) columns in
          metres relative to some local origin. Standard surveyed format.
        - ``"NWU"``: CSV already has ``north`` and ``west`` columns in metres.
        - ``"LATLONG"``: CSV has ``lat`` and ``lon`` columns in WGS-84 decimal
          degrees. Converted to NWU using the supplied reference point.

        Args:
            csv_path: Path to CSV file with waypoint data
            last_row_index: Index of last waypoint in current row (heading inference)
            coordinate_system: One of ``"ENU"``, ``"NWU"``, or ``"LATLONG"``
            reference_lat: Reference latitude for LATLONG mode (decimal degrees)
            reference_lon: Reference longitude for LATLONG mode (decimal degrees)

        Returns:
            Dictionary mapping waypoint_index → world_from_hole pose
        """
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip().str.lower()

        if coordinate_system == "LATLONG":
            north, west = self._load_latlong(df, reference_lat, reference_lon)
        elif coordinate_system == "NWU":
            north = df["north"].astype(float).to_numpy()
            west = df["west"].astype(float).to_numpy()
        else:
            # ENU → NWU: NWU_X = ENU_Y (dy), NWU_Y = -ENU_X (-dx)
            north = df["dy"].astype(float).to_numpy()
            west = (-df["dx"].astype(float)).to_numpy()

        # Heading inference
        if "yaw_deg" in df.columns:
            yaw = np.deg2rad(df["yaw_deg"].astype(float).to_numpy())
        else:
            yaw = self._infer_yaw_from_path(north, west, last_row_index)

        # Build Pose3F64 objects
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

        logger.info(
            "Loaded %d waypoints from %s (coordinate_system=%s)",
            len(poses), csv_path, coordinate_system,
        )
        return poses

    def _load_latlong(
        self,
        df: pd.DataFrame,
        reference_lat: float | None,
        reference_lon: float | None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Extract NWU (north, west) arrays from a lat/lon CSV dataframe.

        The CSV must contain ``lat`` and ``lon`` (or ``long``) columns.
        If no reference point is provided in config, the first row of the
        CSV is used as the origin (convenient for small pre-surveyed sites).

        Args:
            df: Dataframe with lat/lon columns (column names already lowercased)
            reference_lat: Reference latitude override (decimal degrees)
            reference_lon: Reference longitude override (decimal degrees)

        Returns:
            Tuple of (north_m, west_m) numpy arrays
        """
        # Accept either 'lon' or 'long'
        lon_col = "lon" if "lon" in df.columns else "long"
        lats = df["lat"].astype(float).to_numpy()
        lons = df[lon_col].astype(float).to_numpy()

        if reference_lat is None or reference_lon is None:
            logger.warning(
                "No reference lat/lon in config — using first CSV row as origin. "
                "Set reference_lat/reference_lon to the base station coordinates "
                "for accurate world-frame alignment."
            )
            reference_lat = lats[0]
            reference_lon = lons[0]

        target_latlons = np.column_stack((lats, lons))
        nwu = self.latlong_to_nwu(reference_lat, reference_lon, target_latlons)
        return nwu[:, 0], nwu[:, 1]

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

            # Special: last waypoint in each row uses backward diff so the
            # robot faces the row approach direction (not toward the next-row
            # waypoint).  idx is 0-based: last_row_index is the per-row count
            # (1-based), so subtract 1.
            if last_row_index > 0 and last_row_index <= len(north):
                idx = last_row_index - 1
                if idx > 0:
                    yaw[idx] = np.arctan2(
                        west[idx] - west[idx - 1], north[idx] - north[idx - 1]
                    )

        return yaw
