import time
import redis
from labjack import ljm
import csv

def append_to_csv(data):
    return True
    file_path = "/mnt/managed_home/farm-ng-user-nrivadeneyra/orica/xdipper/data/data_logger_1.csv"
    with open(file_path, mode="a", newline='') as dfile:
        writer = csv.writer(dfile)
        writer.writerows([data])

def detect_and_publish_encoder_data():
    # Open first found LabJack
    handle = ljm.openS("T7", "ANY", "ANY")

    # Configure encoder
    ljm.eWriteName(handle, "DIO0_EF_ENABLE", 0)
    ljm.eWriteName(handle, "DIO1_EF_ENABLE", 0)
    ljm.eWriteName(handle, "DIO0_EF_INDEX", 10)
    ljm.eWriteName(handle, "DIO1_EF_INDEX", 10)
    ljm.eWriteName(handle, "DIO0_EF_ENABLE", 1)
    ljm.eWriteName(handle, "DIO1_EF_ENABLE", 1)

    # Connect to Redis
    host = "localhost"
    r = redis.Redis(host=host, port=6379, db=0)

    try:
        while True:
            timestamp = time.time()
            counter_value = ljm.eReadName(handle, "DIO0_EF_READ_A_F")
            volt_ain0 = ljm.eReadName(handle, "AIN0")
            volt_ain2 = ljm.eReadName(handle, "AIN2")
            volt_ain5 = ljm.eReadName(handle, "AIN5")

            revolutions = counter_value / 800.0

            print(f"Net counts: {counter_value}, Revolutions: {revolutions}, Tension: {volt_ain0}, Water: {volt_ain2}, TD: {volt_ain5}")

            data_array = [timestamp, counter_value, revolutions, volt_ain0, volt_ain2, volt_ain5]

            # Save to CSV
            # append_to_csv(data_array)

            # Publish to Redis Pub/Sub
            r.publish('encoder_data', str(data_array))

            time.sleep(0.01)  # Optional: throttle publishing rate

    except KeyboardInterrupt:
        ljm.close(handle)
        print("Data acquisition stopped.")

if __name__ == "__main__":
    detect_and_publish_encoder_data()
