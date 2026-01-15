# Configuration System Documentation

## Overview

The X-Platform uses a **multi-tier configuration system** that separates concerns:

1. **Platform Configuration** (`platform_config.yaml`) - Stable platform settings
2. **Mission Configuration** (`mission_config.yaml`) - Per-mission settings and module selection
3. **Module Configuration** (`modules/<module_name>/config.yaml`) - Module-specific parameters

## Configuration Files

### 1. Platform Configuration (`platform_config.yaml`)

Contains platform-level settings that rarely change:

- **Services**: EventService endpoints (filter, track_follower, canbus, cameras)
- **Filter**: Convergence settings and IMU wiggle parameters
- **Navigation**: Search zone, track generation, accuracy thresholds, error recovery
- **Vision**: Detection parameters, camera mounting positions
- **CAN**: CAN bus communication settings

**When to edit**: When changing hardware configuration, service ports, or platform behavior

### 2. Mission Configuration (`mission_config.yaml`)

Contains mission-specific settings:

- **mission_name**: Descriptive name for the mission
- **module_name**: Which module to load (`"xstem"`, `"xprime"`, `"none"`)
- **blast_pattern**: CSV path, coordinate system, echelon configuration

**When to edit**: When starting a new mission or changing fields

### 3. Module Configuration (`modules/<module_name>/config.yaml`)

Contains module-specific parameters:

**For XStem module** (`modules/xstem/config.yaml`):
- Tool offsets (dipbob, chute positions)
- Dipbob deployment settings (CAN ID, timing)
- Chute actuation settings (actuator ID, pulse timing)
- Alignment tolerances

**When to edit**: When calibrating tools or adjusting module behavior

## Usage

### Using v2 Multi-Tier Configs (Recommended)

```python
from core.config import XStemConfig
from pathlib import Path

config = XStemConfig.from_multi_tier(
    platform_config_path=Path("config/platform_config.yaml"),
    mission_config_path=Path("config/mission_config.yaml"),
    # module_config_path is auto-discovered from mission.module_name
)
```

### Using v1 Legacy Config (Backward Compatible)

```python
from core.config import XStemConfig
from pathlib import Path

config = XStemConfig.from_yaml(Path("config/navigation_config.yaml"))
```

## Examples

Example configurations are provided in `config/examples/`:

- **navigation_only.yaml**: Navigation testing without module deployment

To use an example:

```bash
cp config/examples/navigation_only.yaml config/mission_config.yaml
```

## Configuration Values

### Hardcoded Values Eliminated

All previously hardcoded values have been moved to configuration files:

**From main.py:**
- Filter convergence wait times → `filter.convergence_check_timeout_s`
- IMU wiggle duration → `filter.imu_wiggle_duration_s`
- Max retries → `navigation.max_retries`

**From navigation/path_planner.py:**
- Segment spacing (0.5m) → `navigation.segment_spacing_m`
- Turn spacing (0.15m) → `navigation.turn_spacing_m`
- Approach offset (1.2m) → `navigation.search_zone_approach_offset_m`

**From navigation/navigation_manager.py:**
- Track execution timeout (60s) → `navigation.execution_timeout_s`
- Track load wait (1s) → `navigation.track_load_wait_s`

**From vision/vision_system.py:**
- Detection averaging (3 samples) → `vision.averaging_samples`
- FOV width (0.5m) → `vision.fov_width_m`

**From hardware/filter_utils.py:**
- CAN command rate (20Hz) → `can.command_rate_hz`
- IMU wiggle angular velocity → `filter.imu_wiggle_angular_velocity_rad_s`

**From modules/xstem:**
- Dipbob CAN ID → `modules/xstem/config.yaml: dipbob.can_arbitration_id`
- Tool offsets → `modules/xstem/config.yaml: tool_offset.*`
- Chute timing → `modules/xstem/config.yaml: chute.*`

## Validation

To validate configuration files:

```bash
python3 test_yaml_configs.py
```

This checks:
- YAML syntax validity
- File structure
- Required keys present

## Migration from v1

The old `navigation_config.yaml` format is still supported for backward compatibility.

To migrate to v2:

1. Platform settings → `config/platform_config.yaml`
2. Mission/waypoint settings → `config/mission_config.yaml`
3. Tool-specific settings → `modules/xstem/config.yaml`

The `XStemConfig.from_multi_tier()` method automatically converts v2 configs to v1 format internally, ensuring compatibility with existing code.

## Best Practices

1. **Platform config**: Version control this, changes require team review
2. **Mission config**: Create per-field configs, easy to swap
3. **Module config**: Version with module code, calibrate per robot/tool

## Troubleshooting

**Config loading fails:**
- Check YAML syntax with `python3 test_yaml_configs.py`
- Verify file paths are correct
- Check for required keys

**Values not taking effect:**
- Ensure you're loading the correct config file
- Check config precedence (v2 multi-tier vs v1 single file)
- Verify the value is being read in code

**Module config not found:**
- Check `mission_config.yaml` has correct `module_name`
- Verify `modules/<module_name>/config.yaml` exists
- Check module directory structure
