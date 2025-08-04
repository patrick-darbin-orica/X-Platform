import csv
import amiga_sdk
import keyboard

# Initialize the Amiga platform
amiga = amiga_sdk.Amiga()


# Function to read coordinates from a CSV file
def read_coordinates(file_path):
    coordinates = []
    with open(file_path, mode='r') as file:
        csv_reader = csv.DictReader(file)
        for row in csv_reader:
            coordinates.append((row['lat'], row['long']))
    return coordinates


# Function to convert coordinates into tracks
def create_tracks(coordinates):
    tracks = []
    for lat, long in coordinates:
        track_point = amiga_sdk.TrackPoint(latitude=float(lat), longitude=float(long))
        tracks.append(track_point)
    return tracks


# Function to move Amiga to the first waypoint
def move_to_first_waypoint(tracks):
    if tracks:
        first_waypoint = tracks
        amiga.move_to(first_waypoint)
        print(f"Moving to the first waypoint: {first_waypoint}")


# Main function to read the file and create tracks
def main(file_path):
    coordinates = read_coordinates(file_path)
    tracks = create_tracks(coordinates)
    print("Tracks have been set for the Amiga to follow.")

    # Wait for the 'f' key press to move to the first waypoint
    print("Press 'f' to move to the first waypoint.")
    keyboard.wait('f')
    move_to_first_waypoint(tracks)


# Example usage
file_path = 'coordinates.csv'
main(file_path)
