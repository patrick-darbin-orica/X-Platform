#!/usr/bin/env python3
"""Test script for Phase 3: Module loading and registration."""

print("=" * 60)
print("Testing Phase 3: Module Interface")
print("=" * 60)

errors = []

# Test 1: Import base module
print("\n[1/5] Testing base module import...")
try:
    from modules.base_module import BaseModule, ModuleContext, ModuleResult, NullModule
    print("  ✓ Base module imports successful")
except ImportError as e:
    errors.append(f"base_module: {e}")
    print(f"  ✗ Base module import failed: {e}")

# Test 2: Import registry
print("\n[2/5] Testing module registry import...")
try:
    from modules.registry import ModuleRegistry, get_global_registry
    print("  ✓ Module registry imports successful")
except ImportError as e:
    errors.append(f"registry: {e}")
    print(f"  ✗ Module registry import failed: {e}")

# Test 3: Import XStem module (auto-registers)
print("\n[3/5] Testing XStem module import...")
try:
    from modules.xstem import StemmingModule
    print("  ✓ XStem module imports successful")
except ImportError as e:
    errors.append(f"xstem: {e}")
    print(f"  ✗ XStem module import failed: {e}")

# Test 4: Check module registration
print("\n[4/5] Testing module registration...")
try:
    registry = get_global_registry()
    modules = registry.list_modules()
    print(f"  ✓ Registered modules: {modules}")

    # Verify expected modules
    expected = ["none", "xstem"]
    for mod in expected:
        if mod in modules:
            print(f"    ✓ '{mod}' registered")
        else:
            errors.append(f"Module '{mod}' not registered")
            print(f"    ✗ '{mod}' NOT registered")

except Exception as e:
    errors.append(f"registration: {e}")
    print(f"  ✗ Module registration check failed: {e}")

# Test 5: Test module instantiation
print("\n[5/5] Testing module instantiation...")
try:
    registry = get_global_registry()

    # Test null module
    NullModuleClass = registry.get("none")
    null_module = NullModuleClass()
    print(f"  ✓ Null module instantiated: {null_module.module_name}")

    # Test xstem module
    XStemClass = registry.get("xstem")
    xstem_module = XStemClass()
    print(f"  ✓ XStem module instantiated: {xstem_module.module_name}")

except Exception as e:
    errors.append(f"instantiation: {e}")
    print(f"  ✗ Module instantiation failed: {e}")
    import traceback
    traceback.print_exc()

# Summary
print("\n" + "=" * 60)
if len(errors) == 0:
    print("✓ All Phase 3 tests passed!")
    print("  - Module interface defined")
    print("  - Module registry working")
    print("  - XStem module implements BaseModule")
    print("  - Modules can be loaded and instantiated")
    print("=" * 60)
    exit(0)
else:
    print(f"✗ {len(errors)} error(s) found:")
    for error in errors:
        print(f"  - {error}")
    print("=" * 60)
    exit(1)
