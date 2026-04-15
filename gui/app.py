#!/usr/bin/env python3
"""Flask GUI for X-Platform Navigation System.

Provides web-based monitoring and control interface for the Amiga robot.
Accessible via Tailscale at http://<tailscale-ip>:5000
"""

import sys
import os
from pathlib import Path
from flask import Flask, render_template, Response, jsonify, request
from flask_socketio import SocketIO, emit
import json
import threading
import subprocess
import signal
import time
import asyncio
from typing import Optional

# Add repo root to path for utils imports
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from utils.pose_cache import get_latest_pose, set_latest_pose
from utils.navigation_state import get_navigation_state, get_waypoint_status
from utils.camera_frame_cache import get_latest_frame_bytes

# Import filter client dependencies
from farm_ng.core.event_client import EventClient
from farm_ng.core.event_service_pb2 import EventServiceConfig, EventServiceConfigList
from farm_ng.core.events_file_reader import proto_from_json_file
from farm_ng_core_pybind import Pose3F64

app = Flask(__name__)
app.config['SECRET_KEY'] = 'x-platform-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')


# Global state
class AppState:
    """Shared state for the GUI."""
    def __init__(self):
        self.navigation_process: Optional[subprocess.Popen] = None
        self.module_name: str = "none"

    def is_navigation_running(self) -> bool:
        if self.navigation_process is None:
            return False
        return self.navigation_process.poll() is None


state = AppState()

# Load module name from navigation config at startup
try:
    import yaml as _yaml
    _nav_cfg_path = REPO_ROOT / 'config' / 'navigation_config.yaml'
    with open(_nav_cfg_path) as _f:
        _nav_cfg = _yaml.safe_load(_f)
    state.module_name = _nav_cfg.get('module', 'none')
except Exception:
    pass


# ==================== Routes ====================

@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('dashboard.html')


@app.route('/video_feed')
def video_feed():
    """Stream camera feed 1 (OAK-2 via depthai)."""
    def generate():
        while True:
            frame_bytes = get_latest_frame_bytes()
            if frame_bytes is not None:
                try:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                except Exception as e:
                    print(f"Error streaming frame: {e}")
            time.sleep(1/15)

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/video_feed_2')
def video_feed_2():
    """Stream camera feed 2."""
    def generate():
        while True:
            # Camera feed 2 reads from oak2 cache file
            try:
                oak2_path = Path("/tmp/amiga_oak2_frame.jpg")
                if oak2_path.exists():
                    with open(oak2_path, 'rb') as f:
                        frame_bytes = f.read()
                    if frame_bytes:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            except Exception as e:
                print(f"Error streaming oak2 frame: {e}")
            time.sleep(1/10)

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/plot_data')
def plot_data():
    """Get waypoint plot data for D3.js visualization."""
    waypoint_data = load_waypoint_data()

    # Update waypoint statuses
    for wp in waypoint_data:
        wp['status'] = get_waypoint_status(wp['index'])

    # Get current robot pose
    robot_data = None
    pose = get_latest_pose()
    if pose is not None:
        robot_data = {
            'x': pose.x,
            'y': pose.y,
            'heading': pose.yaw
        }

    # Get navigation state
    nav_state = get_navigation_state()

    return jsonify({
        'waypoints': waypoint_data,
        'robot': robot_data,
        'current_index': nav_state['current_waypoint_index'],
        'total': nav_state['total_waypoints']
    })


@app.route('/robot_status')
def robot_status():
    """Get current robot status."""
    pose = get_latest_pose()
    nav_state = get_navigation_state()

    subprocess_running = state.is_navigation_running()

    if not subprocess_running and nav_state['navigation_running']:
        from utils.navigation_state import clear_navigation_state
        clear_navigation_state()
        nav_state = get_navigation_state()

    status = {
        'navigation_running': subprocess_running,
        'module': state.module_name,
        'track_status': nav_state['track_status'],
        'current_waypoint': nav_state['current_waypoint_index'],
        'total_waypoints': nav_state['total_waypoints'],
        'filter_converged': False,
        'vision_active': nav_state['vision_active'],
        'pose': None
    }

    if pose is not None:
        import math
        status['filter_converged'] = pose.converged
        status['pose'] = {
            'x': pose.x,
            'y': pose.y,
            'heading_deg': math.degrees(pose.yaw)
        }

    return jsonify(status)


