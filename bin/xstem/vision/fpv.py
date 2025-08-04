import cv2

def display_usb_camera(camera_index=0):
    """
    Display live video from a USB camera connected to a Windows machine.

    Parameters:
    - camera_index (int): Index of the camera (default is 0 for the first camera)
    """
    color = (0, 255, 0)  # Green
    thickness = 2
    length_forward = 405
    length_backward = 235
    length_top = 330
    length_bottom = 150  # Half-length of the cross-hair lines
    cap = cv2.VideoCapture(camera_index)


    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    print("Press 'q' to quit the video stream.")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame.")
            break

        height, width = frame.shape[:2]
        center_x, center_y = width // 2, height // 2
        center_x += -10
        center_y += 140

        # Horizontal line
        cv2.line(frame, (center_x - length_backward, center_y), (center_x + length_forward, center_y), color, thickness)

        # Vertical line
        cv2.line(frame, (center_x, center_y - length_top), (center_x, center_y + length_bottom), color, thickness)

        cv2.imshow("USB Camera Feed", frame)

        # Exit on pressing 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

display_usb_camera(0)
    

# windows_camera_stream.py
# from flask import Flask, Response
# import cv2
#
# app = Flask(__name__)
# cap = cv2.VideoCapture(1)
#
# def generate_frames():
#     while True:
#         success, frame = cap.read()
#         if not success:
#             break
#         _, buffer = cv2.imencode('.jpg', frame)
#         yield (b'--frame\r\n'
#                b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
#
# @app.route('/video')
# def video():
#     return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
#
# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=8080)


