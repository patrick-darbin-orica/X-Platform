import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QDoubleSpinBox, QLabel
from PyQt5.QtCore import Qt, QTimer, QThread, QObject, pyqtSignal
import asyncio
from pathlib import Path
from qasync import QEventLoop, asyncSlot
import time

from farm_ng.canbus.tool_control_pb2 import ActuatorCommands
from farm_ng.canbus.tool_control_pb2 import HBridgeCommand
from farm_ng.canbus.tool_control_pb2 import HBridgeCommandType
from farm_ng.canbus.tool_control_pb2 import PtoCommand
from farm_ng.canbus.tool_control_pb2 import PtoCommandType
from farm_ng.canbus.tool_control_pb2 import ToolStatuses
from farm_ng.core.event_client import EventClient
from farm_ng.core.event_service_pb2 import EventServiceConfig
from farm_ng.core.events_file_reader import proto_from_json_file
from farm_ng.core.stamp import get_stamp_by_semantics_and_clock_type
from farm_ng.core.stamp import StampSemantics
from farm_ng.filter.filter_pb2 import DivergenceCriteria
from farm_ng_core_pybind import Pose3F64
import subprocess

def tool_control_from_key_presses(pressed_keys: set, pto_rpm: float) -> ActuatorCommands:
    if 'space' in pressed_keys:
        print("Set all to passive with empty command")
        return ActuatorCommands()

    commands: ActuatorCommands = ActuatorCommands()

    # H-bridges controlled with 0, 1, 2, 3 & up / down arrows
    # up = forward, down = reverse, both = stop, neither / not pressed => omitted => passive
    if 'up' in pressed_keys and 'down' in pressed_keys:
        for hbridge_id in pressed_keys & {'0', '1', '2', '3'}:
            commands.hbridges.append(HBridgeCommand(id=int(hbridge_id), command=HBridgeCommandType.HBRIDGE_STOPPED))
    elif 'up' in pressed_keys:
        for hbridge_id in pressed_keys & {'0', '1', '2', '3'}:
            commands.hbridges.append(HBridgeCommand(id=int(hbridge_id), command=HBridgeCommandType.HBRIDGE_FORWARD))
    elif 'down' in pressed_keys:
        for hbridge_id in pressed_keys & {'0', '1', '2', '3'}:
            commands.hbridges.append(HBridgeCommand(id=int(hbridge_id), command=HBridgeCommandType.HBRIDGE_REVERSE))

    # PTOs controlled with a, b, c, d & left / right arrows
    # left = forward, right = reverse, both = stop, neither / not pressed => omitted => passive
    pto_id_mapping = {'a': 0x0, 'b': 0x1, 'c': 0x2, 'd': 0x3}

    if 'left' in pressed_keys and 'right' in pressed_keys:
        for pto_char in pressed_keys & {'a', 'b', 'c', 'd'}:
            pto_id = pto_id_mapping[pto_char]
            commands.ptos.append(PtoCommand(id=pto_id, command=PtoCommandType.PTO_STOPPED, rpm=pto_rpm))
    elif 'left' in pressed_keys:
        for pto_char in pressed_keys & {'a', 'b', 'c', 'd'}:
            pto_id = pto_id_mapping[pto_char]
            commands.ptos.append(PtoCommand(id=pto_id, command=PtoCommandType.PTO_FORWARD, rpm=pto_rpm))
    elif 'right' in pressed_keys:
        for pto_char in pressed_keys & {'a', 'b', 'c', 'd'}:
            pto_id = pto_id_mapping[pto_char]
            commands.ptos.append(PtoCommand(id=pto_id, command=PtoCommandType.PTO_REVERSE, rpm=pto_rpm))

    print("KEYS:", pressed_keys)
    return commands

async def control_tools(service_config_path: Path, pressed_keys: set, pto_rpm: float) -> None:
    """Control the tools / actuators on your Amiga.

    Args:
        service_config_path (Path): The path to the canbus service config.
    """
    config: EventServiceConfig = proto_from_json_file(service_config_path, EventServiceConfig())
    client: EventClient = EventClient(config)
    while True:
        # Send the tool control command
        commands: ActuatorCommands = tool_control_from_key_presses(pressed_keys, pto_rpm)
        await client.request_reply("/control_tools", commands, decode=True)

        # Sleep for a bit
        await asyncio.sleep(0.1)

