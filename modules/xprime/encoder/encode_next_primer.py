"""
encode_next_primer.py — Encode the first non-encoded primer in the blast.

Fetches the current blast data, walks holes in order, and encodes the first
primer whose detStatus or DRXId is empty (i.e. not yet encoded).

Usage:
    python3 encode_next_primer.py
    python3 encode_next_primer.py --dry-run
    python3 encode_next_primer.py --host 198.168.1.24

Arguments:
    --host      Windows bridge IP address (default: 198.168.1.24)
    --port      Bridge TCP port (default: 8765)
    --lat       GPS latitude  (default: 0.0)
    --long      GPS longitude (default: 0.0)
    --hmsl      GPS height above mean sea level (default: 0.0)
    --dry-run   Print what would be encoded without actually encoding
"""

import argparse
import json
import sys

from amiga_bridge_client import AmigaBridgeClient
from encode_primer import (
    find_holes,
    find_primers_in_hole,
    extract_primer_uid,
    extract_hole_ring,
)


def find_first_unencoded(holes: list):
    """
    Walk holes in order and return (hole_name, drx_index, primer, hole_dict)
    for the first primer missing detStatus or DRXId, or None if all are encoded.
    """
    for hole in holes:
        if not isinstance(hole, dict):
            continue
        hole_name = str(hole.get("name", "")).strip()
        if not hole_name:
            continue
        _, primers = find_primers_in_hole(holes, hole_name)
        if not primers:
            continue
        for drx_index, primer in enumerate(primers):
            det_status = primer.get("detStatus", "")
            drx_id = primer.get("DRXId", "")
            if not (det_status and drx_id):
                return hole_name, drx_index, primer, hole
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Encode the first non-encoded primer in the blast."
    )
    parser.add_argument("--host", default="192.168.1.24", help="Bridge host IP")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--lat", type=float, default=0.0)
    parser.add_argument("--long", type=float, default=0.0)
    parser.add_argument("--hmsl", type=float, default=0.0)
    parser.add_argument(
        "--dry-run", action="store_true", help="Print params without encoding"
    )
    args = parser.parse_args()

    with AmigaBridgeClient(host=args.host, port=args.port) as client:

        print(f"Fetching blast data from {args.host}:{args.port}...")
        payload = client.get_encoding_blast()

        holes = find_holes(payload)
        if not holes:
            print("ERROR: Could not find holes in blast data.")
            sys.exit(1)

        result = find_first_unencoded(holes)
        if result is None:
            print("All primers are already encoded.")
            sys.exit(0)

        hole_name, drx_index, primer, hole_dict = result
        primer_uid = extract_primer_uid(primer)
        hole_ring = extract_hole_ring(primer, hole_dict)

        if not primer_uid:
            print(
                f"ERROR: primerUID is empty for hole {hole_name}, "
                f"index {drx_index + 1}."
            )
            sys.exit(1)

        print(
            f"\nHole: {hole_name}  |  Primer index: {drx_index + 1} "
            f"(drxIndex: {drx_index})"
        )
        print(f"primerUID : {primer_uid}")
        print(f"holeRing  : '{hole_ring}'")
        print(f"gpsInfo   : lat={args.lat}, long={args.long}, hmsl={args.hmsl}")

        if args.dry_run:
            print("\n[DRY RUN] — no encoding performed.")
        else:
            print("\nEncoding — waiting for hardware response (up to 60s)...")
            encode_result = client.encode_drx(
                hole_name=hole_name,
                drx_index=drx_index,
                primer_uid=primer_uid,
                hole_ring=hole_ring,
                lat=args.lat,
                long_=args.long,
                hmsl=args.hmsl,
            )

            if encode_result.get("isSuccess"):
                print("SUCCESS — primer encoded.")
                print(json.dumps(encode_result, indent=2))
            else:
                print("FAILED:")
                print(json.dumps(encode_result, indent=2))
                sys.exit(1)

        print("\nVerifying primer status in blast...")
        verify_payload = client.get_encoding_blast()
        verify_holes = find_holes(verify_payload)
        if verify_holes:
            _, verify_primers = find_primers_in_hole(verify_holes, hole_name)
            if verify_primers and drx_index < len(verify_primers):
                verified_primer = verify_primers[drx_index]
                det_status = verified_primer.get("detStatus", "")
                drx_id = verified_primer.get("DRXId", "")
                is_encoded = bool(det_status and drx_id)
                print(
                    f"Encoded: {is_encoded}  |  detStatus: '{det_status}'"
                    f"  |  DRXId: '{drx_id}'"
                )
                print(json.dumps(verified_primer, indent=2))
            else:
                print("WARNING: Could not locate primer in post-encode blast data.")
        else:
            print("WARNING: Could not fetch blast data for verification.")


if __name__ == "__main__":
    main()
