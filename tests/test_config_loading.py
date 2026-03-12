#!/usr/bin/env python3
"""Test script for configuration loading."""
from pathlib import Path

from amiga_platform.core.config import PlatformConfig

print("=" * 60)
print("Testing Configuration Loading")
print("=" * 60)

try:
    config_path = Path("config/navigation_config.yaml")
    config = PlatformConfig.from_yaml(config_path)

    print("\n✓ Configuration loaded successfully!")
    print(f"\nWaypoints CSV: {config.waypoints.csv_path}")
    print(f"Coordinate system: {config.waypoints.coordinate_system}")
    print(f"Turn direction: {config.waypoints.turn_direction}")
    print(f"Vision enabled: {config.vision.enabled}")
    print(f"Module: {config.module}")
    print(f"Approach offset: {config.navigation.approach_offset_m}m")
    print(f"Max retries: {config.navigation.error_recovery_max_retries}")
    print(f"Filter convergence retries: {config.navigation.filter_convergence_retries}")

    print("\n✓ All configuration values accessible")

except Exception as e:
    print(f"\n✗ Configuration loading failed: {e}")
    import traceback

    traceback.print_exc()

print("\n" + "=" * 60)
print("Configuration Test Complete")
print("=" * 60)
