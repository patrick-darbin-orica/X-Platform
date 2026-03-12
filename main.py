"""X-Platform Navigation System - Main Entry Point."""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Import platform components
from amiga_platform.core.blast_pattern import BlastPattern
from amiga_platform.core.config import PlatformConfig, load_service_configs
from amiga_platform.core.service_manager import ServiceManager
from amiga_platform.core.state_machine import NavigationStateMachine
from amiga_platform.hardware.filter_utils import check_filter_convergence, imu_wiggle
from amiga_platform.navigation.navigation_manager import NavigationManager
from amiga_platform.navigation.path_planner import PathPlanner
from utils.detection_relay import CollarDetection, DetectionRelay

# Import module system
from modules.base_module import BaseModule, ModuleContext
from modules.registry import get_global_registry


def setup_logging() -> Path:
    """Configure logging to both console and file.

    Returns:
        Path to the log file
    """
    # Create logs directory
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)

    # Create timestamped log file
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = log_dir / f"mission_{timestamp}.log"

    # Configure root logger
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)  # More verbose in file
    file_handler.setFormatter(logging.Formatter(log_format))

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return log_file


log_file = setup_logging()
logger = logging.getLogger(__name__)


def _robot_frame_to_world(det: CollarDetection, robot_pose):
    """Convert a robot-frame detection offset to a world-frame Pose3F64.

    Uses the robot's current yaw + position to rotate the offset into the
    world coordinate frame (NWU).
    """
    import math as _math

    from farm_ng_core_pybind import Isometry3F64, Pose3F64, Rotation3F64

    t = robot_pose.a_from_b.translation
    xr, yr = float(t[0]), float(t[1])

    # Extract yaw from SO3 log (rotation vector; yaw is the z-component)
    yaw = float(robot_pose.a_from_b.rotation.log()[-1])

    c, s = _math.cos(yaw), _math.sin(yaw)
    dx, dy = det.x_fwd_m, det.y_left_m
    xw = xr + dx * c - dy * s
    yw = yr + dx * s + dy * c

    iso = Isometry3F64([xw, yw, 0.0], Rotation3F64.Rz(yaw))
    return Pose3F64(
        a_from_b=iso,
        frame_a="world",
        frame_b="hole",
    )


