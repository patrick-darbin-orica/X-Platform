"""XPrime priming module."""
from __future__ import annotations

import asyncio
import logging
import sys
import os
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from modules.base_module import BaseModule, ModuleContext, ModuleResult

if TYPE_CHECKING:
    from farm_ng.core.event_client import EventClient
    from amiga_platform.vision.vision_system import VisionSystem

# Make encoder submodule importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "encoder"))
from amiga_bridge_client import AmigaBridgeClient  # noqa: E402

logger = logging.getLogger(__name__)

# Flag file used for operator confirmation via Flask UI
_CONFIRM_FLAG = Path("/tmp/xprime_drx_ready")
_WAITING_FLAG = Path("/tmp/xprime_waiting_for_operator")


class PrimingModule(BaseModule):
    """XPrime priming module.

    Pre-start:
        initialize()   — reads bridge config, fetches blast data
        verify_ready() — confirms TCP connection and blast is loaded with primers
        calibrate()    — registers COM port on encoder hardware

    Per-hole:
        execute()      — finds next unencoded primer, calls encode_drx()
    """

    def __init__(self) -> None:
        self.canbus: Optional[EventClient] = None
        self.vision: Optional[VisionSystem] = None
        self.config: dict = {}
        self._bridge_host: str = "10.95.76.24"
        self._bridge_port: int = 8765
        self._com_port: str = "COM10"
        self._blast_file: str = ""
        self._blast_data: Optional[dict] = None

    @property
    def module_name(self) -> str:
        return "xprime"

    # ------------------------------------------------------------------
    # Pre-start
    # ------------------------------------------------------------------

    async def initialize(self, context: ModuleContext) -> None:
        logger.info("Initializing XPrime priming module...")
        self.canbus = context.canbus_client
        self.vision = context.vision_system
        self.config = context.module_config

        bridge_cfg = self.config.get("bridge", {})
        self._bridge_host = bridge_cfg.get("host", self._bridge_host)
        self._bridge_port = bridge_cfg.get("port", self._bridge_port)
        self._com_port = bridge_cfg.get("com_port", self._com_port)
        self._blast_file = bridge_cfg.get("blast_file", self._blast_file)

        logger.info(f"Bridge: {self._bridge_host}:{self._bridge_port}")
        logger.info(f"Blast file: {self._blast_file}")

        # Fetch blast data upfront so verify_ready() can check it
        try:
            with AmigaBridgeClient(host=self._bridge_host, port=self._bridge_port) as client:
                self._blast_data = client.get_encoding_blast()
            logger.info("Blast data fetched successfully")
        except Exception as e:
            logger.error(f"Failed to fetch blast data during init: {e}")
            self._blast_data = None

    async def verify_ready(self) -> bool:
        """Confirm bridge connection and blast data loaded with primers."""
        # Check bridge is reachable
        try:
            with AmigaBridgeClient(host=self._bridge_host, port=self._bridge_port) as client:
                client.get_state()
            logger.info("✓ Bridge connection OK")
        except Exception as e:
            logger.error(f"Bridge not reachable at {self._bridge_host}:{self._bridge_port}: {e}")
            return False

        # Check blast file path is set (warning only — blast may already be loaded in Windows)
        if not self._blast_file:
            logger.warning("blast_file not set in config.yaml — calibrate() will not import a blast file")

        # Check blast data was fetched and contains primers
        if self._blast_data is None:
            logger.error("Blast data not loaded — check bridge connection and blast file")
            return False

        holes = _find_holes(self._blast_data)
        if not holes:
            logger.error("Blast data loaded but no holes found")
            return False

        total_primers = sum(
            len(_get_primers(h)) for h in holes if isinstance(h, dict)
        )
        unencoded = sum(
            1
            for h in holes if isinstance(h, dict)
            for p in _get_primers(h)
            if not _is_encoded(p)
        )
        logger.info(f"✓ Blast loaded: {len(holes)} holes, {total_primers} primers, {unencoded} unencoded")

        if unencoded == 0:
            logger.warning("No unencoded primers remaining in blast")

        return True

    async def calibrate(self) -> bool:
        """Register the encoder COM port on the Windows device."""
        try:
            with AmigaBridgeClient(host=self._bridge_host, port=self._bridge_port) as client:
                if self._blast_file:
                    client.import_blast(self._blast_file)
                    logger.info(f"✓ Blast imported: {self._blast_file}")
                else:
                    logger.warning("Skipping blast import — blast_file not set, using existing loaded blast")
                client.set_com_port(self._com_port)
            logger.info(f"✓ COM port {self._com_port} registered")
            return True
        except Exception as e:
            logger.error(f"Calibration failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Per-hole
    # ------------------------------------------------------------------

    async def execute(self, context: ModuleContext) -> ModuleResult:
        """Find the next unencoded primer and encode it."""
        hole_name, drx_index = None, None
        try:
            with AmigaBridgeClient(host=self._bridge_host, port=self._bridge_port) as client:
                blast_data = client.get_encoding_blast()

                holes = _find_holes(blast_data)
                if not holes:
                    return ModuleResult(success=False, error="No holes found in blast data", hole_completed=False)

                # Find next unencoded primer across all holes
                primer, hole_name, drx_index = _find_next_unencoded(holes)
                if primer is None:
                    return ModuleResult(success=False, error="No unencoded primers remaining", hole_completed=False)

                primer_uid = _extract_primer_uid(primer)
                hole_ring = _extract_hole_ring(primer)

                if not primer_uid:
                    return ModuleResult(success=False, error=f"Empty primerUID for hole {hole_name} index {drx_index}", hole_completed=False)

                logger.info(f"Encoding: hole={hole_name} drxIndex={drx_index} primerUID={primer_uid}")

                # Wait for operator to confirm DRX is loaded in encoder tube
                _CONFIRM_FLAG.unlink(missing_ok=True)
                _WAITING_FLAG.touch()
                logger.info("Waiting for operator confirmation via web UI...")
                try:
                    while not _CONFIRM_FLAG.exists():
                        await asyncio.sleep(0.5)
                finally:
                    _WAITING_FLAG.unlink(missing_ok=True)
                    _CONFIRM_FLAG.unlink(missing_ok=True)
                logger.info("Operator confirmed — starting encode")

                result = client.encode_drx(
                    hole_name=hole_name,
                    drx_index=drx_index,
                    primer_uid=primer_uid,
                    hole_ring=hole_ring,
                )

            # --- Payload-level result handling (testResult from PrimerTestResult enum) ---
            test_result = result.get("testResult", "")

            if result.get("isSuccess"):
                if test_result == "Ok":
                    logger.info(f"Primer encoded OK: hole={hole_name} drxIndex={drx_index}")
                    # TODO: handle Ok — nominal success, move to next hole
                    return ModuleResult(
                        success=True,
                        measurements={"hole_name": hole_name, "drx_index": drx_index, "primer_uid": primer_uid, "test_result": test_result},
                        hole_completed=True,
                    )
                elif test_result == "Programmed":
                    logger.info(f"Primer already programmed: hole={hole_name} drxIndex={drx_index}")
                    # TODO: handle Programmed — detonator was already encoded; decide whether to skip or treat as success
                    return ModuleResult(success=True, measurements={"hole_name": hole_name, "test_result": test_result}, hole_completed=True)
                elif test_result == "CommWarning":
                    logger.warning(f"Encode succeeded with comm warning: hole={hole_name} drxIndex={drx_index}")
                    # TODO: handle CommWarning — encoded but communication was marginal; log and continue or flag for review
                    return ModuleResult(success=True, measurements={"hole_name": hole_name, "test_result": test_result}, hole_completed=True)
                else:
                    logger.info(f"Encode reported isSuccess with testResult='{test_result}': hole={hole_name}")
                    # TODO: handle any other isSuccess testResult values not yet accounted for
                    return ModuleResult(success=True, measurements={"hole_name": hole_name, "test_result": test_result}, hole_completed=True)

            else:
                if test_result == "Faulty":
                    logger.error(f"Detonator faulty: hole={hole_name} drxIndex={drx_index}")
                    # TODO: handle Faulty — detonator hardware fault; decide whether to skip hole or abort mission
                    return ModuleResult(success=False, error=f"Detonator faulty at hole {hole_name}", hole_completed=False)
                elif test_result == "NoReply":
                    logger.error(f"No reply from detonator: hole={hole_name} drxIndex={drx_index}")
                    # TODO: handle NoReply — detonator not responding; retry or skip
                    return ModuleResult(success=False, error=f"No reply from detonator at hole {hole_name}", hole_completed=False)
                elif test_result == "LowVolt":
                    logger.error(f"Detonator low voltage: hole={hole_name} drxIndex={drx_index}")
                    # TODO: handle LowVolt — detonator battery low; decide whether to skip or abort
                    return ModuleResult(success=False, error=f"Detonator low voltage at hole {hole_name}", hole_completed=False)
                elif test_result == "Fusehead":
                    logger.error(f"Fusehead detected (not a DRX): hole={hole_name} drxIndex={drx_index}")
                    # TODO: handle Fusehead — wrong device type connected; skip hole or alert operator
                    return ModuleResult(success=False, error=f"Fusehead detected at hole {hole_name}", hole_completed=False)
                elif test_result == "DataError":
                    logger.error(f"Data error on detonator: hole={hole_name} drxIndex={drx_index}")
                    # TODO: handle DataError — corrupt data from detonator; retry or skip
                    return ModuleResult(success=False, error=f"Data error at hole {hole_name}", hole_completed=False)
                elif test_result == "NotTested":
                    logger.warning(f"Detonator not tested: hole={hole_name} drxIndex={drx_index}")
                    # TODO: handle NotTested — encode attempted but test did not run; determine if safe to proceed
                    return ModuleResult(success=False, error=f"Detonator not tested at hole {hole_name}", hole_completed=False)
                else:
                    error = result.get("error", f"Unknown encode failure (testResult='{test_result}')")
                    logger.error(f"Encode failed: {error}")
                    # TODO: handle any unrecognised failure — log full result payload for diagnosis
                    return ModuleResult(success=False, error=error, hole_completed=False)

        except TimeoutError:
            logger.error(f"Encode timed out after 65s: hole={hole_name} drxIndex={drx_index}")
            # TODO: handle timeout — no response from hardware within limit; retry or skip hole
            return ModuleResult(success=False, error="Encode timed out", hole_completed=False)
        except RuntimeError as e:
            error_str = str(e)
            if "BACKTOBACK_INTERVAL_NOT_ELAPSED" in error_str:
                logger.warning(f"Back-to-back interval not elapsed: {error_str}")
                # TODO: handle BACKTOBACK_INTERVAL_NOT_ELAPSED — hardware cooldown active; wait and retry or skip
                return ModuleResult(success=False, error=error_str, hole_completed=False)
            else:
                logger.error(f"Bridge error during encode: {error_str}", exc_info=True)
                # TODO: handle other bridge RuntimeErrors not yet identified
                return ModuleResult(success=False, error=error_str, hole_completed=False)
        except Exception as e:
            logger.error(f"XPrime execute failed: {e}", exc_info=True)
            return ModuleResult(success=False, error=str(e), hole_completed=False)

    async def shutdown(self) -> None:
        logger.info("XPrime priming module shutdown")


# ---------------------------------------------------------------------------
# Blast data helpers (shared with encode_primer.py logic)
# ---------------------------------------------------------------------------

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
    for value in hole.values():
        if isinstance(value, list) and len(value) > 0:
            return value
    return []


def _is_encoded(primer: dict) -> bool:
    return bool(primer.get("detStatus") and primer.get("DRXId"))


def _find_next_unencoded(holes: list):
    """Return (primer_dict, hole_name, drx_index) for the next unencoded primer, or (None, None, None)."""
    for hole in holes:
        if not isinstance(hole, dict):
            continue
        hole_name = str(hole.get("name", ""))
        primers = _get_primers(hole)
        for i, primer in enumerate(primers):
            if not _is_encoded(primer):
                return primer, hole_name, i
    return None, None, None


def _extract_primer_uid(primer: dict) -> str:
    for key in ("primerUID", "uid", "uuid", "id", "primerUid"):
        if key in primer and primer[key]:
            return primer[key]
    return ""


def _extract_hole_ring(primer: dict) -> str:
    for key in ("holeRing", "ring"):
        if key in primer and primer[key] is not None:
            return str(primer[key])
    return ""
