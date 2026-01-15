"""Multi-tier configuration system for platform, mission, and module configs."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


class ServiceConfig(BaseModel):
    """EventService connection details."""

    name: str
    host: str = "localhost"
    port: int
    timeout_s: Optional[float] = None


class FilterConfig(BaseModel):
    """Filter service convergence and wiggle configuration."""

    convergence_check_timeout_s: float = 5.0
    convergence_max_retries: int = 3
    imu_wiggle_duration_s: float = 3.0
    imu_wiggle_angular_velocity_rad_s: float = 0.3
    imu_wiggle_check_rate_hz: float = 20.0


class NavigationConfig(BaseModel):
    """Navigation behavior configuration."""

    # Search zone
    search_zone_approach_offset_m: float = 1.2
    search_zone_search_radius_m: float = 1.0

    # Track generation
    segment_spacing_m: float = 0.5
    turn_spacing_m: float = 0.15
    execution_timeout_s: float = 60.0
    track_load_wait_s: float = 1.0

    # Accuracy thresholds
    positioning_tolerance_m: float = 0.05
    heading_tolerance_deg: float = 10.0

    # Row-end maneuver
    headland_buffer_m: float = 2.0
    turn_angle_deg: float = 90.0

    # Error recovery
    max_retries: int = 3
    segment_timeout_fallback: bool = True
    retry_delay_s: float = 1.0


class CameraConfig(BaseModel):
    """Camera configuration."""

    service_name: str  # "oak/0" or "oak/1"
    model_path: Path
    offset_x: float  # Camera position on robot
    offset_y: float
    offset_z: float
    pitch_deg: float = 0.0  # Camera tilt angle

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class VisionConfig(BaseModel):
    """Vision system configuration."""

    enabled: bool = True
    detection_timeout_s: float = 10.0
    min_confidence: float = 0.7
    averaging_samples: int = 3
    alignment_check_timeout_s: float = 10.0
    fov_width_m: float = 0.5  # Approximate field of view

    forward_camera: CameraConfig
    downward_camera: CameraConfig


class CANConfig(BaseModel):
    """CAN bus configuration."""

    command_rate_hz: float = 20.0
    recovery_delay_s: float = 0.5


class PlatformConfig(BaseModel):
    """Platform-level configuration."""

    platform_name: str = "Amiga Base Platform"
    platform_version: str = "2.0.0"

    services: Dict[str, ServiceConfig]
    filter: FilterConfig
    navigation: NavigationConfig
    vision: VisionConfig
    can: CANConfig

    @classmethod
    def from_yaml(cls, path: Path) -> PlatformConfig:
        """Load platform configuration from YAML file.

        Args:
            path: Path to platform config YAML

        Returns:
            Validated platform configuration
        """
        logger.info(f"Loading platform config from {path}")
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)


class BlastPatternConfig(BaseModel):
    """Blast pattern configuration."""

    csv_path: Path
    coordinate_system: str = "ENU"
    last_row_waypoint_index: int
    turn_direction: str = "left"
    row_spacing_m: float = 6.0

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class MissionConfig(BaseModel):
    """Mission-specific configuration."""

    mission_name: str
    module_name: str  # Module to load (e.g., "xstem", "xprime", "none")
    blast_pattern: BlastPatternConfig

    @classmethod
    def from_yaml(cls, path: Path) -> MissionConfig:
        """Load mission configuration from YAML file.

        Args:
            path: Path to mission config YAML

        Returns:
            Validated mission configuration
        """
        logger.info(f"Loading mission config from {path}")
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)


class ModuleConfig(BaseModel):
    """Module-specific configuration (flexible dict)."""

    module_name: str
    module_type: str
    config: Dict[str, Any]  # Module-specific parameters

    @classmethod
    def from_yaml(cls, path: Path) -> ModuleConfig:
        """Load module configuration from YAML file.

        Args:
            path: Path to module config YAML

        Returns:
            Validated module configuration
        """
        logger.info(f"Loading module config from {path}")
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)


class ConfigLoader:
    """Loads and manages multi-tier configuration system."""

    def __init__(
        self,
        platform_config_path: Path,
        mission_config_path: Path,
        module_config_path: Optional[Path] = None,
    ) -> None:
        """Initialize configuration loader.

        Args:
            platform_config_path: Path to platform config YAML
            mission_config_path: Path to mission config YAML
            module_config_path: Optional path to module config YAML
        """
        self.platform_config = PlatformConfig.from_yaml(platform_config_path)
        self.mission_config = MissionConfig.from_yaml(mission_config_path)

        # Load module config if module is specified
        if self.mission_config.module_name != "none":
            if module_config_path:
                self.module_config = ModuleConfig.from_yaml(module_config_path)
            else:
                # Auto-discover module config
                auto_path = (
                    Path(__file__).parent.parent
                    / "modules"
                    / self.mission_config.module_name
                    / "config.yaml"
                )
                if auto_path.exists():
                    self.module_config = ModuleConfig.from_yaml(auto_path)
                    logger.info(f"Auto-loaded module config from {auto_path}")
                else:
                    logger.warning(
                        f"No module config found for {self.mission_config.module_name}"
                    )
                    self.module_config = None
        else:
            self.module_config = None
            logger.info("No module configured (module_name='none')")

    def get_platform_config(self) -> PlatformConfig:
        """Get platform configuration."""
        return self.platform_config

    def get_mission_config(self) -> MissionConfig:
        """Get mission configuration."""
        return self.mission_config

    def get_module_config(self) -> Optional[ModuleConfig]:
        """Get module configuration."""
        return self.module_config

    def validate_all(self) -> bool:
        """Validate all configurations.

        Returns:
            True if all configs are valid
        """
        try:
            # Platform validation
            assert (
                self.platform_config.platform_name
            ), "Platform name must be specified"
            assert len(self.platform_config.services) > 0, "No services configured"

            # Mission validation
            assert self.mission_config.mission_name, "Mission name must be specified"
            assert (
                self.mission_config.blast_pattern.csv_path.suffix == ".csv"
            ), "Blast pattern must be CSV file"

            # Module validation (if applicable)
            if self.module_config:
                assert (
                    self.module_config.module_name
                    == self.mission_config.module_name
                ), "Module config name mismatch"

            logger.info("All configurations validated successfully")
            return True

        except AssertionError as e:
            logger.error(f"Configuration validation failed: {e}")
            return False
