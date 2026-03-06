#!/usr/bin/env python3
"""Standalone collar detection script using depthai v3 + host-side YOLO.

Connects to an OAK-D camera via IP (PoE), runs YOLO inference on the host
to detect collars, calculates 3D robot-frame coordinates from stereo depth,
and relays results via UDP to the main navigation process.

Usage:
    python vision/detector.py --config config/navigation_config.yaml

Config is read from the ``vision.forward_camera`` section of
``navigation_config.yaml``.  The camera IP, model path, and extrinsic
offsets are all pulled from there.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import signal
import socket
import sys
import time
from pathlib import Path
from typing import List, Optional

import depthai as dai
import numpy as np
from farm_ng_core_pybind import Isometry3F64, Pose3F64, Rotation3F64

# Add repo root to path for utils imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.camera_frame_cache import set_latest_frame

# YOLO model — prefer YOLOE (works for standard YOLO models too in
# ultralytics >= 8.3), fall back to YOLO if YOLOE is unavailable.
try:
    from ultralytics import YOLOE as _YOLO
except ImportError:
    from ultralytics import YOLO as _YOLO

# On Jetson, torchvision C++ ops (including NMS) are broken due to ABI
# mismatch with NVIDIA's PyTorch build.  Ultralytics has a pure-torch
# TorchNMS fallback but only uses it when torchvision is not in sys.modules.
# Since importing ultralytics pulls in torchvision, we force-remove it so
# the NMS code path falls through to TorchNMS.
import sys as _sys
_sys.modules.pop("torchvision", None)
_sys.modules.pop("torchvision.ops", None)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
IMG_SIZE = 640
FPS = 15
YOLO_PROCESS_EVERY_N_FRAMES = 5
DEPTH_LOWER_MM = 100
DEPTH_UPPER_MM = 5000

RELAY_ADDR = ("127.0.0.1", 41234)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("detector")


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config(config_path: Path) -> dict:
    """Load the vision.forward_camera section from navigation_config.yaml.

    Returns a dict with keys: ip_address, model_path, offset_x/y/z, pitch_deg,
    plus top-level vision keys (min_confidence, etc.).
    """
    import yaml

    with open(config_path) as f:
        data = yaml.safe_load(f)

    vision = data.get("vision", {})
    cam = vision.get("forward_camera", {})

    return {
        # Camera connection
        "ip_address": cam.get("ip_address"),
        # Model
        "model_path": Path(cam.get("model_path", "")).expanduser(),
        # Extrinsics
        "offset_x": float(cam.get("offset_x", 0.0)),
        "offset_y": float(cam.get("offset_y", 0.0)),
        "offset_z": float(cam.get("offset_z", 0.0)),
        "pitch_deg": float(cam.get("pitch_deg", 0.0)),
        # Detection thresholds
        "min_confidence": float(vision.get("min_confidence", 0.5)),
    }


# ---------------------------------------------------------------------------
# CollarDetector — host-side YOLO wrapper
# ---------------------------------------------------------------------------

class CollarDetector:
    """YOLO detector that filters to class 0 (Collar) only."""

    def __init__(self, model_path: Path, conf: float = 0.5, iou: float = 0.5):
        self.model = _YOLO(str(model_path))
        self.conf = conf
        self.iou = iou
        self.class_names = self.model.names
        logger.info("Loaded YOLO model: %s (%d classes)", model_path, len(self.class_names))

    def detect(self, frame: np.ndarray) -> List[dict]:
        """Run detection, return list of collar detections (normalised coords)."""
        results = self.model.predict(frame, conf=self.conf, iou=self.iou, verbose=False)
        detections = []
        h, w = frame.shape[:2]

        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                if cls_id != 0:
                    continue  # Only class 0 (Collar)

                xyxy = box.xyxy[0].cpu().numpy()
                xmin, ymin, xmax, ymax = xyxy
                label_name = self.class_names.get(cls_id, f"class_{cls_id}")

                detections.append({
                    "label_id": cls_id,
                    "label_name": label_name,
                    "confidence": float(box.conf[0]),
                    "xmin": xmin / w,
                    "ymin": ymin / h,
                    "xmax": xmax / w,
                    "ymax": ymax / h,
                })

        return detections


# ---------------------------------------------------------------------------
# CameraTransforms — camera frame → robot (NWU) frame
# ---------------------------------------------------------------------------

class CameraTransforms:
    """Transform detections from DepthAI camera frame to robot NWU frame.

    DepthAI camera frame: +X right, +Y down, +Z forward
    Robot NWU frame:      +X forward, +Y left, +Z up
    """

    def __init__(self, offset_x: float, offset_y: float, offset_z: float,
                 pitch_deg: float):
        # Fixed axis alignment (DepthAI cam → NWU robot):
        #   Xr ← Zc,  Yr ← -Xc,  Zr ← -Yc
        # This equals Rx(-90°) * Ry(+90°).
        R_align = Rotation3F64.Rx(math.radians(-90.0)) * Rotation3F64.Ry(math.radians(90.0))

        # Camera tilt: positive pitch_deg means camera pitched DOWN.
        # In camera frame, down-tilt is Rx(-pitch).
        R_tilt = Rotation3F64.Rx(math.radians(-pitch_deg))

        R_cam_to_robot = R_align * R_tilt

        self.robot_from_camera = Pose3F64(
            a_from_b=Isometry3F64([offset_x, offset_y, offset_z], R_cam_to_robot),
            frame_a="robot",
            frame_b="camera",
        )

    def robot_pose_from_cam_point(self, p_cam_m: np.ndarray) -> Pose3F64:
        """Transform a 3D camera-frame point to a pose in the robot frame."""
        camera_from_object = Pose3F64(
            a_from_b=Isometry3F64(p_cam_m.tolist(), Rotation3F64()),
            frame_a="camera",
            frame_b="object",
        )
        return self.robot_from_camera * camera_from_object


# ---------------------------------------------------------------------------
# Depth + projection utilities
# ---------------------------------------------------------------------------

def get_depth_at_point(depth_frame: np.ndarray, x_norm: float, y_norm: float,
                       radius: int = 3) -> Optional[float]:
    """Median depth (mm) in a small ROI around normalised coords."""
    h, w = depth_frame.shape
    cx = int(np.clip(x_norm * w, radius, w - radius - 1))
    cy = int(np.clip(y_norm * h, radius, h - radius - 1))

    roi = depth_frame[cy - radius:cy + radius + 1, cx - radius:cx + radius + 1]
    valid = roi[roi > 0]
    if len(valid) == 0:
        return None
    return float(np.median(valid))


def pixel_to_camera_3d(x_norm: float, y_norm: float, depth_mm: float,
                       img_w: int, img_h: int, intrinsics: dict) -> np.ndarray:
    """Unproject normalised pixel + depth to 3D camera coordinates (metres).

    Camera frame: +X right, +Y down, +Z forward.
    """
    u = x_norm * img_w
    v = y_norm * img_h
    z = depth_mm / 1000.0
    x = (u - intrinsics["cx"]) * z / intrinsics["fx"]
    y = (v - intrinsics["cy"]) * z / intrinsics["fy"]
    return np.array([x, y, z], dtype=float)


def add_spatial_to_detections(detections: List[dict],
                              depth_frame: np.ndarray,
                              img_w: int, img_h: int,
                              intrinsics: dict) -> List[dict]:
    """Attach 3D camera-frame coordinates to each detection using stereo depth.

    Depth is sampled at the top 20 % of the bounding box (more consistent for
    tall pipes / collars).
    """
    spatial = []
    for det in detections:
        x_center = (det["xmin"] + det["xmax"]) / 2.0
        bbox_height = det["ymax"] - det["ymin"]
        y_measure = det["ymin"] + 0.2 * bbox_height  # top 20 %

        depth_mm = get_depth_at_point(depth_frame, x_center, y_measure)
        if depth_mm is None or depth_mm < DEPTH_LOWER_MM or depth_mm > DEPTH_UPPER_MM:
            continue

        coords = pixel_to_camera_3d(x_center, y_measure, depth_mm,
                                    img_w, img_h, intrinsics)
        det_copy = dict(det)
        det_copy["cam_xyz_m"] = coords
        spatial.append(det_copy)

    return spatial


# ---------------------------------------------------------------------------
# DetectionAverager — rolling confidence-weighted average
# ---------------------------------------------------------------------------

class DetectionAverager:
    """Rolling average filter for detection positions to reduce noise."""

    def __init__(self, window_size: int = 5, max_age_s: float = 1.0):
        self.window_size = window_size
        self.max_age_s = max_age_s
        self.detections: list[tuple[float, float, float, float]] = []

    def add(self, x_fwd: float, y_left: float, conf: float) -> None:
        now = time.time()
        self.detections.append((x_fwd, y_left, conf, now))
        # Prune old / excess entries
        self.detections = [
            d for d in self.detections if (now - d[3]) < self.max_age_s
        ]
        if len(self.detections) > self.window_size:
            self.detections = self.detections[-self.window_size:]

    def get_average(self) -> Optional[tuple[float, float, float]]:
        """Return (x_fwd, y_left, avg_conf) or None if < 3 samples."""
        if len(self.detections) < 3:
            return None

        now = time.time()
        total_w = 0.0
        wx = wy = 0.0
        for x, y, conf, ts in self.detections:
            w = conf * math.exp(-(now - ts) / 0.5)
            total_w += w
            wx += x * w
            wy += y * w

        if total_w < 0.01:
            return None

        avg_conf = sum(d[2] for d in self.detections) / len(self.detections)
        return wx / total_w, wy / total_w, avg_conf

    def clear(self) -> None:
        self.detections.clear()


# ---------------------------------------------------------------------------
# depthai v3 pipeline
# ---------------------------------------------------------------------------

def build_pipeline(device: dai.Device) -> tuple:
    """Create an OAK-D pipeline: RGB + stereo depth.

    Returns (pipeline, qRgb, qDepth).
    """
    pipeline = dai.Pipeline(device)

    # Camera nodes (v3 unified Camera node)
    camRgb = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    monoL = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    monoR = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)

    # Stereo depth
    stereo = pipeline.create(dai.node.StereoDepth)
    stereo.setExtendedDisparity(True)
    stereo.setDepthAlign(dai.CameraBoardSocket.CAM_A)
    if pipeline.getDefaultDevice().getPlatform() == dai.Platform.RVC2:
        stereo.setOutputSize(640, 400)

    monoL.requestOutput((640, 400)).link(stereo.left)
    monoR.requestOutput((640, 400)).link(stereo.right)

    # Output queues (v3 style)
    xoutRgb = camRgb.requestOutput((IMG_SIZE, IMG_SIZE))
    xoutDepth = stereo.depth

    qRgb = xoutRgb.createOutputQueue(maxSize=1, blocking=False)
    qDepth = xoutDepth.createOutputQueue(maxSize=1, blocking=False)

    return pipeline, qRgb, qDepth


def drain_latest(q):
    """Drain a depthai output queue and return only the most recent message."""
    last = None
    while q.has():
        last = q.get()
    return last


# ---------------------------------------------------------------------------
# UDP relay
# ---------------------------------------------------------------------------

class UDPRelay:
    """Send detection messages to the navigation process via UDP."""

    def __init__(self, addr: tuple[str, int] = RELAY_ADDR, min_period: float = 0.8):
        self.addr = addr
        self.min_period = min_period
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._last_send_time = 0.0

    def send(self, x_fwd: float, y_left: float, confidence: float,
             class_name: str = "collar", class_id: int = 0) -> None:
        now = time.time()
        if (now - self._last_send_time) < self.min_period:
            return

        msg = {
            "class_name": class_name,
            "class_id": class_id,
            "x_fwd_m": float(x_fwd),
            "y_left_m": float(y_left),
            "confidence": float(confidence),
            "stamp": now,
        }
        try:
            self._sock.sendto(json.dumps(msg).encode("utf-8"), self.addr)
            self._last_send_time = now
            logger.debug("UDP → %s  x=%.2f y=%.2f conf=%.2f", self.addr, x_fwd, y_left, confidence)
        except Exception as e:
            logger.warning("UDP send failed: %s", e)


# ---------------------------------------------------------------------------
# Main detection loop
# ---------------------------------------------------------------------------

def run_detection_loop(
    config: dict,
    pipeline: dai.Pipeline,
    qRgb,
    qDepth,
    detector: CollarDetector,
    xfm: CameraTransforms,
    intrinsics: dict,
) -> None:
    """Core detection loop — runs until pipeline stops or SIGINT."""

    relay = UDPRelay()
    averager = DetectionAverager(window_size=5, max_age_s=1.0)

    latest_rgb = None
    latest_depth = None
    img_w = img_h = None

    frame_count = 0
    fps_start = time.time()
    min_interval = 1.0 / FPS
    last_process = time.time()

    detections: List[dict] = []

    while pipeline.isRunning() and not _shutdown:
        now = time.time()
        if (now - last_process) < min_interval:
            time.sleep(0.001)
            continue
        last_process = now

        # Drain queues (always keep latest, discard stale frames)
        depth_msg = drain_latest(qDepth)
        if depth_msg is not None:
            latest_depth = depth_msg.getFrame()

        rgb_msg = drain_latest(qRgb)
        if rgb_msg is not None:
            latest_rgb = rgb_msg.getCvFrame()
            if img_w is None:
                img_h, img_w = latest_rgb.shape[:2]
            frame_count += 1
            # Write frame to cache for Flask GUI
            set_latest_frame(latest_rgb)

        if latest_rgb is None or latest_depth is None:
            continue

        # Frame-skip: only run YOLO every Nth frame
        if (frame_count % YOLO_PROCESS_EVERY_N_FRAMES) == 0:
            detections = detector.detect(latest_rgb)

        # Attach spatial (3D) coordinates from depth
        spatial = add_spatial_to_detections(
            detections, latest_depth, img_w, img_h, intrinsics,
        )

        # Find closest detection, transform to robot frame, relay
        closest = None
        closest_dist = float("inf")

        for det in spatial:
            p_cam = det["cam_xyz_m"]
            robot_pose = xfm.robot_pose_from_cam_point(p_cam)
            v_r = np.array(robot_pose.a_from_b.translation)
            x_fwd, y_left = float(v_r[0]), float(v_r[1])
            dist = math.hypot(x_fwd, y_left)

            if dist < closest_dist:
                closest_dist = dist
                closest = (x_fwd, y_left, det["confidence"], det["label_name"])

        if closest is not None:
            x_fwd, y_left, conf, label = closest
            averager.add(x_fwd, y_left, conf)

            avg = averager.get_average()
            if avg is not None:
                relay.send(avg[0], avg[1], avg[2], class_name=label)

        # Periodic FPS log
        if frame_count % 30 == 0 and frame_count > 0:
            elapsed = time.time() - fps_start
            fps = 30.0 / elapsed if elapsed > 0 else 0
            logger.info(
                "FPS: %.1f | Detections: %d | Spatial: %d",
                fps, len(detections), len(spatial),
            )
            fps_start = time.time()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_shutdown = False


def _sighandler(signum, _frame):
    global _shutdown
    logger.info("Received signal %d — shutting down", signum)
    _shutdown = True


def main() -> None:
    global _shutdown

    parser = argparse.ArgumentParser(description="Standalone collar detector (depthai v3)")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / "Amiga" / "X-Platform" / "config" / "navigation_config.yaml",
        help="Path to navigation_config.yaml",
    )
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)
    logger.info("Config loaded from %s", args.config)

    # Validate model exists
    model_path = config["model_path"]
    if not model_path.exists():
        logger.error("Model not found: %s", model_path)
        sys.exit(1)

    # Signal handlers
    signal.signal(signal.SIGINT, _sighandler)
    signal.signal(signal.SIGTERM, _sighandler)

    # Connect to camera via IP
    ip = config["ip_address"]
    if ip:
        logger.info("Connecting to OAK camera at %s ...", ip)
        device_info = dai.DeviceInfo(ip)
        device = dai.Device(device_info)
    else:
        logger.info("No IP configured — using auto-detected camera")
        device = dai.Device()

    # Read calibration intrinsics
    calib = device.readCalibration()
    intr_matrix = calib.getCameraIntrinsics(dai.CameraBoardSocket.CAM_A, IMG_SIZE, IMG_SIZE)
    intrinsics = {
        "fx": intr_matrix[0][0],
        "fy": intr_matrix[1][1],
        "cx": intr_matrix[0][2],
        "cy": intr_matrix[1][2],
    }
    logger.info("Intrinsics: fx=%.1f fy=%.1f cx=%.1f cy=%.1f",
                intrinsics["fx"], intrinsics["fy"], intrinsics["cx"], intrinsics["cy"])

    # Build pipeline
    pipeline, qRgb, qDepth = build_pipeline(device)

    # Host-side YOLO detector
    detector = CollarDetector(model_path, conf=config["min_confidence"])

    # Camera-to-robot transforms
    xfm = CameraTransforms(
        offset_x=config["offset_x"],
        offset_y=config["offset_y"],
        offset_z=config["offset_z"],
        pitch_deg=config["pitch_deg"],
    )

    # Run
    logger.info("Starting detection loop ...")
    pipeline.start()
    try:
        with pipeline:
            run_detection_loop(config, pipeline, qRgb, qDepth,
                               detector, xfm, intrinsics)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        logger.info("Detector exited cleanly")


if __name__ == "__main__":
    main()
