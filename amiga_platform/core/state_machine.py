"""Navigation state machine for explicit state management."""
from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class NavState(str, Enum):
    """Navigation states aligned with Amiga Base Platform Process flowchart.

    State flow:
    IDLE → INITIALIZING → PLANNING → PLOTTING_PATH → FOLLOWING_PATH →
    STOPPING → DETECTING → CONVERTING → MODULE_PHASE → UPDATING_PATTERN →
    [Decision: blast pattern complete?]
      Yes → RETURNING → COMPLETE
      No → [Decision: echelon end?]
        Yes → ECHELON_TURN → PLANNING
        No → PLANNING

    Error states: SEGMENT_TIMEOUT → RECOVERING → [retry/skip/abort]
    """

    # Initialization states
    IDLE = "idle"
    INITIALIZING = "initializing"

    # Navigation cycle states (per hole)
    PLANNING = "planning"              # Set goal point at hole in CSV
    PLOTTING_PATH = "plotting_path"    # Plot path to hole search zone
    FOLLOWING_PATH = "following_path"  # Follow path
    STOPPING = "stopping"              # Stop at search zone
    DETECTING = "detecting"            # Detect hole with vision
    CONVERTING = "converting"          # Convert hole distance to GPS coordinates

    # Module execution states (RED BOX in flowchart)
    MODULE_PHASE = "module_phase"      # Execute module action at hole

    # Pattern update state (PINK BOX in flowchart)
    UPDATING_PATTERN = "updating_pattern"  # Update blast pattern with result

    # Transition states
    ECHELON_TURN = "echelon_turn"      # U-turn at row end
    RETURNING = "returning"            # Return to start after mission

    # Error/recovery states
    SEGMENT_TIMEOUT = "segment_timeout"  # Segment timeout decision point
    RECOVERING = "recovering"          # Handle failures (retry/skip/abort)

    # Terminal states
    COMPLETE = "complete"
    FAILED = "failed"
    EMERGENCY_STOP = "emergency_stop"  # E-stop triggered