class XModuleNavigator:
    """Main navigation orchestrator."""

    def __init__(self, config: PlatformConfig, service_config_path: Path) -> None:
        """Initialize navigator with configuration.

        Args:
            config: System configuration
            service_config_path: Path to service_config.json
        """
        self.config = config
        self.state_machine = NavigationStateMachine()
        self.shutdown_requested = False

        # Services
        self.services = ServiceManager(load_service_configs(service_config_path))

        # Components (will be initialized in setup())
        self.path_planner: Optional[PathPlanner] = None
        self.nav_manager: Optional[NavigationManager] = None
        self.vision = None
        self.relay: Optional[DetectionRelay] = None
        self.module: Optional[BaseModule] = None
        self.blast_pattern: Optional[BlastPattern] = None

    async def setup(self) -> None:
        """Initialize all components."""
        logger.info("Initializing navigation system...")

        # Path planner (tool offset applied later, after hole detection)
        self.path_planner = PathPlanner(
            self.config.waypoints,
            self.services.filter,
        )

        # Blast pattern (mission state tracking)
        csv_name = Path(str(self.config.waypoints.csv_path)).stem
        self.blast_pattern = BlastPattern(
            holes=list(self.path_planner.hole_poses.values()),
            echelon_ends=self.path_planner.echelon_ends,
            hole_ids=self.path_planner.hole_ids,
            mission_name=f"mission_{csv_name}",
        )

        # Navigation manager
        self.nav_manager = NavigationManager(
            self.services.track_follower,
            self.services.filter,
        )
        await self.nav_manager.start_monitoring()

        # Vision: standalone detector communicates via UDP relay.
        # VisionSystem (gRPC camera clients) is not needed for this path.
        self.vision = None
        if self.config.vision.enabled:
            self.relay = DetectionRelay()
            await self.relay.start()
        else:
            logger.info("Vision system disabled")

        # Dynamically import only the selected module (auto-registers it)
        module_name = self.config.module
        if module_name != "none":
            import importlib
            importlib.import_module(f"modules.{module_name}")
        logger.info(f"Loading module: {module_name}")

        # Load module config from its own config.yaml
        module_config_path = Path(__file__).parent / "modules" / module_name / "config.yaml"
        if module_config_path.exists():
            import yaml as _yaml
            with open(module_config_path) as f:
                _module_yaml = _yaml.safe_load(f)
            self.module_config = _module_yaml.get("config", {})
            logger.info(f"Loaded module config from {module_config_path}")
        else:
            self.module_config = {}
            logger.warning(f"No config.yaml found for module '{module_name}'")

        registry = get_global_registry()
        try:
            ModuleClass = registry.get(module_name)
            self.module = ModuleClass()
            logger.info(f"✓ Module instantiated: {self.module.module_name}")

            # Initialize module with platform context
            context = ModuleContext(
                hole_position=None,  # Will be provided during execute()
                robot_pose=None,     # Will be provided during execute()
                waypoint_index=0,    # Will be provided during execute()
                canbus_client=self.services.canbus,
                filter_client=self.services.filter,
                vision_system=self.vision if hasattr(self, 'vision') else None,
                module_config=self.module_config,
            )

            await self.module.initialize(context)

            # Verify module readiness
            if not await self.module.verify_ready():
                logger.error("Module not ready!")
            else:
                logger.info("✓ Module ready")

        except KeyError:
            logger.warning(f"Module '{module_name}' not found in registry, using NullModule")
            ModuleClass = registry.get("none")
            self.module = ModuleClass()
            await self.module.initialize(ModuleContext(
                hole_position=None,
                robot_pose=None,
                waypoint_index=0,
                canbus_client=self.services.canbus,
                filter_client=self.services.filter,
                vision_system=None,
                module_config={}
            ))

        # Check filter convergence
        converged = await check_filter_convergence(self.services.filter)
        if not converged:
            logger.warning("Filter not converged, attempting IMU wiggle...")
            wiggle_ok = await imu_wiggle(
                self.services.canbus,
                self.services.filter,
                duration_seconds=3.0,
                max_attempts=self.config.navigation.filter_convergence_retries,
                stop_event=self.nav_manager.shutdown_event,
            )
            if not wiggle_ok:
                if self.nav_manager.shutdown_event.is_set():
                    logger.error("Wiggle aborted by operator. Awaiting supervisory input.")
                else:
                    logger.error(
                        "Filter did not converge after %d wiggle attempts. "
                        "Awaiting supervisory input.",
                        self.config.navigation.filter_convergence_retries,
                    )
                # TODO: Implement supervisory input interface (dashboard / remote command)
                raise SystemExit(1)

        logger.info("Initialization complete")

    async def run(self) -> None:
        """Main navigation loop."""
        logger.info("Starting navigation...")
        self.state_machine.start()

        try:
            while not self.shutdown_requested and not self.state_machine.is_terminal():
                # Get next hole from blast pattern
                hole = self.blast_pattern.get_next_hole()

                if hole is None:
                    logger.info("All holes completed")
                    stats = self.blast_pattern.get_completion_stats()
                    logger.info(
                        f"Mission complete: {stats['completed']} completed, "
                        f"{stats['failed']} failed, {stats['skipped']} skipped"
                    )
                    self.state_machine.all_waypoints_complete()
                    break

                wp_index = hole.index
                # Waypoints are 1-indexed in PathPlanner (traversal order)
                wp_pose = self.path_planner.waypoints[wp_index + 1]
                logger.info(f"========== Navigating to hole {hole.hole_id} (index {wp_index}) ==========")

                # Debug: log waypoint and robot positions
                _wp_t = wp_pose.a_from_b.translation
                logger.info(
                    "Waypoint NWU: north=%.2f west=%.2f  (all waypoints: %s)",
                    float(_wp_t[0]), float(_wp_t[1]),
                    ", ".join(
                        f"{self.path_planner.hole_ids.get(k, k)}=({float(v.a_from_b.translation[0]):.1f}, {float(v.a_from_b.translation[1]):.1f})"
                        for k, v in sorted(self.path_planner.waypoints.items())
                    ),
                )
                _cur = await self.path_planner.get_current_pose()
                _cur_t = _cur.a_from_b.translation
                _cur_yaw = float(_cur.a_from_b.rotation.log()[-1])
                logger.info(
                    "Robot pose NWU: north=%.2f west=%.2f yaw=%.2f rad",
                    float(_cur_t[0]), float(_cur_t[1]), _cur_yaw,
                )

                # Mark hole as in progress
                self.blast_pattern.mark_in_progress(wp_index)

                # State: PLANNING
                self.state_machine.waypoint_planned()

                # Plan approach segment (stop before waypoint for vision)
                approach_track = await self.path_planner.plan_approach_segment(
                    wp_pose,
                    offset_m=self.config.navigation.approach_offset_m,
                )

                # State: APPROACHING
                self.state_machine.search_zone_reached()
                logger.info("Executing approach segment...")
                success = await self._execute_with_recovery(approach_track, "approach")

                if not success:
                    logger.error("Approach track failed after retries")
                    self.state_machine.track_failed()
                    continue

                # Check for shutdown before starting next track
                if self.shutdown_requested:
                    logger.info("Shutdown requested after approach - exiting")
                    break

                # State: DETECTING
                hole_pose = None
                if self.config.vision.enabled and self.relay:
                    logger.info("Waiting for collar detection from standalone detector...")
                    self.relay.clear()
                    deadline = asyncio.get_event_loop().time() + self.config.vision.detection_timeout_s
                    while asyncio.get_event_loop().time() < deadline:
                        det = self.relay.get_latest(max_age_s=1.0)
                        if det and det.confidence >= self.config.vision.min_confidence:
                            current_pose = await self.path_planner.get_current_pose()
                            hole_pose = _robot_frame_to_world(det, current_pose)
                            logger.info(
                                "Collar detected: x_fwd=%.2f y_left=%.2f conf=%.2f",
                                det.x_fwd_m, det.y_left_m, det.confidence,
                            )
                            break
                        await asyncio.sleep(0.1)
                # Note: inline VisionSystem detection removed — standalone
                # detector + relay is the only supported vision path.

                # Determine hole position (from vision or CSV fallback)
                if hole_pose:
                    logger.info("Hole detected by vision, using refined position")
                    self.state_machine.hole_detected()
                    detected_hole = hole_pose
                else:
                    logger.info("Using CSV waypoint position (vision disabled or failed)")
                    self.state_machine.hole_not_found()
                    detected_hole = wp_pose

                # Apply module's tool offset to get robot navigation target
                # This positions the robot so the module's tool is over the hole
                tool_offset = self.module_config.get("tool_offset", {})
                tool_offset_config = {
                    "offset_x": tool_offset.get("x", 0.0),
                    "offset_y": tool_offset.get("y", 0.0),
                    "offset_z": tool_offset.get("z", 0.0),
                }
                final_target = self.path_planner.apply_tool_offset(detected_hole, tool_offset_config)
                logger.info("Applied tool offset to get robot navigation target")

                # State: REFINING / EXECUTING
                self.state_machine.path_refined()
                logger.info("Executing final approach to hole...")
                final_track = await self.path_planner.plan_segment(
                    await self.path_planner.get_current_pose(), final_target
                )

                success = await self._execute_with_recovery(final_track, "final approach")

                if not success:
                    logger.error("Final approach failed after retries")
                    self.state_machine.track_failed()
                    continue

                # Check for shutdown before executing module
                if self.shutdown_requested:
                    logger.info("Shutdown requested after final approach - exiting")
                    break

                # State: MODULE_PHASE (Execute module action at hole)
                self.state_machine.track_complete()
                logger.info(f"Executing module at hole {hole.hole_id}...")

                # Create execution context for module
                current_pose = await self.path_planner.get_current_pose()
                exec_context = ModuleContext(
                    hole_position=final_target,
                    robot_pose=current_pose,
                    waypoint_index=wp_index,
                    canbus_client=self.services.canbus,
                    filter_client=self.services.filter,
                    vision_system=self.vision if hasattr(self, 'vision') else None,
                    module_config=self.module_config,
                )

                # Execute module
                result = await self.module.execute(exec_context)

                # State: UPDATING_PATTERN (Update blast pattern with module result)
                if result.success:
                    logger.info(f"✓ Hole {hole.hole_id} completed successfully")
                    self.blast_pattern.mark_completed(wp_index, measurements=result.measurements)
                    self.state_machine.tool_complete()

                    # Execute row-end maneuver after servicing the last hole in a row
                    if self.blast_pattern.is_echelon_end(wp_index):
                        logger.info("Echelon end detected, executing U-turn maneuver")
                        uturn_ok = await self._execute_row_end_maneuver()
                        if not uturn_ok:
                            logger.error("U-turn failed — stopping mission")
                            break
                else:
                    logger.error(f"✗ Module execution failed at hole {hole.hole_id}: {result.error}")
                    self.blast_pattern.mark_failed(wp_index, error=result.error or "Unknown error")
                    self.state_machine.tool_failed()
                    # TODO: Implement recovery logic (retry/skip/abort)

        except asyncio.CancelledError:
            logger.info("Navigation cancelled")
        except Exception as e:
            logger.error(f"Navigation error: {e}", exc_info=True)
            self.state_machine.abort()
        finally:
            await self.shutdown()

    async def _execute_with_recovery(self, track, label: str) -> bool:
        """Execute a track with automatic retry on recoverable failures.

        Retries on CANBUS_TIMEOUT (with delay) and FILTER_DIVERGED (with IMU wiggle).
        Raises RuntimeError on fatal failures (AUTO_MODE_DISABLED) to abort the mission.

        Args:
            track: Track segment to execute
            label: Human-readable label for logging (e.g. "approach", "final approach")

        Returns:
            True if track completed successfully, False on non-fatal failure

        Raises:
            RuntimeError: On fatal failures that require mission abort
        """
        max_retries = self.config.navigation.error_recovery_max_retries
        can_delay = self.config.navigation.can_recovery_delay_s
        filter_retries = self.config.navigation.filter_convergence_retries

        canbus_attempts = 0
        filter_attempts = 0

        for attempt in range(1, max_retries + 2):  # +1 for the initial attempt
            success = await self.nav_manager.execute_track(track)
            if success:
                return True

            failure_modes = self.nav_manager.last_failure_modes
            logger.warning(f"{label} failed (attempt {attempt}), failure modes: {failure_modes}")

            if "AUTO_MODE_DISABLED" in failure_modes:
                logger.error("AUTO_MODE_DISABLED — robot auto mode is off, aborting mission")
                raise RuntimeError("AUTO_MODE_DISABLED")

            elif "CANBUS_TIMEOUT" in failure_modes:
                canbus_attempts += 1
                if canbus_attempts > max_retries:
                    logger.error(f"Max CAN bus retries ({max_retries}) exceeded for {label}")
                    return False
                logger.info(f"CANBUS_TIMEOUT — waiting {can_delay}s before retry ({canbus_attempts}/{max_retries})")
                await asyncio.sleep(can_delay)

            elif "FILTER_DIVERGED" in failure_modes:
                filter_attempts += 1
                if filter_attempts > filter_retries:
                    logger.error(f"Max filter retries ({filter_retries}) exceeded for {label}")
                    return False
                logger.info(f"FILTER_DIVERGED — attempting IMU wiggle recovery ({filter_attempts}/{filter_retries})")
                await imu_wiggle(
                    self.services.canbus,
                    self.services.filter,
                    stop_event=self.shutdown_event if hasattr(self, 'shutdown_event') else None,
                )

            else:
                # Unknown or unrecoverable failure
                if not failure_modes:
                    logger.error(f"{label} failed with no specific failure mode")
                return False

        return False

    async def _execute_row_end_maneuver(self) -> bool:
        """Execute row-end turn maneuver.

        Returns:
            True if all segments completed successfully
        """
        total = self.path_planner.row_end_total_segments
        logger.info(f"Executing row-end maneuver ({total} segments)...")

        for segment_idx in range(1, total + 1):
            track = await self.path_planner.plan_row_end_maneuver()
            if track is None:
                break

            logger.info(f"Row-end segment {segment_idx}/{total}")
            success = await self.nav_manager.execute_track(track)

            if not success:
                logger.error(f"Row-end segment {segment_idx} failed")
                self.path_planner.reset_row_end_state()
                return False

        logger.info("Row-end maneuver complete")
        return True

    async def shutdown(self) -> None:
        """Clean shutdown."""
        logger.info("Shutting down...")
        self.shutdown_requested = True

        # Shutdown module
        if self.module:
            await self.module.shutdown()

        # Stop detection relay
        if self.relay:
            await self.relay.stop()

        # Stop navigation manager monitoring
        if self.nav_manager:
            await self.nav_manager.shutdown()

        # TODO: Close service clients gracefully if needed
        # The EventClient instances in ServiceManager may need explicit cleanup

        logger.info("Shutdown complete")


