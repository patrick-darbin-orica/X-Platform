from farm_ng.core.event_client import EventClient
from farm_ng.core.event_service_pb2 import EventServiceConfig
from farm_ng.track.track_pb2 import Track
from farm_ng_core_pybind import Isometry3F64
from farm_ng_core_pybind import Pose3F64
from farm_ng_core_pybind import Rotation3F64
from farm_ng.core.events_file_reader import proto_from_json_file
from farm_ng.filter.filter_pb2 import FilterState
from farm_ng.track.track_pb2 import TrackFollowRequest
import asyncio
from google.protobuf.empty_pb2 import Empty
from xstem.utils.convert import (
    latlong_to_xy,
    calculate_relative_positions,
    create_pose_from_arrays,
    calculate_rotation_matrix_and_angle,
    calculate_distance,
    rotation_angle_from_matrix,
    equivalent_angle,
)
from xstem.farm_ng.track_builder import TrackBuilder
from xstem.farm_ng.track_plotter import plot
import matplotlib.pyplot as plt
from pathlib import Path
import pdb
import numpy as np
import pandas as pd
import time
from math import radians
import sys
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QDialogButtonBox,
    QLabel,
)
from PyQt5.QtGui import QDoubleValidator
from farm_ng.canbus.canbus_pb2 import Twist2d

from ..vehicle_twist.main import update_twist_from_data


X_OFFSET = 0
Y_OFFSET = 0

STARTING_POINT_ID = 4

import matplotlib.pyplot as plt

import math


def calculate_twist_for_arc(radius=12, duration=10):
    """
    Calculate the linear and angular velocity required to follow a 1/4 circle arc.

    Parameters:
    - radius (float): Radius of the arc in meters.
    - duration (float): Time in seconds to complete the arc.

    Returns:
    - linear_velocity (float): Linear velocity in m/s (negative for backward motion).
    - angular_velocity (float): Angular velocity in rad/s (negative for clockwise rotation).
    """
    arc_length = (math.pi / 2) * radius
    linear_velocity = -arc_length / duration
    angular_velocity = linear_velocity / radius
    return {"x": linear_velocity, "y": angular_velocity}


def plot_tuples(points):
    """
    Plots a list of (x, y) tuples on a 2D graph.

    Parameters:
        points (list of tuples): Each tuple contains (x, y) coordinates.
    """
    x_vals = [pt[0] for pt in points]
    y_vals = [pt[1] for pt in points]

    plt.figure(figsize=(8, 6))
    plt.plot(x_vals, y_vals, marker="o", linestyle="-", color="blue")
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.title("Plot of (x, y) Tuples")
    plt.grid(True)
    plt.axis("equal")
    plt.show()


def ask_question(message="Accept this pose (y/n)?"):
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    reply = QMessageBox.question(
        None,
        "XDipper Navigation",
        message,
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    res = "y" if reply == QMessageBox.Yes else "n"
    return res


def show_message(
    message="Make sure the filter has not diverged.\nPress OK to continue.",
):
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Information)
    msg.setWindowTitle("Notice")
    msg.setText(message)
    msg.setStandardButtons(QMessageBox.Ok)
    msg.exec_()


class XYInputDialog(QDialog):
    def __init__(self, x_row="X:", y_row="Y:"):
        super().__init__()
        self.setWindowTitle("Enter X and Y values")

        layout = QVBoxLayout()
        form_layout = QFormLayout()

        self.x_input = QLineEdit("0.0")
        self.y_input = QLineEdit("0.0")

        validator = QDoubleValidator()
        self.x_input.setValidator(validator)
        self.y_input.setValidator(validator)

        form_layout.addRow(x_row, self.x_input)
        form_layout.addRow(y_row, self.y_input)

        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)

        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_values(self):
        return float(self.x_input.text()), float(self.y_input.text())


def get_xy_values(x_row="X:", y_row="Y:"):
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    dialog = XYInputDialog(x_row, y_row)
    if dialog.exec_() == QDialog.Accepted:
        return dialog.get_values()
    return None, None


import numpy as np
import csv
from io import StringIO

