# windows_joystick_client.py
import pygame
import socket
import json
import time

HOST = '172.26.161.16'  # Replace with your WSL IP
PORT = 65432


# Initialize pygame and joystick
pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("No joystick detected.")
    pygame.quit()
    exit()

joystick = pygame.joystick.Joystick(0)
joystick.init()

while True:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            print(f"Connecting to WSL server at {HOST}:{PORT}...")
            s.connect((HOST, PORT))
            print("Connected!")

            try:
                while True:
                    pygame.event.pump()
                    x = -joystick.get_axis(3) * 0.4  # Forward/backward
                    y = joystick.get_axis(2) * -0.3  # Left/right

                    data = json.dumps({'x': x, 'y': y}) + '\n'
                    s.sendall(data.encode('utf-8'))
                    time.sleep(0.01)
            except KeyboardInterrupt:
                print("Client shutting down.")
                break
            except ConnectionResetError:
                print("Connection Reset. Retrying...")
                time.sleep(1)
    except (ConnectionRefusedError, ConnectionResetError):
        print("Connection refused. Retrying in 1 second...")
        time.sleep(1)
