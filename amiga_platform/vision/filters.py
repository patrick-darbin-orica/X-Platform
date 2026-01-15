"""Detection filtering and averaging for stable measurements."""
from __future__ import annotations

import time
from collections import deque

import numpy as np


class DetectionAverager:
    """Running average of detections with exponential decay."""

    def __init__(
        self,
        window_size: int = 10,
        decay_alpha: float = 0.9,
        min_confidence: float = 0.7,
    ) -> None:
        """Initialize detection averager.

        Args:
            window_size: Maximum number of detections to keep
            decay_alpha: Exponential decay factor for older detections
            min_confidence: Minimum confidence threshold to accept detection
        """
        self.window_size = window_size
        self.decay_alpha = decay_alpha
        self.min_confidence = min_confidence

        self.buffer: deque[tuple[float, float, float, float]] = deque(
            maxlen=window_size
        )

    def add(self, x: float, y: float, confidence: float, timestamp: float) -> None:
        """Add detection to buffer.

        Args:
            x: X coordinate
            y: Y coordinate
            confidence: Detection confidence (0-1)
            timestamp: Detection timestamp
        """
        if confidence >= self.min_confidence:
            self.buffer.append((x, y, confidence, timestamp))

    def get_average(self) -> tuple[float, float, float] | None:
        """Get weighted average position.

        Returns:
            Tuple of (x, y, confidence) or None if insufficient detections
        """
        if len(self.buffer) < 2:
            return None

        now = time.time()
        weights = []
        positions = []

        for x, y, conf, ts in self.buffer:
            # Exponential decay by age
            age = now - ts
            weight = conf * (self.decay_alpha**age)
            weights.append(weight)
            positions.append([x, y])

        weights_array = np.array(weights)
        positions_array = np.array(positions)

        # Weighted average
        total_weight = weights_array.sum()
        if total_weight == 0:
            return None

        avg_pos = (positions_array * weights_array[:, None]).sum(axis=0) / total_weight
        avg_conf = weights_array.mean()

        return (float(avg_pos[0]), float(avg_pos[1]), float(avg_conf))

    def clear(self) -> None:
        """Clear buffer."""
        self.buffer.clear()
