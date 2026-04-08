"""
encode_primer.py — Encode a specific primer by hole name and position index.

Fetches the current blast data from the bridge, finds the primer at the given
hole/index, and sends the ENCODE_DRX command automatically.

Usage:
    python3 encode_primer.py --host 10.42.0.2 --hole 12 --index 1
    python3 encode_primer.py --host 10.42.0.2 --hole 12 --index 1 --dry-run

Arguments:
    --host      Windows bridge IP address
    --port      Bridge TCP port (default: 8765)
    --hole      Hole name as shown in the blast file (e.g. 11, 12, A1)
    --index     Primer number, 1-based (primer 1 = first primer in the hole)
    --lat       GPS latitude  (default: 0.0)
    --long      GPS longitude (default: 0.0)
    --hmsl      GPS height above mean sea level (default: 0.0)
    --dry-run   Print what would be encoded without actually encoding
"""

import argparse
import json
import sys

from amiga_bridge_client import AmigaBridgeClient


# ---------------------------------------------------------------------------
# Blast data search
# ---------------------------------------------------------------------------

def find_holes(data) -> list:
    """
    Recursively search the blast payload for the holes array.
    Handles varying nesting (payload > encoder > holes, or payload > holes, etc.)
    """
    if isinstance(data, dict):
        if "holes" in data and isinstance(data["holes"], list):
            return data["holes"]
        for value in data.values():
            result = find_holes(value)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = find_holes(item)
            if result is not None:
                return result
    return None


def find_primers_in_hole(holes: list, hole_name: str) -> tuple:
    """Return (hole_dict, primers_list) for the hole matching hole_name."""
    for hole in holes:
        if not isinstance(hole, dict):
            continue
        if str(hole.get("name", "")).strip() == str(hole_name).strip():
            for key in ("primers", "drxs", "detonators", "items"):
                if key in hole and isinstance(hole[key], list):
                    return hole, hole[key]
            # Fallback: first list value in hole dict
            for value in hole.values():
                if isinstance(value, list) and len(value) > 0:
                    return hole, value
    return None, None


def extract_primer_uid(primer: dict) -> str:
    for key in ("primerUID", "uid", "uuid", "id", "primerUid"):
        if key in primer and primer[key]:
            return primer[key]
    return ""


def extract_hole_ring(primer: dict, hole: dict = None) -> str:
    for key in ("holeRing", "ring"):
        if key in primer and primer[key] is not None:
            return str(primer[key])
    if hole:
        for key in ("ring", "holeRing"):
            if key in hole and hole[key] is not None:
                return str(hole[key])
    return ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Encode a primer by hole and index.")
    parser.add_argument("--host", required=True, help="Bridge host IP")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--hole", required=True, help="Hole name (e.g. 11, 12, A1)")
    parser.add_argument("--index", type=int, required=True, help="Primer number, 1-based")
    parser.add_argument("--lat",  type=float, default=0.0)
    parser.add_argument("--long", type=float, default=0.0)
    parser.add_argument("--hmsl", type=float, default=0.0)
    parser.add_argument("--dry-run", action="store_true", help="Print params without encoding")
    args = parser.parse_args()

    if args.index < 1:
        print("ERROR: --index must be 1 or greater.")
        sys.exit(1)

    drx_index = args.index - 1  # convert 1-based user index to 0-based

    with AmigaBridgeClient(host=args.host, port=args.port) as client:

        print(f"Fetching blast data from {args.host}:{args.port}...")
        payload = client.get_encoding_blast()

        holes = find_holes(payload)
        if not holes:
            print("ERROR: Could not find holes in blast data.")
            sys.exit(1)

        hole_name = str(args.hole)
        hole_dict, primers = find_primers_in_hole(holes, hole_name)
        if primers is None:
            available = [str(h.get("name", "?")) for h in holes if isinstance(h, dict)]
            print(f"ERROR: Hole '{hole_name}' not found. Available holes: {available}")
            sys.exit(1)

        if drx_index >= len(primers):
            print(f"ERROR: Hole '{hole_name}' has {len(primers)} primer(s). "
                  f"Index {args.index} is out of range.")
            sys.exit(1)

        primer = primers[drx_index]
        primer_uid = extract_primer_uid(primer)
        hole_ring  = extract_hole_ring(primer, hole_dict)

        if not primer_uid:
            print(f"ERROR: primerUID is empty for hole {hole_name}, index {args.index}.")
            sys.exit(1)

        print(f"\nHole: {hole_name}  |  Primer index: {args.index} (drxIndex: {drx_index})")
        print(f"primerUID : {primer_uid}")
        print(f"holeRing  : '{hole_ring}'")
        print(f"gpsInfo   : lat={args.lat}, long={args.long}, hmsl={args.hmsl}")

        if args.dry_run:
            print("\n[DRY RUN] — no encoding performed.")
            return

        print("\nEncoding — waiting for hardware response (up to 60s)...")
        result = client.encode_drx(
            hole_name=hole_name,
            drx_index=drx_index,
            primer_uid=primer_uid,
            hole_ring=hole_ring,
            lat=args.lat,
            long_=args.long,
            hmsl=args.hmsl,
        )

        if result.get("isSuccess"):
            print("SUCCESS — primer encoded.")
            print(json.dumps(result, indent=2))
        else:
            print("FAILED:")
            print(json.dumps(result, indent=2))
            sys.exit(1)


if __name__ == "__main__":
    main()
