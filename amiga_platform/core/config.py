"""Configuration system using Pydantic for validation and type safety.

This module maintains backward compatibility with the v1 config system
while also supporting the new multi-tier platform/mission/module configs.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Literal, Optional

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ServiceConfig(BaseModel):
    """EventService connection details."""

    name: str
    host: str = "localhost"
    port: int


class WaypointConfig(BaseModel):
    """Waypoint loading configuration."""

    csv_path: Path
    coordinate_system: Literal["ENU", "NWU"] = "ENU"
    last_row_waypoint_index: int
    turn_direction: Literal["left", "right"] = "left"
    row_spacing_m: float = 6.0
    headland_buffer_m: float = 2.0

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class ToolConfig(BaseModel):
    """Tool/implement configuration."""

    type: str = "stemming"
    offset_x: float = 0.25  # meters forward
    offset_y: float = 0.0
    offset_z: float = 0.0

    # Dipbob settings
    dipbob_can_signal: str = "dipbob_deploy"
    dipbob_ack_timeout_s: float = 5.0

    # Chute settings
    chute_actuator_id: int = 0
    chute_open_duration_s: float = 0.2
    chute_close_duration_s: float = 0.3
    chute_rate_hz: float = 10.0


class CameraConfig(BaseModel):
    """Camera configuration."""

    service_name: str  # "oak/0" or "oak/1"
    role: Literal["forward", "downward"]
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
    mode: Literal["stop_to_detect", "detect_on_fly"] = "stop_to_detect"
    search_radius_m: float = 1.0
    detection_timeout_s: float = 10.0
    min_confidence: float = 0.7
    forward_camera: CameraConfig
    downward_camera: CameraConfig


class NavigationConfig(BaseModel):
    """Navigation behavior configuration."""

    approach_offset_m: float = 1.2
    error_recovery_max_retries: int = 3
    filter_convergence_retries: int = 3
    can_recovery_delay_s: float = 0.5


class ThresholdsConfig(BaseModel):
    """Detection and control thresholds."""

    positioning_accuracy_m: float = 0.05
    heading_accuracy_deg: float = 10.0
    alignment_tolerance_m: float = 0.02


class XStemConfig(BaseModel):
    """Master configuration (v1 - backward compatible)."""

    services: Dict[str, ServiceConfig]
    waypoints: WaypointConfig
    tool: ToolConfig
    vision: VisionConfig
    navigation: NavigationConfig
    thresholds: ThresholdsConfig

    @classmethod
    def from_yaml(cls, path: Path) -> XStemConfig:
        """Load configuration from YAML file (v1 format).

        Args:
            path: Path to v1-style navigation_config.yaml

        Returns:
            Validated configuration
        """
        logger.info(f"Loading v1 config from {path}")
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    @classmethod
    def from_multi_tier(
        cls,
        platform_config_path: Path,
        mission_config_path: Path,
        module_config_path: Optional[Path] = None,
    ) -> XStemConfig:
        """Load configuration from v2 multi-tier configs.

        This method bridges the new platform/mission/module config system
        with the v1 XStemConfig format for backward compatibility.

        Args:
            platform_config_path: Path to platform config YAML
            mission_config_path: Path to mission config YAML
            module_config_path: Optional path to module config YAML

        Returns:
            Validated configuration in v1 format
        """
        from amiga_platform.config_loader import ConfigLoader

        logger.info("Loading v2 multi-tier configs and converting to v1 format")
        loader = ConfigLoader(platform_config_path, mission_config_path, module_config_path)

        platform = loader.get_platform_config()
        mission = loader.get_mission_config()
        module = loader.get_module_config()

        # Map v2 config to v1 structure
        services = {name: ServiceConfig(**svc.dict()) for name, svc in platform.services.items()}

        waypoints = WaypointConfig(
            csv_path=mission.blast_pattern.csv_path,
            coordinate_system=mission.blast_pattern.coordinate_system,
            last_row_waypoint_index=mission.blast_pattern.last_row_waypoint_index,
            turn_direction=mission.blast_pattern.turn_direction,
            row_spacing_m=mission.blast_pattern.row_spacing_m,
            headland_buffer_m=platform.navigation.headland_buffer_m,
        )

        # Tool config from module (if present)
        if module and module.module_type == "stemming":
            tool_cfg = module.config.get("tool_offset", {})
            dipbob_cfg = module.config.get("dipbob", {})
            chute_cfg = module.config.get("chute", {})

            tool = ToolConfig(
                type="stemming",
                offset_x=tool_cfg.get("dipbob_x", 0.25),
                offset_y=tool_cfg.get("dipbob_y", 0.0),
                offset_z=tool_cfg.get("dipbob_z", 0.0),
                dipbob_ack_timeout_s=dipbob_cfg.get("ack_timeout_s", 5.0),
                chute_actuator_id=chute_cfg.get("actuator_id", 0),
                chute_open_duration_s=chute_cfg.get("open_duration_s", 0.2),
                chute_close_duration_s=chute_cfg.get("close_duration_s", 0.3),
                chute_rate_hz=chute_cfg.get("control_rate_hz", 10.0),
            )
        else:
            # Default tool config (no module)
            tool = ToolConfig()

        vision = VisionConfig(
            enabled=platform.vision.enabled,
            mode="stop_to_detect",
            search_radius_m=platform.navigation.search_zone_search_radius_m,
            detection_timeout_s=platform.vision.detection_timeout_s,
            min_confidence=platform.vision.min_confidence,
            forward_camera=CameraConfig(
                service_name=platform.vision.forward_camera.service_name,
                role="forward",
                model_path=platform.vision.forward_camera.model_path,
                offset_x=platform.vision.forward_camera.offset_x,
                offset_y=platform.vision.forward_camera.offset_y,
                offset_z=platform.vision.forward_camera.offset_z,
                pitch_deg=platform.vision.forward_camera.pitch_deg,
            ),
            downward_camera=CameraConfig(
                service_name=platform.vision.downward_camera.service_name,
                role="downward",
                model_path=platform.vision.downward_camera.model_path,
                offset_x=platform.vision.downward_camera.offset_x,
                offset_y=platform.vision.downward_camera.offset_y,
                offset_z=platform.vision.downward_camera.offset_z,
                pitch_deg=platform.vision.downward_camera.pitch_deg,
            ),
        )

        navigation = NavigationConfig(
            approach_offset_m=platform.navigation.search_zone_approach_offset_m,
            error_recovery_max_retries=platform.navigation.max_retries,
            filter_convergence_retries=platform.filter.convergence_max_retries,
            can_recovery_delay_s=platform.can.recovery_delay_s,
        )

        thresholds = ThresholdsConfig(
            positioning_accuracy_m=platform.navigation.positioning_tolerance_m,
            heading_accuracy_deg=platform.navigation.heading_tolerance_deg,
            alignment_tolerance_m=module.config.get("alignment", {}).get("dipbob_tolerance_m", 0.02) if module else 0.02,
        )

        logger.info("Successfully converted v2 configs to v1 format")
        return cls(
            services=services,
            waypoints=waypoints,
            tool=tool,
            vision=vision,
            navigation=navigation,
            thresholds=thresholds,
        )
