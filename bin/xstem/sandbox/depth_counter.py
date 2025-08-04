import time
import redis
from labjack import ljm

def detect_and_push_encoder_data():
    # Open first found LabJack
    handle = ljm.openS("T7", "ANY", "ANY")

    # Write the specified values
    ljm.eWriteName(handle, "DIO0_EF_ENABLE", 0)  # Cannot change index if enabled.
    ljm.eWriteName(handle, "DIO0_EF_INDEX", 8)
    ljm.eWriteName(handle, "DIO0_EF_ENABLE", 1)
    ljm.eWriteName(handle, "DAC1_FREQUENCY_OUT_ENABLE", 1)

    # Initialize counters
    net_counts = 0
    revolutions = 0

    # Initialize previous states
    prev_state_fio0 = 0
    prev_state_fio1 = 0
    prev_counter_value = 0
    direction = 1  # 1 for clockwise, -1 for counterclockwise

    # Connect to Redis
    r = redis.Redis(host='localhost', port=6379, db=0)
    try:
        while True:
            timestamp = time.time()
            # Read digital inputs from FIO0 and FIO1
            state_fio0 = ljm.eReadName(handle, "FIO0")
            state_fio1 = ljm.eReadName(handle, "FIO1")
            volt_ain0 = ljm.eReadName(handle, "AIN0")
            counter_value = ljm.eReadName(handle, "DIO0_EF_READ_A")  # Read the integrated counter

            # Detect rising edges to determine direction
            if state_fio0 == 1 and prev_state_fio0 == 0:
                if prev_state_fio1 == 0:
                    direction = 1  # Clockwise
                else:
                    direction = -1  # Counterclockwise

            # Calculate net counts and revolutions based on count delta
            count_delta = counter_value - prev_counter_value
            net_counts += count_delta * direction
            revolutions = net_counts / 200.0

            print(f"Direction: {'Clockwise' if direction == 1 else 'Counterclockwise'}, Delta counts: {count_delta}")
            print(f"Net counts: {net_counts}, Revolutions: {revolutions}")

            data_array = [timestamp, net_counts, revolutions, volt_ain0, counter_value]
            # Push data to Redis queue
            r.rpush('encoder_data', str(data_array))

            # Update previous states
            prev_state_fio0 = state_fio0
            prev_state_fio1 = state_fio1
            prev_counter_value = counter_value

            # time.sleep(1)  # Sleep for 1 second before reading again

    except KeyboardInterrupt:
        # Close the LabJack handle on exit
        ljm.close(handle)
        print("Data acquisition stopped.")

# Example usage of the first script
detect_and_push_encoder_data()