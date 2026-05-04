"""
start_arm.py — Trigger a preprogrammed motion sequence on a Techman TM7 cobot.

Connects to the robot's Listen Node via TCP and sends a ScriptExit() command,
releasing the robot to execute its preprogrammed motion sequence.

The TM7 TMflow project must have a Listen Node placed immediately before the
motion sequence. The robot pauses at the Listen Node until this script connects
and sends ScriptExit().

Usage:
    python3 start_arm.py
    python3 start_arm.py --host 192.168.1.50
    python3 start_arm.py --dry-run

Arguments:
    --host      TM7 IP address (default: 192.168.1.50)
    --port      Listen Node TCP port (default: 5891)
    --dry-run   Print packet without sending
"""

import argparse
import socket
import sys


def compute_checksum(data: str) -> str:
    """XOR checksum of all characters between $ and * in a TMSCT packet."""
    checksum = 0
    for ch in data:
        checksum ^= ord(ch)
    return f"{checksum:02X}"


def build_tmsct_packet(script: str, packet_id: str = "1") -> bytes:
    """Build a TMSCT packet to send to the TM7 Listen Node.

    Format: $TMSCT,<length>,<id>,<script>,*<checksum>\r\n
    Length covers the id, script, and their surrounding commas.
    """
    content = f"{packet_id},{script},"
    data = f"TMSCT,{len(content)},{content}"
    return f"${data}*{compute_checksum(data)}\r\n".encode()


def parse_response(raw: bytes) -> tuple[bool, str]:
    """Parse a TMSCT response packet. Returns (success, message)."""
    text = raw.decode(errors="replace").strip()
    # Expected: $TMSCT,<len>,<id>,OK,*XX  or  $TMSCT,<len>,<id>,ERROR:XX,*XX
    if "OK" in text:
        return True, text
    if "ERROR" in text:
        return False, text
    return False, f"Unexpected response: {text}"


def send_script_exit(host: str, port: int) -> bool:
    """Connect to TM7 Listen Node and send ScriptExit() to release the robot."""
    packet = build_tmsct_packet("ScriptExit()")
    print(f"Packet: {packet.decode().strip()}")

    with socket.create_connection((host, port), timeout=10) as sock:
        # The robot may send an initial status message on connect — drain it
        sock.settimeout(1.0)
        try:
            initial = sock.recv(1024)
            print(f"Robot: {initial.decode(errors='replace').strip()}")
        except socket.timeout:
            pass

        sock.settimeout(10.0)
        sock.sendall(packet)

        response = sock.recv(1024)
        success, message = parse_response(response)
        print(f"Response: {message}")
        return success


def main():
    parser = argparse.ArgumentParser(
        description="Trigger preprogrammed motion on TM7 via Listen Node."
    )
    parser.add_argument("--host", default="192.168.1.50", help="TM7 IP address")
    parser.add_argument("--port", type=int, default=5891, help="Listen Node port")
    parser.add_argument("--dry-run", action="store_true", help="Print packet without sending")
    args = parser.parse_args()

    print(f"TM7 at {args.host}:{args.port}")

    if args.dry_run:
        packet = build_tmsct_packet("ScriptExit()")
        print(f"Packet: {packet.decode().strip()}")
        print("[DRY RUN] — not sent.")
        sys.exit(0)

    print("Connecting to Listen Node...")
    try:
        success = send_script_exit(args.host, args.port)
        if success:
            print("SUCCESS — arm motion sequence started.")
        else:
            print("FAILED — robot returned an error.")
            sys.exit(1)
    except ConnectionRefusedError:
        print("FAILED — connection refused. Is the robot at the Listen Node?")
        sys.exit(1)
    except TimeoutError:
        print("FAILED — connection timed out. Check IP and network.")
        sys.exit(1)
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