def signal_handler(navigator: XModuleNavigator):
    """Create signal handler for graceful shutdown.

    Args:
        navigator: Navigator instance to shutdown

    Returns:
        Signal handler function
    """

    def handler(signum, _frame):
        logger.info(f"Received signal {signum} - requesting immediate shutdown")
        navigator.shutdown_requested = True
        # Trigger immediate track cancellation
        if navigator.nav_manager:
            navigator.nav_manager.request_immediate_shutdown()

    return handler


async def main(config_path: Path, service_config_path: Path) -> None:
    """Entry point.

    Args:
        config_path: Path to navigation_config.yaml
        service_config_path: Path to service_config.json
    """
    logger.info(f"Logging to: {log_file}")

    # Load configuration
    config = PlatformConfig.from_yaml(config_path)
    logger.info(f"Loaded configuration from {config_path}")

    # Create navigator
    navigator = XModuleNavigator(config, service_config_path)

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler(navigator))
    signal.signal(signal.SIGTERM, signal_handler(navigator))

    # Run
    await navigator.setup()
    await navigator.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="X-Platform Navigation System")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / "Amiga" / "X-Platform" / "config" / "navigation_config.yaml",
        help="Path to navigation config YAML file",
    )
    parser.add_argument(
        "--service-config",
        type=Path,
        default=Path.home() / "Amiga" / "X-Platform" / "config" / "service_config.json",
        help="Path to service config JSON file",
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(args.config, args.service_config))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
