"""Blast pattern tracking and mission state management."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from farm_ng_core_pybind import Pose3F64

logger = logging.getLogger(__name__)


class HoleStatus(Enum):
    """Status of a hole in the blast pattern."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class HoleRecord:
    """Record for a single hole in the blast pattern.

    Tracks position, status, attempts, errors, and measurements.
    """

    index: int
    position: Pose3F64
    hole_id: str = ""
    status: HoleStatus = HoleStatus.PENDING
    attempts: int = 0
    last_error: Optional[str] = None
    measurements: Dict = field(default_factory=dict)
    timestamp_completed: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "index": self.index,
            "hole_id": self.hole_id,
            "position": {
                "x": self.position.a_from_b.translation[0],
                "y": self.position.a_from_b.translation[1],
                "z": self.position.a_from_b.translation[2],
            },
            "status": self.status.value,
            "attempts": self.attempts,
            "last_error": self.last_error,
            "measurements": self.measurements,
            "timestamp_completed": self.timestamp_completed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> HoleRecord:
        """Create from dictionary (for loading saved state)."""
        from farm_ng_core_pybind import Isometry3F64, Rotation3F64

        pos = data["position"]
        position = Pose3F64(
            frame_a="world",
            frame_b="hole",
            a_from_b=Isometry3F64([pos["x"], pos["y"], pos["z"]], Rotation3F64()),
        )

        return cls(
            index=data["index"],
            hole_id=data.get("hole_id", ""),
            position=position,
            status=HoleStatus(data["status"]),
            attempts=data["attempts"],
            last_error=data.get("last_error"),
            measurements=data.get("measurements", {}),
            timestamp_completed=data.get("timestamp_completed"),
        )


