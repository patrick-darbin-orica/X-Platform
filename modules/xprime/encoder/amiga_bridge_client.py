"""
amiga_bridge_client.py — Amiga-side TCP client for the encoding bridge

Copy this file to the farm-ng Amiga robot (Linux).
Can be used as a standalone CLI tool or imported as a library from ROS2 nodes
or Python scripts.

Requirements (Amiga/Linux):
    pip install --user websockets   # not needed — this uses raw TCP sockets

CLI usage:
    python3 amiga_bridge_client.py --host 192.168.1.100 --port 8765 --command GET_STATE
    python3 amiga_bridge_client.py --host 192.168.1.100 --command ENCODE_DRX \
        --params '{"holeName":"H1","drxIndex":1,"primerUID":"UID-001","holeRing":"R1","gpsInfo":{"lat":-27.47,"long":153.02,"hmsl":25.0}}'

Library usage:
    from amiga_bridge_client import AmigaBridgeClient

    client = AmigaBridgeClient(host="192.168.1.100", port=8765)
    state = client.get_state()
    client.set_com_port("COM10")
    client.import_blast("C:\\\\blasts\\\\myblast.lgf")
    result = client.encode_drx(
        hole_name="H1", drx_index=1, primer_uid="UID-001",
        hole_ring="R1", lat=-27.47, long_=153.02, hmsl=25.0
    )
    client.export_blast()
    client.close()
"""

import argparse
import json
import socket
import uuid
from typing import Any, Dict, Optional


