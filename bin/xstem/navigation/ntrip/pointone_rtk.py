import socket
import base64
import sys
import time
from pyrtcm import RTCMReader

# Replace with your actual NTRIP credentials and mountpoint
NTRIP_CASTER = "virtualrtk.pointonenav.com"
NTRIP_PORT = 2101
MOUNTPOINT = "POLARIS"
USERNAME = "9bef2wptc7"
PASSWORD = "z32atc7csc"

NTRIP_CASTER = "100.111.62.128"
NTRIP_PORT = 50010
MOUNTPOINT = "Woven_RTK_Mob"
USERNAME = "amiga@gmail.com"
PASSWORD = "amiga"






MESSAGE_ID = "1005"

def build_ntrip_request():
    credentials = f"{USERNAME}:{PASSWORD}"
    auth = base64.b64encode(credentials.encode()).decode()
    request = (
        f"GET /{MOUNTPOINT} HTTP/1.0\r\n"
        f"User-Agent: NTRIP python-client\r\n"
        f"Authorization: Basic {auth}\r\n"
        f"Ntrip-Version: Ntrip/2.0\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    return request

def send_gga(sock):
    # Example GGA sentence (replace with actual GNSS data if available)
    print("Sending GGA 1")
    gga_sentence = "$GPGGA,173938,3012.6120,N,09706.0840,W,1,08,0.9,150.0,M,0.0,M,,*63\r\n"
    sock.sendall(gga_sentence.encode())

def connect_ntrip():
    sock = socket.create_connection((NTRIP_CASTER, NTRIP_PORT))
    sock.sendall(build_ntrip_request().encode())

    # Read response header
    response = b""
    while not b"\r\n\r\n" in response:
        chunk = sock.recv(1024)
        if not chunk:
            break
        response += chunk

    if b"200 OK" not in response:
        print("Failed to connect to mountpoint.")
        print(response.decode())
        sys.exit(1)

    return sock

def parse_message_1005(msg):
   print(msg)
   return
   print(f"  RTCM Message 1005 received")
   print(f"  Station ID: {msg.reference_station_id}")
   print(f"  ECEF X: {msg.ref_station_ecef_x} m")
   print(f"  ECEF Y: {msg.ref_station_ecef_y} m")
   print(f"  ECEF Z: {msg.ref_station_ecef_z} m")
   print(f"  Antenna Height: {msg.antenna_height} m")
   print("-" * 50)


def main():
    print("Connecting to NTRIP caster...")
    sock = connect_ntrip()
    print("Connected. Sending GGA and reading RTCM messages...")

    stream = sock.makefile('rb')
    reader = RTCMReader(stream)
    send_gga(sock)
    last_gga_time = time.time()
    while True:
        if time.time() - last_gga_time > 10:
            print("Sending GGA")
            send_gga(sock)
            last_gga_time = time.time()

        try:
            i, msg = next(reader)
            print(f"RTCM Message Received: {msg.identity}")
            if msg.identity == MESSAGE_ID:
                parse_message_1005(msg)
            #print(msg)
        except StopIteration:
            print("No more messages.")
            break
        except Exception as e:
            print(f"Error reading message: {e}")
            break

if __name__ == "__main__":
    main()