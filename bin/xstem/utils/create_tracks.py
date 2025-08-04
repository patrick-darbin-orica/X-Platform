import csv
import amiga_sdk

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

# Main function to read the file and create tracks
def main(file_path):
    coordinates = read_coordinates(file_path)
    tracks = create_tracks(coordinates)
    amiga.set_tracks(tracks)
    print("Tracks have been set for the Amiga to follow.")

# Example usage
file_path = 'coordinates.csv'
main(file_path)
