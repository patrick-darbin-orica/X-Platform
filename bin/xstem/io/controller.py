import pygame
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Initialize Pygame
pygame.init()
pygame.joystick.init()

# Check for controller
if pygame.joystick.get_count() == 0:
    print("No joystick connected")
    exit()

# Initialize the controller
joystick = pygame.joystick.Joystick(0)
joystick.init()

# Set up the plot
fig, ax = plt.subplots()
x_data, y_data = [], []
ln, = plt.plot([], [], 'ro')

def init():
    ax.set_xlim(-1, 1)
    ax.set_ylim(-1, 1)
    return ln,

def update(frame):
    pygame.event.pump()
    x = joystick.get_axis(0)  # Left thumbstick X-axis
    y = joystick.get_axis(1)  # Left thumbstick Y-axis
    x_data.append(x)
    y_data.append(y)
    ln.set_data(x_data, y_data)
    return ln,

ani = FuncAnimation(fig, update, init_func=init, blit=True)

def print_button_events():
    for event in pygame.event.get():
        if event.type == pygame.JOYBUTTONDOWN:
            print(f"Button {event.button} pressed")

# Run the animation and button event loop
while True:
    print_button_events()
    plt.pause(0.01)
