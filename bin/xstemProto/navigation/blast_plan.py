#!/usr/bin/env python3
from __future__ import annotations
import argparse
import asyncio
import threading
from pathlib import Path
import sys

import pandas as pd
import numpy as np

from farm_ng.core.event_client import EventClient
from farm_ng.core.event_service_pb2 import EventServiceConfigList, SubscribeRequest
from farm_ng.track.track_pb2 import TrackFollowRequest, Track, TrackFollowerState, TrackStatusEnum, RobotStatus
from farm_ng.filter.filter_pb2 import FilterState
from farm_ng.core.uri_pb2 import Uri
from farm_ng.core.events_file_reader import proto_from_json_file
from google.protobuf.empty_pb2 import Empty
from farm_ng_core_pybind import Pose3F64, Isometry3F64, Rotation3F64


async def get_pose(clients: dict[str, EventClient]) -> Pose3F64:
    """Fetch the robot’s current pose (NWU frame) from the filter service."""
    state: FilterState = await clients["filter"].request_reply(
        "/get_state", Empty(), decode=True
    )
    # Debug dump
    print(f"Current filter state:\n{state}")
    return Pose3F64.from_proto(state.pose)


async def stream_track_state(
    clients: dict[str, EventClient], exit_event: asyncio.Event
) -> None:
    """Stream the track_follower state until it finishes, fails, or user quits."""
    await asyncio.sleep(1.0)  # allow /start to register
    async for _, msg in clients["track_follower"].subscribe(
        SubscribeRequest(uri=Uri(path="/state")), decode=True
    ):
        print("###################")
        print(msg)

        # user pressed 'q' in the background watcher
        if exit_event.is_set():
            print("🔴 Exit requested—sending /cancel …")
            try:
                await clients["track_follower"].request_reply("/cancel", Empty())
                print("✅ Track cancelled.")
            except Exception as e:
                print(f"⚠️  Cancel failed: {e}")
            break

        # if the track failed, show exactly which failure_modes triggered it
        if msg.status.track_status == TrackStatusEnum.TRACK_FAILED:
            modes = msg.status.robot_status.failure_modes
            if modes:
                names = [RobotStatus.FailureMode.Name(m) for m in modes]
                print(f"❌ Track failed – reasons: {names}")
            else:
                print("❌ Track failed (no failure_modes flags set)")
            break

        # normal completion
        if getattr(msg, "done", False):
            print("✅ Arrived at the goal!")
            break


def format_track(waypoints: list[Pose3F64]) -> Track:
    return Track(waypoints=[p.to_proto() for p in waypoints])


async def set_track(clients: dict[str, EventClient], track: Track) -> None:
    await clients["track_follower"].request_reply(
        "/set_track", TrackFollowRequest(track=track)
    )


async def start_following(clients: dict[str, EventClient]) -> None:
    await clients["track_follower"].request_reply("/start", Empty())


def start_exit_watcher(exit_event: asyncio.Event):
    """Spawn a thread that waits for 'q' + Enter, then sets exit_event."""
    def _watch():
        for line in sys.stdin:
            if line.strip().lower() == "q":
                print("🔴 'q' received—will exit soon.")
                exit_event.set()
                return

    thread = threading.Thread(target=_watch, daemon=True)
    thread.start()


async def main():
    parser = argparse.ArgumentParser(
        prog="python blast_plan.py",
        description="Drive to the first point in a CSV drill plan (press 'q' to quit)",
    )
    parser.add_argument(
        "--service-config",
        type=Path,
        default=Path("navigation/service_config.json"),
        help="JSON with 'filter' and 'track_follower' configs",
    )
    parser.add_argument(
        "--csv", type=Path, required=True, help="CSV file (must include dx,dy)"
    )
    args = parser.parse_args()

    cfg_list = proto_from_json_file(
        args.service_config, EventServiceConfigList()
    )
    clients = {c.name: EventClient(c) for c in cfg_list.configs}
    for svc in ("filter", "track_follower"):
        if svc not in clients:
            raise RuntimeError(f"Missing '{svc}' in {args.service_config}")

    df = pd.read_csv(args.csv)
    df.columns = df.columns.str.strip().str.lower()
    if "dx" not in df.columns or "dy" not in df.columns:
        raise RuntimeError(f"Expected 'dx' and 'dy' in {args.csv}")
    row0 = df.iloc[0]
    goal_easting = float(row0["dx"])
    goal_northing = float(row0["dy"])

    current = await get_pose(clients)
    raw_north = float(current.a_from_b.translation[0])
    raw_west = float(current.a_from_b.translation[1])
    current_easting = -raw_west
    current_northing = raw_north

    goal_north = goal_northing
    goal_west = -goal_easting

    print(
        f"Current → (Easting {current_easting:.3f}, Northing {current_northing:.3f})\n"
        f"Goal    → (Easting {goal_easting:.3f}, Northing {goal_northing:.3f})"
    )

    zero_tangent = np.zeros((6, 1), dtype=np.float64)
    goal_iso = Isometry3F64(
        np.array([goal_north, goal_west, 0.0], dtype=np.float64),
        Rotation3F64.Rz(0.0),
    )
    goal = Pose3F64(
        a_from_b=goal_iso,
        frame_a="world",
        frame_b="robot",
        tangent_of_b_in_a=zero_tangent,
    )

    track = format_track([current, goal])
    await set_track(clients, track)
    print("Track set; starting execution.")
    await start_following(clients)

    # Start exit watcher
    exit_event = asyncio.Event()
    start_exit_watcher(exit_event)

    # Stream until done/fail or 'q'
    await stream_track_state(clients, exit_event)


if __name__ == "__main__":
    asyncio.run(main())
