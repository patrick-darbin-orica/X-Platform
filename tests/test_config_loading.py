#!/usr/bin/env python3
"""Test script for multi-tier configuration loading."""
from pathlib import Path

from amiga_platform.core.config import XStemConfig

# Test v2 multi-tier config loading
print("=" * 60)
print("Testing v2 Multi-Tier Configuration Loading")
print("=" * 60)

try:
    platform_path = Path("config/platform_config.yaml")
    mission_path = Path("config/mission_config.yaml")

    config = XStemConfig.from_multi_tier(platform_path, mission_path)

    print("\n✓ Configuration loaded successfully!")
    print(f"\nServices configured: {list(config.services.keys())}")
    print(f"Vision enabled: {config.vision.enabled}")
    print(f"Waypoints CSV: {config.waypoints.csv_path}")
    print(f"Tool type: {config.tool.type}")
    print(f"Tool offset: ({config.tool.offset_x}, {config.tool.offset_y}, {config.tool.offset_z})")
    print(f"Approach offset: {config.navigation.approach_offset_m}m")
    print(f"Max retries: {config.navigation.error_recovery_max_retries}")
    print(f"Filter convergence retries: {config.navigation.filter_convergence_retries}")

    print("\n✓ All configuration values accessible in v1 format")

except Exception as e:
    print(f"\n✗ Configuration loading failed: {e}")
    import traceback
    traceback.print_exc()

# Test v1 backward compatibility
print("\n" + "=" * 60)
print("Testing v1 Backward Compatibility")
print("=" * 60)

try:
    v1_path = Path("config/navigation_config.yaml")
    if v1_path.exists():
        v1_config = XStemConfig.from_yaml(v1_path)
        print("\n✓ v1 config loaded successfully!")
        print(f"Services: {list(v1_config.services.keys())}")
    else:
        print("\n⚠ v1 config file not found (this is OK for new installations)")

except Exception as e:
    print(f"\n✗ v1 config loading failed: {e}")

print("\n" + "=" * 60)
print("Configuration Test Complete")
print("=" * 60)