async def stream_tool_statuses(service_config_path: Path) -> None:
    """Stream the tool statuses.

    Args:
        service_config_path (Path): The path to the canbus service config.
    """
    config: EventServiceConfig = proto_from_json_file(service_config_path, EventServiceConfig())

    message: ToolStatuses
    async for event, message in EventClient(config).subscribe(config.subscriptions[0], decode=True):
        print("###################")
        print(message)


class FilterWorker(QObject):
    data_received = pyqtSignal(dict)

    def __init__(self, service_config_path):
        super().__init__()
        # print("INIT")
        self.service_config_path = service_config_path
        self._last_update_time = 0
        self._running = True

    def stop(self):
        self._running = False

    async def run_filter(self):
        # print("RUN")
        config = proto_from_json_file(self.service_config_path, EventServiceConfig())
        async for event, message in EventClient(config).subscribe(config.subscriptions[0], decode=True):
            stamp = (
                    get_stamp_by_semantics_and_clock_type(event, StampSemantics.SERVICE_SEND, "monotonic")
                    or event.timestamps[0].stamp
            )
            now = time.time()
            if now - self._last_update_time < 1.0:
                continue
            self._last_update_time = now

            pose = Pose3F64.from_proto(message.pose)
            orientation = message.heading
            uncertainties = [message.uncertainty_diagonal.data[i] for i in range(3)]
            divergence_criteria = [DivergenceCriteria.Name(c) for c in message.divergence_criteria]

            data = {
                "stamp": stamp,
                "x": pose.translation[0],
                "y": pose.translation[1],
                "orientation": orientation,
                "frame_a": pose.frame_a,
                "frame_b": pose.frame_b,
                "has_converged": message.has_converged,
                "uncertainties": uncertainties,
                "divergence_criteria": divergence_criteria
            }
            # print(data)
            self.data_received.emit(data)


class SimpleGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.control_tools_task = None
        self.pto_keys = set(["a", "right"])
        self.navigator_process = None
        self.twist_process = None
        self.log_file_process = None

        # Start filter worker
        self.worker = FilterWorker(Path("filter_service_config.json"))
        self.worker.data_received.connect(self.update_filter_data)

    def closeEvent(self, event):
        if self.control_tools_task:
            self.control_tools_task.cancel()
        if self.worker:
            self.worker.stop()  # if you have a stop method
        event.accept()

    def update_filter_data(self, data):
        has_converged = data["has_converged"]
        if has_converged:
            self.converged_label.setStyleSheet("color: green;")
        else:
            self.converged_label.setStyleSheet("color: red;")

        self.stamp_label.setText(str(data["stamp"]))
        self.pose_label.setText(f"x: {data['x']:.3f} m, y: {data['y']:.3f} m, orientation: {data['orientation']:.3f} rad")
        self.frame_label.setText(f"Parent frame: {data['frame_a']} -> Child frame: {data['frame_b']}")
        self.converged_label.setText(f"Filter has converged: {has_converged}")
        self.uncertainty_label.setText(
            f"Pose uncertainties:\nx: {data['uncertainties'][0]:.3f} m, y: {data['uncertainties'][1]:.3f} m, orientation: {data['uncertainties'][2]:.3f} rad"
        )
        self.divergence_label.setText(
            f"Filter diverged due to: {data['divergence_criteria'] if not data['has_converged'] else 'None'}"
        )

    def initUI(self):
        main_layout = QHBoxLayout()
        twist_layout = QVBoxLayout()
        self.twist_go_button = QPushButton('Twist')
        self.twist_stop_button = QPushButton('Stop Twist')
        self.twist_go_button.clicked.connect(self.start_twist)
        self.twist_stop_button.clicked.connect(self.stop_twist)
        twist_layout.addWidget(self.twist_go_button)
        twist_layout.addWidget(self.twist_stop_button)

        left_layout = QVBoxLayout()
        self.go_button = QPushButton('Go')
        self.stop_button = QPushButton('Stop')
        self.go_button.clicked.connect(self.start_navigator)
        self.stop_button.clicked.connect(self.stop_navigator)
        left_layout.addWidget(self.go_button)
        left_layout.addWidget(self.stop_button)

        filter_layout = QVBoxLayout()
        self.stamp_label = QLabel()
        self.pose_label = QLabel()
        self.frame_label = QLabel()
        self.converged_label = QLabel()
        self.uncertainty_label = QLabel()
        self.divergence_label = QLabel()
        for label in [self.stamp_label, self.pose_label, self.frame_label, self.converged_label, self.uncertainty_label, self.divergence_label]:
            filter_layout.addWidget(label)

        log_layout = QVBoxLayout()
        self.log_start_button = QPushButton('Start Log File')
        self.log_stop_button = QPushButton('Stop Log File')
        self.log_start_button.clicked.connect(self.start_log_file)
        self.log_stop_button.clicked.connect(self.stop_log_file)
        log_layout.addWidget(self.log_start_button)
        log_layout.addWidget(self.log_stop_button)


        right_layout = QVBoxLayout()
        self.toggle_button = QPushButton('Down')
        self.toggle_button.setCheckable(True)
        self.toggle_button.setStyleSheet("""QPushButton {
            background-color: green;border: 2px solid gray;
            border-radius: 10px;
            padding: 5px;
            }
            QPushButton:checked {
            background-color: yellow;
            color: black;
            }""")
        self.toggle_button.toggled.connect(self.on_direction_changed)
        right_layout.addWidget(self.toggle_button)

        self.pto_rpm = QDoubleSpinBox()
        self.pto_rpm.setValue(10.0)
        right_layout.addWidget(self.pto_rpm)

        self.start_stop_button = QPushButton('Stopped')
        self.start_stop_button.setCheckable(True)
        self.start_stop_button.setStyleSheet("""QPushButton {
                background-color: red;border: 2px solid black;
                border-radius: 10px;
                padding: 5px;
                }
                QPushButton:checked {
                background-color: green;
                color: white;
                }""")
        self.start_stop_button.toggled.connect(self.on_start_stop)
        right_layout.addWidget(self.start_stop_button)

        main_layout.addLayout(left_layout)
        main_layout.addLayout(twist_layout)
        main_layout.addLayout(log_layout)
        main_layout.addLayout(right_layout)
        main_layout.addLayout(filter_layout)
        self.setLayout(main_layout)

    def on_direction_changed(self, checked):
        print(self.pto_rpm.value())
        if checked:
            self.toggle_button.setText('Up')
            self.pto_keys = set(["a", "left"])
        else:
            self.toggle_button.setText('Down')
            self.pto_keys = set(["a", "right"])
        if self.start_stop_button.isChecked():
            self.on_start_stop(False)
            self.on_start_stop(True)

    def start_navigator(self):
        if self.navigator_process is None or self.navigator_process.poll() is not None:
            self.navigator_process = subprocess.Popen([sys.executable, "../navigation/navigator.py"])
        print("Navigator started.")

    def stop_navigator(self):
        if self.navigator_process and self.navigator_process.poll() is None:
            self.navigator_process.terminate()
            self.navigator_process.wait()
        print("Navigator stopped.")

    def start_log_file(self):
        if self.log_file_process is None or self.log_file_process.poll() is not None:
            self.log_file_process = subprocess.Popen([sys.executable, "../logger/log_file.py"])
        print("Navigator started.")

    def stop_log_file(self):
        if self.log_file_process and self.log_file_process.poll() is None:
            self.log_file_process.terminate()
            self.log_file_process.wait()
        print("Log File stopped.")

    def start_twist(self):
        if self.twist_process is None or self.twist_process.poll() is not None:
            self.twist_process = subprocess.Popen([sys.executable, "../vehicle_twist/main.py", "--service-config", "service_config.json"])
        print("Twist started.")

    def stop_twist(self):
        if self.twist_process and self.twist_process.poll() is None:
            self.twist_process.terminate()
            self.twist_process.wait()
        print("Twist stopped.")

    @asyncSlot(bool)
    async def on_start_stop(self, checked):
        if checked:
            self.start_stop_button.setText('Running')
            print("Starting control_tools...")
            self.control_tools_task = asyncio.create_task(control_tools(Path("service_config.json"), self.pto_keys, self.pto_rpm.value()))
        else:
            self.start_stop_button.setText('Stopped')
            print("Stopping control_tools...")
            if self.control_tools_task:
                self.control_tools_task.cancel()
                self.control_tools_task = None


