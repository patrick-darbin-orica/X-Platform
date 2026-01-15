#!/usr/bin/env python3
"""Simple YAML validation test for new configuration files."""
from pathlib import Path
import yaml

def test_yaml_file(path: Path, name: str):
    """Test loading a YAML file."""
    print(f"\nTesting {name}:")
    print(f"  Path: {path}")

    if not path.exists():
        print(f"  ✗ File does not exist")
        return False

    try:
        with open(path) as f:
            data = yaml.safe_load(f)

        print(f"  ✓ YAML syntax valid")
        print(f"  ✓ Top-level keys: {list(data.keys())}")
        return True

    except Exception as e:
        print(f"  ✗ Failed to load: {e}")
        return False

print("=" * 60)
print("YAML Configuration File Validation")
print("=" * 60)

results = []

# Test all new config files
results.append(test_yaml_file(
    Path("config/platform_config.yaml"),
    "Platform Config"
))

results.append(test_yaml_file(
    Path("config/mission_config.yaml"),
    "Mission Config"
))

results.append(test_yaml_file(
    Path("modules/xstem/config.yaml"),
    "XStem Module Config"
))

results.append(test_yaml_file(
    Path("config/examples/navigation_only.yaml"),
    "Example: Navigation Only"
))

# Test old config for comparison
results.append(test_yaml_file(
    Path("config/navigation_config.yaml"),
    "Legacy v1 Config (for comparison)"
))

print("\n" + "=" * 60)
print(f"Results: {sum(results)}/{len(results)} files valid")
print("=" * 60)

if all(results[:4]):  # First 4 are critical
    print("\n✓ All required configuration files are valid!")
else:
    print("\n✗ Some configuration files have errors")
