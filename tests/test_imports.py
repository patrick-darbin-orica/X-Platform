#!/usr/bin/env python3
"""Test script to verify all imports work after directory restructuring."""

print("=" * 60)
print("Testing Phase 2: Import Verification")
print("=" * 60)

errors = []

# Test platform imports
print("\n[1/5] Testing platform.core imports...")
try:
    from amiga_platform.core.config import XStemConfig
    from amiga_platform.core.service_manager import ServiceManager
    from amiga_platform.core.state_machine import NavigationStateMachine, NavState
    print("  ✓ platform.core imports successful")
except ImportError as e:
    errors.append(f"platform.core: {e}")
    print(f"  ✗ platform.core import failed: {e}")

print("\n[2/5] Testing platform.navigation imports...")
try:
    from amiga_platform.navigation.path_planner import PathPlanner
    from amiga_platform.navigation.navigation_manager import NavigationManager
    from amiga_platform.navigation.coordinate_transforms import CoordinateTransforms
    print("  ✓ platform.navigation imports successful")
except ImportError as e:
    errors.append(f"platform.navigation: {e}")
    print(f"  ✗ platform.navigation import failed: {e}")

print("\n[3/5] Testing platform.vision imports...")
try:
    from amiga_platform.vision.vision_system import VisionSystem
    print("  ✓ platform.vision imports successful")
except ImportError as e:
    errors.append(f"platform.vision: {e}")
    print(f"  ✗ platform.vision import failed: {e}")

print("\n[4/5] Testing platform.hardware imports...")
try:
    from amiga_platform.hardware.actuator import CanHBridgeActuator, NullActuator
    from amiga_platform.hardware.filter_utils import check_filter_convergence
    print("  ✓ platform.hardware imports successful")
except ImportError as e:
    errors.append(f"platform.hardware: {e}")
    print(f"  ✗ platform.hardware import failed: {e}")

print("\n[5/5] Testing modules imports...")
try:
    from modules.tool_manager import ToolManager, ToolModule
    from modules.xstem.module import StemmingModule
    print("  ✓ modules imports successful")
except ImportError as e:
    errors.append(f"modules: {e}")
    print(f"  ✗ modules import failed: {e}")

# Summary
print("\n" + "=" * 60)
if len(errors) == 0:
    print("✓ All imports successful! Phase 2 restructuring verified.")
    print("=" * 60)
    exit(0)
else:
    print(f"✗ {len(errors)} import error(s) found:")
    for error in errors:
        print(f"  - {error}")
    print("=" * 60)
    exit(1)