# async def main():
#     app = QApplication(sys.argv)
#     loop = QEventLoop(app)
#     asyncio.set_event_loop(loop)
#
#     gui = SimpleGUI()
#     gui.show()
#
#     # Schedule the filter worker to start after the event loop begins
#     loop.call_soon(asyncio.create_task, gui.worker.run_filter())
#
#     with loop:
#         loop.run_forever()
#
#
#     with loop:
#         loop.run_forever()
#
#
# if __name__ == '__main__':
#     asyncio.run(main())

if __name__ == '__main__':
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    gui = SimpleGUI()
    gui.show()

    # Schedule the filter worker to start after the event loop begins
    loop.call_soon(asyncio.create_task, gui.worker.run_filter())

    try:
        with loop:
            loop.run_forever()
    except KeyboardInterrupt:
        print("Application interrupted.")
    finally:
        print("Closing application...")




# class SimpleGUI(QWidget):
#     def __init__(self):
#         super().__init__()
# 
#         # Initialize the layout
#         self.initUI()
#         self.control_tools_task = None  # Task for control_tools
#         self.pto_keys = set(["a","right"])
#         self.navigator_process = None
#         self.twist_process = None
# 
#     def start_filter_timer(self):
#         self.timer = QTimer()
#         self.timer.timeout.connect(self.update_filter_data)
#         self.timer.start(1000)  # Update every second
# 
#     def update_filter_data(self):
#         global POSE, ORIENTATION, MESSAGE, UNCERTAINTIES, DIVERGENCECRITERIA
#         # Simulated data (replace with actual data fetching)
#         pose = POSE
#         orientation = ORIENTATION
#         has_converged = MESSAGE.has_converged
#         uncertainties = UNCERTAINTIES
#         divergence_criteria = DIVERGENCECRITERIA
# 
#         # Update labels
#         self.pose_label.setText(f"x: {pose['translation'][0]:.3f} m, y: {pose['translation'][1]:.3f} m, orientation: {orientation:.3f} rad")
#         self.frame_label.setText(f"Parent frame: {pose['frame_a']} -> Child frame: {pose['frame_b']}")
#         self.converged_label.setText(f"Filter has converged: {has_converged}")
#         self.uncertainty_label.setText(f"Pose uncertainties:\nx: {uncertainties[0]:.3f} m, y: {uncertainties[1]:.3f} m, orientation: {uncertainties[2]:.3f} rad")
#         self.divergence_label.setText(f"Filter diverged due to: {divergence_criteria if not has_converged else 'None'}")
# 
# 
#     def initUI(self):
#         # Create the main layout
#         main_layout = QHBoxLayout()
# 
#         # Create the left section layout
#         twist_layout = QVBoxLayout()
# 
#         self.twist_go_button = QPushButton('Twist')
#         self.twist_stop_button = QPushButton('Stop Twist')
# 
#         self.twist_go_button.clicked.connect(self.start_twist)
#         self.twist_stop_button.clicked.connect(self.stop_twist)
# 
#         # self.no_button = QPushButton('No')
#         twist_layout.addWidget(self.twist_go_button)
#         twist_layout.addWidget(self.twist_stop_button)
# 
#         left_layout = QVBoxLayout()
# 
#         # Add buttons to the left section
#         self.go_button = QPushButton('Go')
#         self.stop_button = QPushButton('Stop')
# 
#         self.go_button.clicked.connect(self.start_navigator)
#         self.stop_button.clicked.connect(self.stop_navigator)
# 
#         # self.no_button = QPushButton('No')
#         left_layout.addWidget(self.go_button)
#         left_layout.addWidget(self.stop_button)
#         # left_layout.addWidget(self.no_button)
# 
#         filter_layout = QVBoxLayout()
# 
#         self.pose_label = QLabel()
#         self.frame_label = QLabel()
#         self.converged_label = QLabel()
#         self.uncertainty_label = QLabel()
#         self.divergence_label = QLabel()
# 
#         for label in [self.pose_label, self.frame_label, self.converged_label, self.uncertainty_label,
#                       self.divergence_label]:
#             filter_layout.addWidget(label)
# 
#         self.start_filter_timer()
# 
#         # Create the right section layout
#         right_layout = QVBoxLayout()
# 
#         # Add up/down toggle button to the right section
#         self.toggle_button = QPushButton('Down')
#         self.toggle_button.setCheckable(True)
#         self.toggle_button.setStyleSheet("""QPushButton {
#         background-color: green;border: 2px solid gray;
#         border-radius: 10px;
#         padding: 5px;
#         }
#         QPushButton:checked {
#         background-color: yellow;
#         color: black;
#         }
#         """)
# 
#         right_layout.addWidget(self.toggle_button)
#         self.toggle_button.toggled.connect(self.on_direction_changed)
# 
#         # Add numeric field to the right section
#         self.pto_rpm = QDoubleSpinBox()
#         self.pto_rpm.setValue(10.0)
#         right_layout.addWidget(self.pto_rpm)
# 
#         # Add start/stop button to the right section
#         self.start_stop_button = QPushButton('Stopped')
#         self.start_stop_button.setCheckable(True)
#         self.start_stop_button.setStyleSheet("""QPushButton {
#                 background-color: red;border: 2px solid black;
#                 border-radius: 10px;
#                 padding: 5px;
#                 }
#                 QPushButton:checked {
#                 background-color: green;
#                 color: white;
#                 }
#                 """)
#         self.start_stop_button.toggled.connect(self.on_start_stop)
#         right_layout.addWidget(self.start_stop_button)
# 
#         # Add left and right sections to the main layout
#         main_layout.addLayout(left_layout)
#         main_layout.addLayout(twist_layout)
#         main_layout.addLayout(right_layout)
#         main_layout.addLayout(filter_layout)
# 
#         # Set the main layout for the widget
#         self.setLayout(main_layout)
# 
#     def on_direction_changed(self, checked):
#         print(self.pto_rpm.value())
#         if checked:
#             self.toggle_button.setText('Up')
#             self.pto_keys = set(["a", "left"])
#             print("Button is in the 'Up' position")
#         else:
#             self.toggle_button.setText('Down')
#             self.pto_keys = set(["a", "right"])
#             print("Button is in the 'Down' position")
#         pto_checked = self.start_stop_button.isChecked()
#         if pto_checked:
#             self.on_start_stop(False)
#             self.on_start_stop(True)
# 
#     def start_navigator(self):
#                 if self.navigator_process is None or self.navigator_process.poll() is not None:
#                         self.navigator_process = subprocess.Popen([sys.executable, "../navigation/navigator.py"])
# 
#                 print("Navigator started.")
# 
#        
# 
#     def stop_navigator(self):
#                 if self.navigator_process and self.navigator_process.poll() is None:
#                         self.navigator_process.terminate()
# 
#                 self.navigator_process.wait()
#                 print("Navigator stopped.")
# 
#     def start_twist(self):
#         if self.twist_process is None or self.twist_process.poll() is not None:
#             self.twist_process = subprocess.Popen([sys.executable, "../vehicle_twist/main.py", "--service-config", "service_config.json"])
# 
#         print("Twist started.")
# 
#     def stop_twist(self):
#         if self.twist_process and self.twist_process.poll() is None:
#             self.twist_process.terminate()
# 
#         self.twist_process.wait()
#         print("Twist stopped.")
# 
#     @asyncSlot(bool)
#     async def on_start_stop(self, checked):
#         if checked:
#             self.start_stop_button.setText('Running')
#             print("Starting control_tools...")
#             self.control_tools_task = asyncio.create_task(control_tools(Path("service_config.json"), self.pto_keys,
#                                                                         self.pto_rpm.value()))
#         else:
#             self.start_stop_button.setText('Stopped')
#             print("Stopping control_tools...")
#             if self.control_tools_task:
#                 self.control_tools_task.cancel()
#                 self.control_tools_task = None
# 
# async def main():
#     app = QApplication(sys.argv)
#     loop = QEventLoop(app)
#     asyncio.set_event_loop(loop)
# 
#     gui = SimpleGUI()
#     gui.show()
# 
#     with loop:
#         loop.run_forever()
# 
# # Run the application
# if __name__ == '__main__':
#     asyncio.run(main())

