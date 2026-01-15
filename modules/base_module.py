"""Base module interface for all tool modules."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from farm_ng.core.event_client import EventClient
    from farm_ng_core_pybind import Pose3F64

    from amiga_platform.vision.vision_system import VisionSystem


@dataclass
class ModuleResult:
    """Result of module execution at a hole.

    Attributes:
        success: Whether the module operation succeeded
        error: Error message if failed (None if successful)
        measurements: Optional measurement data from module (e.g., {"depth_cm": 45})
        telemetry: Optional telemetry data (e.g., {"dispense_time_s": 0.52})
        hole_completed: Whether to mark hole as completed in blast pattern
    """

    success: bool
    error: Optional[str] = None
    measurements: Optional[Dict[str, Any]] = None
    telemetry: Optional[Dict[str, Any]] = None
    hole_completed: bool = True


@dataclass
class ModuleContext:
    """Context provided by platform to modules during execution.

    This contains all the services and information a module needs
    to perform its operation at a hole.

    Attributes:
        hole_position: Detected/planned hole location in world frame
        robot_pose: Current robot pose in world frame
        waypoint_index: Current hole number in blast pattern
        canbus_client: EventClient for CAN bus communication
        filter_client: EventClient for filter/localization service
        vision_system: Vision system for alignment checks (optional)
        module_config: Module-specific configuration dictionary
    """

    hole_position: Pose3F64
    robot_pose: Pose3F64
    waypoint_index: int
    canbus_client: EventClient
    filter_client: EventClient
    vision_system: Optional[VisionSystem]
    module_config: Dict[str, Any]


class BaseModule(ABC):
    """Abstract base class for all modules.

    All modules must implement this interface to be compatible with
    the base platform. The platform will call these methods in order:

    1. initialize() - Once at startup
    2. verify_ready() - Before first waypoint
    3. calibrate() - If configured (optional)
    4. execute() - At each hole (main loop)
    5. shutdown() - When mission completes or aborts

    Example Implementation:
        ```python
        class MyModule(BaseModule):
            @property
            def module_name(self) -> str:
                return "my_module"

            async def initialize(self, context: ModuleContext) -> None:
                self.canbus = context.canbus_client
                self.config = context.module_config
                # Initialize hardware, load calibration, etc.

            async def verify_ready(self) -> bool:
                # Check hardware status
                return True

            async def calibrate(self) -> bool:
                # Perform calibration routine
                return True

            async def execute(self, context: ModuleContext) -> ModuleResult:
                # Perform module operation at hole
                try:
                    # ... do work ...
                    return ModuleResult(success=True)
                except Exception as e:
                    return ModuleResult(success=False, error=str(e))

            async def shutdown(self) -> None:
                # Clean shutdown
                pass
        ```
    """

    @property
    @abstractmethod
    def module_name(self) -> str:
        """Unique module identifier.

        This should match the module_name in mission_config.yaml.

        Returns:
            Module name (e.g., "xstem", "xprime")
        """
        pass

    @abstractmethod
    async def initialize(self, context: ModuleContext) -> None:
        """Initialize module with platform-provided context.

        Called once at startup before any operations. Use this to:
        - Store references to platform services
        - Initialize hardware connections
        - Load calibration data
        - Validate configuration

        Args:
            context: Module context with services and configuration

        Raises:
            Exception: If initialization fails (will abort mission)
        """
        pass

    @abstractmethod
    async def verify_ready(self) -> bool:
        """Check if module is ready for operation.

        Called before starting the mission. Use this to:
        - Check hardware status
        - Verify sensor readings
        - Confirm actuators are operational
        - Check resource levels (e.g., gravel level)

        Returns:
            True if module is ready, False otherwise
        """
        pass

    @abstractmethod
    async def calibrate(self) -> bool:
        """Perform module calibration routine.

        Called if configured in mission settings. Use this to:
        - Home actuators
        - Calibrate sensors
        - Verify tool alignment
        - Test communication with hardware

        Returns:
            True if calibration succeeded, False otherwise
        """
        pass

    @abstractmethod
    async def execute(self, context: ModuleContext) -> ModuleResult:
        """Execute module operation at hole.

        This is the main module action called at each hole. The platform
        has already navigated to the hole position. The module should:
        1. Perform any necessary alignment checks
        2. Execute the tool-specific operation
        3. Return the result

        Args:
            context: Execution context with hole position and services

        Returns:
            ModuleResult with success/failure and optional data
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean shutdown of module.

        Called when mission completes or is aborted. Use this to:
        - Stop any running operations
        - Return actuators to safe positions
        - Close hardware connections
        - Save any necessary state

        This method should not raise exceptions.
        """
        pass


class NullModule(BaseModule):
    """Null module that does nothing.

    This is used when module_name is "none" in mission config.
    Allows testing navigation without tool deployment.
    """

    @property
    def module_name(self) -> str:
        """Return module name."""
        return "none"

    async def initialize(self, context: ModuleContext) -> None:
        """Initialize null module (no-op)."""
        pass

    async def verify_ready(self) -> bool:
        """Null module is always ready."""
        return True

    async def calibrate(self) -> bool:
        """Null module calibration (no-op)."""
        return True

    async def execute(self, context: ModuleContext) -> ModuleResult:
        """Execute null operation (no-op).

        Returns success immediately without doing anything.
        """
        return ModuleResult(success=True, hole_completed=True)

    async def shutdown(self) -> None:
        """Shutdown null module (no-op)."""
        pass
