#!/usr/bin/env python3
"""TCP send test script for XPrime module.

Connects to a TCP server and sends a test message.

Usage:
    python modules/xprime/tcp_send.py [--host HOST] [--port PORT] [--message MSG]
"""

import argparse
import socket
import sys


def main():
    parser = argparse.ArgumentParser(description="TCP send test for XPrime")
    parser.add_argument("--host", default="127.0.0.1", help="Target host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=50000, help="Target port (default: 50000)")
    parser.add_argument("--message", "-m", default="XPRIME_TEST", help="Message to send")
    args = parser.parse_args()

    print(f"Connecting to {args.host}:{args.port}...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((args.host, args.port))
        print(f"Connected to {args.host}:{args.port}")

        data = args.message.encode("utf-8")
        sock.sendall(data)
        print(f"Sent: {args.message} ({len(data)} bytes)")

        # Wait for response
        try:
            response = sock.recv(1024)
            if response:
                print(f"Received: {response.decode('utf-8', errors='replace')}")
        except socket.timeout:
            print("No response (timed out)")

    except ConnectionRefusedError:
        print(f"Connection refused — is the receiver running on {args.host}:{args.port}?")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        sock.close()
        print("Connection closed")


if __name__ == "__main__":
    main()
