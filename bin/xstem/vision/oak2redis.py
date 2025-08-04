import depthai as dai
import cv2
import redis
import json
from datetime import datetime

# Initialize Redis client
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Create a pipeline
pipeline = dai.Pipeline()

mono = False
if mono:
    # Configure the monochrome camera
    cam_mono = pipeline.createMonoCamera()
    cam_mono.setBoardSocket(dai.CameraBoardSocket.CAM_B)
    cam_mono.setResolution(dai.MonoCameraProperties.SensorResolution.THE_400_P)
    cam_mono.setFps(5)
else:
# Configure the monochrome camera
    cam_mono = pipeline.createColorCamera()
    cam_mono.setBoardSocket(dai.CameraBoardSocket.CAM_A)
    cam_mono.setResolution(dai.ColorCameraProperties.SensorResolution.THE_1080_P)
    cam_mono.setFps(3)

# Create an output stream
xout_video = pipeline.createXLinkOut()
xout_video.setStreamName("video")

if mono:
    cam_mono.out.link(xout_video.input)
else:
    cam_mono.video.link(xout_video.input)

# Start the pipeline
with dai.Device(pipeline) as device:
    device.setIrFloodLightIntensity(1.0)  # Max floodlight

    video_queue = device.getOutputQueue(name="video", maxSize=4, blocking=False)

    print("Streaming night vision frames. Press Ctrl+C to stop.")

    try:
        while True:
            video_frame = video_queue.get()
            frame = video_frame.getCvFrame()

            if not mono:
                frame = cv2.resize(frame, (640, 480), interpolation=cv2.INTER_AREA)

            _, buffer = cv2.imencode('.webp', frame, [cv2.IMWRITE_WEBP_QUALITY, 30])
            payload = {
                "timestamp": datetime.now().isoformat(),
                "frame": buffer.tobytes().hex()  # Send as hex string
            }
            redis_client.publish("night_vision", json.dumps(payload))

            # Prepare data to publish
            #payload = {
            #    "timestamp": datetime.now().isoformat(),
            #    "frame": frame.tolist()  # Convert NumPy array to list for JSON serialization
            #}

            # Publish to Redis
            #redis_client.publish("night_vision", json.dumps(payload))

    except KeyboardInterrupt:
        print("Stream stopped.")

cv2.destroyAllWindows()
