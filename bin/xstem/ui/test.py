import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton
import asyncio
from pathlib import Path
from qasync import QEventLoop, asyncSlot

from farm_ng.canbus.tool_control_pb2 import ActuatorCommands
from farm_ng.canbus.tool_control_pb2 import HBridgeCommand
from farm_ng.canbus.tool_control_pb2 import HBridgeCommandType
from farm_ng.canbus.tool_control_pb2 import PtoCommand
from farm_ng.canbus.tool_control_pb2 import PtoCommandType
from farm_ng.canbus.tool_control_pb2 import ToolStatuses
from farm_ng.core.event_client import EventClient
from farm_ng.core.event_service_pb2 import EventServiceConfig
from farm_ng.core.events_file_reader import proto_from_json_file

def tool_control_from_key_presses(pressed_keys: set) -> ActuatorCommands:
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
    pto_rpm: float = 100.0

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

async def control_tools(service_config_path: Path) -> None:
    """Control the tools / actuators on your Amiga.

    Args:
        service_config_path (Path): The path to the canbus service config.
    """
    config: EventServiceConfig = proto_from_json_file(service_config_path, EventServiceConfig())
    client: EventClient = EventClient(config)
    pressed_keys = set(["a", "left"])
    while True:
        # Send the tool control command
        commands: ActuatorCommands = tool_control_from_key_presses(pressed_keys)
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

class SimpleGUI(QWidget):
    def __init__(self):
        super().__init__()

        # Initialize the layout
        self.initUI()
        self.control_tools_task = None  # Task for control_tools

    def initUI(self):
        # Create the main layout
        main_layout = QVBoxLayout()

        # Add a button to the layout
        self.button = QPushButton('Start')
        self.button.setCheckable(True)
        self.button.clicked.connect(self.on_button_click)
        main_layout.addWidget(self.button)

        # Set the main layout for the widget
        self.setLayout(main_layout)

    @asyncSlot()
    async def on_button_click(self):
        if self.button.isChecked():
            self.button.setText('Stop')
            print("Starting control_tools...")
            self.control_tools_task = asyncio.create_task(control_tools(Path("service_config.json")))
        else:
            self.button.setText('Start')
            print("Stopping control_tools...")
            if self.control_tools_task:
                self.control_tools_task.cancel()
                self.control_tools_task = None

async def main():
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    gui = SimpleGUI()
    gui.show()

    with loop:
        loop.run_forever()

# Run the application
if __name__ == '__main__':
    asyncio.run(main())
