import math

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from farm_ng_core_pybind import Isometry3F64
from farm_ng_core_pybind import Pose3F64
from farm_ng_core_pybind import Rotation3F64


def equivalent_angle(x):
    """
        This function takes an angle in radians and returns the equivalent angle less than Pi.
    """
    # Normalize the angle to be within the range [0, 2*Pi)
    x = x % (2 * np.pi)

    # If the angle is greater than or equal to Pi, subtract 2*Pi to get the equivalent angle less than Pi
    if x >= math.pi:
        x -= 2 * np.pi

    return x

def latlong_to_xy(reference_point, target_points):
    """
    Convert latitude and longitude to X/Y coordinates relative to a reference point.

    Parameters:
    reference_point: Tuple containing latitude and longitude of the reference point (RTK station or moving object)
    target_points: 2D array containing latitude and longitude of the target points

    Returns:
    2D array with X/Y coordinates relative to the reference point
    """
    lat1, lon1 = reference_point
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)

    # Radius of the Earth in meters
    R = 6378137.0

    # Convert degrees to radians for target points
    target_points_rad = np.radians(target_points)

    # Differences in coordinates
    dlat = target_points_rad[:, 0] - lat1_rad
    dlon = target_points_rad[:, 1] - lon1_rad

    # Calculate X and Y coordinates
    y = R * dlon * np.cos((lat1_rad + target_points_rad[:, 0]) / 2)
    x = R * dlat

    return np.column_stack((x, -y))

def quaternion_to_rotation_matrix(quaternion):
    """
    Calculate the rotation matrix from a unit quaternion.

    Parameters:
    quaternion (dict): A dictionary representing the unit quaternion with keys 'real' and 'imag'.

    Returns:
    numpy.ndarray: A 3x3 rotation matrix.
    """
    real = quaternion['real']
    imag = quaternion['imag']
    x, y, z = imag.get('x', 0), imag.get('y', 0), imag.get('z', 0)

    # Calculate the rotation matrix elements
    R = np.array([
        [1 - 2*y**2 - 2*z**2, 2*x*y - 2*z*real, 2*x*z + 2*y*real],
        [2*x*y + 2*z*real, 1 - 2*x**2 - 2*z**2, 2*y*z - 2*x*real],
        [2*x*z - 2*y*real, 2*y*z + 2*x*real, 1 - 2*x**2 - 2*y**2]
    ])

    return R

def rotation_matrix_to_quaternion(matrix):
    """
    Calculate the unit quaternion from a rotation matrix.

    Parameters:
    matrix (numpy.ndarray): A 3x3 rotation matrix.

    Returns:
    dict: A dictionary representing the unit quaternion with keys 'real' and 'imag'.
    """
    # Ensure the matrix is a 3x3 numpy array
    if not isinstance(matrix, np.ndarray) or matrix.shape != (3, 3):
        raise ValueError("Input must be a 3x3 numpy array.")

    # Calculate the trace of the matrix
    trace = np.trace(matrix)

    if trace > 0:
        s = 0.5 / np.sqrt(trace + 1.0)
        real = 0.25 / s
        x = (matrix[2, 1] - matrix[1, 2]) * s
        y = (matrix[0, 2] - matrix[2, 0]) * s
        z = (matrix[1, 0] - matrix[0, 1]) * s
    elif (matrix[0, 0] > matrix[1, 1]) and (matrix[0, 0] > matrix[2, 2]):
        s = 2.0 * np.sqrt(1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2])
        real = (matrix[2, 1] - matrix[1, 2]) / s
        x = 0.25 * s
        y = (matrix[0, 1] + matrix[1, 0]) / s
        z = (matrix[0, 2] + matrix[2, 0]) / s
    elif matrix[1, 1] > matrix[2, 2]:
        s = 2.0 * np.sqrt(1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2])
        real = (matrix[0, 2] - matrix[2, 0]) / s
        x = (matrix[0, 1] + matrix[1, 0]) / s
        y = 0.25 * s
        z = (matrix[1, 2] + matrix[2, 1]) / s
    else:
        s = 2.0 * np.sqrt(1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1])
        real = (matrix[1, 0] - matrix[0, 1]) / s
        x = (matrix[0, 2] + matrix[2, 0]) / s
        y = (matrix[1, 2] + matrix[2, 1]) / s
        z = 0.25 * s

    quaternion = {
        'real': real,
        'imag': {
            'x': x,
            'y': y,
            'z': z
        }
    }

    return quaternion


def calculate_relative_positions(origin, targets):
    """
    Calculate X/Y positions of targets relative to an origin (RTK station or moving object).

    Parameters:
    origin: Tuple containing latitude and longitude of the origin (lat, lon)
    targets: List of tuples containing latitude and longitude of target points [(lat, lon), ...]

    Returns:
    relative_positions: List of tuples containing X/Y positions relative to the origin [(x, y), ...]
    """
    origin_lat, origin_lon = origin
    relative_positions = []

    for target in targets:
        target_lat, target_lon = target
        x, y = latlong_to_xy(origin_lat, origin_lon, target_lat, target_lon)
        relative_positions.append((x, y))

    return relative_positions

def create_pose_from_arrays(translation_array, rotation_angle=0):
    zero_tangent = np.zeros((6, 1), dtype=np.float64)
    translation = np.asarray(translation_array)
    rotation = Rotation3F64.Rz(rotation_angle)
    a_from_b = Isometry3F64(translation=translation, rotation=rotation)
    pose: Pose3F64 = Pose3F64(a_from_b=a_from_b, frame_a="world", frame_b="robot",
                               tangent_of_b_in_a=zero_tangent)
    return pose


