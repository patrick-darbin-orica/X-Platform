import pandas as pd
import json
import pdb

path = "drill_plan.json"

data = json.load(open(path, "r"))

# Extract RTK data
rtk_data = {
    "id": data["RTK"]["id"],
    'name': data['RTK']['name'],
    'lat': data['RTK']['gps']['lat'],
    'long': data['RTK']['gps']['long']
}

# Extract points data
points_data = [
    {
        "id": point["id"],
        'name': point['name'],
        'lat': point['gps']['lat'],
        'long': point['gps']['long']
    }
    for point in data['points']
]

# Combine RTK and points data
combined_data = [rtk_data] + points_data

# Convert to DataFrame
df = pd.DataFrame(combined_data)
df.to_csv("drill_plan.csv", index=False)

print(df)