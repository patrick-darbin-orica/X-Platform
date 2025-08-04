import math
import matplotlib.pyplot as plt


def calculate_point_on_line(coord1, coord2, n, p):
    """
    Calculate the position (Xt, Yt) of a point on the line defined by two coordinates that is n meters from point p.

    Parameters:
    coord1: Tuple containing the first coordinate (x1, y1) or (lat1, lon1)
    coord2: Tuple containing the second coordinate (x2, y2) or (lat2, lon2)
    n: Distance in meters from point p
    p: Index of the reference point (0 or 1)

    Returns:
    (Xt, Yt): Position of the point on the line that is n meters from point p
    """
    # Extract coordinates
    x1, y1 = coord1
    x2, y2 = coord2

    # Calculate the distance between the two points
    distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    # Calculate the unit vector along the line
    unit_vector_x = (x2 - x1) / distance
    unit_vector_y = (y2 - y1) / distance

    # Determine the reference point
    if p == 0:
        ref_x, ref_y = x1, y1
    else:
        ref_x, ref_y = x2, y2

    # Calculate the position of the target point
    Xt = ref_x + n * unit_vector_x
    Yt = ref_y + n * unit_vector_y

    return Xt, Yt


# Example usage
coord1 = (0.017, 0.048)  # Example coordinate 1
coord2 = (0.020, 0.050)  # Example coordinate 2
n = -0.05  # Distance in meters from point p
p = 0  # Reference point index

# Calculate the position of the target point
Xt, Yt = calculate_point_on_line(coord1, coord2, n, p)

plt.scatter(coord1[0], coord1[1], label="P0")
plt.scatter(coord2[0], coord2[1], label="P1")
plt.scatter(Xt, Yt, label="Pt")
plt.legend()
plt.show()

print(f"The position of the point on the line that is {n} meters from point {p} is ({Xt}, {Yt}).")