@app.route('/camera_diagnostics')
def camera_diagnostics():
    """Get camera feed diagnostics."""
    diagnostics = {
        'camera_1': {
            'source': 'OAK-2 (depthai v3)',
            'cache_file': '/tmp/amiga_camera_frame.jpg',
            'status': 'active' if Path('/tmp/amiga_camera_frame.jpg').exists() else 'no_frames'
        },
        'camera_2': {
            'source': 'oak2 camera',
            'cache_file': '/tmp/amiga_oak2_frame.jpg',
            'status': 'active' if Path('/tmp/amiga_oak2_frame.jpg').exists() else 'no_frames'
        }
    }

    for key, cache_path in [('camera_1', '/tmp/amiga_camera_frame.jpg'),
                             ('camera_2', '/tmp/amiga_oak2_frame.jpg')]:
        p = Path(cache_path)
        if p.exists():
            age = time.time() - p.stat().st_mtime
            diagnostics[key]['frame_age_seconds'] = round(age, 2)
            if age > 2.0:
                diagnostics[key]['status'] = 'stale'

    return jsonify(diagnostics)


# ==================== Socket.IO Events ====================

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit('status', {'message': 'Connected to X-Platform GUI'})


@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")


@socketio.on('start_navigation')
def handle_start_navigation():
    """Start the navigation system by running main.py."""
    if state.is_navigation_running():
        emit('error', {'message': 'Navigation already running'})
        return

    try:
        venv_python = REPO_ROOT / 'venv' / 'bin' / 'python'
        main_script = REPO_ROOT / 'main.py'

        if not main_script.exists():
            emit('error', {'message': f'main.py not found at {main_script}'})
            return

        python_bin = str(venv_python) if venv_python.exists() else sys.executable

        state.navigation_process = subprocess.Popen(
            [python_bin, str(main_script)],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
            preexec_fn=os.setsid
        )

        def read_output():
            try:
                for line in iter(state.navigation_process.stdout.readline, ''):
                    if line:
                        socketio.emit('nav_log', {'message': line.rstrip()})
            except Exception as e:
                socketio.emit('nav_log', {'message': f'Error reading output: {e}'})

        output_thread = threading.Thread(target=read_output, daemon=True)
        output_thread.start()

        emit('success', {'message': 'Navigation started'})
        print(f"Started main.py (PID: {state.navigation_process.pid})")

    except Exception as e:
        emit('error', {'message': f'Failed to start navigation: {str(e)}'})


@socketio.on('stop_navigation')
def handle_stop_navigation():
    """Stop the navigation system."""
    if not state.is_navigation_running():
        emit('error', {'message': 'Navigation not running'})
        return

    try:
        os.killpg(os.getpgid(state.navigation_process.pid), signal.SIGTERM)
        state.navigation_process.wait(timeout=5)
        state.navigation_process = None

        from utils.navigation_state import clear_navigation_state
        clear_navigation_state()

        emit('success', {'message': 'Navigation stopped'})
        print("Navigation process stopped")

    except Exception as e:
        try:
            os.killpg(os.getpgid(state.navigation_process.pid), signal.SIGKILL)
            state.navigation_process = None
            from utils.navigation_state import clear_navigation_state
            clear_navigation_state()
            emit('warning', {'message': 'Navigation force killed'})
        except Exception:
            emit('error', {'message': f'Failed to stop navigation: {str(e)}'})


@socketio.on('emergency_stop')
def handle_emergency_stop():
    """Emergency stop."""
    if state.is_navigation_running():
        try:
            os.killpg(os.getpgid(state.navigation_process.pid), signal.SIGKILL)
            state.navigation_process = None
        except Exception:
            pass

    from utils.navigation_state import clear_navigation_state
    clear_navigation_state()

    emit('success', {'message': 'EMERGENCY STOP ACTIVATED'})
    print("EMERGENCY STOP")


@socketio.on('confirm_drx_ready')
def handle_confirm_drx_ready():
    """Operator confirms DRX is loaded in encoder tube — unblocks xprime module."""
    flag = Path('/tmp/xprime_drx_ready')
    flag.touch()
    emit('success', {'message': 'DRX confirmed — encoding started'})


# ==================== Helper Functions ====================

