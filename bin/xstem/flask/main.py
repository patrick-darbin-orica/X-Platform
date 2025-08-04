import sys
from flask import Flask, render_template, Response, jsonify
from flask_socketio import SocketIO, emit
import matplotlib
import matplotlib.pyplot as plt
matplotlib.use('Agg')
import numpy as np
import cv2
import asyncio
import random
import threading
import pandas as pd
from pathlib import Path
from farm_ng.canbus.packet import MotorState
from farm_ng.core.events_file_reader import proto_from_json_file
from farm_ng.core.event_service_pb2 import EventServiceConfig
from farm_ng.core.stamp import StampSemantics
from farm_ng.core.event_client import EventClient
from farm_ng.core.stamp import get_stamp_by_semantics_and_clock_type
import time

app = Flask(__name__)
socketio = SocketIO(app)

# Function to read the CSV file and return the data as a dictionary
def read_csv_data():
    df = pd.read_csv('tmp/drill_plan_tmp.csv')
    data = {
        "x": df['x'].tolist(),
        "y": df['y'].tolist(),
        "status": df['status'].tolist()
    }
    return data

# Route to serve the plot data as JSON
@app.route('/plot_data')
def plot_data():
    data = read_csv_data()
    return jsonify(data)

# Function to generate the plot and save it as an image
def generate_plot():
    data = read_csv_data()
    plt.figure()
    plt.scatter(data['x'], data['y'], c='red')
    plt.xlabel('x')
    plt.ylabel('y')
    plt.title('Scatter plot of x vs y')
    plt.grid(True)
    plt.savefig('static/plot.png')
    plt.close()

# Background thread to update the plot periodically
def update_plot():
    while True:
        generate_plot()
        time.sleep(5)  # Update every 5 seconds

# Async function to generate two random numpy arrays for video stream
async def get_oak0(path="service_configs/service_config2.json") -> None:
    try:
        service_config_path = Path(path)
        config: EventServiceConfig = proto_from_json_file(service_config_path, EventServiceConfig())
        async for event, message in EventClient(config).subscribe(config.subscriptions[0], decode=True):
            stamp = (
                get_stamp_by_semantics_and_clock_type(event, StampSemantics.DRIVER_RECEIVE, "monotonic")
                or event.timestamps[0].stamp
            )
            image = cv2.imdecode(np.frombuffer(message.image_data, dtype="uint8"), cv2.IMREAD_UNCHANGED)
            yield image
    except:
        print("get Oak0 error")

async def get_oak1(path="service_configs/service_config2.json") -> None:
    color = (0, 255, 0)   # Green
    thickness = 2
    length_forward = 400
    length_backward = 230
    length_top = 300
    length_bottom = 110 # Half-length of the cross-hair lines



    try:
        service_config_path = Path(path)
        config: EventServiceConfig = proto_from_json_file(service_config_path, EventServiceConfig())
        async for event, message in EventClient(config).subscribe(config.subscriptions[1], decode=True):
            stamp = (
                get_stamp_by_semantics_and_clock_type(event, StampSemantics.DRIVER_RECEIVE, "monotonic")
                or event.timestamps[0].stamp
            )
            image = cv2.imdecode(np.frombuffer(message.image_data, dtype="uint8"), cv2.IMREAD_UNCHANGED)

            height, width = image.shape[:2]
            center_x, center_y = width // 2, height // 2
            center_x -= 86
            center_y += 90

            # Horizontal line
            cv2.line(image, (center_x - length_backward, center_y), (center_x + length_forward, center_y), color, thickness)

            # Vertical line
            cv2.line(image, (center_x, center_y - length_top), (center_x, center_y + length_bottom), color, thickness)
            yield image
    except:
        print("get oak1 error")

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
        _, buffer = cv2.imencode('.jpg', image0)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

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
        _, buffer = cv2.imencode('.jpg', image1)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')



# def generate_video_fpv():
#     cap = cv2.VideoCapture("http://172.26.160.1:8080/video")
#
#     if not cap.isOpened():
#         print("Error: Could not open video stream from Windows.")
#         return None  # Important: explicitly return None
#
#     while True:
#         ret, frame = cap.read()
#         if not ret:
#             print("Failed to grab frame from stream.")
#             continue
#
#         _, buffer = cv2.imencode('.jpg', frame)
#         frame_bytes = buffer.tobytes()
#
#         yield (b'--frame\r\n'
#                b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')




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


# @app.route('/video_feed_fpv')
# def video_feed_fpv():
#     try:
#         stream = generate_video_fpv()
#         if stream is None:
#             return "Camera stream not available", 503
#         return Response(stream, mimetype='multipart/x-mixed-replace; boundary=frame')
#     except Exception as e:
#         print("Video Feed FPV Error:", e)
#         return "Internal Server Error", 500


@app.route('/motor_states')
def motor_states():
    return render_template('motor_states.html')

@app.route('/get_motor_states')
def get_motor_states():
    motor_states_text = ""
    try:
        service_config_path = Path("service_configs/motor_service_config.json")
        config: EventServiceConfig = proto_from_json_file(service_config_path, EventServiceConfig())

        async def fetch_motor_states():
            nonlocal motor_states_text
            async for event, message in EventClient(config).subscribe(config.subscriptions[0], decode=True):
                motors = []
                for motor in message.motors:
                    motors.append(MotorState.from_proto(motor))

                motor_states_text = "\n###################\n"
                for motor in sorted(motors, key=lambda m: m.id):
                    motor_states_text += str(motor) + "\n"
                return motor_states_text

        asyncio.run(fetch_motor_states())
    except Exception as e:
        motor_states_text = f"Error in get_motor_states: {e}"

    return motor_states_text

if __name__ == '__main__':
    # Start the background thread to update the plot
    from threading import Thread
    thread = Thread(target=update_plot)
    thread.start()

    socketio.run(app, host='0.0.0.0', port=5000, debug=True)