# def get_arc_path_from_csv(csv_data, start_point=[0,0], radius=6, num_points=100):
#     # Parse CSV data
#     points = []
#     reader = csv.DictReader(StringIO(csv_data))
#     for row in reader:
#         name = row['name']
#         east = float(row['east'])
#         north = float(row['north'])
#         label = row[' row'].strip()
#         points.append({'name': name, 'x': east, 'y': north, 'row': int(label) if label else None})
#
#     # Separate points by row label
#     line1_points = [p for p in points if p['row'] == 0]
#     line2_points = [p for p in points if p['row'] == 1]
#
#     # Fit lines through the respective points using linear regression
#     def fit_line(points):
#         xs = np.array([p['x'] for p in points])
#         ys = np.array([p['y'] for p in points])
#         coeffs = np.polyfit(xs, ys, 1)
#         return coeffs  # slope and intercept
#
#     line1_coeffs = fit_line(line1_points)
#     line2_coeffs = fit_line(line2_points)
#
#     # Get T2
#     # T2 = np.array([p for p in points if p['name'] == start_point][0][['x', 'y']])
#     T2 = np.array(start_point)
#
#     # Compute direction vector of Line 1 from its slope
#     slope1 = line1_coeffs[0]
#     dir_vec = np.array([1, slope1])
#     dir_vec = dir_vec / np.linalg.norm(dir_vec)
#
#     # Normal vector (perpendicular to Line 1)
#     normal_vec = np.array([-dir_vec[1], dir_vec[0]])
#
#     # Center of the circle lies along the normal vector from T2
#     center = T2 + radius * normal_vec
#
#     # Estimate intersection point with Line 2
#     slope2, intercept2 = line2_coeffs
#     for theta in np.linspace(0, 2 * np.pi, 1000):
#         x = center[0] + radius * np.cos(theta)
#         y = center[1] + radius * np.sin(theta)
#         if np.isclose(y, slope2 * x + intercept2, atol=0.05):
#             intersection_point = np.array([x, y])
#             break
#     else:
#         raise ValueError("No intersection found")
#
#     # Compute angles of T2 and intersection point relative to center
#     def angle_from_center(pt):
#         vec = pt - center
#         return np.arctan2(vec[1], vec[0])
#
#     angle_start = angle_from_center(T2)
#     angle_end = angle_from_center(intersection_point)
#
#     # Ensure shortest arc direction
#     if angle_end < angle_start:
#         angle_end += 2 * np.pi
#     if angle_end - angle_start > np.pi:
#         angle_start, angle_end = angle_end, angle_start + 2 * np.pi
#
#     # Generate arc points
#     angles = np.linspace(angle_start, angle_end, num_points)
#     arc_points = [(center[0] + radius * np.cos(a), center[1] + radius * np.sin(a)) for a in angles]
#
#     return arc_points

import numpy as np


def get_arc_path_from_dataframe(df, start_point=[0, 0], radius=6, num_points=10):
    # Separate points by row label
    line1_points = df[df["row"] == 0]
    line2_points = df[df["row"] == 1]

    # Fit lines through the respective points using linear regression
    def fit_line(points):
        xs = points["east"].values
        ys = points["north"].values
        coeffs = np.polyfit(xs, ys, 1)
        return coeffs  # slope and intercept

    line1_coeffs = fit_line(line1_points)
    line2_coeffs = fit_line(line2_points)

    # Get T2
    T2 = np.asarray(start_point)

    # Compute direction vector of Line 1 from its slope
    slope1 = line1_coeffs[0]
    dir_vec = np.array([1, slope1])
    dir_vec = dir_vec / np.linalg.norm(dir_vec)

    # Normal vector (perpendicular to Line 1)
    normal_vec = np.array([-dir_vec[1], dir_vec[0]])

    # Center of the circle lies along the normal vector from T2
    center = T2 + radius * normal_vec

    # Estimate intersection point with Line 2
    slope2, intercept2 = line2_coeffs
    for theta in np.linspace(0, 2 * np.pi, 1000):
        x = center[0] + radius * np.cos(theta)
        y = center[1] + radius * np.sin(theta)
        if np.isclose(y, slope2 * x + intercept2, atol=0.05):
            intersection_point = np.array([x, y])
            break
    else:
        raise ValueError("No intersection found")

    # Compute angles of T2 and intersection point relative to center
    def angle_from_center(pt):
        vec = pt - center
        return np.arctan2(vec[1], vec[0])

    angle_start = angle_from_center(T2)
    angle_end = angle_from_center(intersection_point)

    # Ensure shortest arc direction
    if angle_end < angle_start:
        angle_end += 2 * np.pi
    if angle_end - angle_start > np.pi:
        angle_start, angle_end = angle_end, angle_start + 2 * np.pi

    # Generate arc points
    angles = np.linspace(angle_start, angle_end, num_points)
    arc_points = [
        (center[0] + radius * np.cos(a), center[1] + radius * np.sin(a)) for a in angles
    ]

    return arc_points