class BlastPattern:
    """Blast pattern mission state manager.

    Manages the state of all holes in a mission:
    - Which holes are completed, pending, failed
    - Hole positions and measurements
    - Mission progress tracking
    - State persistence for mission resume

    Separate from PathPlanner to decouple mission state from navigation.
    """

    def __init__(
        self,
        holes: List[Pose3F64],
        echelon_ends: List[int],
        hole_ids: Optional[Dict[int, str]] = None,
        mission_name: str = "mission",
    ):
        """Initialize blast pattern.

        Args:
            holes: List of hole positions (Pose3F64) in traversal order
            echelon_ends: 0-based indices where each echelon ends
            hole_ids: Optional dict mapping 1-based index → hole ID string (e.g. "A0")
            mission_name: Name for this mission (for state files)
        """
        self.mission_name = mission_name
        self.echelon_ends = set(echelon_ends)
        self.echelon_ends_list = list(echelon_ends)

        # Create hole records with hole IDs
        self.holes: List[HoleRecord] = []
        for i, pose in enumerate(holes):
            hid = hole_ids.get(i + 1, str(i)) if hole_ids else str(i)
            self.holes.append(HoleRecord(index=i, position=pose, hole_id=hid))

        self.current_hole_index: Optional[int] = None

        ids_str = ", ".join(h.hole_id for h in self.holes)
        logger.info(
            f"Blast pattern initialized: {len(self.holes)} holes [{ids_str}], "
            f"echelon ends: {sorted(self.echelon_ends)}"
        )

    def get_next_hole(self) -> Optional[HoleRecord]:
        """Get next pending hole to process.

        Returns:
            Next hole with PENDING status, or None if all done
        """
        for hole in self.holes:
            if hole.status == HoleStatus.PENDING:
                return hole
        return None

    def get_hole(self, index: int) -> Optional[HoleRecord]:
        """Get hole by index.

        Args:
            index: Hole index

        Returns:
            HoleRecord or None if index invalid
        """
        if 0 <= index < len(self.holes):
            return self.holes[index]
        return None

    def mark_in_progress(self, index: int) -> None:
        """Mark hole as in progress.

        Args:
            index: Hole index
        """
        hole = self.get_hole(index)
        if hole:
            hole.status = HoleStatus.IN_PROGRESS
            hole.attempts += 1
            self.current_hole_index = index
            logger.info(f"Hole {hole.hole_id} marked IN_PROGRESS (attempt {hole.attempts})")

    def mark_completed(
        self, index: int, measurements: Optional[Dict] = None
    ) -> None:
        """Mark hole as completed with optional measurements.

        Args:
            index: Hole index
            measurements: Optional measurements from module
        """
        hole = self.get_hole(index)
        if hole:
            hole.status = HoleStatus.COMPLETED
            hole.timestamp_completed = datetime.now().isoformat()
            if measurements:
                hole.measurements = measurements
            logger.info(f"✓ Hole {hole.hole_id} marked COMPLETED")

    def mark_failed(self, index: int, error: str) -> None:
        """Mark hole as failed with error message.

        Args:
            index: Hole index
            error: Error description
        """
        hole = self.get_hole(index)
        if hole:
            hole.status = HoleStatus.FAILED
            hole.last_error = error
            logger.error(f"✗ Hole {hole.hole_id} marked FAILED: {error}")

    def mark_skipped(self, index: int, reason: str) -> None:
        """Mark hole as skipped.

        Args:
            index: Hole index
            reason: Reason for skipping
        """
        hole = self.get_hole(index)
        if hole:
            hole.status = HoleStatus.SKIPPED
            hole.last_error = reason
            logger.warning(f"⊘ Hole {hole.hole_id} marked SKIPPED: {reason}")

    def is_complete(self) -> bool:
        """Check if all holes are processed (completed, failed, or skipped).

        Returns:
            True if no holes are pending or in progress
        """
        return all(
            hole.status
            in [HoleStatus.COMPLETED, HoleStatus.FAILED, HoleStatus.SKIPPED]
            for hole in self.holes
        )

    def is_echelon_end(self, index: int) -> bool:
        """Check if hole index is at the end of an echelon/row.

        Used to determine if U-turn maneuver is needed.
        Returns False for the very last hole in the pattern since
        there is no next row to turn into.

        Args:
            index: 0-based hole index

        Returns:
            True if this is the last hole in a row (but not the last hole overall)
        """
        if index >= len(self.holes) - 1:
            return False
        return index in self.echelon_ends

    def get_completion_stats(self) -> Dict[str, int]:
        """Get completion statistics.

        Returns:
            Dictionary with counts for each status
        """
        stats = {
            "total": len(self.holes),
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "failed": 0,
            "skipped": 0,
        }

        for hole in self.holes:
            stats[hole.status.value] += 1

        return stats

    def get_progress_percentage(self) -> float:
        """Get mission progress as percentage.

        Returns:
            Percentage of holes completed (0-100)
        """
        stats = self.get_completion_stats()
        processed = stats["completed"] + stats["failed"] + stats["skipped"]
        return (processed / stats["total"]) * 100 if stats["total"] > 0 else 0

    def save_state(self, path: Path) -> None:
        """Save blast pattern state to JSON file.

        Enables mission resume capability.

        Args:
            path: Path to save state file
        """
        state = {
            "mission_name": self.mission_name,
            "echelon_ends": self.echelon_ends_list,
            "current_hole_index": self.current_hole_index,
            "timestamp": datetime.now().isoformat(),
            "holes": [hole.to_dict() for hole in self.holes],
            "stats": self.get_completion_stats(),
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(state, f, indent=2)

        logger.info(f"Blast pattern state saved to {path}")

    @classmethod
    def load_state(cls, path: Path) -> BlastPattern:
        """Load blast pattern state from JSON file.

        Args:
            path: Path to state file

        Returns:
            BlastPattern instance with restored state
        """
        with open(path, "r") as f:
            state = json.load(f)

        # Create instance
        holes = [HoleRecord.from_dict(h) for h in state["holes"]]
        hole_positions = [h.position for h in holes]
        hole_ids = {h.index + 1: h.hole_id for h in holes}
        echelon_ends = state.get("echelon_ends", [])

        pattern = cls(
            holes=hole_positions,
            echelon_ends=echelon_ends,
            hole_ids=hole_ids,
            mission_name=state["mission_name"],
        )

        # Restore hole records with their states
        pattern.holes = holes
        pattern.current_hole_index = state.get("current_hole_index")

        logger.info(f"Blast pattern state loaded from {path}")
        logger.info(f"Progress: {pattern.get_progress_percentage():.1f}%")

        return pattern

    def __repr__(self) -> str:
        """String representation."""
        stats = self.get_completion_stats()
        return (
            f"BlastPattern(mission={self.mission_name}, "
            f"total={stats['total']}, completed={stats['completed']}, "
            f"failed={stats['failed']}, pending={stats['pending']})"
        )
