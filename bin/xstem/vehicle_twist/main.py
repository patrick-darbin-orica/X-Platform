# wsl_twist_server.py
import asyncio
import socket
import json
from pathlib import Path

from farm_ng.canbus.canbus_pb2 import Twist2d
from farm_ng.core.event_client import EventClient
from farm_ng.core.event_service_pb2 import EventServiceConfig
from farm_ng.core.events_file_reader import proto_from_json_file
from numpy import clip

HOST = '0.0.0.0'
PORT = 65432

MAX_LINEAR_VELOCITY_MPS = 1.0
MAX_ANGULAR_VELOCITY_RPS = 1.0

def update_twist_from_data(twist: Twist2d, data: dict):
    x = data.get('x', 0.0)
    y = data.get('y', 0.0)
    twist.linear_velocity_x = clip(x * MAX_LINEAR_VELOCITY_MPS, -MAX_LINEAR_VELOCITY_MPS, MAX_LINEAR_VELOCITY_MPS)
    twist.angular_velocity = clip(y * MAX_ANGULAR_VELOCITY_RPS, -MAX_ANGULAR_VELOCITY_RPS, MAX_ANGULAR_VELOCITY_RPS)
    return twist

async def main(service_config_path: Path):
    twist = Twist2d()
    config: EventServiceConfig = proto_from_json_file(service_config_path, EventServiceConfig())
    client: EventClient = EventClient(config)

    print(client.config)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        s.bind((HOST, PORT))
        s.listen(1)
        print(f"Waiting for joystick client on {HOST}:{PORT}...")
        conn, addr = s.accept()
        print(f"Connected by {addr}")
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        buffer = b""
        while True:
            data = conn.recv(1024)
            if not data:
                break
            buffer += data
            while b'\n' in buffer:
                line, buffer = buffer.split(b'\n', 1)
                try:
                    payload = json.loads(line.decode('utf-8'))
                    twist = update_twist_from_data(twist, payload)
                    print(f"Received: {payload} → Sending linear: {twist.linear_velocity_x:.3f}, angular: {twist.angular_velocity:.3f}")
                    await client.request_reply("/twist", twist)
                except json.JSONDecodeError:
                    print("Invalid JSON received")

            await asyncio.sleep(0.01)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--service-config", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.service_config))
