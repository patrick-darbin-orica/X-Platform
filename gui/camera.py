#!/usr/bin/env python3
"""RGB camera streamer for OAK-D W PoE.

Connects to the camera by IP, grabs RGB frames, and writes them to
/tmp/amiga_camera_frame.jpg for the Flask video_feed route to serve.

Usage:
    python3 gui/camera.py
    python3 gui/camera.py --ip 10.95.76.12
"""

import argparse
import sys
import time
from pathlib import Path

import depthai as dai

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils.camera_frame_cache import set_latest_frame

CAMERA_IP = "10.95.76.12"
RESOLUTION = (1280, 720)
FPS = 15


def run(ip: str) -> None:
    print(f"Connecting to OAK-D W PoE at {ip} ...")
    device_info = dai.DeviceInfo(ip)
    device = dai.Device(device_info)
    print("Connected.")

    pipeline = dai.Pipeline(device)

    cam = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_A)
    q = cam.requestOutput(RESOLUTION, dai.ImgFrame.Type.BGR888p).createOutputQueue(
        maxSize=1, blocking=False
    )

    pipeline.start()
    print(f"Streaming RGB at {RESOLUTION[0]}x{RESOLUTION[1]} {FPS}fps → /tmp/amiga_camera_frame.jpg")

    with pipeline:
        while True:
            frame = q.get()
            if frame is not None:
                set_latest_frame(frame.getCvFrame())
            time.sleep(1 / FPS)


def main() -> None:
    parser = argparse.ArgumentParser(description="OAK-D W PoE RGB streamer")
    parser.add_argument("--ip", default=CAMERA_IP, help="Camera IP address")
    args = parser.parse_args()

    while True:
        try:
            run(args.ip)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:
            print(f"Camera error: {e} — retrying in 3s...")
            time.sleep(3)


if __name__ == "__main__":
    main()
