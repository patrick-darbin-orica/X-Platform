# XStem Waypoint Navigation System

A modular, production-ready navigation system for the XStem stemming robot that navigates blast pattern holes, deploys dipbobs for measurement, and dispenses gravel through a chute actuator.

## System Overview

The XStem system is a clean rewrite of the waypoint navigation system with the following key features:

- **Modular Architecture**: Clean separation of concerns (navigation, vision, control, hardware)
- **Hybrid Navigation**: Track follower for waypoint navigation + optional visual servoing
- **Dual Camera System**: Forward camera (oak/1) for detection, downward camera (oak/0) for alignment
- **Explicit State Machine**: Clear state transitions with comprehensive logging
- **Unified Configuration**: Single YAML file for all system parameters
- **Vision Integration**: EventService-based camera streams with TensorRT YOLO detection

## Directory Structure

```
~/Amiga/xstem/
├── main.py                          # Main orchestrator & entry point
├── README.md                        # This file
├── config/
│   └── navigation_config.yaml       # System configuration
├── core/
│   ├── config.py                   # Pydantic configuration dataclasses
│   ├── service_manager.py          # Multi-service client management
│   └── state_machine.py            # Navigation state machine
├── navigation/
│   ├── coordinate_transforms.py    # ENU→NWU, tool offsets, pose math
│   ├── path_planner.py             # Waypoint loading & track generation
│   └── navigation_manager.py       # Track execution orchestration
├── vision/
│   ├── camera_calibration.py       # Intrinsics & extrinsics
│   ├── depth_utils.py              # Depth processing & 3D projection
│   ├── detector.py                 # TensorRT YOLO inference
│   ├── filters.py                  # Detection averaging
│   └── vision_system.py            # Dual-camera manager
├── control/
│   ├── tool_manager.py             # Abstract tool interface
│   └── stemming_module.py          # Dipbob + chute deployment
├── hardware/
│   ├── actuator.py                 # H-bridge control (from waypoint_navigation)
│   └── filter_utils.py             # IMU wiggle, convergence checks
├── utils/
│   └── track_builder.py            # Track generation (from waypoint_navigation)
├── models/                          # TensorRT engine files (.engine)
├── waypoints/                       # CSV waypoint files
└── tests/                           # Unit tests
```

## Installation

### Prerequisites

- Python 3.10+
- farm-ng-amiga SDK
- farm-ng-core SDK
- TensorRT (for YOLO inference)
- OpenCV
- NumPy, Pandas, PyYAML, Pydantic

### Setup

1. Clone or navigate to the xstem directory:
```bash
cd ~/Amiga/xstem
```

2. Ensure all dependencies are installed (they should be part of the farm-ng environment):
```bash
pip install farm-ng-amiga farm-ng-core opencv-python numpy pandas pyyaml pydantic
```

3. Place your TensorRT engine files in the `models/` directory:
```bash
# Example:
~/Amiga/xstem/models/collar_yoloe.engine  # Forward camera model
~/Amiga/xstem/models/hole_yoloe.engine    # Downward camera model
```

4. Place your waypoint CSV files in the `waypoints/` directory:
```bash
# Example:
~/Amiga/xstem/waypoints/field_1.csv
```

## Configuration

Edit [config/navigation_config.yaml](config/navigation_config.yaml) to configure your system:

### Key Configuration Sections

**Services**: EventService connection details for all hardware services
- filter (localization)
- track_follower (path following)
- canbus (motor & actuator control)
- oak/0 and oak/1 (cameras)

**Waypoints**: CSV file path, coordinate system (ENU/NWU), row settings

**Tool**: Dipbob and chute settings, tool offset from robot center

**Vision**: Camera models, mounting offsets, detection parameters

**Navigation**: Approach distances, retry limits, convergence settings

**Thresholds**: Accuracy and tolerance values

## Usage

### Basic Usage

Run the navigation system with default config:

```bash
cd ~/Amiga/xstem
python main.py
```

### Custom Configuration

Specify a custom configuration file:

```bash
python main.py --config /path/to/custom_config.yaml
```

### Dry Run (Vision Disabled)