class AmigaBridgeClient:
    """Synchronous TCP client for the amiga-bridge service."""

    def __init__(
        self, host: str = "192.168.1.100", port: int = 8765, timeout: float = 65.0
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None
        self._buf = b""

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self):
        """Open the TCP connection (called automatically on first use)."""
        if self._sock is not None:
            return
        self._sock = socket.create_connection((self.host, self.port), timeout=10)
        self._sock.settimeout(self.timeout)

    def close(self):
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self._buf = b""

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.close()

    # ------------------------------------------------------------------
    # Low-level send/receive
    # ------------------------------------------------------------------

    def _send(self, command: str, params: Optional[Dict] = None) -> Dict:
        self.connect()
        corr_id = str(uuid.uuid4())
        req: Dict[str, Any] = {"correlationId": corr_id, "command": command}
        if params:
            req["params"] = params
        payload = json.dumps(req).encode() + b"\n"
        self._sock.sendall(payload)

        # Read until newline (response may arrive in multiple TCP segments)
        while b"\n" not in self._buf:
            chunk = self._sock.recv(65536)
            if not chunk:
                raise ConnectionError("Bridge closed the connection unexpectedly")
            self._buf += chunk

        line, self._buf = self._buf.split(b"\n", 1)
        response = json.loads(line.strip())
        return response

    def _require_ok(self, resp: Dict) -> Dict:
        if not resp.get("ok"):
            error = resp.get("error", "UNKNOWN_ERROR")
            extra = {
                k: v
                for k, v in resp.items()
                if k not in ("ok", "error", "correlationId")
            }
            raise RuntimeError(f"Bridge error: {error} {extra}")
        return resp

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_state(self) -> Dict:
        """Return the wg-backend state dict."""
        return _expand_json_strings(
            self._require_ok(self._send("GET_STATE"))["payload"]
        )

    def set_com_port(self, port: str = "COM10") -> bool:
        """Register the encoder serial port. Call once per session."""
        self._require_ok(self._send("SET_COM_PORT", {"port": port}))
        return True

    def import_blast(self, windows_path: str) -> bool:
        """Load a blast .lgf file from a path on the Windows host."""
        self._require_ok(self._send("IMPORT_BLAST", {"path": windows_path}))
        return True

    def encode_drx(
        self,
        hole_name: str,
        drx_index: int,
        primer_uid: str,
        hole_ring: str,
        lat: float = 0.0,
        long_: float = 0.0,
        hmsl: float = 0.0,
    ) -> Dict:
        """
        Encode one detonator (DRX). Blocks until the encoder hardware responds
        or timeout expires (default 65 s). Raises RuntimeError on failure.

        Returns the wg-backend payload dict.
        """
        params = {
            "holeName": hole_name,
            "drxIndex": drx_index,
            "primerUID": primer_uid,
            "holeRing": hole_ring,
            "gpsInfo": {"lat": lat, "long": long_, "hmsl": hmsl},
        }
        resp = self._require_ok(self._send("ENCODE_DRX", params))
        return _expand_json_strings(resp["payload"])

    def decode_drx(
        self,
        hole_name: str,
        drx_index: int,
        primer_uid: str,
        hole_ring: str,
        lat: float = 0.0,
        long_: float = 0.0,
        hmsl: float = 0.0,
    ) -> Dict:
        """Decode (read back) one detonator."""
        params = {
            "holeName": hole_name,
            "drxIndex": drx_index,
            "primerUID": primer_uid,
            "holeRing": hole_ring,
            "gpsInfo": {"lat": lat, "long": long_, "hmsl": hmsl},
        }
        return _expand_json_strings(
            self._require_ok(self._send("DECODE_DRX", params))["payload"]
        )

    def get_encoding_blast(self) -> Dict:
        """Return the full blast data with primer encoding statuses."""
        payload = self._require_ok(self._send("GET_ENCODING_BLAST"))["payload"]
        return _expand_json_strings(payload)

    def export_blast(self) -> Dict:
        """Finalise and export the fully-encoded blast."""
        return _expand_json_strings(
            self._require_ok(self._send("EXPORT_BLAST"))["payload"]
        )

    def revert_blast_state(self) -> bool:
        """Revert the blast back to ready-to-encode state."""
        self._require_ok(self._send("REVERT_BLAST_STATE"))
        return True

    def reset_database(self) -> bool:
        """Clear all encoding state. Use before loading a new blast."""
        self._require_ok(self._send("RESET_DATABASE"))
        return True

    def get_system_uid(self) -> str:
        """Return the Windows host system UID string."""
        return self._require_ok(self._send("GET_SYSTEM_UID"))["payload"]

    # ------------------------------------------------------------------
    # High-level convenience: full encoding session
    # ------------------------------------------------------------------

    def run_encoding_session(
        self,
        blast_windows_path: str,
        primers: list,
        com_port: str = "COM10",
        on_primer_encoded=None,
    ) -> Dict:
        """
        Convenience wrapper that runs a full encoding session.

        Parameters
        ----------
        blast_windows_path : str
            Path on the Windows host to the .lgf blast file.
        primers : list of dict
            Each dict must have keys:
              hole_name, drx_index, primer_uid, hole_ring,
              lat (optional), long_ (optional), hmsl (optional)
        com_port : str
            Serial port for the encoder hardware.
        on_primer_encoded : callable(primer_dict, result_dict) | None
            Optional callback called after each successful encode.

        Returns
        -------
        dict  — the export result payload
        """
        self.set_com_port(com_port)
        self.import_blast(blast_windows_path)

        for p in primers:
            result = self.encode_drx(
                hole_name=p["hole_name"],
                drx_index=p["drx_index"],
                primer_uid=p["primer_uid"],
                hole_ring=p["hole_ring"],
                lat=p.get("lat", 0.0),
                long_=p.get("long_", 0.0),
                hmsl=p.get("hmsl", 0.0),
            )
            if on_primer_encoded:
                on_primer_encoded(p, result)

        return self.export_blast()


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def _expand_json_strings(obj):
    """Recursively parse any string values that contain embedded JSON."""
    if isinstance(obj, dict):
        return {k: _expand_json_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_json_strings(i) for i in obj]
    if isinstance(obj, str):
        stripped = obj.strip()
        if stripped and stripped[0] in ("{", "["):
            try:
                return _expand_json_strings(json.loads(stripped))
            except json.JSONDecodeError:
                pass
    return obj


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _cli():
    parser = argparse.ArgumentParser(
        description="Amiga bridge client — send commands to the Windows encoding bridge."
    )
    parser.add_argument("--host", default="172.16.3.248", help="Bridge host IP")
    parser.add_argument("--port", type=int, default=8765, help="Bridge TCP port")
    parser.add_argument(
        "--command",
        required=True,
        choices=[
            "GET_STATE",
            "SET_COM_PORT",
            "IMPORT_BLAST",
            "ENCODE_DRX",
            "DECODE_DRX",
            "GET_ENCODING_BLAST",
            "REVERT_BLAST_STATE",
            "EXPORT_BLAST",
            "RESET_DATABASE",
            "GET_SYSTEM_UID",
        ],
    )
    parser.add_argument(
        "--params",
        default=None,
        help='JSON string of command parameters, e.g. \'{"port":"COM10"}\'',
    )
    parser.add_argument("--timeout", type=float, default=65.0)
    args = parser.parse_args()

    params = json.loads(args.params) if args.params else None

    client = AmigaBridgeClient(host=args.host, port=args.port, timeout=args.timeout)
    try:
        resp = client._send(args.command, params)
        print(json.dumps(_expand_json_strings(resp), indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    _cli()
