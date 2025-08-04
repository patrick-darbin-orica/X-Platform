import depthai as dai
import cv2

print("This")
# Create a pipeline
pipeline = dai.Pipeline()

# Define a source - monochrome camera (night vision)
cam_mono = pipeline.createMonoCamera()
cam_mono.setBoardSocket(dai.CameraBoardSocket.CAM_B)  # Use CAM_B for the monochrome camera
cam_mono.setResolution(dai.MonoCameraProperties.SensorResolution.THE_720_P)  # Set resolution

# Create an output stream
xout_video = pipeline.createXLinkOut()
xout_video.setStreamName("video")
cam_mono.out.link(xout_video.input)

# Connect to the device and start the pipeline
with dai.Device(pipeline) as device:
    # Set floodlight intensity (0.0 to 1.0)
    #device.setIrLaserDotProjectorIntensity(0.1)
    device.setIrFloodLightIntensity(1)  # Maximum brightness for no-light settings

    # Get output queue
    video_queue = device.getOutputQueue(name="video", maxSize=4, blocking=False)

    print("Starting night vision stream with floodlight. Press 'Q' to quit.")

    while True:
        # Get the video frame
        video_frame = video_queue.get()
        frame = video_frame.getCvFrame()  # Convert to OpenCV format

        # Apply visual enhancements (optional)
        frame = cv2.normalize(frame, None, 0, 255, cv2.NORM_MINMAX)  # Normalize brightness
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)  # Convert grayscale to BGR for display

        # Display the frame
        cv2.imshow("Night Vision Stream with Floodlight", frame)

        if cv2.waitKey(1) == ord('q'):  # Exit on pressing 'Q'
            break

# Release resources
cv2.destroyAllWindows()






# import depthai as dai
# import cv2
#
# # Function to select a specific camera
# def select_camera(pipeline, camera_index):
#     cam_mono = pipeline.createMonoCamera()
#     if camera_index == 0:
#         cam_mono.setBoardSocket(dai.CameraBoardSocket.CAM_A)
#     elif camera_index == 1:
#         cam_mono.setBoardSocket(dai.CameraBoardSocket.CAM_B)
#     elif camera_index == 2:
#         cam_mono.setBoardSocket(dai.CameraBoardSocket.CAM_C)
#     else:
#         raise ValueError("Invalid camera index. Please select 0, 1, or 2.")
#     cam_mono.setResolution(dai.MonoCameraProperties.SensorResolution.THE_720_P)
#     return cam_mono
#
# # Create a pipeline
# pipeline = dai.Pipeline()
#
# # Select the specific camera (change the index to 0, 1, or 2 as needed)
# camera_index = 0  # Example: selecting the second camera
# cam_mono = select_camera(pipeline, camera_index)
#
# # Create an output stream
# xout_video = pipeline.createXLinkOut()
# xout_video.setStreamName("video")
# cam_mono.out.link(xout_video.input)
#
# # Connect to the device and start the pipeline
# with dai.Device(pipeline) as device:
#     # Set floodlight intensity (0.0 to 1.0)
#     device.setIrFloodLightIntensity(1)  # Maximum brightness for no-light settings
#
#     # Get output queue
#     video_queue = device.getOutputQueue(name="video", maxSize=4, blocking=False)
#
#     print("Starting night vision stream with floodlight. Press 'Q' to quit.")
#
#     while True:
#         # Get the video frame
#         video_frame = video_queue.get()
#         frame = video_frame.getCvFrame()  # Convert to OpenCV format
#
#         # Apply visual enhancements (optional)
#         frame = cv2.normalize(frame, None, 0, 255, cv2.NORM_MINMAX)  # Normalize brightness
#         frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)  # Convert grayscale to BGR for display
#
#         # Display the frame
#         cv2.imshow("Night Vision Stream with Floodlight", frame)
#
#         if cv2.waitKey(1) == ord('q'):  # Exit on pressing 'Q'
#             break
#
# # Release resources
# cv2.destroyAllWindows()






# import cv2
#
# # IP camera URL
# ip_camera_url = "http://10.95.76.12/"
#
# # Connect to the IP camera
# cap = cv2.VideoCapture(ip_camera_url)
#
# if not cap.isOpened():
#     print("Error: Could not open video stream from IP camera.")
#     exit()
#
# print("Starting video stream from IP camera. Press 'Q' to quit.")
#
# while True:
#     # Capture frame-by-frame
#     ret, frame = cap.read()
#     if not ret:
#         print("Error: Could not read frame from IP camera.")
#         break
#
#     # Apply visual enhancements (optional)
#
#     frame = cv2.normalize(frame, None, 0, 255, cv2.NORM_MINMAX) # Normalize brightness
#
#     frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR) # Convert grayscale to BGR for display
#
#
#     # Display the frame
#
#     cv2.imshow("IP Camera Stream", frame)
#
#
#     if cv2.waitKey(1) == ord('q'):
#         break
#
# # Release resources
# cap.release()
# cv2.destroyAllWindows()


