"""Navigation state machine for explicit state management."""
from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class NavState(str, Enum):
    """Navigation states."""

    IDLE = "idle"
    PLANNING = "planning"
    APPROACHING = "approaching"
    DETECTING = "detecting"
    REFINING = "refining"
    EXECUTING = "executing"
    DEPLOYING = "deploying"
    RECOVERING = "recovering"
    COMPLETE = "complete"
    FAILED = "failed"


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
        """Check if in a terminal state (complete or failed).

        Returns:
            True if in COMPLETE or FAILED state
        """
        return self._current_state in (NavState.COMPLETE, NavState.FAILED)

    # Convenience transition methods
    def start(self) -> None:
        """Start navigation - transition from IDLE to PLANNING."""
        self.transition(NavState.PLANNING)

    def waypoint_planned(self) -> None:
        """Waypoint planned - transition to APPROACHING."""
        self.transition(NavState.APPROACHING)

    def search_zone_reached(self) -> None:
        """Reached search zone - transition to DETECTING."""
        self.transition(NavState.DETECTING)

    def hole_detected(self) -> None:
        """Hole detected by vision - transition to REFINING."""
        self.transition(NavState.REFINING)

    def hole_not_found(self) -> None:
        """Hole not found, using CSV position - transition to REFINING."""
        self.transition(NavState.REFINING)

    def path_refined(self) -> None:
        """Path refined - transition to EXECUTING."""
        self.transition(NavState.EXECUTING)

    def track_complete(self) -> None:
        """Track execution complete - transition to DEPLOYING."""
        self.transition(NavState.DEPLOYING)

    def track_failed(self) -> None:
        """Track execution failed - transition to RECOVERING."""
        self.transition(NavState.RECOVERING)

    def tool_complete(self) -> None:
        """Tool deployment complete - transition back to PLANNING for next waypoint."""
        self.transition(NavState.PLANNING)

    def tool_failed(self) -> None:
        """Tool deployment failed - transition to RECOVERING."""
        self.transition(NavState.RECOVERING)

    def retry(self) -> None:
        """Retry from RECOVERING - transition to PLANNING."""
        self.transition(NavState.PLANNING)

    def skip(self) -> None:
        """Skip waypoint from RECOVERING - transition to PLANNING."""
        self.transition(NavState.PLANNING)

    def abort(self) -> None:
        """Abort from RECOVERING - transition to FAILED."""
        self.transition(NavState.FAILED)

    def all_waypoints_complete(self) -> None:
        """All waypoints processed - transition to COMPLETE."""
        self.transition(NavState.COMPLETE)

    def shutdown(self) -> None:
        """Shutdown - transition to COMPLETE."""
        self.transition(NavState.COMPLETE)