class Navigator:
    def __init__(self):
        self.current_pose = None
        self.track = None

    def get_rtk_position(self):
        # Placeholder for RTK Position implementation
        pass

    @property
    def RTK(self):
        return self.df.loc[self.df.name == "RTK", :]

    # def Willy(self):
    #     return self.df.loc[self.df.name=="RTK", :]

    @property
    def points(self):
        return self.df.loc[~self.df.name.isin(["RTK", "WILLY"]), :]

    @property
    def current_x(self):
        return self.current_pose.a_from_b.translation[0]

    @property
    def current_y(self):
        return self.current_pose.a_from_b.translation[1]

    @property
    def current_xy(self):
        return [self.current_x, self.current_y]

    @property
    def next_xy(self):
        return self.next_point[["x", "y"]].values

    @property
    def points_lat_long(self):
        return self.points[["lat", "long"]].values

    @property
    def next_point(self):
        return self.df.iloc[self.df[self.df["status"] == "pending"].index[0]]

    @property
    def previous_point(self):
        previous = self.df[self.df["status"] == "completed"]
        if len(previous) > 1:
            return self.df.iloc[previous.index[-1]]
        else:
            return None

    def load_drill_plan(self, path):
        self.df = pd.read_csv(path)
        self.df["status"] = "pending"
        self.df.loc[self.df.name == "RTK", "status"] = "completed"
        self.df.loc[self.df.name == "WILLY", "status"] = "current"
        return self.df

    def calculate_xy_positions(self, x_offset=-0, y_offset=0):
        global X_OFFSET, Y_OFFSET
        reference_point = (self.RTK.lat, self.RTK.long)
        willy_xy = [self.current_x, self.current_y]
        xy = latlong_to_xy(reference_point, self.df[["lat", "long"]].values)
        xy.T[0][1:] += 0  # -0.333209
        xy.T[1][1:] += 0  # 0.038363
        self.df[["x", "y"]] = xy
        self.df.loc[self.df["name"] == "WILLY", ["x", "y"]] = willy_xy
        self.df.to_csv("../flask/tmp/drill_plan_tmp.csv")
        return self.df

    def calculate_xy_positions_point_one(self, x_offset=-0, y_offset=0):
        # global X_OFFSET, Y_OFFSET
        # reference_point = (self.RTK.lat, self.RTK.long)
        willy_xy = [self.current_x, self.current_y]
        # xy = latlong_to_xy(reference_point, self.df[["lat", "long"]].values)
        # xy.T[0][1:] += 0 #-0.333209
        # xy.T[1][1:] += 0 # 0.038363
        self.df[["x", "y"]] = self.df[["east", "north"]].values
        self.df.loc[self.df["name"] == "WILLY", ["x", "y"]] = willy_xy
        self.df.to_csv("../flask/tmp/drill_plan_tmp.csv")
        return self.df

    # def calculate_xy_positions_ecf(self, x_offset=-0, y_offset=0):
    #     global X_OFFSET, Y_OFFSET
    #     reference_point = (self.RTK.utm_x.values[0], self.RTK.utm_y.values[0])
    #     willy_xy = [98,31]
    #     # xy = latlong_to_xy(reference_point, self.df[["lat", "long"]].values)
    #     self.df["x"] = self.df["utm_x"].values - reference_point[0] + X_OFFSET
    #     self.df["y"] = self.df["utm_y"].values - reference_point[1] + Y_OFFSET
    #     self.df.loc[self.df["name"]=="WILLY", ["x","y"]] = willy_xy
    #     self.df.to_csv("../flask/tmp/drill_plan_tmp.csv")
    #     return self.df

    async def get_current_pose(
        self, service_config_path: Path = None, timeout: float = 0.5, path: Path = None
    ) -> Pose3F64:
        """Create a start pose for the track.

        Args:
            client: A EventClient for the required service (filter)
        Returns:
            The start pose (Pose3F64)
        """
        print("Creating start pose...")
        # pdb.set_trace()
        zero_tangent = np.zeros((6, 1), dtype=np.float64)
        start: Pose3F64 = Pose3F64(
            a_from_b=Isometry3F64(),
            frame_a="world",
            frame_b="robot",
            tangent_of_b_in_a=zero_tangent,
        )
        timeout = True
        counter = 0
        if service_config_path is not None:
            client = EventClient(
                proto_from_json_file(service_config_path, EventServiceConfig())
            )
            while timeout and counter < 10:
                counter += 1
                try:
                    # Get the current state of the filter
                    state: FilterState = await asyncio.wait_for(
                        client.request_reply("/get_state", Empty(), decode=True),
                        timeout=timeout,
                    )

                    # state.pose.a_from_b.translation.y *= -1

                    start = Pose3F64.from_proto(state.pose)

                    timeout = False
                except asyncio.TimeoutError:
                    timeout = True
                    print(
                        "Timeout while getting filter state. Using default start pose."
                    )
                except Exception as e:
                    print(f"Error getting filter state: {e}. Using default start pose.")
        elif path is not None:
            try:
                track0 = proto_from_json_file(path, Track())
                pose0 = track0.waypoints[0]
                translation_array = [
                    pose0.a_from_b.translation.x,
                    pose0.a_from_b.translation.y,
                    0,
                ]
                rotation_angle = 0
                start = create_pose_from_arrays(translation_array, rotation_angle)
            except Exception as e:
                print(f"Error loading start pose file: {e}. Using default start pose.")

        print("Current Pose", start.a_from_b.translation)
        message = f"Accept this pose: {start.a_from_b.translation} (y/n)?"
        res = ask_question(message)

        if res.lower() == "n":
            # res2 = input("Enter correct xy values separated by comma:")
            # override = res2.split(",")
            # o_x = float(override[0])
            # o_y = float(override[1])
            o_x, o_y = get_xy_values()

            translation_array = [o_x, o_y, 0]
            rotation_angle = start.a_from_b.rotation.log()[0]
            start = create_pose_from_arrays(translation_array, rotation_angle)

        self.current_pose = start
        self.df.loc[self.df["name"] == "WILLY", ["x", "y"]] = [
            start.a_from_b.translation[0],
            start.a_from_b.translation[1],
        ]
        self.df.to_csv("../flask/tmp/drill_plan_tmp.csv")
        return start

    def build_track_to_next_point(self):
        global X_OFFSET, Y_OFFSET
        # pdb.set_trace()
        builder = TrackBuilder(self.current_pose)
        point0 = self.current_xy
        point1 = self.next_xy
        point0[0] += X_OFFSET
        point0[1] += Y_OFFSET

        next_frame_b = self.next_point["name"]
        spacing = 0.1
        distance = calculate_distance(point0, point1)

        res = ask_question("Stop 1 m short (y/n)?")
        stop_short = res.lower() == "y"
        if stop_short:
            distance -= 1

        heading_to_next_pose: float = np.arctan2(
            point1[0] - point0[0],
            point1[1] - point0[1],
        )
        turn_angle: float = (
            np.pi / 2
            - heading_to_next_pose
            - self.current_pose.a_from_b.rotation.log()[-1]
        )
        turn_angle = equivalent_angle(turn_angle)
        print("Turn Angle New", turn_angle)
        pdb.set_trace()
        builder.create_turn_segment(
            next_frame_b=next_frame_b, angle=turn_angle, spacing=spacing
        )
        builder._create_segment(
            next_frame_b=next_frame_b, distance=distance, spacing=spacing
        )
        self.track = builder.track
        a = "START" if self.previous_point is None else self.previous_point["name"]
        b = self.next_point["name"]
        name = f"../navigation/test_{a}_to_{b}.json"
        # builder.save_track(name)
        plot(self.track, goals=self.points)
        # pdb.set_trace()
        return

    def build_arch_track(self):
        global X_OFFSET, Y_OFFSET
        pdb.set_trace()
        builder = TrackBuilder(self.current_pose)

        arch_points = get_arc_path_from_dataframe(self.points)

        for i in np.arange(1, len(arch_points)):
            point0 = arch_points[i - 1]
            point1 = arch_points[i]
            next_frame_b = "arch_{i}".format(i=i)
            spacing = 0.1
            distance = calculate_distance(point0, point1)

            heading_to_next_pose: float = np.arctan2(
                point1[0] - point0[0],
                point1[1] - point0[1],
            )
            turn_angle: float = (
                np.pi / 2
                - heading_to_next_pose
                - self.current_pose.a_from_b.rotation.log()[-1]
            )
            turn_angle = equivalent_angle(turn_angle)
            # print("Turn Angle New", turn_angle)
            builder.create_turn_segment(
                next_frame_b=next_frame_b, angle=turn_angle, spacing=spacing
            )
            builder._create_segment(
                next_frame_b=next_frame_b, distance=distance, spacing=spacing
            )
        self.track = builder.track
        a = "End_Line_1"
        b = "Begin_Line_2"
        name = f"../navigation/test_{a}_to_{b}.json"
        builder.save_track(name)
        plot(self.track, goals=self.points)
        # pdb.set_trace()
        return

    def rotate_in_place(self, delta_x=0, delta_y=0, angle=None, rotate_and_move=False):
        # pdb.set_trace()
        builder = TrackBuilder(self.current_pose)
        next_frame_b = self.next_point["name"]
        spacing = 0.1

        if angle is None:
            point0 = self.current_xy
            point1 = [
                self.current_xy[0] + float(delta_x),
                self.current_xy[1] + float(delta_y),
            ]

            spacing = 0.1
            distance = calculate_distance(point0, point1)

            heading_to_next_pose: float = np.arctan2(
                point1[0] - point0[0],
                point1[1] - point0[1],
            )
            turn_angle: float = (
                np.pi / 2
                - heading_to_next_pose
                - self.current_pose.a_from_b.rotation.log()[-1]
            )
            turn_angle = equivalent_angle(turn_angle)
            print("Turn Angle New", turn_angle)
        else:
            turn_angle = angle
            rotate_and_move = False  # Can't move if only an angle is sent

        builder.create_turn_segment(
            next_frame_b=next_frame_b, angle=turn_angle, spacing=spacing
        )
        if rotate_and_move:
            builder._create_segment(
                next_frame_b=next_frame_b, distance=distance, spacing=spacing
            )
        self.track = builder.track
        a = self.next_point["name"]
        name = f"../navigation/test_{a}_fine_tune_rotate_in_place.json"
        builder.save_track(name)
        plot(self.track, goals=self.points)
        # pdb.set_trace()
        return

    async def go_to_goal(self, pose: Pose3F64):
        # pdb.set_trace()
        service_config_path = "../navigation/track_service_config.json"
        service_config: EventServiceConfig = proto_from_json_file(
            service_config_path, EventServiceConfig()
        )

        self.build_track_to_next_point()

        # print("Canceling the run and clearing the track")
        # await EventClient(service_config).request_reply("/cancel", Empty())
        # pdb.set_trace()
        print(f"Setting track:\n{self.track}")
        await EventClient(service_config).request_reply(
            "/set_track", TrackFollowRequest(track=self.track)
        )

        # pdb.set_trace()
        print("Sending request to start following the track...")
        await EventClient(service_config).request_reply("/start", Empty())

        # await EventClient(service_config).request_reply("/get_state", Empty())

        # print(f"Setting goal:\n{pose}")
        # await EventClient(service_config).request_reply("/go_to_goal", self.next_pose)

        return True

    async def turn_around(self):
        print("Starting turn around...")

        filter_service_config_path = "../navigation/service_config.json"

        track_service_config_path = "../navigation/track_service_config.json"
        service_config: EventServiceConfig = proto_from_json_file(
            track_service_config_path, EventServiceConfig()
        )

        start = await self.get_current_pose(
            service_config_path=filter_service_config_path
        )

        clearance = 3
        row_spacing = 6
        angle = 90
        breadcrumb_spacing = 0.1

        track_builder = TrackBuilder(start=start)
        track_builder.create_straight_segment(
            next_frame_b="goal1", distance=clearance, spacing=breadcrumb_spacing
        )
        track_builder.create_arc_segment(
            next_frame_b="goal2",
            radius=row_spacing,
            angle=radians(angle),
            spacing=breadcrumb_spacing,
        )
        # track_builder.create_turn_segment(next_frame_b="goal_3", angle=radians(angle), spacing=breadcrumb_spacing)
        # track_builder.create_straight_segment(next_frame_b="goal4", distance=clearance, spacing=breadcrumb_spacing)

        self.track = track_builder.track
        name = f"../navigation/test_turn_around.json"
        track_builder.save_track(name)
        plot(self.track, goals=self.points)

        pdb.set_trace()

        # self.build_arch_track()

        # pdb.set_trace()
        print(f"Setting track:\n{self.track}")
        await EventClient(service_config).request_reply(
            "/set_track", TrackFollowRequest(track=self.track)
        )

        # pdb.set_trace()
        print("Sending request to start following the track...")
        await EventClient(service_config).request_reply("/start", Empty())

        return True

    async def arch_backwards(self):
        print("Starting arch backwards...")

        twist_service_config_path = "../navigation/twist_service_config.json"
        service_config: EventServiceConfig = proto_from_json_file(
            twist_service_config_path, EventServiceConfig()
        )
        twist = Twist2d()
        client: EventClient = EventClient(service_config)

        drive_time = 10
        radius = 12

        payload = calculate_twist_for_arc(radius=radius, duration=drive_time)

        twist = update_twist_from_data(twist, payload)

        start = int(time.time())
        now = int(time.time())
        print(
            f"Received: {payload} → Sending linear: {twist.linear_velocity_x:.3f}, angular: {twist.angular_velocity:.3f}"
        )
        while now - start <= drive_time:
            await client.request_reply("/twist", twist)
        return

    async def fine_tune(self):
        global X_OFFSET, Y_OFFSET
        # pdb.set_trace()
        service_config_path = "../navigation/track_service_config.json"
        service_config: EventServiceConfig = proto_from_json_file(
            service_config_path, EventServiceConfig()
        )

        # resp = input("Rotate by XY offset? (y/n):")
        # if resp.lower()=="y":
        # delta_x = input("What is the X offset:")
        # delta_y = input("What is the Y offset:")
        delta_x, delta_y = get_xy_values(x_row="Delta X:", y_row="Delta Y:")
        #     resp = input("Rotate and move? (y/n):")
        #     rotate_and_move = resp.lower() == "y"
        #     angle = None
        # else:
        #     delta_x = 0
        #     delta_y = 0
        #     angle = input("Enter the turn angle in degrees (-CCW/+CW):")
        #     angle = (float(angle) * np.pi) / 180.0
        #     rotate_and_move = False
        #
        # self.rotate_in_place(delta_x=delta_x, delta_y=delta_y, angle=angle, rotate_and_move=rotate_and_move)
        #
        # # print("Canceling the run and clearing the track")
        # # await EventClient(service_config).request_reply("/cancel", Empty())
        # pdb.set_trace()
        # print(f"Setting track:\n{self.track}")
        # await EventClient(service_config).request_reply("/set_track", TrackFollowRequest(track=self.track))
        #
        # pdb.set_trace()
        # print("Sending request to start following the track...")
        # await EventClient(service_config).request_reply("/start", Empty())
        #
        # resp = input("Update global offsets (y/n)?")
        # if resp.lower() == "y":
        X_OFFSET += float(delta_x)
        Y_OFFSET += float(delta_y)

        # await EventClient(service_config).request_reply("/get_state", Empty())

        # print(f"Setting goal:\n{pose}")
        # await EventClient(service_config).request_reply("/go_to_goal", self.next_pose)

        return True

    def log(self):
        start_time = time.time()
        print("Here is where we log the blasthole")
        time.sleep(2)
        end_time = time.time()
        elapsed_time = end_time - start_time
        return elapsed_time

    async def update_navigation_plan(self, status, operating_time):
        current_point_index = self.df[self.df["status"] == "pending"].index[0]
        # pdb.set_trace()
        pose = await self.get_current_pose(
            service_config_path="../navigation/service_config.json"
        )
        # Placeholder values for real_x, real_y, real_lat, real_long
        real_x = pose.a_from_b.translation[0]
        real_y = pose.a_from_b.translation[1]
        real_lat, real_long = 0, 0

        self.df.at[current_point_index, "status"] = status
        self.df.at[current_point_index, "real_x"] = real_x
        self.df.at[current_point_index, "real_y"] = real_y
        self.df.at[current_point_index, "real_lat"] = real_lat
        self.df.at[current_point_index, "real_long"] = real_long

        self.df.at[current_point_index, "operating_time"] = operating_time
        self.df.to_csv("../flask/tmp/drill_plan_tmp.csv")
        print(self.df)

    def plot_plan(self):
        plt.figure()
        plt.scatter(self.RTK.x, self.RTK.y, c="green")
        plt.scatter(self.points.x, self.points.y, c="red")
        # Add labels to each point
        for i in range(len(self.points)):
            plt.text(
                self.df.x.values[i] + 0.1,
                self.df.y.values[i],
                self.df.name.values[i],
                fontsize=10,
            )

        plt.xlabel("x")
        plt.ylabel("y")
        plt.title("Scatter plot of x vs y converted from Lat/Long")
        plt.grid(True)
        plt.show()

    def plot_pose(self, current_x, current_y, angle_degrees):
        # Convert angle from degrees to radians
        plt.figure()

        angle_radians = np.radians(angle_degrees)

        # Calculate the direction vector
        direction_vector = np.array([np.cos(angle_radians), np.sin(angle_radians)])

        # Plot the point and the arrow
        plt.plot(current_x, current_y, "bo")  # Plot the point
        plt.arrow(
            current_x,
            current_y,
            direction_vector[0],
            direction_vector[1],
            head_width=0.1,
            head_length=0.2,
            fc="r",
            ec="r",
        )

        plt.scatter(self.RTK.x, self.RTK.y, c="green")
        plt.scatter(self.points.x, self.points.y, c="red")

        # Add labels and title
        plt.xlabel("X")
        plt.ylabel("Y")
        plt.title("Arrow pointing in the direction of the angle")

        # Show the plot
        plt.grid(True)
        plt.show()


