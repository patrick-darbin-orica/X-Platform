"""UDP listener for collar detections from the standalone detector process.

The standalone ``vision/detector.py`` sends JSON messages on UDP port 41234
containing robot-frame offsets (x_fwd_m, y_left_m).  This module runs an
asyncio UDP listener inside ``main.py`` so the navigation loop can poll for
the latest detection without blocking.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

RELAY_PORT = 41234


@dataclass
class CollarDetection:
    """A single collar detection in the robot frame."""

    x_fwd_m: float
    y_left_m: float
    confidence: float
    stamp: float


@dataclass
class DetectionRelay:
    """Asyncio UDP listener that stores the latest collar detection."""

    latest: Optional[CollarDetection] = field(default=None)
    _transport: Optional[asyncio.DatagramTransport] = field(
        default=None, repr=False,
    )

    async def start(self) -> None:
        """Bind the UDP listener on localhost."""
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: _RelayProtocol(self),
            local_addr=("127.0.0.1", RELAY_PORT),
        )
        logger.info("Detection relay listening on UDP %d", RELAY_PORT)

    def get_latest(self, max_age_s: float = 2.0) -> Optional[CollarDetection]:
        """Return the latest detection if it is younger than *max_age_s*."""
        if self.latest is None:
            return None
        if time.time() - self.latest.stamp > max_age_s:
            return None
        return self.latest

    def clear(self) -> None:
        """Discard stored detection."""
        self.latest = None

    async def stop(self) -> None:
        """Close the UDP socket."""
        if self._transport is not None:
            self._transport.close()
            self._transport = None
            logger.info("Detection relay stopped")


class _RelayProtocol(asyncio.DatagramProtocol):
    """Internal protocol that parses incoming JSON datagrams."""

    def __init__(self, relay: DetectionRelay) -> None:
        self._relay = relay

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        try:
            msg = json.loads(data.decode())
            self._relay.latest = CollarDetection(
                x_fwd_m=float(msg["x_fwd_m"]),
                y_left_m=float(msg["y_left_m"]),
                confidence=float(msg["confidence"]),
                stamp=float(msg["stamp"]),
            )
        except Exception as exc:
            logger.debug("Bad relay datagram from %s: %s", addr, exc)
