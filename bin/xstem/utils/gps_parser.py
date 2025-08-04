import csv
import pdb

# Function to extract latitude and longitude from a block of text
def extract_lat_long(text):
    lines = text.split('\n')
    lat, long = None, None
    for line in lines:
        if "Latitude:" in line:
            lat = line.split(":")[1].strip()
        elif "Longitude:" in line:
            long = line.split(":")[1].strip()
    return lat, long

def extract_north_east(text):
    lines = text.split('\n')
    north, east = None, None
    for line in lines:
        if "Relative pose north:" in line:
            north = line.split(":")[1].strip()
        elif "Relative pose east:" in line:
            east = line.split(":")[1].strip()
    return north, east

def extract_ecef(text):
    print(text)
    pdb.set_trace()
    lines = text.split('\n')
    x, y, z, accuracy, flags = None, None, None, None, None
    for line in lines:
        if "x:" in line:
            x = line.split(":")[1].strip()
        elif "y:" in line and "Accuracy" not in line and "accuracy" not in line:
            y = line.split(":")[1].strip()
        elif "z:" in line and "Horizontal" not in line:
            z = line.split(":")[1].strip()
        elif "Accuracy:" in line:
            accuracy = line.split(":")[1].strip()
        elif "Flags:" in line:
            flags = line.split(":")[1].strip()
    return [x,y,z,accuracy,flags]

t_file = 9

# Read the content of the text file
with open(f'/home/natalr/Documents/xdipper/xdipper/bin/xdipper/navigation/T{t_file}_gps_point_one_true.txt', 'r') as file:
    content = file.read()

# Split the content into blocks
# blocks = content.split('PVT FRAME')
#
# # Extract latitude and longitude from each block
# lat_long_data = []
# east_north_data = []
# ecef_data = []
# for block in blocks:
#     lat, long = extract_lat_long(block)
#     if lat and long:
#         lat_long_data.append([lat, long])
#
# blocks = content.split('RELATIVE POSITION FRAME')
#
# # Extract latitude and longitude from each block
# lat_long_data = []
# for block in blocks:
#     north, east = extract_north_east(block)
#     if north and east:
#         east_north_data.append([north, east])
#
# blocks = content.split("ECEF FRAME")
x = []
y= []
z=[]
east = []
north = []
lat = []
lon = []
accuracy=[]
flags=[]
# pdb.set_trace()
for line in content.split("\n"):
    if "Relative pose north:" in line:
        north.append(float(line.split(":")[1].strip()))
    elif "Relative pose east:" in line:
        east.append(float(line.split(":")[1].strip()))
    elif "Latitude:" in line:
        # pdb.set_trace()
        lat.append(float(line.split(":")[1].strip()))
    elif "Longitude:" in line:
        lon.append(float(line.split(":")[1].strip()))
    elif "x:" in line:
        x.append(float(line.split(":")[1].strip()))
    elif "y:" in line and "Accuracy" not in line and "accuracy" not in line:
        y.append(float(line.split(":")[1].strip()))
    elif "z:" in line and "Horizontal" not in line:
        z.append(float(line.split(":")[1].strip()))
    elif "Accuracy:" in line:
        accuracy.append(float(line.split(":")[1].strip()))
    elif "Flags:" in line:
        flags.append(line.split(":")[1].strip())
    else:
        pass

final_data = [(a , b , c , d , e, f, g, h, i) for a, b, c, d, e, f, g, h, i in zip(north, east, lat, lon, x, y, z, accuracy, flags)]

# Write the extracted data to a CSV file
with open(f'/home/natalr/Documents/xdipper/xdipper/bin/xdipper/navigation/T{t_file}_gps_point_one.csv', 'w', newline='') as csvfile:
    csvwriter = csv.writer(csvfile)
    csvwriter.writerow(["North", "East", "Lat", "Lon", "X", "Y", "Z", "Accuracy", "Flags"])
    csvwriter.writerows(final_data)

print("Latitude and Longitude data has been extracted and saved to lat_long_data.csv")