async def main():
    # Test case to go through all steps in order
    nav = Navigator()

    # Load drill plan from a CSV file (assuming the file path is 'drill_plan.csv')
    nav.load_drill_plan("../sandbox/drill_plan_one_point_true.csv")

    # path = Path("/home/natalr/Documents/xdipper/data/tracks/test_pose.json")
    path = None
    service_config_path = "../navigation/service_config.json"
    await nav.get_current_pose(
        service_config_path=service_config_path, timeout=0, path=path
    )

    # Calculate XY positions with initial offsets (0, 0)
    # nav.calculate_xy_positions(-2, -1.418)

    # pdb.set_trace()

    nav.calculate_xy_positions_point_one(0, 0)

    if STARTING_POINT_ID is not None:
        nav.df.loc[nav.df["id"] <= STARTING_POINT_ID, "status"] = "completed"

    nav.plot_plan()

    while True:
        # Calculate initial pose (placeholders for client and timeout)
        await nav.get_current_pose(
            service_config_path=service_config_path, timeout=0, path=path
        )

        # Calculate track to next position using the pose (placeholder for pose)
        # offsets = nav.calculate_next_point()
        #
        # if offsets is None:
        #     print("Can't find a suitable next point.  Will exit now")
        #     break

        # x, y, turn_angle = offsets
        # nav.plot_pose(nav.current_x, nav.current_y, turn_angle)

        print("Setting goal and following track")
        # Go to goal (placeholder for goal)
        await nav.go_to_goal(pose=None)

        res = ask_question("Did Willy move to the right spot (y/n)?")
        if res.lower() == "n":
            # print("Make sure the filter has not diverged")
            # input("Press Enter to try to navigate again")
            show_message()
            continue

        show_message(
            "Press Twist on main control and manually position willy.  Press Ok when ready to log"
        )

        start_time = time.monotonic()

        # # Fine tune (if needed)
        # res = ask_question("Fine tune needed (y/n)?")
        # fine_tune = res.lower() == "y"
        #
        # while fine_tune:
        #     await nav.fine_tune()
        #     res = ask_question("Fine tune needed (y/n)?")
        #     fine_tune = res.lower() == "y"

        # input("Press Enter to continue to Log function...")
        show_message("Press Enter Once the logging has been completed ...")
        end_time = time.monotonic()

        # Log the operation time
        operating_time = end_time - start_time
        print(operating_time)

        # input("Press Enter to continue to Update Navigation Plan function...")
        show_message("Press Enter to continue to Update Navigation Plan function...")

        # Update navigation plan with status 'completed'
        await nav.update_navigation_plan(
            status="completed", operating_time=operating_time
        )

        print(nav.df[["x", "y", "real_x", "real_y"]])
        # pdb.set_trace()

        # Fine tune (if needed)
        res = ask_question("Do you need to turn around (y/n)?")
        turn_around = res.lower() == "y"

        if turn_around:
            await nav.turn_around()
            await nav.arch_backwards()
            show_message("Press Enter Once you're ready to move to next location ...")


if __name__ == "__main__":
    asyncio.run(main())
