import time
import ast
import redis
from utils import *
import csv
import os

host = "100.124.157.128"
r = redis.Redis(host=host, port=6379, db=0)
pubsub = r.pubsub()
pubsub.subscribe("encoder_data")

def append_to_csv(data, file_path):
    with open(file_path, mode="a", newline='') as dfile:
        writer = csv.writer(dfile)
        writer.writerows([data])


def main():
    print("Starting Redis listener...")
    file_identifier = str(int(time.time()))
    # data_dir = "/mnt/managed_home/farm-ng-user-nrivadeneyra/orica/xdipper/data/logs"
    data_dir = "/home/natalr/Documents/xdipper/data/logs"
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, f"data_logger_{file_identifier}.csv")
    print(f"Logging to {file_path}")
    while True:
        try:
            message = pubsub.get_message()
            if message and message['type'] == 'message':
                try:
                    raw = message['data']
                    if isinstance(raw, bytes):
                        entry = ast.literal_eval(raw.decode('utf-8'))
                        timestamp = round(entry[0], 2)
                        net_counts = entry[1] * 0
                        depth = calculate_line_depth(entry[2])
                        tension = calibrate_tension(entry[3])
                        water_sensor = calibrate_water_contact(entry[4])
                        td_sensor = calibrate_td_contact(entry[5])
                        data_array = [timestamp, net_counts, depth, tension, water_sensor, td_sensor]
                        append_to_csv(data_array, file_identifier)
                except Exception as e:
                    print("File Manager Inside Loop: ", e)
        except Exception as e:
            print("File Manager Outside Loop: ", e)

if __name__ == "__main__":
    main()

