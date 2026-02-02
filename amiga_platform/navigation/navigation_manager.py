"""Navigation manager for track execution and state coordination."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from farm_ng.core.event_service_pb2 import SubscribeRequest
from farm_ng.core.uri_pb2 import Uri
from farm_ng.track.track_pb2 import (
    Track,
    TrackFollowerState,
    TrackFollowRequest,
    TrackStatusEnum,
)
from google.protobuf.empty_pb2 import Empty

if TYPE_CHECKING:
    from farm_ng.core.event_client import EventClient

logger = logging.getLogger(__name__)


class NavigationManager:
    """Executes track segments via track_follower service."""

    def __init__(
        self,
        track_follower_client: EventClient,
        filter_client: EventClient,
    ) -> None:
        """Initialize navigation manager.

        Args:
            track_follower_client: Track follower service client
            filter_client: Filter service client
        """
        self.track_follower = track_follower_client
        self.filter_client = filter_client

        # Event coordination
        self.track_complete = asyncio.Event()
        self.track_failed = asyncio.Event()
        self.shutdown_event = asyncio.Event()  # For immediate shutdown
        self.current_status: TrackStatusEnum | None = None

        # Thread safety
        self._lock = asyncio.Lock()

        # Monitoring task
        self.monitor_task: asyncio.Task | None = None
        self.shutdown_requested = False

    async def start_monitoring(self) -> None:
        """Start background state monitoring."""
        self.monitor_task = asyncio.create_task(self._monitor_state())
        logger.info("Navigation manager monitoring started")

    async def _monitor_state(self) -> None:
        """Background task to monitor track follower state."""
        try:
            config = self.track_follower.config
            # Use configured subscription or create one for /state endpoint
            if config.subscriptions:
                subscription = config.subscriptions[0]
            else:
                subscription = SubscribeRequest(
                    uri=Uri(path="/state"),
                    every_n=1,
                )
            logger.info(f"[TRACK] Subscribing to track_follower state...")

            async for event, message in self.track_follower.subscribe(
                subscription, decode=True
            ):
                if self.shutdown_requested:
                    break

                if isinstance(message, TrackFollowerState):
                    status = message.status.track_status
                    prev_status = self.current_status
                    self.current_status = status

                    # Log status changes
                    if prev_status != status:
                        try:
                            status_name = TrackStatusEnum.Name(status)
                            prev_name = TrackStatusEnum.Name(prev_status) if prev_status else "None"
                            logger.info(f"[TRACK] Status: {prev_name} → {status_name}")
                        except Exception:
                            logger.info(f"[TRACK] Status: {prev_status} → {status}")

                    if status == TrackStatusEnum.TRACK_COMPLETE:
                        logger.info("Track complete event received")
                        self.track_complete.set()
                    elif status in [
                        TrackStatusEnum.TRACK_FAILED,
                        TrackStatusEnum.TRACK_ABORTED,
                        TrackStatusEnum.TRACK_CANCELLED,
                    ]:
                        logger.warning(f"Track failed with status: {TrackStatusEnum.Name(status)}")
                        self.track_failed.set()
        except asyncio.CancelledError:
            logger.info("State monitoring cancelled")
        except Exception as e:
            logger.error(f"Error in state monitoring: {e}", exc_info=True)

    async def execute_track(self, track: Track, timeout: float = 60.0) -> bool:
        """Execute single track segment.

        Args:
            track: Track segment to execute
            timeout: Maximum execution time in seconds

        Returns:
            True if track completed successfully, False otherwise
        """
        # Clear events
        self.track_complete.clear()
        self.track_failed.clear()

        # Set track
        async with self._lock:
            req = TrackFollowRequest(track=track)
            await self.track_follower.request_reply("/set_track", req)

        await asyncio.sleep(1.0)  # Allow track to load

        # Start following
        async with self._lock:
            await self.track_follower.request_reply("/start", Empty())

        logger.info("Track execution started")

        # Wait for completion, failure, or shutdown
        done, pending = await asyncio.wait(
            [
                asyncio.create_task(self.track_complete.wait()),
                asyncio.create_task(self.track_failed.wait()),
                asyncio.create_task(self.shutdown_event.wait()),
            ],
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Check for shutdown first
        if self.shutdown_event.is_set():
            logger.info("Shutdown requested - cancelling track")
            await self.cancel_track()
            return False

        if not done:
            logger.warning("Track execution timeout")
            await self.cancel_track()
            return False

        success = self.track_complete.is_set()
        if success:
            logger.info("Track execution completed successfully")
        else:
            logger.error("Track execution failed")

        return success

    async def cancel_track(self) -> None:
        """Cancel current track execution."""
        async with self._lock:
            try:
                await self.track_follower.request_reply("/cancel", Empty())
                logger.info("Track cancelled")
            except Exception as e:
                logger.warning(f"Error cancelling track: {e}")

    def request_immediate_shutdown(self) -> None:
        """Request immediate shutdown - call from signal handler.

        This sets the shutdown event which will interrupt any pending
        track execution and trigger cancellation.
        """
        logger.info("Immediate shutdown requested")
        self.shutdown_requested = True
        self.shutdown_event.set()

    async def shutdown(self) -> None:
        """Clean shutdown."""
        logger.info("Shutting down navigation manager...")
        self.shutdown_requested = True
        self.shutdown_event.set()  # Ensure any pending waits are interrupted

        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        await self.cancel_track()
        logger.info("Navigation manager shutdown complete")