def load_waypoint_data():
    """Load waypoint data from CSV for plotting."""
    waypoints = []

    try:
        import yaml
        config_path = REPO_ROOT / 'config' / 'navigation_config.yaml'
        with open(config_path) as f:
            config = yaml.safe_load(f)

        csv_path = Path(config.get('waypoints', {}).get('csv_path', '')).expanduser()
        if not csv_path.exists():
            print(f"Waypoint file not found: {csv_path}")
            return waypoints

        import pandas as pd
        df = pd.read_csv(csv_path)

        for idx, row in df.iterrows():
            waypoints.append({
                'x': float(row.get('dx', 0)),
                'y': float(row.get('dy', 0)),
                'index': int(idx),
                'status': 'pending'
            })
    except Exception as e:
        print(f"Error loading waypoints: {e}")

    return waypoints


async def filter_pose_updater():
    """Subscribe to filter state and continuously update pose cache."""
    try:
        config_path = REPO_ROOT / 'config' / 'service_config.json'
        config_list = proto_from_json_file(config_path, EventServiceConfigList())

        filter_config = None
        for config in config_list.configs:
            if config.name == "filter":
                filter_config = config
                break

        if filter_config is None:
            print("Filter service not found in config, pose updates disabled")
            return

        from farm_ng.core.event_service_pb2 import SubscribeRequest
        from farm_ng.core.uri_pb2 import Uri

        subscription = SubscribeRequest(
            uri=Uri(path="/state", query="service_name=filter"),
            every_n=1
        )

        client = EventClient(filter_config)
        print(f"Subscribed to filter service at {filter_config.host}:{filter_config.port}")

        async for event, message in client.subscribe(subscription, decode=True):
            pose = Pose3F64.from_proto(message.pose)
            x = float(pose.a_from_b.translation[0])
            y = float(pose.a_from_b.translation[1])
            yaw = float(pose.a_from_b.rotation.log()[-1])
            converged = bool(getattr(message, "has_converged", False))
            set_latest_pose(x, y, yaw, converged)

    except Exception as e:
        print(f"Filter pose updater error: {e}")
        import traceback
        traceback.print_exc()


def background_status_updater():
    """Background thread to emit status updates to all clients."""
    while True:
        try:
            nav_state = get_navigation_state()

            subprocess_running = state.is_navigation_running()

            if not subprocess_running and nav_state['navigation_running']:
                from utils.navigation_state import clear_navigation_state
                clear_navigation_state()
                nav_state = get_navigation_state()

            status = {
                'navigation_running': subprocess_running,
                'module': state.module_name,
                'track_status': nav_state['track_status'],
                'current_waypoint': nav_state['current_waypoint_index'],
                'total_waypoints': nav_state['total_waypoints'],
                'filter_converged': False,
                'vision_active': nav_state['vision_active']
            }

            pose = get_latest_pose()
            if pose is not None:
                import math
                status['filter_converged'] = pose.converged
                status['pose'] = {
                    'x': pose.x,
                    'y': pose.y,
                    'heading_deg': math.degrees(pose.yaw)
                }

            status['xprime_waiting'] = Path('/tmp/xprime_waiting_for_operator').exists()
            socketio.emit('status_update', status)

        except Exception as e:
            print(f"Error in status updater: {e}")

        time.sleep(0.5)


# ==================== Main ====================

def run_async_filter_updater():
    """Run the async filter updater in its own event loop."""
    try:
        if sys.platform != 'win32':
            import selectors
            selector = selectors.SelectSelector()
            loop = asyncio.SelectorEventLoop(selector)
        else:
            loop = asyncio.new_event_loop()

        asyncio.set_event_loop(loop)
        loop.run_until_complete(filter_pose_updater())
    except Exception as e:
        print(f"Filter updater thread error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    # Start background filter pose updater
    filter_thread = threading.Thread(target=run_async_filter_updater, daemon=True)
    filter_thread.start()

    # Start background status updater
    status_thread = threading.Thread(target=background_status_updater, daemon=True)
    status_thread.start()

    # Get Tailscale IP for remote access
    try:
        tailscale_ip = subprocess.check_output(['tailscale', 'ip', '-4'], text=True).strip()
    except Exception:
        tailscale_ip = None

    print("\n" + "=" * 70)
    print("X-PLATFORM NAVIGATION - WEB GUI")
    print("=" * 70)
    print("Starting Flask server on http://0.0.0.0:5000")
    print("")
    print("Access URLs:")
    print("  Local:       http://localhost:5000")
    if tailscale_ip:
        print(f"  Tailscale:   http://{tailscale_ip}:5000")
    print("")
    print("Open in browser to monitor and control navigation")
    print("=" * 70 + "\n")

    # Run Flask with SocketIO — bind to 0.0.0.0 for Tailscale access
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
