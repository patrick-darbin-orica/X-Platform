"""Path planning and waypoint management."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from farm_ng.track.track_pb2 import Track
from farm_ng_core_pybind import Isometry3F64, Pose3F64
from google.protobuf.empty_pb2 import Empty

from utils.track_builder import TrackBuilder

from .coordinate_transforms import CoordinateTransforms

if TYPE_CHECKING:
    from core.config import NavigationConfig, ToolConfig, WaypointConfig
    from farm_ng.core.event_client import EventClient

logger = logging.getLogger(__name__)


class PathPlanner:
    """Manages waypoint sequence and track segment generation."""

    def __init__(
        self,
        waypoint_config: WaypointConfig,
        tool_config: ToolConfig,
        filter_client: EventClient,
    ) -> None:
        """Initialize path planner.

        Args:
            waypoint_config: Waypoint loading configuration
            tool_config: Tool offset configuration
            filter_client: Filter service client for pose queries
        """
        self.config = waypoint_config
        self.filter_client = filter_client

        # Coordinate transformations
        self.transforms = CoordinateTransforms(
            {
                "offset_x": tool_config.offset_x,
                "offset_y": tool_config.offset_y,
                "offset_z": tool_config.offset_z,
            }
        )

        # Load waypoints
        hole_poses = self.transforms.load_waypoints_from_csv(
            Path(waypoint_config.csv_path).expanduser(),
            waypoint_config.last_row_waypoint_index,
        )

        # Store original hole positions (for vision search zones)
        self.hole_poses = hole_poses.copy()

        # Transform to robot navigation targets
        self.waypoints = self.transforms.transform_holes_to_robot_targets(hole_poses)

        # Navigation state
        self.current_index = 0
        self.row_end_segment_index = 1

        logger.info(f"Loaded {len(self.waypoints)} waypoints")

    async def get_current_pose(self) -> Pose3F64:
        """Get robot pose from filter service.

        Returns:
            Current robot pose in world frame
        """
        from farm_ng.filter.filter_pb2 import FilterState

        state: FilterState = await self.filter_client.request_reply(
            "/get_state", Empty(), decode=True
        )
        return Pose3F64.from_proto(state.pose)

    def get_next_waypoint(self) -> tuple[int, Pose3F64] | None:
        """Get next waypoint in sequence.

        Returns:
            Tuple of (waypoint_index, waypoint_pose) or None if complete
        """
        if self.current_index >= len(self.waypoints):
            return None

        self.current_index += 1
        return (self.current_index, self.waypoints[self.current_index])

    def get_hole_position(self, index: int) -> Pose3F64 | None:
        """Get original hole position (for vision search zone).

        Args:
            index: Waypoint index

        Returns:
            Hole position pose or None if not found
        """
        return self.hole_poses.get(index)

    async def plan_segment(
        self, start: Pose3F64, goal: Pose3F64, spacing: float = 0.5
    ) -> Track:
        """Create AB track segment from start to goal.

        Args:
            start: Starting pose
            goal: Goal pose
            spacing: Waypoint spacing in meters

        Returns:
            Track segment
        """
        builder = TrackBuilder(start=start)
        builder.create_ab_segment(
            next_frame_b=f"waypoint_{self.current_index}",
            final_pose=goal,
            spacing=spacing,
        )
        return builder.track

    async def plan_approach_segment(
        self, goal: Pose3F64, offset_m: float = 1.2
    ) -> Track:
        """Create segment stopping before goal for vision detection.

        Args:
            goal: Target waypoint
            offset_m: Distance to stop before goal

        Returns:
            Track segment to approach position
        """
        current = await self.get_current_pose()

        # Calculate approach position
        goal_x = goal.a_from_b.translation[0]
        goal_y = goal.a_from_b.translation[1]
        curr_x = current.a_from_b.translation[0]
        curr_y = current.a_from_b.translation[1]

        dx = goal_x - curr_x
        dy = goal_y - curr_y
        dist = np.hypot(dx, dy)

        if dist <= offset_m:
            # Too close, go direct
            logger.warning(f"Already within approach distance ({dist:.2f}m)")
            return await self.plan_segment(current, goal)

        # Approach position
        scale = (dist - offset_m) / dist
        approach_x = curr_x + dx * scale
        approach_y = curr_y + dy * scale

        approach_pose = Pose3F64(
            a_from_b=Isometry3F64(
                [approach_x, approach_y, 0.0],
                current.a_from_b.rotation,  # Keep current heading
            ),
            frame_a="world",
            frame_b=f"approach_{self.current_index}",
        )

        return await self.plan_segment(current, approach_pose)

    def is_row_end(self) -> bool:
        """Check if current waypoint is last in row.

        Returns:
            True if at row end waypoint
        """
        return self.current_index == self.config.last_row_waypoint_index

    async def plan_row_end_maneuver(self) -> Track | None:
        """Create 4-segment U-turn for row end.

        Returns:
            Next segment in row-end maneuver, or None if complete
        """
        if self.row_end_segment_index > 4:
            self.row_end_segment_index = 1  # Reset for next row
            return None

        current = await self.get_current_pose()
        builder = TrackBuilder(start=current)

        if self.row_end_segment_index == 1:
            # Drive into headland
            builder.create_straight_segment(
                "row_end_1", distance=self.config.headland_buffer_m, spacing=0.5
            )
        elif self.row_end_segment_index == 2:
            # Turn 90°
            angle = np.radians(90) * (
                1 if self.config.turn_direction == "left" else -1
            )
            builder.create_turn_segment("row_end_2", angle=angle, spacing=0.15)
        elif self.row_end_segment_index == 3:
            # Lateral movement
            builder.create_straight_segment(
                "row_end_3", distance=self.config.row_spacing_m, spacing=0.5
            )
        elif self.row_end_segment_index == 4:
            # Turn 90° again
            angle = np.radians(90) * (
                1 if self.config.turn_direction == "left" else -1
            )
            builder.create_turn_segment("row_end_4", angle=angle, spacing=0.15)

        self.row_end_segment_index += 1
        return builder.track
