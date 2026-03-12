"""Configuration system using Pydantic for validation and type safety.

Loads from navigation_config.yaml (behavioral/mission settings).
Hardware settings live in platform_config.yaml.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Literal, Optional

import yaml
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ServiceConfig(BaseModel):
    """EventService connection details."""

    name: str
    host: str = "localhost"
    port: int


class WaypointConfig(BaseModel):
    """Waypoint loading configuration."""

    csv_path: Path
    coordinate_system: Literal["ENU", "NWU", "LATLONG"] = "ENU"
    # Reference point for LATLONG coordinate system.
    # Set to the base station (e.g. Emlid RS2+) GPS coordinates so
    # converted waypoints align with the filter's world frame origin.
    reference_lat: Optional[float] = None
    reference_lon: Optional[float] = None
    last_row_waypoint_index: Optional[int] = None
    turn_direction: Literal["left", "right"] = "left"
    turn_type: Literal["pi_turn", "turn_in_place"] = "pi_turn"
    row_spacing_m: float = 6.0
    headland_buffer_m: float = 2.0

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class CameraConfig(BaseModel):
    """Camera configuration."""

    service_name: str  # "oak/0" or "oak/1"
    role: Literal["forward", "downward"]
    model_path: Path
    ip_address: Optional[str] = None  # IP for direct depthai v3 access (PoE cameras)
    offset_x: float  # Camera position on robot
    offset_y: float
    offset_z: float
    pitch_deg: float = 0.0  # Camera tilt angle

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True


class VisionConfig(BaseModel):
    """Vision system configuration.

    Camera hardware settings live in platform_config.yaml.
    Only behavioural knobs belong here.
    """

    enabled: bool = True
    mode: Literal["stop_to_detect", "detect_on_fly"] = "stop_to_detect"
    search_radius_m: float = 1.0
    detection_timeout_s: float = 10.0
    min_confidence: float = 0.7
    forward_camera: Optional[CameraConfig] = None
    downward_camera: Optional[CameraConfig] = None


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


def load_service_configs(path: Path) -> Dict[str, ServiceConfig]:
    """Load service configurations from a farm-ng style JSON file.

    The JSON file uses a ``configs`` list (matching the amiga-adk format).
    Entries with no ``port`` (e.g. multi_subscriber) are skipped because they
    are not EventService endpoints we connect to directly.

    Args:
        path: Path to service_config.json

    Returns:
        Dict mapping service key names to ServiceConfig instances.
        Oak services are keyed by ``oak0`` / ``oak1`` to match ServiceManager.
    """
    logger.info(f"Loading service config from {path}")
    with open(path) as f:
        data = json.load(f)

    configs: Dict[str, ServiceConfig] = {}
    for entry in data.get("configs", []):
        if "port" not in entry:
            continue  # skip subscription-only entries like multi_subscriber
        name = entry["name"]
        # Normalise "oak/0" -> "oak0" etc. for dict key
        key = name.replace("/", "")
        configs[key] = ServiceConfig(name=name, host=entry["host"], port=entry["port"])

    return configs


class PlatformConfig(BaseModel):
    """Platform configuration."""

    waypoints: WaypointConfig
    module: str = "none"
    vision: VisionConfig
    navigation: NavigationConfig
    thresholds: ThresholdsConfig

    @classmethod
    def from_yaml(cls, path: Path) -> PlatformConfig:
        """Load configuration from YAML file.

        Args:
            path: Path to navigation_config.yaml

        Returns:
            Validated configuration
        """
        logger.info(f"Loading config from {path}")
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    # Service configs are loaded separately via load_service_configs()
