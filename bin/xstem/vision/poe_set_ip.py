import depthai as dai

def check_str(s: str):
    parts = s.split(".")
    if len(parts) != 4:
        raise ValueError(f"Invalid format: {s}. Expected format: '255.255.255.255'")
    for num in parts:
        if not num.isdigit() or not (0 <= int(num) <= 255):
            raise ValueError(f"Each octet must be between 0 and 255: {s}")
    return s

# Ask user how to connect
print("Choose connection method:")
print('"1" for USB')
print('"2" for Ethernet (requires known IP address)')
conn_method = input("Enter the number: ").strip()

info = None
if conn_method == "1":
    found, info = dai.DeviceBootloader.getFirstAvailableDevice()
elif conn_method == "2":
    ip = check_str(input("Enter the device IP address: ").strip())
    devices = dai.DeviceBootloader.getAllAvailableDevices()
    info = next((d for d in devices if d.name == ip), None)
    found = info is not None
else:
    raise ValueError("Entered value should be '1' or '2'")

if found:
    print(f"Found device with name: {info.name}")
    print("-------------------------------------")
    print('"1" to set a static IPv4 address')
    print('"2" to set a dynamic IPv4 address')
    print('"3" to clear the config')
    print('"4" to print current configuration')
    key = input("Enter the number: ").strip()
    print("-------------------------------------")

    if key not in ["1", "2", "3", "4"]:
        raise ValueError("Entered value should be '1', '2', '3', or '4'")

    with dai.DeviceBootloader(info) as bl:
        if key == "4":
            config = bl.readConfig()
            print("Current Configuration:")
            print(f"IPv4 Address: {config.getIPv4()}")
            print(f"Subnet Mask: {config.getIPv4Mask()}")
            print(f"Gateway: {config.getIPv4Gateway()}")
            print(f"MacAddress: {config.getMacAddress()}")
            print(f"isStaticIPV4: {config.isStaticIPV4()}")
            exit(0)

        conf = dai.DeviceBootloader.Config()

        if key == "1":
            ipv4 = check_str(input("Enter IPv4: ").strip())
            mask = check_str(input("Enter IPv4 Mask: ").strip())
            gateway = check_str(input("Enter IPv4 Gateway: ").strip())
            conf.setStaticIPv4(ipv4, mask, gateway)

        elif key == "2":
            ipv4 = check_str(input("Enter IPv4: ").strip())
            mask = check_str(input("Enter IPv4 Mask: ").strip())
            gateway = check_str(input("Enter IPv4 Gateway: ").strip())
            conf.setDynamicIPv4(ipv4, mask, gateway)

        elif key == "3":
            success, error = bl.flashConfigClear()
            if success:
                print("Configuration cleared successfully.")
            else:
                print(f"Error clearing configuration: {error}")
            exit(0)

        confirm = input("Proceed with flashing configuration? (y/n): ").strip().lower()
        if confirm == "y":
            success, error = bl.flashConfig(conf)
            if success:
                print("Flashing successful.")
            else:
                print(f"Error flashing configuration: {error}")
        else:
            print("Operation cancelled.")
else:
    print("No device found.")
