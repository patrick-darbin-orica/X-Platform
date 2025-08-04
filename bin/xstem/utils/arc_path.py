import matplotlib.pyplot as plt
import math


def calculate_arc_path(start, end, direction_point, radius=1.0):
    x0, y0 = start
    xA, yA = end
    xB, yB = direction_point

    # Calculate the angle to the direction point from the end point
    angle_to_direction = math.atan2(yB - yA, xB - xA)

    # Calculate the angle from the start point to the end point
    angle_to_end = math.atan2(yA - y0, xA - x0)

    # Calculate the center of the arc
    mid_x = (x0 + xA) / 2
    mid_y = (y0 + yA) / 2
    dx = xA - x0
    dy = yA - y0
    dist = math.sqrt(dx ** 2 + dy ** 2)

    if dist == 0 or radius < dist / 2:
        required_radius = dist / 2
        print(f"Required radius is {required_radius} meters.")
        return [(x0, y0), (xA, yA)]

    h = math.sqrt(radius ** 2 - (dist / 2) ** 2)

    # Determine the arc direction
    arc_direction = 1 if angle_to_direction > angle_to_end else -1

    center_x = mid_x + arc_direction * h * dy / dist
    center_y = mid_y - arc_direction * h * dx / dist

    # Generate points along the arc
    num_points = 100
    path = []

    start_angle = math.atan2(y0 - center_y, x0 - center_x)
    end_angle = math.atan2(yA - center_y, xA - center_x)

    for i in range(num_points + 1):
        t = i / num_points
        angle = start_angle + t * (end_angle - start_angle)
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        path.append((x, y))

    return path


# Example usage
start = (0, 0)  # Starting position
end = (5, 8)  # Ending position A
direction_point = (10, 8)  # Direction point B

# Calculate the path
path = calculate_arc_path(start, end, direction_point)

# Plotting the points and path
plt.figure(figsize=(8, 8))
plt.plot(*zip(*path), label='Arc Path')
plt.scatter(*start, color='red', label='Start Point (0)')
plt.scatter(*end, color='green', label='End Point (A)')
plt.scatter(*direction_point, color='blue', label='Direction Point (B)')
plt.legend()
plt.xlabel('X')
plt.ylabel('Y')
plt.title('Arc Path from Start to End Facing Direction Point')
plt.grid(True)
plt.show()

