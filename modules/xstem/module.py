"""XStem stemming module: dipbob measurement + gravel dispensing."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from amiga_platform.hardware.filter_utils import trigger_dipbob
from amiga_platform.hardware.actuator import CanHBridgeActuator, NullActuator

from modules.base_module import BaseModule, ModuleContext, ModuleResult

if TYPE_CHECKING:
    from farm_ng.core.event_client import EventClient

    from amiga_platform.hardware.actuator import BaseActuator
    from amiga_platform.vision.vision_system import VisionSystem

logger = logging.getLogger(__name__)


class StemmingModule(BaseModule):
    """XStem stemming module: dipbob measurement + gravel dispensing.

    This module implements the full stemming sequence:
    1. Align dipbob over hole using downward camera
    2. Deploy dipbob for depth measurement
    3. Wait for measurement ACK
    4. Move robot forward to align chute (handled by platform)
    5. Align chute over hole
    6. Dispense gravel with timed pulse
    7. Close chute

    The module requires:
    - CAN bus for dipbob trigger
    - Chute actuator (H-bridge) for gravel dispensing
    - Vision system (optional) for alignment verification
    """

    def __init__(self) -> None:
        """Initialize stemming module.

        Actual initialization happens in initialize() method.
        """
        self.canbus: Optional[EventClient] = None
        self.actuator: Optional[BaseActuator] = None
        self.vision: Optional[VisionSystem] = None
        self.config: dict = {}

    @property
    def module_name(self) -> str:
        """Get module name."""
        return "xstem"

    async def initialize(self, context: ModuleContext) -> None:
        """Initialize stemming module with platform context.

        Args:
            context: Module context with services and configuration
        """
        logger.info("Initializing XStem stemming module...")

        # Store service references
        self.canbus = context.canbus_client
        self.vision = context.vision_system
        self.config = context.module_config

        # Initialize chute actuator
        chute_config = self.config.get("chute", {})
        actuator_id = chute_config.get("actuator_id", 0)

        if actuator_id >= 0:
            self.actuator = CanHBridgeActuator(
                context.canbus_client,
                actuator_id
            )
            logger.info(f"Initialized chute actuator (ID: {actuator_id})")
        else:
            self.actuator = NullActuator()
            logger.info("Using null actuator (no physical chute)")

        logger.info("XStem stemming module initialized")

    async def verify_ready(self) -> bool:
        """Check if stemming module is ready.

        Returns:
            True if ready for deployment
        """
        # TODO: Add actual readiness checks
        # - Check dipbob status via CAN
        # - Check chute actuator status
        # - Check gravel level sensor
        # - Verify vision system if required

        if not self.canbus:
            logger.error("CAN bus not initialized")
            return False

        if not self.actuator:
            logger.error("Actuator not initialized")
            return False

        logger.info("Stemming module ready")
        return True

    async def calibrate(self) -> bool:
        """Calibrate stemming module.

        Returns:
            True if calibration succeeded
        """
        logger.info("Stemming module calibration...")

        # TODO: Implement actual calibration
        # - Home chute actuator
        # - Test dipbob trigger/ACK
        # - Verify vision detection
        # - Calibrate tool offsets

        logger.info("Stemming module calibration complete (placeholder)")
        return True

    async def execute(self, context: ModuleContext) -> ModuleResult:
        """Execute stemming sequence at hole.

        Sequence:
        1. Align dipbob over hole (downward camera)
        2. Deploy dipbob for depth measurement
        3. Wait for measurement ACK
        4. Robot moves forward (tool offset) - handled by platform
        5. Align chute over hole
        6. Dispense gravel with timed pulse
        7. Close chute

        Args:
            context: Execution context with hole position

        Returns:
            ModuleResult with success/failure and measurements
        """
        try:
            alignment_config = self.config.get("alignment", {})
            dipbob_config = self.config.get("dipbob", {})
            chute_config = self.config.get("chute", {})

            # Step 1: Verify dipbob alignment with downward camera
            if self.vision:
                logger.info("Step 1: Verifying dipbob alignment...")
                aligned = await self.vision.align_tool_downward(
                    tolerance_m=alignment_config.get("dipbob_tolerance_m", 0.02)
                )

                if not aligned:
                    return ModuleResult(
                        success=False,
                        error="Dipbob alignment failed",
                        hole_completed=False
                    )
            else:
                logger.info("Step 1: Skipping alignment (vision disabled)")

            # Step 2: Deploy dipbob
            logger.info("Step 2: Deploying dipbob...")
            await self._trigger_dipbob()

            # Step 3: Wait for measurement ACK
            logger.info("Step 3: Waiting for dipbob measurement...")
            ack_timeout = dipbob_config.get("ack_timeout_s", 5.0)
            ack = await self._wait_for_dipbob_ack(timeout=ack_timeout)

            if not ack:
                return ModuleResult(
                    success=False,
                    error="Dipbob measurement timeout",
                    hole_completed=False
                )

            # Step 4-5: Platform handles robot movement to align chute
            # Wait for platform to complete movement
            logger.info("Step 4-5: Waiting for chute alignment (platform handles movement)...")
            settle_time = dipbob_config.get("measurement_settle_s", 2.0)
            await asyncio.sleep(settle_time)

            # Optional: Verify chute alignment
            if self.vision:
                chute_aligned = await self.vision.align_tool_downward(
                    tolerance_m=alignment_config.get("chute_tolerance_m", 0.02)
                )

                if not chute_aligned:
                    logger.warning("Chute alignment suboptimal, proceeding anyway")

            # Step 6-7: Dispense gravel
            logger.info("Step 6-7: Dispensing gravel...")
            await self.actuator.pulse_sequence(
                open_seconds=chute_config.get("open_duration_s", 0.2),
                close_seconds=chute_config.get("close_duration_s", 0.3),
                rate_hz=chute_config.get("control_rate_hz", 10.0),
                settle_before=chute_config.get("pre_dispense_settle_s", 2.0),
            )

            logger.info("✓ Stemming sequence complete")
            return ModuleResult(
                success=True,
                measurements={"sequence": "complete"},  # TODO: Add actual measurements
                hole_completed=True
            )

        except Exception as e:
            logger.error(f"✗ Stemming sequence failed: {e}", exc_info=True)
            return ModuleResult(
                success=False,
                error=str(e),
                hole_completed=False
            )

    async def shutdown(self) -> None:
        """Clean shutdown of stemming module."""
        logger.info("Shutting down stemming module...")

        # No ongoing operations to stop (all operations are synchronous in execute)
        # Actuators return to safe state automatically

        logger.info("Stemming module shutdown complete")

    async def _trigger_dipbob(self) -> None:
        """Trigger dipbob deployment via CAN."""
        await trigger_dipbob(self.canbus)

    async def _wait_for_dipbob_ack(self, timeout: float) -> bool:
        """Wait for dipbob measurement acknowledgement.

        Args:
            timeout: Timeout in seconds

        Returns:
            True if ACK received
        """
        # TODO: Listen for actual CAN ACK signal
        # For now, just wait for expected measurement time
        logger.info(f"Waiting {timeout}s for dipbob measurement...")
        await asyncio.sleep(timeout)
        logger.info("Dipbob measurement complete (placeholder)")
        return True
