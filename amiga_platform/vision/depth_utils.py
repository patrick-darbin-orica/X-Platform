"""Depth processing utilities for stereo vision."""
from __future__ import annotations

import numpy as np


def get_depth_at_point(
    disparity: np.ndarray,
    x_norm: float,
    y_norm: float,
    roi_size: int = 5,
) -> float:
    """Get median depth in ROI around point.

    Args:
        disparity: Disparity map
        x_norm: Normalized x coordinate (0-1)
        y_norm: Normalized y coordinate (0-1)
        roi_size: Size of ROI window in pixels

    Returns:
        Median depth value in millimeters, or 0.0 if no valid depths
    """
    h, w = disparity.shape
    cx = int(x_norm * w)
    cy = int(y_norm * h)

    # Extract ROI
    half = roi_size // 2
    roi = disparity[
        max(0, cy - half) : min(h, cy + half + 1),
        max(0, cx - half) : min(w, cx + half + 1),
    ]

    # Median filtering (robust to outliers)
    valid = roi[roi > 0]
    if len(valid) == 0:
        return 0.0

    return float(np.median(valid))


def disparity_to_depth(
    disparity: np.ndarray,
    baseline_m: float = 0.075,
    focal_px: float = 800.0,
) -> np.ndarray:
    """Convert disparity to depth using stereo geometry.

    Args:
        disparity: Disparity map in pixels
        baseline_m: Stereo baseline in meters (default 0.075m for OAK-D)
        focal_px: Focal length in pixels (default 800)

    Returns:
        Depth map in meters
    """
    # Avoid division by zero
    depth = np.zeros_like(disparity, dtype=float)
    valid = disparity > 0
    depth[valid] = (baseline_m * focal_px) / disparity[valid]
    return depth
