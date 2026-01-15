"""Abstract tool interface for swappable tool modules."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from farm_ng_core_pybind import Pose3F64

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Tool deployment result."""

    success: bool
    error: str | None = None
    measurement: dict | None = None


class ToolModule(ABC):
    """Abstract interface for tool modules."""

    @abstractmethod
    async def execute(self, hole_position: Pose3F64) -> ToolResult:
        """Execute tool deployment sequence.

        Args:
            hole_position: Target hole position in world frame

        Returns:
            Tool execution result
        """
        pass

    @abstractmethod
    async def verify_ready(self) -> bool:
        """Check if tool is ready for deployment.

        Returns:
            True if tool is ready
        """
        pass

    @abstractmethod
    async def calibrate(self) -> None:
        """Perform tool calibration if needed."""
        pass


class ToolManager:
    """Manages tool module execution with retry logic."""

    def __init__(self, module: ToolModule) -> None:
        """Initialize tool manager.

        Args:
            module: Tool module implementation
        """
        self.module = module

    async def execute_deployment(
        self, hole_position: Pose3F64, max_retries: int = 2
    ) -> bool:
        """Execute tool module with retry logic.

        Args:
            hole_position: Target hole position
            max_retries: Maximum number of retry attempts

        Returns:
            True if deployment succeeded
        """
        for attempt in range(max_retries + 1):
            if attempt > 0:
                logger.warning(f"Retrying tool deployment (attempt {attempt + 1})")

            result = await self.module.execute(hole_position)

            if result.success:
                logger.info("Tool deployment successful")
                if result.measurement:
                    logger.info(f"Measurement data: {result.measurement}")
                return True

            logger.warning(
                f"Tool deployment failed (attempt {attempt + 1}/{max_retries + 1}): "
                f"{result.error}"
            )

        logger.error("Tool deployment failed after all retries")
        return False
