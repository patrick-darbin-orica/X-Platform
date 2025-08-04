import asyncio
import redis
import json
import math
import websockets
import ast
from utils import *
import pdb

#pdb.set_trace()
# Calibration constants
# reference_voltage = 1.278654563
# reference_water_contact = 0.475634483
# reference_td_voltage = 6.224025124
#
# core_radius = 1
# drum_width = 1
# line_diameter = 1

# Redis setup
r = redis.Redis(host="localhost", port=6379, db=0)
pubsub = r.pubsub()
pubsub.subscribe("encoder_data")

# Calibration functions
# def calibrate_tension(x):
#     dV = reference_voltage - x
#     dmV = dV * 1000
#     kgs = (0.1691 * dmV) + 0.0995
#     return kgs
#
# def calibrate_water_contact(x):
#     return round((x - reference_water_contact) / 2.0 ,2)
#
# def calibrate_td_contact(x):
#     return round((reference_td_voltage - x) / 2.5, 2)
#
# def calculate_line_depth(total_rotations):
#     return total_rotations * -1

# WebSocket clients
connected_clients = set()

async def handle_client(websocket, path):
    connected_clients.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        connected_clients.remove(websocket)

async def redis_listener():
    print("Starting Redis listener...")
    while True:
        message = pubsub.get_message()
        if message and message['type'] == 'message':
            try:
                raw = message['data']
                if isinstance(raw, bytes):
                    entry = ast.literal_eval(raw.decode('utf-8'))
                    timestamp = round(entry[0], 2)
                    net_counts = entry[1] * 0
                    depth = calculate_line_depth(entry[2])
                    tension = calibrate_tension(entry[3])
                    water_sensor = calibrate_water_contact(entry[4])
                    td_sensor = calibrate_td_contact(entry[5])

                    payload = {
                        "timestamp": timestamp,
                        "depth": depth,
                        "tension": tension,
                        "water": water_sensor,
                        "td": td_sensor
                    }

                    print("Broadcasting:", payload)

                    if connected_clients:
                        await asyncio.gather(*[
                            client.send(json.dumps(payload))
                            for client in connected_clients
                        ])
            except Exception as e:
                print("Error parsing message:", e)
        await asyncio.sleep(0.01)

async def main():
    server = await websockets.serve(handle_client, "0.0.0.0", 6789)
    asyncio.create_task(redis_listener())
    print("WebSocket server running on ws://0.0.0.0:6789")
    await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())