def calculate_rotation_matrix_and_angle(current_rotation_matrix, current_x, current_y, target_x, target_y):
    # Calculate the direction vector from point A to point B
    direction_vector = np.array([target_x - current_x, target_y - current_y])

    # Normalize the direction vector
    norm = np.linalg.norm(direction_vector)
    if norm == 0:
        raise ValueError("The current and target positions are the same. No rotation needed.")
    direction_vector = direction_vector / norm

    # Calculate the angle between the x-axis and the direction vector
    angle = np.arctan2(direction_vector[1], direction_vector[0])

    # Create the rotation matrix for the calculated angle
    rotation_matrix = np.array([
        [np.cos(angle), -np.sin(angle), 0],
        [np.sin(angle), np.cos(angle), 0],
        [0, 0, 1]
    ])

    # Combine the current rotation matrix with the new rotation matrix
    new_rotation_matrix = np.dot(rotation_matrix, current_rotation_matrix)

    # Convert angle from radians to degrees
    angle_degrees = np.degrees(angle)

    return new_rotation_matrix, angle_degrees

def rotation_angle_from_matrix(matrix):
    """
    Calculate the rotation angle from the origin given a 3x3 rotation matrix.

    Parameters:
    matrix (numpy.ndarray): A 3x3 rotation matrix.

    Returns:
    float: The rotation angle in degrees.
    """
    # Ensure the matrix is a 3x3 numpy array
    if not isinstance(matrix, np.ndarray) or matrix.shape != (3, 3):
        raise ValueError("Input must be a 3x3 numpy array.")

    # Calculate the angle using the arccosine of the trace of the matrix
    angle_rad = np.arccos((np.trace(matrix) - 1) / 2)

    # Convert the angle from radians to degrees
    angle_deg = np.degrees(angle_rad)

    return angle_deg


def calculate_distance(point1, point2):
    """
    Calculate the Euclidean distance between two points.

    Parameters:
    point1 (array-like): Coordinates of the first point (e.g., [x1, y1]).
    point2 (array-like): Coordinates of the second point (e.g., [x2, y2]).

    Returns:
    float: The Euclidean distance between the two points.
    """
    point1 = np.array(point1)
    point2 = np.array(point2)
    distance = np.linalg.norm(point1 - point2)
    return distance

def main():
    if False:
        path = r"C:\Users\natal\OneDrive - Orica\Documents\Orica\Xdipper\locations.csv"

        loc = pd.read_csv(path)
        loc["lat"] = loc["lat"].astype(np.float64)
        loc["long"] = loc["long"].astype(np.float64)

        lats = loc["lat"].astype(np.float64)
        longs = loc["long"].astype(np.float64)

        points = [(lat, long) for lat, long in zip(lats, longs)]

        rtk_station = points[-1]
        targets = points[:-1]

        # Example usage
        # rtk_station = (49.2827, -123.1207)  # Example RTK station coordinates (latitude, longitude)
        # targets = [
        #     (49.2820, -123.1170),  # Example target coordinates (latitude, longitude)
        #     (49.2830, -123.1210),
        # ]
        moving_object = (49.2810, -123.1190)  # Example moving object coordinates (latitude, longitude)

        # Calculate positions relative to RTK station once
        relative_positions_to_rtk = calculate_relative_positions(rtk_station, targets)

        loc.loc[loc["x"].isna(), "x"] = np.asarray(relative_positions_to_rtk).T[0]
        loc.loc[loc["y"].isna(), "y"] = np.asarray(relative_positions_to_rtk).T[1]
        loc.to_csv(r"C:\Users\natal\OneDrive - Orica\Documents\Orica\Xdipper\locations_converted.csv")

        plt.scatter(loc.x, loc.y, c="green")
        # Add labels to each point
        for i in range(len(loc)):
            plt.text(loc['x'][i] + 0.1, loc['y'][i], loc['name'][i], fontsize=10)

        plt.xlabel('x')
        plt.ylabel('y')
        plt.title('Scatter plot of x vs y converted from Lat/Long')
        plt.grid(True)
        plt.show()
        plt.show()
    else:
        path = r"C:\Users\a98024\OneDrive - Orica\Documents\Orica\Xdipper\locations_converted.csv"
        loc = pd.read_csv(path)

        rtk_station = loc.iloc[0]
        targets = loc.iloc[1:11]
        waypoints = loc.iloc[11:]

        plt.scatter(rtk_station.x, rtk_station.y, c="green")
        plt.scatter(targets.x, targets.y, c="red")
        plt.scatter(waypoints.x, waypoints.y, c="blue")
        # Add labels to each point
        for i in range(len(loc)):
            plt.text(loc['x'][i]+0.1, loc['y'][i], loc['name'][i], fontsize=10)

        plt.xlabel('x')
        plt.ylabel('y')
        plt.title('Scatter plot of x vs y converted from Lat/Long')
        plt.grid(True)
        plt.show()
        plt.show()

    # Calculate positions relative to moving object constantly
    relative_positions_to_moving_object = calculate_relative_positions(moving_object, targets)

    print("Relative positions to RTK station:", relative_positions_to_rtk)
    print("Relative positions to moving object:", relative_positions_to_moving_object)

if __name__ == "__main__":
    main()
