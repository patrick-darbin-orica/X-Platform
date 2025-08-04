import amiga_sdk
import inputs

# Initialize the Amiga platform
amiga = amiga_sdk.Amiga()


# Function to map joystick values to movement commands
def map_joystick_to_movement(x, y, speed):
    if x > 0:
        amiga.move_forward(x * speed)
    elif x < 0:
        amiga.move_backward(-x * speed)

    if y > 0:
        amiga.move_right(y * speed)
    elif y < 0:
        amiga.move_left(-y * speed)


# Main function to read controller inputs and move the Amiga
def main():
    speed = 1.0  # Default speed multiplier
    while True:
        events = inputs.get_gamepad()
        for event in events:
            if event.ev_type == 'Absolute':
                if event.code == 'ABS_X':  # Left thumb joystick horizontal
                    x = event.state / 32767.0  # Normalize to range [-1, 1]
                elif event.code == 'ABS_Y':  # Left thumb joystick vertical
                    y = event.state / 32767.0  # Normalize to range [-1, 1]
                elif event.code == 'ABS_RX':  # Right thumb joystick horizontal
                    speed = (event.state / 32767.0) * 2  # Normalize and scale speed
                elif event.code == 'ABS_RY':  # Right thumb joystick vertical
                    speed = (event.state / 32767.0) * 2  # Normalize and scale speed

            # Move the Amiga based on joystick inputs
            map_joystick_to_movement(x, y, speed)


# Example usage
main()
