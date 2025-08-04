import amiga_sdk

# Initialize the Amiga platform
amiga = amiga_sdk.Amiga()


# Function to move the Amiga based on x and y values
def move_amiga(x, y):
    if x > 0:
        amiga.move_forward(x)
        print(f"Moving forward {x} cm")
    elif x < 0:
        amiga.move_backward(-x)
        print(f"Moving backward {-x} cm")

    if y > 0:
        amiga.move_right(y)
        print(f"Moving right {y} cm")
    elif y < 0:
        amiga.move_left(-y)
        print(f"Moving left {-y} cm")


# Example usage
x = 10  # Move forward 10 cm
y = -5  # Move left 5 cm
move_amiga(x, y)
