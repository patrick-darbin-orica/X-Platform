"""Stemming module: dipbob measurement + gravel dispensing."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from hardware.filter_utils import trigger_dipbob

from .tool_manager import ToolModule, ToolResult

if TYPE_CHECKING:
    from farm_ng.core.event_client import EventClient
    from farm_ng_core_pybind import Pose3F64

    from hardware.actuator import BaseActuator
    from vision.vision_system import VisionSystem

logger = logging.getLogger(__name__)


class StemmingModule(ToolModule):
    """Stemming module: dipbob measurement + gravel dispensing."""

    def __init__(
        self,
        canbus_client: EventClient,
        actuator: BaseActuator,
        vision_system: VisionSystem,
        config: dict,
    ) -> None:
        """Initialize stemming module.

        Args:
            canbus_client: CAN bus service client
            actuator: Chute actuator
            vision_system: Vision system for alignment
            config: Tool configuration dict
        """
        self.canbus = canbus_client
        self.actuator = actuator
        self.vision = vision_system
        self.config = config

    async def verify_ready(self) -> bool:
        """Check if stemming module is ready.

        Returns:
            True if ready for deployment
        """
        # TODO: Add actual readiness checks
        # - Check dipbob status
        # - Check chute actuator status
        # - Check gravel level
        return True

    async def calibrate(self) -> None:
        """Calibrate stemming module.

        This could include:
        - Homing actuators
        - Verifying sensor readings
        - Testing communication with dipbob
        """
        logger.info("Stemming module calibration (placeholder)")
        # TODO: Implement actual calibration

    async def execute(self, hole_position: Pose3F64) -> ToolResult:
        """Execute stemming sequence.

        Sequence:
        1. Align dipper over hole (downward camera)
        2. Deploy dipbob
        3. Wait for measurement ACK
        4. Move forward (tool offset) - handled by navigation
        5. Align chute over hole
        6. Open chute (timer-based)
        7. Close chute

        Args:
            hole_position: Target hole position

        Returns:
            Tool execution result
        """
        try:
            # Step 1: Verify alignment with downward camera
            logger.info("Step 1: Verifying dipbob alignment...")
            aligned = await self.vision.align_tool_downward(
                tolerance_m=self.config.get("alignment_tolerance_m", 0.02)
            )

            if not aligned:
                return ToolResult(success=False, error="Dipbob alignment failed")

            # Step 2: Deploy dipbob
            logger.info("Step 2: Deploying dipbob...")
            await self._trigger_dipbob()

            # Step 3: Wait for measurement
            logger.info("Step 3: Waiting for dipbob measurement...")
            ack = await self._wait_for_dipbob_ack(
                timeout=self.config.get("dipbob_ack_timeout_s", 5.0)
            )

            if not ack:
                return ToolResult(success=False, error="Dipbob measurement timeout")

            # Step 4-5: Navigation moves robot forward to align chute
            # This is handled externally by the navigation system
            logger.info("Step 4-5: Waiting for chute alignment (navigation)...")
            await asyncio.sleep(2.0)  # Wait for robot to move

            # Optional: Verify chute alignment
            chute_aligned = await self.vision.align_tool_downward(
                tolerance_m=self.config.get("alignment_tolerance_m", 0.02)
            )

            if not chute_aligned:
                logger.warning("Chute alignment suboptimal, proceeding anyway")

            # Step 6-7: Dispense gravel
            logger.info("Step 6-7: Dispensing gravel...")
            await self.actuator.pulse_sequence(
                open_seconds=self.config.get("chute_open_duration_s", 0.2),
                close_seconds=self.config.get("chute_close_duration_s", 0.3),
                rate_hz=self.config.get("chute_rate_hz", 10.0),
                settle_before=2.0,
            )

            logger.info("Stemming sequence complete")
            return ToolResult(success=True)

        except Exception as e:
            logger.error(f"Stemming sequence failed: {e}", exc_info=True)
            return ToolResult(success=False, error=str(e))

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
