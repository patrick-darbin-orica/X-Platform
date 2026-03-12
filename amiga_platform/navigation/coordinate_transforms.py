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
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from farm_ng_core_pybind import Isometry3F64, Pose3F64, Rotation3F64

logger = logging.getLogger(__name__)


@dataclass
class WaypointData:
    """Waypoints in boustrophedon traversal order with echelon metadata."""

    poses: dict[int, Pose3F64]       # 1-indexed, traversal order
    hole_ids: dict[int, str]         # 1-indexed → "A0", "B2", etc.
    echelon_ends: list[int]          # 0-based indices where each echelon ends


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
        coordinate_system: str = "ENU",
        reference_lat: float | None = None,
        reference_lon: float | None = None,
    ) -> WaypointData:
        """Load waypoints from CSV and convert to NWU hole positions.

        Hole IDs use a letter+number format (e.g. A0, A1, B0, B1).  The
        letter indicates the echelon/row, the number the hole within that
        row.  Holes are reordered into boustrophedon traversal order: the
        first echelon is traversed forward, the second in reverse, etc.

        Supported coordinate systems:
        - ``"ENU"``: CSV has ``dx`` (East) and ``dy`` (North) columns in
          metres relative to some local origin. Standard surveyed format.
        - ``"NWU"``: CSV already has ``north`` and ``west`` columns in metres.
        - ``"LATLONG"``: CSV has ``lat`` and ``lon`` columns in WGS-84 decimal
          degrees. Converted to NWU using the supplied reference point.

        Args:
            csv_path: Path to CSV file with waypoint data
            coordinate_system: One of ``"ENU"``, ``"NWU"``, or ``"LATLONG"``
            reference_lat: Reference latitude for LATLONG mode (decimal degrees)
            reference_lon: Reference longitude for LATLONG mode (decimal degrees)

        Returns:
            WaypointData with poses in traversal order, hole IDs, and echelon ends
        """
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip().str.lower()

        # Extract NWU coordinates from the raw CSV rows
        if coordinate_system == "LATLONG":
            raw_north, raw_west = self._load_latlong(df, reference_lat, reference_lon)
        elif coordinate_system == "NWU":
            raw_north = df["north"].astype(float).to_numpy()
            raw_west = df["west"].astype(float).to_numpy()
        else:
            # ENU → NWU: NWU_X = ENU_Y (dy), NWU_Y = -ENU_X (-dx)
            raw_north = df["dy"].astype(float).to_numpy()
            raw_west = (-df["dx"].astype(float)).to_numpy()

        # Parse echelon IDs and build boustrophedon traversal order
        raw_ids = df["id"].astype(str).tolist()
        traversal_order, hole_ids, echelon_ends = self._build_traversal_order(
            raw_ids, raw_north, raw_west,
        )

        # Reorder coordinates into traversal order
        north = raw_north[traversal_order]
        west = raw_west[traversal_order]

        # Heading inference
        if "yaw_deg" in df.columns:
            raw_yaw = df["yaw_deg"].astype(float).to_numpy()
            yaw = np.deg2rad(raw_yaw[traversal_order])
        else:
            yaw = self._infer_yaw_from_path(north, west, echelon_ends)

        # Build Pose3F64 objects (1-indexed)
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
        traversal_ids = [hole_ids[i] for i in sorted(hole_ids)]
        logger.info("Traversal order: %s", " → ".join(traversal_ids))

        return WaypointData(poses=poses, hole_ids=hole_ids, echelon_ends=echelon_ends)

    @staticmethod
    def _build_traversal_order(
        raw_ids: list[str],
        north: np.ndarray,
        west: np.ndarray,
    ) -> tuple[np.ndarray, dict[int, str], list[int]]:
        """Parse echelon IDs and build boustrophedon traversal order.

        Args:
            raw_ids: List of hole ID strings from CSV (e.g. ["A0","A1","A2","B0","B1","B2"])
            north: North coordinates in CSV row order
            west: West coordinates in CSV row order

        Returns:
            Tuple of (traversal_indices, hole_ids, echelon_ends):
            - traversal_indices: numpy array of CSV row indices in traversal order
            - hole_ids: dict mapping 1-based traversal index → original string ID
            - echelon_ends: list of 0-based indices where each echelon ends
        """
        # Parse each ID into (echelon_letter, hole_number, csv_row_index)
        echelons: dict[str, list[tuple[int, int]]] = {}
        echelon_order: list[str] = []

        for csv_idx, hole_id in enumerate(raw_ids):
            match = re.match(r'^([A-Za-z]+)(\d+)$', hole_id.strip())
            if not match:
                raise ValueError(
                    f"Invalid hole ID '{hole_id}' at CSV row {csv_idx}. "
                    "Expected format: letter(s) + number (e.g. A0, B1, AA2)"
                )
            letter = match.group(1).upper()
            number = int(match.group(2))

            if letter not in echelons:
                echelons[letter] = []
                echelon_order.append(letter)
            echelons[letter].append((number, csv_idx))

        # Sort holes within each echelon by hole number
        for letter in echelon_order:
            echelons[letter].sort(key=lambda x: x[0])

        # Build traversal order: odd-indexed echelons are reversed
        traversal_indices = []
        hole_ids: dict[int, str] = {}
        echelon_ends: list[int] = []
        pos = 0

        for ech_idx, letter in enumerate(echelon_order):
            holes = echelons[letter]
            if ech_idx % 2 == 1:
                holes = list(reversed(holes))

            for hole_num, csv_idx in holes:
                traversal_indices.append(csv_idx)
                # Reconstruct the ID in traversal order
                hole_ids[pos + 1] = f"{letter}{hole_num}"  # 1-indexed
                pos += 1

            echelon_ends.append(pos - 1)  # 0-based end index

        logger.info(
            "Echelons: %s, echelon ends (0-based): %s",
            [f"{l}({len(echelons[l])})" for l in echelon_order],
            echelon_ends,
        )

        return np.array(traversal_indices), hole_ids, echelon_ends

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
        self, north: np.ndarray, west: np.ndarray, echelon_ends: list[int]
    ) -> np.ndarray:
        """Infer heading from path direction using forward difference.

        At echelon boundaries the last waypoint in each row uses backward
        difference so the robot faces along the row (not toward the first
        waypoint of the next row).

        Args:
            north: Array of north coordinates (already in traversal order)
            west: Array of west coordinates (already in traversal order)
            echelon_ends: 0-based indices where each echelon ends

        Returns:
            Array of yaw angles in radians
        """
        yaw = np.zeros_like(north)

        if len(north) > 1:
            dn = np.diff(north)
            dw = np.diff(west)

            # Forward difference for most waypoints
            yaw[:-1] = np.arctan2(dw, dn)

            # Backward difference for last waypoint overall
            yaw[-1] = np.arctan2(west[-1] - west[-2], north[-1] - north[-2])

            # Backward difference at each echelon boundary
            for idx in echelon_ends:
                if 0 < idx < len(north):
                    yaw[idx] = np.arctan2(
                        west[idx] - west[idx - 1], north[idx] - north[idx - 1]
                    )

        return yaw