class NavigationStateMachine:
    """Simple state machine for navigation control."""

    def __init__(self) -> None:
        """Initialize state machine."""
        self._current_state = NavState.IDLE
        self._previous_state = NavState.IDLE

    @property
    def current_state(self) -> NavState:
        """Get current state."""
        return self._current_state

    @property
    def previous_state(self) -> NavState:
        """Get previous state."""
        return self._previous_state

    def transition(self, new_state: NavState) -> None:
        """Transition to a new state with logging.

        Args:
            new_state: Target state to transition to
        """
        if new_state != self._current_state:
            logger.info(f"[STATE] {self._current_state.value} → {new_state.value}")
            self._previous_state = self._current_state
            self._current_state = new_state

    def is_state(self, state: NavState) -> bool:
        """Check if currently in a specific state.

        Args:
            state: State to check

        Returns:
            True if current state matches
        """
        return self._current_state == state

    def is_terminal(self) -> bool:
        """Check if in a terminal state (complete, failed, or emergency stop).

        Returns:
            True if in a terminal state
        """
        return self._current_state in (
            NavState.COMPLETE,
            NavState.FAILED,
            NavState.EMERGENCY_STOP,
        )

    # Convenience transition methods (flowchart-aligned)

    # Initialization
    def start(self) -> None:
        """Start navigation - transition from IDLE to PLANNING."""
        self.transition(NavState.PLANNING)

    def initialize(self) -> None:
        """Initialize system - transition from IDLE to INITIALIZING."""
        self.transition(NavState.INITIALIZING)

    def initialization_complete(self) -> None:
        """Initialization complete - transition to PLANNING."""
        self.transition(NavState.PLANNING)

    # Per-hole navigation cycle
    def goal_set(self) -> None:
        """Goal point set - transition from PLANNING to PLOTTING_PATH."""
        self.transition(NavState.PLOTTING_PATH)

    def path_plotted(self) -> None:
        """Path plotted - transition to FOLLOWING_PATH."""
        self.transition(NavState.FOLLOWING_PATH)

    def approaching_stop(self) -> None:
        """Approaching stop point - transition to STOPPING."""
        self.transition(NavState.STOPPING)

    def stopped(self) -> None:
        """Stopped at search zone - transition to DETECTING."""
        self.transition(NavState.DETECTING)

    def hole_detected(self) -> None:
        """Hole detected - transition to CONVERTING."""
        self.transition(NavState.CONVERTING)

    def coordinates_converted(self) -> None:
        """Coordinates converted - transition to PLOTTING_PATH for refined approach."""
        self.transition(NavState.PLOTTING_PATH)

    # Module execution
    def ready_for_module(self) -> None:
        """Ready for module execution - transition to MODULE_PHASE."""
        self.transition(NavState.MODULE_PHASE)

    def module_complete(self) -> None:
        """Module execution complete - transition to UPDATING_PATTERN."""
        self.transition(NavState.UPDATING_PATTERN)

    # Pattern update and decisions
    def pattern_updated(self, is_complete: bool, is_echelon_end: bool) -> None:
        """Pattern updated - transition based on mission state.

        Args:
            is_complete: True if all holes in blast pattern are complete
            is_echelon_end: True if at end of current echelon/row
        """
        if is_complete:
            self.transition(NavState.RETURNING)
        elif is_echelon_end:
            self.transition(NavState.ECHELON_TURN)
        else:
            self.transition(NavState.PLANNING)

    def echelon_turn_complete(self) -> None:
        """U-turn complete - transition back to PLANNING."""
        self.transition(NavState.PLANNING)

    # Error handling
    def segment_timeout_detected(self) -> None:
        """Segment timeout detected - transition to SEGMENT_TIMEOUT."""
        self.transition(NavState.SEGMENT_TIMEOUT)

    def enter_recovery(self) -> None:
        """Enter recovery mode - transition to RECOVERING."""
        self.transition(NavState.RECOVERING)

    def retry(self) -> None:
        """Retry from RECOVERING - transition to PLANNING."""
        self.transition(NavState.PLANNING)

    def skip_hole(self) -> None:
        """Skip hole from RECOVERING - transition to PLANNING."""
        self.transition(NavState.PLANNING)

    def abort(self) -> None:
        """Abort mission - transition to FAILED."""
        self.transition(NavState.FAILED)

    def emergency_stop(self) -> None:
        """Emergency stop - transition to EMERGENCY_STOP."""
        self.transition(NavState.EMERGENCY_STOP)

    # Mission completion
    def start_return(self) -> None:
        """Start return to origin - transition to RETURNING."""
        self.transition(NavState.RETURNING)

    def mission_complete(self) -> None:
        """Mission complete - transition to COMPLETE."""
        self.transition(NavState.COMPLETE)

    def shutdown(self) -> None:
        """Shutdown - transition to COMPLETE."""
        self.transition(NavState.COMPLETE)

    # Legacy compatibility methods (for gradual migration)
    def waypoint_planned(self) -> None:
        """Legacy: Waypoint planned - maps to goal_set."""
        self.goal_set()

    def search_zone_reached(self) -> None:
        """Legacy: Search zone reached - maps to approaching_stop."""
        self.approaching_stop()

    def hole_not_found(self) -> None:
        """Legacy: Hole not found - still use CSV position, skip CONVERTING."""
        self.transition(NavState.PLOTTING_PATH)

    def path_refined(self) -> None:
        """Legacy: Path refined - maps to path_plotted."""
        self.path_plotted()

    def track_complete(self) -> None:
        """Legacy: Track complete - maps to ready_for_module."""
        self.ready_for_module()

    def track_failed(self) -> None:
        """Legacy: Track failed - maps to enter_recovery."""
        self.enter_recovery()

    def tool_complete(self) -> None:
        """Legacy: Tool complete - maps to module_complete."""
        self.module_complete()

    def tool_failed(self) -> None:
        """Legacy: Tool failed - maps to enter_recovery."""
        self.enter_recovery()

    def skip(self) -> None:
        """Legacy: Skip - maps to skip_hole."""
        self.skip_hole()

    def all_waypoints_complete(self) -> None:
        """Legacy: All waypoints complete - maps to mission_complete."""
        self.mission_complete()