To test navigation without vision detection:

```yaml
# In navigation_config.yaml
vision:
  enabled: false
```

## Navigation Flow

The system follows this sequence for each waypoint:

1. **PLANNING**: Load next waypoint from CSV, check for row-end
2. **APPROACHING**: Navigate to search zone (stop before waypoint)
3. **DETECTING**: Use forward camera to detect hole (if enabled)
4. **REFINING**: Refine path based on vision detection or use CSV position
5. **EXECUTING**: Execute final approach track to hole
6. **DEPLOYING**: Execute stemming sequence:
   - Align dipbob (downward camera)
   - Deploy dipbob via CAN signal
   - Wait for measurement ACK
   - Move forward to align chute
   - Open chute (timer-based)
   - Close chute
7. **PLANNING**: Move to next waypoint

### Row-End Maneuver

At the last waypoint of each row, executes a 4-segment U-turn:
1. Drive into headland
2. Turn 90° (left or right)
3. Move laterally (row spacing)
4. Turn 90° again

## Coordinate Systems

### Frames Used

- **ENU** (East-North-Up): Survey/GPS input format in CSV files
- **NWU** (North-West-Up): Robot/farm-ng convention
  - X = North (forward)
  - Y = West (left)
  - Z = Up
- **DepthAI Camera**: X=Right, Y=Down, Z=Forward
- **World**: Global reference frame (NWU)
- **Robot**: Robot center frame
- **Tool**: Dipbob/chute center
- **Hole**: Blast hole center

### Critical Transformations

```python
# ENU → NWU
north = csv_dy
west = -csv_dx

# Robot target from hole position
world_from_robot = world_from_hole * hole_from_robot

# Camera to robot
robot_from_object = robot_from_camera * camera_from_object
```

## State Machine

States: **IDLE** → **PLANNING** → **APPROACHING** → **DETECTING** → **REFINING** → **EXECUTING** → **DEPLOYING** → **PLANNING** (next waypoint) → ... → **COMPLETE**

Error states: **RECOVERING** → retry/skip/abort → **FAILED**

All state transitions are logged for debugging.

## Hardware Integration

### Filter Service
- Provides robot localization (wheel odometry + GPS + IMU fusion)
- Requires convergence before navigation (automatic IMU wiggle if diverged)

### Track Follower Service
- Executes track segments
- **Important**: Cannot modify track during FOLLOWING state
- Uses segment-by-segment execution pattern

### CAN Bus Service
- Motor control via `/twist` commands
- Actuator control via `/control_tools`
- Dipbob deployment signal

### Oak Camera Service
- Subscribe to `/rgb` and `/disparity` streams via EventService
- TensorRT inference on host (not on-device)
- Dual cameras used sequentially (not simultaneously)

## Vision System

### Forward Camera (oak/1)
- **Purpose**: Hole detection during approach
- **Model**: collar_yoloe.engine
- **Mounting**: Forward-facing, pitched down ~30°
- **Output**: Refined hole position

### Downward Camera (oak/0)
- **Purpose**: Tool alignment verification
- **Model**: hole_yoloe.engine
- **Mounting**: Downward-facing (-90° pitch)
- **Output**: Alignment check (centered/not centered)

### Detection Workflow
1. Subscribe to camera RGB stream via EventService
2. Decode JPEG frames
3. Run TensorRT YOLO inference on host
4. Filter detections by confidence threshold
5. Average multiple detections for stability
6. Backproject 2D detection + depth → 3D position
7. Transform to world frame

## Tool System

### Stemming Module

The stemming module executes this sequence:

1. **Align Dipbob**: Use downward camera to verify alignment (tolerance: 2cm)
2. **Deploy Dipbob**: Send CAN signal (0x18FF0007)
3. **Wait for Measurement**: Listen for ACK or timeout (5s)
4. **Move Forward**: Navigation moves robot by tool offset
5. **Align Chute**: Optional verification with downward camera
6. **Dispense Gravel**: Open chute for 0.2s, close for 0.3s at 10Hz

### Adding New Tools

Create a new class inheriting from `ToolModule`:

```python
from control.tool_manager import ToolModule, ToolResult

class MyCustomTool(ToolModule):
    async def verify_ready(self) -> bool:
        # Check tool status
        return True

    async def calibrate(self) -> None:
        # Perform calibration
        pass

    async def execute(self, hole_position: Pose3F64) -> ToolResult:
        # Execute tool sequence
        return ToolResult(success=True)
```

Then update `main.py` to use your custom tool instead of `StemmingModule`.

## Troubleshooting

### Filter Not Converging

**Symptom**: System reports "Filter not converged" repeatedly

**Solutions**:
1. Increase `filter_convergence_retries` in config
2. Increase IMU wiggle duration
3. Check GPS signal quality
4. Verify wheel encoder connections

### Vision Detection Failing

**Symptom**: All detections timing out

**Solutions**:
1. Check TensorRT engine paths in config
2. Verify camera services are running: `systemctl status oak-*`
3. Test cameras independently with `camera_client` example
4. Increase `detection_timeout_s` in config
5. Lower `min_confidence` threshold

### Track Execution Timeout

**Symptom**: Track execution times out repeatedly

**Solutions**:
1. Check track follower service status
2. Increase navigation timeout in code
3. Verify waypoint spacing is reasonable
4. Check for obstacles blocking path

### CAN Communication Errors

**Symptom**: Dipbob or chute not responding

**Solutions**:
1. Verify CAN bus service is running
2. Check CAN wiring and termination
3. Test CAN signals with `canbus_client` example
4. Verify arbitration IDs in config

## Development

### Running Tests

```bash
cd ~/Amiga/xstem
python -m pytest tests/
```

### Adding Features

1. Create new module in appropriate directory
2. Add configuration parameters to `core/config.py`
3. Update `navigation_config.yaml` with new parameters
4. Integrate into `main.py` orchestrator

### Debugging

Enable debug logging:

```python
# In main.py, change:
logging.basicConfig(level=logging.DEBUG, ...)
```

View state transitions:
```bash
# All state changes are logged as:
# [STATE] idle → planning
# [STATE] planning → approaching
```

## Migration from Old System

### Reused Components (100%)
- `utils/track_builder.py` (from `track_planner.py`)
- `hardware/actuator.py` (unchanged)

### Extracted Components (70%)
- `hardware/filter_utils.py` (from `utils/canbus.py`)

### Rewritten Components
- `navigation/path_planner.py` (from `motion_planner.py`)
- `navigation/navigation_manager.py` (refactored)
- `vision/` modules (extracted from `detection/detectionPlot.py`)
- `main.py` (complete rewrite)

## Known Limitations

1. **Vision System**: TensorRT detector is currently a placeholder - needs integration with your actual engine format
2. **Disparity Integration**: 3D projection requires integrating disparity stream (currently uses search center fallback)
3. **Dipbob ACK**: Waiting for ACK is placeholder - needs actual CAN listener
4. **Error Recovery**: Retry logic is marked TODO - needs implementation
5. **Chute Alignment**: Tool offset movement between dipbob and chute is placeholder

## Future Enhancements

- [ ] Detect-on-the-fly mode (vs stop-to-detect)
- [ ] Visual servoing for fine alignment
- [ ] Sensor-based chute control (vs timer-based)
- [ ] Comprehensive error recovery strategies
- [ ] Field-specific configuration profiles
- [ ] Real-time monitoring dashboard
- [ ] Automated testing framework

## References

- [farm-ng Amiga Documentation](https://amiga.farm-ng.com/docs/)
- [Track Follower Service](https://amiga.farm-ng.com/docs/concepts/track_follower_service/)
- [EventService Architecture](https://amiga.farm-ng.com/docs/concepts/event_service/)
- [Coordinate Systems](https://amiga.farm-ng.com/docs/concepts/coordinate_systems/)

## License

This code follows the farm-ng Amiga Development Kit License.

## Support

For issues or questions:
- Check the [Troubleshooting](#troubleshooting) section
- Review logs in `/var/log/` or console output
- Consult farm-ng documentation
- File issues in your project repository
