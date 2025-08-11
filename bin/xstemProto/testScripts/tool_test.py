# Works!

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
import time

from farm_ng.canbus.tool_control_pb2 import ActuatorCommands
from farm_ng.canbus.tool_control_pb2 import HBridgeCommand, HBridgeCommandType, ToolStatuses
from farm_ng.core.event_client import EventClient
from farm_ng.core.event_service_pb2 import EventServiceConfig
from farm_ng.core.events_file_reader import proto_from_json_file


def build_hbridge_cmd(hbridge_id: int, cmd: HBridgeCommandType.ValueType) -> ActuatorCommands:
    commands: ActuatorCommands = ActuatorCommands()
    commands.hbridges.append(HBridgeCommand(id=hbridge_id, command=cmd))
    return commands


async def publish_for_duration(
    client: EventClient,
    topic: str,
    commands_factory,
    duration_s: float,
    rate_hz: float = 10.0,
    decode_reply: bool = True,
):
    """Periodically publish the command built by commands_factory for 'duration_s' seconds."""
    period = 1.0 / rate_hz if rate_hz > 0 else duration_s
    t_end = time.monotonic() + duration_s
    while time.monotonic() < t_end:
        cmds: ActuatorCommands = commands_factory()
        await client.request_reply(topic, cmds, decode=decode_reply)
        await asyncio.sleep(period)


async def do_sequence(service_config_path: Path, reverse_s: float, forward_s: float) -> None:
    # Load config and create client
    config: EventServiceConfig = proto_from_json_file(
        service_config_path, EventServiceConfig())
    client = EventClient(config)

    # 1) Countdown
    for i in (3, 2, 1):
        print(i)
        await asyncio.sleep(1.0)

    # 2) Reverse (id 0)
    print("H-bridge 0: FORWARD")
    await publish_for_duration(
        client,
        "/control_tools",
        lambda: build_hbridge_cmd(0, HBridgeCommandType.HBRIDGE_FORWARD),
        duration_s=reverse_s,
        rate_hz=10.0,
    )

    # 3) Forward (id 0)
    print("H-bridge 0: REVERSE")
    await publish_for_duration(
        client,
        "/control_tools",
        lambda: build_hbridge_cmd(0, HBridgeCommandType.HBRIDGE_REVERSE),
        duration_s=forward_s,
        rate_hz=10.0,
    )

    # Optionally send an explicit STOP at the end (nice, predictable end state)
    print("H-bridge 0: STOP")
    await client.request_reply(
        "/control_tools",
        build_hbridge_cmd(0, HBridgeCommandType.HBRIDGE_STOPPED),
        decode=True,
    )


async def main():
    parser = argparse.ArgumentParser(
        prog="python script.py",
        description="Countdown, drive H-bridge id 0 reverse then forward, repeat on Enter.",
    )
    parser.add_argument("--service-config", type=Path,
                        required=True, help="Path to canbus service config JSON.")
    parser.add_argument("--reverse-seconds", type=float,
                        default=2.0, help="Reverse duration (seconds).")
    parser.add_argument("--forward-seconds", type=float,
                        default=2.0, help="Forward duration (seconds).")
    args = parser.parse_args()

    # Repeat loop: Enter to replay, q to quit
    while True:
        await do_sequence(args.service_config, args.reverse_seconds, args.forward_seconds)
        print("\nPress Enter to replay, or 'q' then Enter to quit.")
        # Using asyncio.to_thread so we don't block the event loop
        choice = await asyncio.to_thread(sys.stdin.readline)
        if choice.strip().lower() == "q":
            print("Exiting.")
            break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
