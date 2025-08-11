#!/usr/bin/env python3
from __future__ import annotations
import argparse
import asyncio
from pathlib import Path

import numpy as np

from farm_ng.core.event_client import EventClient
from farm_ng.core.events_file_reader import proto_from_json_file
from farm_ng.core.event_service_pb2 import EventServiceConfigList
from farm_ng.gps import gps_pb2
from farm_ng.filter.filter_pb2 import FilterState, DivergenceCriteria
from farm_ng.core.stamp import get_stamp_by_semantics_and_clock_type, StampSemantics
from farm_ng_core_pybind import Pose3F64


def print_relative_position_frame(msg: gps_pb2.RelativePositionFrame) -> None:
    print("\n=== RELATIVE POSITION FRAME ===")
    print(f"Message stamp:       {msg.stamp.stamp}")
    print(f"GPS time:            {msg.gps_time.stamp}")
    print(f"Relative north (m):  {msg.relative_pose_north}")
    print(f"Relative east  (m):  {msg.relative_pose_east}")
    print(f"Relative down  (m):  {msg.relative_pose_down}")
    print(f"Solution length (m): {msg.relative_pose_length}")
    print(f"Accuracy north (m):  {msg.accuracy_north}")
    print(f"Accuracy east  (m):  {msg.accuracy_east}")
    print(f"Accuracy down  (m):  {msg.accuracy_down}")
    print(f"Carrier solution:    {msg.carr_soln}")
    print(f"GNSS fix ok:         {msg.gnss_fix_ok}")
    print("=" * 40)


def print_filter_state(event, msg: FilterState) -> None:
    stamp = (
        get_stamp_by_semantics_and_clock_type(
            event, StampSemantics.SERVICE_SEND, "monotonic")
        or event.timestamps[0].stamp
    )
    pose = Pose3F64.from_proto(msg.pose)
    unc = list(msg.uncertainty_diagonal.data[:3])
    divergence = [DivergenceCriteria.Name(c) for c in msg.divergence_criteria]

    print("\n=== FILTER STATE ===")
    print(f"Timestamp:           {stamp}")
    print(f"x: {pose.a_from_b.translation[0]:.3f} m, "
          f"y: {pose.a_from_b.translation[1]:.3f} m, "
          f"heading: {msg.heading:.3f} rad")
    print(f"Converged:           {msg.has_converged}")
    print(f"Uncertainty (x,y,θ): {unc[0]:.3f}, {unc[1]:.3f}, {unc[2]:.3f}")
    if not msg.has_converged:
        print(f"Divergence reason(s): {divergence}")
    print("=" * 40)


async def gps_listener(configs: dict[str, EventServiceConfigList], clients: dict[str, EventClient]) -> None:
    cfg = configs["gps"]
    client = clients["gps"]
    # assume the first subscription is the RelativePositionFrame
    sub = cfg.subscriptions[0]
    async for _, msg in client.subscribe(sub, decode=True):
        if isinstance(msg, gps_pb2.RelativePositionFrame):
            print_relative_position_frame(msg)


async def filter_listener(configs: dict[str, EventServiceConfigList], clients: dict[str, EventClient]) -> None:
    cfg = configs["filter"]
    client = clients["filter"]
    sub = cfg.subscriptions[0]
    async for event, msg in client.subscribe(sub, decode=True):
        print_filter_state(event, msg)


async def main():
    parser = argparse.ArgumentParser(
        prog="python combined_client.py",
        description="Stream GPS and filter outputs from one config file"
    )
    parser.add_argument(
        "--service-config",
        type=Path,
        required=True,
        help="JSON list containing both 'gps' and 'filter' service configs",
    )
    args = parser.parse_args()

    # Load a list of configs (must include entries named "gps" and "filter")
    cfg_list = proto_from_json_file(
        args.service_config, EventServiceConfigList())
    configs = {cfg.name: cfg for cfg in cfg_list.configs}
    clients = {name: EventClient(cfg) for name, cfg in configs.items()}

    # sanity check
    for svc in ("gps", "filter"):
        if svc not in clients:
            raise RuntimeError(f"Missing '{svc}' in {args.service_config}")

    # run both listeners concurrently
    await asyncio.gather(
        gps_listener(configs, clients),
        filter_listener(configs, clients),
    )


if __name__ == "__main__":
    asyncio.run(main())
