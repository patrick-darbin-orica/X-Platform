from flask import Flask, render_template, Response, jsonify, redirect
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import cv2
import random
import json
import asyncio
from pathlib import Path

app = Flask(__name__)

# Sample DataFrame
df = pd.DataFrame({
    'Row': [1, 2, 3],
    'Hole_Name': ['A', 'B', 'C'],
    'Planned_X': [1, 2, 3],
    'Planned_Y': [3, 2, 1],
    'Real_X': [1.1, 1.9, 2.8],
    'Real_Y': [2.9, 2.1, 0.9],
    'Status': ['OK', 'Warning', 'Error']
})

# Function to generate plot
def create_plot():
    plt.figure(figsize=(5, 5))
    plt.scatter(df['Planned_X'], df['Planned_Y'], edgecolor='black', facecolor='none', s=100, label='Planned')
    colors = {'OK': 'green', 'Warning': 'yellow', 'Error': 'red'}
    plt.scatter(df['Real_X'], df['Real_Y'], c=df['Status'].apply(lambda x: colors[x]), s=100, label='Real')
    plt.xlim(0, 5)
    plt.ylim(0, 5)
    plt.xlabel('X Coordinate')
    plt.ylabel('Y Coordinate')
    plt.title('XY Coordinate Plot')
    plt.legend()
    plt.grid()
    plt.savefig('static/plot.png')
    plt.close()

@app.route('/')
def home():
    return redirect('/bench')  # Redirect to the /bench route

@app.route('/bench')
def bench():
    create_plot()
    return render_template('bench.html')

async def generate_video_stream(service_config_path: Path) -> None:
    """Run the camera service client.

    Args:
        service_config_path (Path): The path to the camera service config.
    """
    # Create a client to the camera service
    config: EventServiceConfig = proto_from_json_file(service_config_path, EventServiceConfig())

    async for event, message in EventClient(config).subscribe(config.subscriptions[0], decode=True):
        # Find the monotonic driver receive timestamp, or the first timestamp if not available.
        stamp = (
            get_stamp_by_semantics_and_clock_type(event, StampSemantics.DRIVER_RECEIVE, "monotonic")
            or event.timestamps[0].stamp
        )

        # Print the timestamp and metadata
        print(f"Timestamp: {stamp}\n")
        print(f"Meta: {message.meta}")
        print("###################\n")

        yield message

        # # Cast image data bytes to numpy and decode
        # image = cv2.imdecode(np.frombuffer(message.image_data, dtype="uint8"), cv2.IMREAD_UNCHANGED)
        #
        # # Visualize the image
        # cv2.namedWindow("image", cv2.WINDOW_FULLSCREEN)
        # cv2.imshow("image", image)
        # cv2.waitKey(1)

@app.route('/video_feed')
async def video_feed():
    service_config_path = Path("service_configs/service_config2.json")
    resp = generate_video_stream(service_config_path)
    print (resp)
    return Response(generate_video_stream(service_config_path),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/dynamic_json')
def dynamic_json():
    # Generate a dynamic JSON object
    data = {
        'timestamp': pd.Timestamp.now().isoformat(),
        'value': random.randint(1, 100),  # Example dynamic value
        'status': random.choice(['OK', 'Warning', 'Error'])
    }
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)