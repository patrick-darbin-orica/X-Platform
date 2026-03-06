"""Shared camera frame cache for inter-process communication between
detection scripts and Flask GUI.

Uses file-based shared memory to pass the latest camera frame
from the vision system to the web interface.
"""

import numpy as np
import cv2
import threading
from pathlib import Path
from typing import Optional

# Shared frame file location
FRAME_FILE = Path("/tmp/amiga_camera_frame.jpg")
_frame_lock = threading.Lock()


def set_latest_frame(frame: np.ndarray) -> None:
    """Set the latest camera frame by writing to shared file (thread-safe).

    Args:
        frame: OpenCV BGR image (numpy array)
    """
    if frame is None:
        return

    with _frame_lock:
        try:
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            temp_file = FRAME_FILE.with_suffix('.tmp')
            with open(temp_file, 'wb') as f:
                f.write(buffer.tobytes())
            temp_file.replace(FRAME_FILE)
        except Exception:
            pass


def get_latest_frame() -> Optional[np.ndarray]:
    """Get the latest camera frame (thread-safe).

    Returns:
        OpenCV BGR image (numpy array) or None
    """
    with _frame_lock:
        try:
            if not FRAME_FILE.exists():
                return None
            with open(FRAME_FILE, 'rb') as f:
                buffer = f.read()
            return cv2.imdecode(np.frombuffer(buffer, dtype=np.uint8), cv2.IMREAD_COLOR)
        except Exception:
            return None


def get_latest_frame_bytes() -> Optional[bytes]:
    """Get the latest camera frame as JPEG bytes (optimized for Flask streaming).

    Returns:
        JPEG bytes or None
    """
    try:
        if not FRAME_FILE.exists():
            return None
        with open(FRAME_FILE, 'rb') as f:
            return f.read()
    except Exception:
        return None
