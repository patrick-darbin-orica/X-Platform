import redis
import json
import numpy as np
import cv2
import binascii
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--ip", default="192.168.1.30")
parser.add_argument("--mono", action="store_true")
args = parser.parse_args()
mono = args.mono
ip = args.ip

if mono:
    channel = "mono"
else:
    channel = "night_vision"

color = (0, 255, 0)  # Green
thickness = 2
length_forward = 405
length_backward = 235
length_top = 330
length_bottom = 150  # Half-length of the cross-hair lines

def show_webp_stream(channel=channel):
    r = redis.Redis(host=ip, port=6379, db=0)
    pubsub = r.pubsub()
    pubsub.subscribe(channel)

    print(f"Subscribed to Redis channel: {channel}")
    try:
        for message in pubsub.listen():
            if message['type'] != 'message':
                continue

            try:
                # Parse JSON message
                data = json.loads(message['data'])

                # Decode WebP image from hex string
                hex_data = data['frame']
                webp_bytes = binascii.unhexlify(hex_data)
                webp_array = np.frombuffer(webp_bytes, dtype=np.uint8)
                frame = cv2.imdecode(webp_array, cv2.IMREAD_COLOR)  # or IMREAD_GRAYSCALE

                if mono:
                    color = (0,255,0)
                    height, width = frame.shape[:2]
                    center_x, center_y = width // 2, height // 2
                    center_x += -118
                    center_y += 198

                    # Horizontal line
                    cv2.line(frame, (center_x - length_backward, center_y), (center_x + length_forward, center_y),
                             color, thickness)

                    # Vertical line
                    cv2.line(frame, (center_x, center_y - length_top), (center_x, center_y + length_bottom), color,
                             thickness)
                else:
                    color = (0, 0, 255)  # Red
                    height, width = frame.shape[:2]
                    center_x, center_y = width // 2, height // 2
                    center_x2, center_y2 = width // 2, height // 2

                    center_x += -188
                    center_y += 198

                    center_x2 += 308
                    center_y2 += 198

                    # Horizontal line
                    cv2.line(frame, (center_x - length_backward, center_y), (center_x + length_forward, center_y),
                             color, thickness)

                    # # Vertical line
                    # cv2.line(frame, (center_x, center_y - length_top), (center_x, center_y + length_bottom), color,
                    #          thickness)
                    #
                    # # Vertical line
                    # cv2.line(frame, (center_x2, center_y2 - length_top), (center_x2, center_y2 + length_bottom), color,
                    #          thickness)

                    # Vertical line
                    cv2.line(frame, (84, 480), (204, 0), color,
                             thickness)

                    # Vertical line
                    cv2.line(frame, (640, 400), (500, 0), color,
                             thickness)

                    # Vertical line
                    cv2.line(frame, (362, 400), (352, 0), color,
                             thickness)

                # Display the frame
                cv2.imshow(f"{channel} Stream (WebP)", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            except Exception as e:
                print(f"Error decoding frame: {e}")

    except redis.exceptions.ConnectionError as e:
        print(f"Redis connection error: {e}")

    finally:
        cv2.destroyAllWindows()
        pubsub.unsubscribe(channel)
        print("Unsubscribed and closed.")

show_webp_stream()
