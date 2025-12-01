"""Multi-service client management for EventService connections."""
from __future__ import annotations

from typing import TYPE_CHECKING

from farm_ng.core.event_client import EventClient
from farm_ng.core.event_service_pb2 import EventServiceConfig

if TYPE_CHECKING:
    from .config import ServiceConfig


class ServiceManager:
    """Manages EventClient instances for multiple services."""

    def __init__(self, service_configs: dict[str, ServiceConfig]) -> None:
        """Initialize service clients from configuration.

        Args:
            service_configs: Dictionary mapping service names to their configurations
        """
        self.clients: dict[str, EventClient] = {}

        for name, config in service_configs.items():
            event_config = EventServiceConfig(
                name=config.name,
                host=config.host,
                port=config.port,
            )
            self.clients[name] = EventClient(event_config)

    def get(self, name: str) -> EventClient:
        """Get client by name with validation.

        Args:
            name: Service name to retrieve

        Returns:
            EventClient for the requested service

        Raises:
            KeyError: If service name is not configured
        """
        if name not in self.clients:
            raise KeyError(f"Service '{name}' not configured")
        return self.clients[name]

    @property
    def filter(self) -> EventClient:
        """Get the filter service client."""
        return self.get("filter")

    @property
    def track_follower(self) -> EventClient:
        """Get the track follower service client."""
        return self.get("track_follower")

    @property
    def canbus(self) -> EventClient:
        """Get the CAN bus service client."""
        return self.get("canbus")

    @property
    def oak0(self) -> EventClient:
        """Get the downward camera (oak/0) service client."""
        return self.get("oak0")

    @property
    def oak1(self) -> EventClient:
        """Get the forward camera (oak/1) service client."""
        return self.get("oak1")
