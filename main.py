"""XStem Navigation System - Main Entry Point."""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

from control.stemming_module import StemmingModule
from control.tool_manager import ToolManager
from core.config import XStemConfig
from core.service_manager import ServiceManager
from core.state_machine import NavigationStateMachine, NavState
from hardware.actuator import CanHBridgeActuator, NullActuator
from hardware.filter_utils import check_filter_convergence, imu_wiggle
from navigation.navigation_manager import NavigationManager
from navigation.path_planner import PathPlanner
from vision.vision_system import VisionSystem

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class XStemNavigator:
    """Main navigation orchestrator."""

    def __init__(self, config: XStemConfig) -> None:
        """Initialize navigator with configuration.

        Args:
            config: System configuration
        """
        self.config = config
        self.state_machine = NavigationStateMachine()
        self.shutdown_requested = False

        # Services
        self.services = ServiceManager(config.services)

        # Components (will be initialized in setup())
        self.path_planner = None
        self.nav_manager = None
        self.vision = None
        self.tool_manager = None

    async def setup(self) -> None:
        """Initialize all components."""
        logger.info("Initializing XStem navigation system...")

        # Path planner
        self.path_planner = PathPlanner(
            self.config.waypoints,
            self.config.tool,
            self.services.filter,
        )

        # Navigation manager
        self.nav_manager = NavigationManager(
            self.services.track_follower,
            self.services.filter,
        )
        await self.nav_manager.start_monitoring()

        # Vision system
        if self.config.vision.enabled:
            self.vision = VisionSystem(
                self.services.oak0,
                self.services.oak1,
                self.config.vision.forward_camera.dict(),
                self.config.vision.downward_camera.dict(),
            )
            await self.vision.initialize()
        else:
            logger.info("Vision system disabled")
            self.vision = None

        # Actuator
        if self.config.tool.chute_actuator_id >= 0:
            actuator = CanHBridgeActuator(
                self.services.canbus,
                self.config.tool.chute_actuator_id,
            )
        else:
            actuator = NullActuator()

        # Tool manager
        stemming_module = StemmingModule(
            self.services.canbus,
            actuator,
            self.vision,
            self.config.tool.dict(),
        )
        self.tool_manager = ToolManager(stemming_module)

        # Check filter convergence
        converged = await check_filter_convergence(self.services.filter)
        if not converged:
            logger.warning("Filter not converged, attempting IMU wiggle...")
            await imu_wiggle(
                self.services.canbus,
                self.services.filter,
                duration_seconds=3.0,
                max_attempts=self.config.navigation.filter_convergence_retries,
            )

        logger.info("Initialization complete")

    async def run(self) -> None:
        """Main navigation loop."""
        logger.info("Starting navigation...")
        self.state_machine.start()

        try:
            while not self.shutdown_requested and not self.state_machine.is_terminal():
                # Get next waypoint
                waypoint = self.path_planner.get_next_waypoint()

                if waypoint is None:
                    logger.info("All waypoints completed")
                    self.state_machine.all_waypoints_complete()
                    break

                wp_index, wp_pose = waypoint
                logger.info(f"========== Navigating to waypoint {wp_index} ==========")

                # State: PLANNING
                self.state_machine.waypoint_planned()

                # Check for row-end maneuver
                if self.path_planner.is_row_end():
                    logger.info("Row end detected, executing U-turn maneuver")
                    await self._execute_row_end_maneuver()
                    continue

                # Plan approach segment (stop before waypoint for vision)
                approach_track = await self.path_planner.plan_approach_segment(
                    wp_pose,
                    offset_m=self.config.navigation.approach_offset_m,
                )

                # State: APPROACHING
                self.state_machine.search_zone_reached()
                logger.info("Executing approach segment...")
                success = await self.nav_manager.execute_track(approach_track)

                if not success:
                    logger.error("Approach track failed")
                    self.state_machine.track_failed()
                    # TODO: Implement retry logic
                    continue

                # State: DETECTING
                hole_pose = None
                if self.config.vision.enabled and self.vision:
                    logger.info("Detecting hole with forward camera...")
                    hole_pose = await self.vision.detect_hole_forward(
                        search_center=self.path_planner.get_hole_position(wp_index),
                        search_radius_m=self.config.vision.search_radius_m,
                        timeout_s=self.config.vision.detection_timeout_s,
                    )

                if hole_pose:
                    logger.info("Hole detected by vision, using refined position")
                    self.state_machine.hole_detected()
                    final_target = hole_pose
                else:
                    logger.info("Using CSV waypoint position (vision disabled or failed)")
                    self.state_machine.hole_not_found()
                    final_target = wp_pose

                # State: REFINING / EXECUTING
                self.state_machine.path_refined()
                logger.info("Executing final approach to hole...")
                final_track = await self.path_planner.plan_segment(
                    await self.path_planner.get_current_pose(), final_target
                )

                success = await self.nav_manager.execute_track(final_track)

                if not success:
                    logger.error("Final approach failed")
                    self.state_machine.track_failed()
                    continue

                # State: DEPLOYING
                self.state_machine.track_complete()
                logger.info("Deploying tool...")
                success = await self.tool_manager.execute_deployment(final_target)

                if success:
                    logger.info(f"✓ Waypoint {wp_index} completed successfully")
                    self.state_machine.tool_complete()
                else:
                    logger.error(f"✗ Tool deployment failed at waypoint {wp_index}")
                    self.state_machine.tool_failed()
                    # TODO: Implement recovery logic

        except asyncio.CancelledError:
            logger.info("Navigation cancelled")
        except Exception as e:
            logger.error(f"Navigation error: {e}", exc_info=True)
            self.state_machine.abort()
        finally:
            await self.shutdown()

    async def _execute_row_end_maneuver(self) -> None:
        """Execute 4-segment row-end turn."""
        logger.info("Executing row-end maneuver (4 segments)...")

        for segment_idx in range(1, 5):
            track = await self.path_planner.plan_row_end_maneuver()
            if track is None:
                break

            logger.info(f"Row-end segment {segment_idx}/4")
            success = await self.nav_manager.execute_track(track)

            if not success:
                logger.error(f"Row-end segment {segment_idx} failed")
                # TODO: Implement retry logic
                break

        logger.info("Row-end maneuver complete")

    async def shutdown(self) -> None:
        """Clean shutdown."""
        logger.info("Shutting down...")
        self.shutdown_requested = True

        # Stop navigation manager monitoring
        if self.nav_manager:
            await self.nav_manager.shutdown()

        # TODO: Close service clients gracefully if needed
        # The EventClient instances in ServiceManager may need explicit cleanup

        logger.info("Shutdown complete")


def signal_handler(navigator: XStemNavigator):
    """Create signal handler for graceful shutdown.

    Args:
        navigator: Navigator instance to shutdown

    Returns:
        Signal handler function
    """

    def handler(signum, frame):
        logger.info(f"Received signal {signum}")
        navigator.shutdown_requested = True

    return handler


async def main(config_path: Path) -> None:
    """Entry point.

    Args:
        config_path: Path to configuration YAML file
    """
    # Load configuration
    config = XStemConfig.from_yaml(config_path)
    logger.info(f"Loaded configuration from {config_path}")

    # Create navigator
    navigator = XStemNavigator(config)

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler(navigator))
    signal.signal(signal.SIGTERM, signal_handler(navigator))

    # Run
    await navigator.setup()
    await navigator.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="XStem Navigation System")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / "Amiga" / "xstem" / "config" / "navigation_config.yaml",
        help="Path to configuration file",
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(args.config))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
