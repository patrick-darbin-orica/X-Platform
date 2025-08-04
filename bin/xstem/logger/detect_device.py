from labjack import ljm

# Open the first found LabJack
handle = ljm.openS("T7", "ANY", "ANY")

# Read the device name
device_name = ljm.eReadNameString(handle, "DEVICE_NAME_DEFAULT")
print("Device Name:", device_name)

# Close the handle
ljm.close(handle)