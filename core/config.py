"""Configuration system using Pydantic for validation and type safety."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


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
    """Master configuration."""

    services: dict[str, ServiceConfig]
    waypoints: WaypointConfig
    tool: ToolConfig
    vision: VisionConfig
    navigation: NavigationConfig
    thresholds: ThresholdsConfig

    @classmethod
    def from_yaml(cls, path: Path) -> XStemConfig:
        """Load configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)
