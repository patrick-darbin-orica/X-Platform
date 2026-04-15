"""
verify_bridge.py — Pre-mission connection and blast verification for XPrime.

Runs the same checks as initialize() + verify_ready() without starting the robot.

Usage:
    python3 verify_bridge.py
    python3 verify_bridge.py --host 10.95.76.24 --blast "C:\\blasts\\myblast.lgf"
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "encoder"))
from amiga_bridge_client import AmigaBridgeClient  # noqa: E402


def _find_holes(data) -> list:
    if isinstance(data, dict):
        if "holes" in data and isinstance(data["holes"], list):
            return data["holes"]
        for value in data.values():
            result = _find_holes(value)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = _find_holes(item)
            if result is not None:
                return result
    return None


def _get_primers(hole: dict) -> list:
    for key in ("primers", "drxs", "detonators", "items"):
        if key in hole and isinstance(hole[key], list):
            return hole[key]
    return []


def _is_encoded(primer: dict) -> bool:
    return bool(primer.get("detStatus") and primer.get("DRXId"))


def main():
    parser = argparse.ArgumentParser(description="Verify XPrime bridge connection and blast data.")
    parser.add_argument("--host", default="10.95.76.24", help="Windows bridge IP")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--blast", default="", help="Windows path to .lgf blast file")
    args = parser.parse_args()

    passed = True

    # ---- 1. Bridge reachable ----
    print(f"\n[1] Connecting to bridge at {args.host}:{args.port}...")
    try:
        with AmigaBridgeClient(host=args.host, port=args.port) as client:
            state = client.get_state()
        print(f"    PASS — bridge reachable")
        print(f"    State: {json.dumps(state, indent=6)}")
    except Exception as e:
        print(f"    FAIL — {e}")
        passed = False

    # ---- 2. Blast file path set ----
    print(f"\n[2] Checking blast file path...")
    if not args.blast:
        print("    WARN — --blast not provided; calibrate() will not import a blast file")
        print("           OK if blast is already loaded in the Windows program")
    else:
        print(f"    PASS — blast path: {args.blast}")

    # ---- 3. Fetch blast data ----
    print(f"\n[3] Fetching blast data...")
    blast_data = None
    try:
        with AmigaBridgeClient(host=args.host, port=args.port) as client:
            blast_data = client.get_encoding_blast()
        print("    PASS — blast data received")
    except Exception as e:
        print(f"    FAIL — {e}")
        passed = False

    # ---- 4. Holes and primer summary ----
    if blast_data is not None:
        print(f"\n[4] Analysing primers...")
        holes = _find_holes(blast_data)
        if not holes:
            print("    FAIL — no holes found in blast data")
            passed = False
        else:
            encoded = 0
            unencoded = 0
            for hole in holes:
                if not isinstance(hole, dict):
                    continue
                hole_name = hole.get("name", "?")
                primers = _get_primers(hole)
                for i, p in enumerate(primers):
                    if _is_encoded(p):
                        encoded += 1
                        status = "encoded "
                    else:
                        unencoded += 1
                        status = "PENDING "
                    print(f"    hole={hole_name:>4}  primer={i}  [{status}]  detStatus={p.get('detStatus')!r}  DRXId={p.get('DRXId')!r}")

            print(f"\n    Total encoded : {encoded}")
            print(f"    Total pending : {unencoded}")
            if unencoded == 0:
                print("    WARNING — no unencoded primers remaining")

    # ---- Summary ----
    print(f"\n{'='*40}")
    if passed:
        print("RESULT: PASS — ready to start mission")
    else:
        print("RESULT: FAIL — resolve issues above before starting")
    print('='*40)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
