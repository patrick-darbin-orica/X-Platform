"""Test blast pattern tracking functionality."""
import tempfile
from pathlib import Path
from typing import List

from farm_ng_core_pybind import Isometry3F64, Pose3F64, Rotation3F64

from amiga_platform.core.blast_pattern import BlastPattern, HoleStatus


def create_test_holes(count: int = 6) -> List[Pose3F64]:
    """Create test hole positions."""
    holes = []
    for i in range(count):
        position = Pose3F64(
            frame_a="world",
            frame_b=f"hole_{i}",
            a_from_b=Isometry3F64([float(i), 0.0, 0.0], Rotation3F64()),
        )
        holes.append(position)
    return holes


def test_blast_pattern_initialization():
    """Test basic initialization."""
    holes = create_test_holes(6)
    pattern = BlastPattern(
        holes=holes, last_row_waypoint_index=2, mission_name="test_mission"
    )

    assert len(pattern.holes) == 6
    assert pattern.last_row_index == 2
    assert pattern.mission_name == "test_mission"
    print("✓ Initialization test passed")


def test_hole_iteration():
    """Test getting next hole."""
    holes = create_test_holes(4)
    pattern = BlastPattern(holes=holes, last_row_waypoint_index=1)

    # All should be pending initially
    next_hole = pattern.get_next_hole()
    assert next_hole is not None
    assert next_hole.index == 0
    assert next_hole.status == HoleStatus.PENDING

    # Mark first as completed
    pattern.mark_completed(0)
    next_hole = pattern.get_next_hole()
    assert next_hole.index == 1

    print("✓ Hole iteration test passed")


def test_status_tracking():
    """Test hole status changes."""
    holes = create_test_holes(3)
    pattern = BlastPattern(holes=holes, last_row_waypoint_index=1)

    # Mark in progress
    pattern.mark_in_progress(0)
    assert pattern.holes[0].status == HoleStatus.IN_PROGRESS
    assert pattern.holes[0].attempts == 1

    # Mark completed with measurements
    pattern.mark_completed(0, measurements={"depth": 1.5})
    assert pattern.holes[0].status == HoleStatus.COMPLETED
    assert pattern.holes[0].measurements["depth"] == 1.5
    assert pattern.holes[0].timestamp_completed is not None

    # Mark failed
    pattern.mark_failed(1, "Vision detection timeout")
    assert pattern.holes[1].status == HoleStatus.FAILED
    assert pattern.holes[1].last_error == "Vision detection timeout"

    # Mark skipped
    pattern.mark_skipped(2, "Max retries exceeded")
    assert pattern.holes[2].status == HoleStatus.SKIPPED

    print("✓ Status tracking test passed")


def test_echelon_detection():
    """Test echelon end detection."""
    holes = create_test_holes(8)
    pattern = BlastPattern(
        holes=holes, last_row_waypoint_index=3
    )  # 4 holes per row

    # Row ends at indices 3, 7, 11...
    assert pattern.is_echelon_end(3) is True
    assert pattern.is_echelon_end(7) is True
    assert pattern.is_echelon_end(0) is False
    assert pattern.is_echelon_end(5) is False

    print("✓ Echelon detection test passed")


def test_completion_stats():
    """Test completion statistics."""
    holes = create_test_holes(5)
    pattern = BlastPattern(holes=holes, last_row_waypoint_index=1)

    pattern.mark_completed(0)
    pattern.mark_completed(1)
    pattern.mark_failed(2, "error")
    pattern.mark_skipped(3, "skipped")
    # Hole 4 remains pending

    stats = pattern.get_completion_stats()
    assert stats["total"] == 5
    assert stats["completed"] == 2
    assert stats["failed"] == 1
    assert stats["skipped"] == 1
    assert stats["pending"] == 1

    progress = pattern.get_progress_percentage()
    assert progress == 80.0  # 4 out of 5 processed

    assert pattern.is_complete() is False

    # Complete last hole
    pattern.mark_completed(4)
    assert pattern.is_complete() is True

    print("✓ Completion stats test passed")


def test_state_persistence():
    """Test saving and loading state."""
    holes = create_test_holes(4)
    pattern = BlastPattern(
        holes=holes, last_row_waypoint_index=1, mission_name="persistence_test"
    )

    # Mark some holes
    pattern.mark_in_progress(0)
    pattern.mark_completed(0, measurements={"depth": 2.0})
    pattern.mark_failed(1, "test error")

    # Save state
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "blast_pattern_state.json"
        pattern.save_state(state_file)

        # Load state
        loaded_pattern = BlastPattern.load_state(state_file)

        # Verify
        assert loaded_pattern.mission_name == "persistence_test"
        assert len(loaded_pattern.holes) == 4
        assert loaded_pattern.holes[0].status == HoleStatus.COMPLETED
        assert loaded_pattern.holes[0].measurements["depth"] == 2.0
        assert loaded_pattern.holes[1].status == HoleStatus.FAILED
        assert loaded_pattern.holes[1].last_error == "test error"
        assert loaded_pattern.holes[2].status == HoleStatus.PENDING

    print("✓ State persistence test passed")


def main():
    """Run all tests."""
    print("Testing BlastPattern class...\n")

    test_blast_pattern_initialization()
    test_hole_iteration()
    test_status_tracking()
    test_echelon_detection()
    test_completion_stats()
    test_state_persistence()

    print("\n✅ All BlastPattern tests passed!")


if __name__ == "__main__":
    main()
