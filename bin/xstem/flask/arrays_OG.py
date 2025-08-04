import sys

from flask import Flask, render_template, Response, jsonify
import matplotlib.pyplot as plt
import numpy as np
import cv2
import asyncio
import random
import threading
import pandas as pd
from pathlib import Path
from farm_ng.core.events_file_reader import proto_from_json_file
from farm_ng.core.event_service_pb2 import EventServiceConfig
from farm_ng.core.stamp import StampSemantics
from farm_ng.core.event_client import EventClient
from farm_ng.core.stamp import get_stamp_by_semantics_and_clock_type

app = Flask(__name__)

# Async function to generate two random numpy arrays for video stream
async def get_oak0(path="service_configs/service_config2.json") -> None:
    try:
        service_config_path = Path(path)
        # await asyncio.sleep(1)  # Simulate async operation

        config: EventServiceConfig = proto_from_json_file(service_config_path, EventServiceConfig())

        async for event, message in EventClient(config).subscribe(config.subscriptions[0], decode=True):
            # Find the monotonic driver receive timestamp, or the first timestamp if not available.
            stamp = (
                    get_stamp_by_semantics_and_clock_type(event, StampSemantics.DRIVER_RECEIVE, "monotonic")
                    or event.timestamps[0].stamp
            )
            # Cast image data bytes to numpy and decode
            image = cv2.imdecode(np.frombuffer(message.image_data, dtype="uint8"), cv2.IMREAD_UNCHANGED)
            # Yield the arrays for each loop iteration
            yield image
    except:
        print("get Oak0 error")


async def get_oak1(path="service_configs/service_config2.json") -> None:
    try:
        service_config_path = Path(path)
        # await asyncio.sleep(1)  # Simulate async operation

        config: EventServiceConfig = proto_from_json_file(service_config_path, EventServiceConfig())

        async for event, message in EventClient(config).subscribe(config.subscriptions[1], decode=True):
            # Find the monotonic driver receive timestamp, or the first timestamp if not available.
            stamp = (
                    get_stamp_by_semantics_and_clock_type(event, StampSemantics.DRIVER_RECEIVE, "monotonic")
                    or event.timestamps[0].stamp
            )
            # Cast image data bytes to numpy and decode
            image = cv2.imdecode(np.frombuffer(message.image_data, dtype="uint8"), cv2.IMREAD_UNCHANGED)
            # Yield the arrays for each loop iteration
            yield image
    except:
        print("get oak1 error")

async def get_states(path="service_configs/service_config2.json") -> None:
    try:
        service_config_path = Path(path)
        # await asyncio.sleep(1)  # Simulate async operation

        config: EventServiceConfig = proto_from_json_file(service_config_path, EventServiceConfig())

        async for event, message in EventClient(config).subscribe(config.subscriptions[1], decode=True):
            # Find the monotonic driver receive timestamp, or the first timestamp if not available.
            stamp = (
                    get_stamp_by_semantics_and_clock_type(event, StampSemantics.DRIVER_RECEIVE, "monotonic")
                    or event.timestamps[0].stamp
            )
            # Cast image data bytes to numpy and decode
            image = cv2.imdecode(np.frombuffer(message.image_data, dtype="uint8"), cv2.IMREAD_UNCHANGED)
            # Yield the arrays for each loop iteration
            print(image)
            yield image
    except:
        print("get oak1 error")

# # Function to generate video stream
# def generate_video_stream():
#     loop0 = asyncio.new_event_loop()
#     loop1 = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop0)
#     asyncio.set_event_loop(loop1)
#     oak0_gen = get_oak0()
#     oak1_gen = get_oak1()
#
#     while True:
#         image0 = loop0.run_until_complete(oak0_gen.__anext__())
#         image1 = loop1.run_until_complete(oak1_gen.__anext__())
#         combined_frame = np.hstack((image0, image1))
#         # combined_frame = image1# Combine the two images side by side
#
#         # Encode frame to JPEG
#         _, buffer = cv2.imencode('.jpg', combined_frame)
#         frame = buffer.tobytes()
#
#         yield (b'--frame\r\n'
#                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# Async function to generate dynamic JSON object
# async def generate_dynamic_json():
#     await asyncio.sleep(1)  # Simulate async operation
#     data = {
#         'timestamp': pd.Timestamp.now().isoformat(),
#         'value': random.randint(1, 100),
#         'status': random.choice(['OK', 'Warning', 'Error'])
#     }
#     return data

@app.route('/')
def home():
    return render_template('main.html')

def generate_video_stream_0():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    oak0_gen = get_oak0()

    while True:
        try:
            image0 = loop.run_until_complete(oak0_gen.__anext__())
        except:
            print(f"Error Video Stream 0:", sys.exc_info())
            continue

        # Encode frame to JPEG
        _, buffer = cv2.imencode('.jpg', image0)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# Function to generate video stream for image1
def generate_video_stream_1():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    oak1_gen = get_oak1()

    while True:
        try:
            image1 = loop.run_until_complete(oak1_gen.__anext__())
        except:
            print(f"Error Video Stream 1:", sys.exc_info())
            continue

        # Encode frame to JPEG
        _, buffer = cv2.imencode('.jpg', image1)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed_0')
def video_feed_0():
    try:
        return Response(generate_video_stream_0(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    except:
        print("Error Video Feed 0")

@app.route('/video_feed_1')
def video_feed_1():
    try:
        return Response(generate_video_stream_1(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    except:
        print("Video Feed 1")


@app.route('/plot_data')
def plot_data():
    data = {
        "designed": {
            "x": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            "y": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        },
        "current": {
            "x": 3.1,
            "y": 3.1
        },
        "completed": {
            "x": [0.1, 1.2, 1.9],
            "y": [-0.1, 1.1, 2.1]
        },
        "hole_id": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
    }
    return jsonify(data)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)