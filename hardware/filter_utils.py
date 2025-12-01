"""Filter service utilities for convergence checking and IMU wiggle."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from farm_ng.canbus.canbus_pb2 import RawCanbusMessage, Twist2d
from farm_ng.filter.filter_pb2 import FilterState
from google.protobuf.empty_pb2 import Empty

if TYPE_CHECKING:
    from farm_ng.core.event_client import EventClient

logger = logging.getLogger(__name__)

# SocketCAN extended frame constants
CAN_EFF_FLAG = 0x80000000  # SocketCAN "extended frame" flag
CAN_EFF_MASK = 0x1FFFFFFF  # 29-bit ID mask


def eff_id(arb29: int) -> int:
    """Convert 29-bit arbitration ID to extended frame format.

    Args:
        arb29: 29-bit CAN ID

    Returns:
        Extended frame ID with flag set

    Raises:
        ValueError: If ID exceeds 29 bits
    """
    if arb29 & ~CAN_EFF_MASK:
        raise ValueError(f"ID {arb29:#x} exceeds 29 bits")
    return CAN_EFF_FLAG | arb29


async def _send_can_signal(client: EventClient, arb29: int, payload: bytes) -> None:
    """Send raw CAN message.

    Args:
        client: CAN bus service client
        arb29: 29-bit arbitration ID
        payload: Message payload (8 bytes)
    """
    msg = RawCanbusMessage()
    msg.id = eff_id(arb29)
    msg.remote_transmission = False  # RTR=0 (data frame)
    msg.error = False
    msg.data = payload
    await client.request_reply("/can_message", msg, decode=True)


async def trigger_dipbob(canbus_client: EventClient) -> None:
    """Trigger dipbob deployment via CAN signal.

    Args:
        canbus_client: CAN bus service client
    """
    await _send_can_signal(canbus_client, 0x18FF0007, b"\x06\x00\x02\x00\x00\x00\x00\x00")
    await asyncio.sleep(0.02)
    logger.info("Dipbob deployment signal sent")


async def check_filter_convergence(
    filter_client: EventClient, timeout: float = 5.0
) -> bool:
    """Check if the filter has converged.

    Args:
        filter_client: EventClient for the filter service
        timeout: Timeout for getting filter state

    Returns:
        True if filter has converged, False otherwise
    """
    try:
        state: FilterState = await asyncio.wait_for(
            filter_client.request_reply("/get_state", Empty(), decode=True),
            timeout=timeout,
        )
        converged = bool(getattr(state, "has_converged", False))
        if converged:
            logger.info("Filter has converged")
        else:
            logger.warning("Filter has not converged")
        return converged
    except asyncio.TimeoutError:
        logger.warning("Timeout checking filter convergence")
        return False
    except Exception as e:
        logger.error(f"Error checking filter convergence: {e}")
        return False


async def imu_wiggle(
    canbus_client: EventClient,
    filter_client: EventClient | None = None,
    duration_seconds: float = 3.0,
    angular_velocity: float = 0.3,
    check_convergence: bool = True,
    max_attempts: int = 3,
) -> bool:
    """Wiggle the robot back and forth to help the UKF filter converge.

    The filter fuses wheel odometry, GPS, and IMU data. When diverged (typically at startup),
    GPS-based waypoint navigation doesn't work, but basic twist commands do. This function
    mimics manually shaking the robot by sending alternating left/right angular velocity
    commands to excite the IMU and help the filter converge.

    Args:
        canbus_client: EventClient for the canbus service
        filter_client: Optional EventClient for checking filter convergence
        duration_seconds: How long to wiggle for each attempt (default 3.0s)
        angular_velocity: Angular velocity for wiggling (rad/s, default 0.3)
        check_convergence: Whether to check if filter converged after wiggling
        max_attempts: Maximum number of wiggle attempts before giving up

    Returns:
        True if filter converged (or if not checking), False if still diverged after max attempts
    """
    logger.info("Starting IMU wiggle to help filter converge...")

    # Check initial convergence state
    initial_converged = False
    if filter_client and check_convergence:
        initial_converged = await check_filter_convergence(filter_client)
        if initial_converged:
            logger.info("Filter already converged, no wiggle needed")
            return True

    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        logger.info(
            f"Wiggle attempt {attempt}/{max_attempts} - "
            f"Duration: {duration_seconds}s, Angular vel: ±{angular_velocity} rad/s"
        )

        # Wiggle pattern: left -> right -> left -> right
        wiggle_cycle_duration = duration_seconds / 4  # Quarter of total time per direction
        directions = [
            angular_velocity,
            -angular_velocity,
            angular_velocity,
            -angular_velocity,
        ]

        for ang_vel in directions:
            # Send twist command for this direction
            twist = Twist2d(linear_velocity_x=0.0, angular_velocity=ang_vel)

            start_time = asyncio.get_event_loop().time()
            end_time = start_time + wiggle_cycle_duration

            # Hold this direction for the cycle duration
            while asyncio.get_event_loop().time() < end_time:
                await canbus_client.request_reply("/twist", twist)
                await asyncio.sleep(0.05)  # Send at 20 Hz

        # Stop the robot
        stop_twist = Twist2d(linear_velocity_x=0.0, angular_velocity=0.0)
        await canbus_client.request_reply("/twist", stop_twist)
        logger.info("Wiggle complete, robot stopped")

        # Wait a moment for filter to settle
        await asyncio.sleep(0.5)

        # Check if filter converged
        if filter_client and check_convergence:
            converged = await check_filter_convergence(filter_client)
            if converged:
                logger.info(f"✓ Filter converged after {attempt} wiggle attempt(s)!")
                return True
            else:
                logger.warning(
                    f"Filter still diverged after attempt {attempt}/{max_attempts}"
                )
        else:
            # If not checking convergence, assume success after wiggling
            logger.info("Wiggle complete (convergence check disabled)")
            return True

    # Failed to converge after max attempts
    logger.error(f"✗ Filter did not converge after {max_attempts} wiggle attempts")
    return False
