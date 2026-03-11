#!/usr/bin/env python3
"""TCP receive test script for XPrime module.

Listens for incoming TCP connections and prints received messages.

Usage:
    python modules/xprime/tcp_receive.py [--host HOST] [--port PORT]
"""

import argparse
import signal
import socket
import sys

_running = True


def _sighandler(signum, frame):
    global _running
    print("\nShutting down...")
    _running = False


def main():
    parser = argparse.ArgumentParser(description="TCP receive test for XPrime")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=50000, help="Listen port (default: 50000)")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _sighandler)
    signal.signal(signal.SIGTERM, _sighandler)

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.settimeout(1.0)
    server.bind((args.host, args.port))
    server.listen(1)

    print(f"Listening on {args.host}:{args.port}...")

    while _running:
        try:
            conn, addr = server.accept()
        except socket.timeout:
            continue

        print(f"Connection from {addr[0]}:{addr[1]}")

        try:
            conn.settimeout(5.0)
            while _running:
                data = conn.recv(1024)
                if not data:
                    break
                message = data.decode("utf-8", errors="replace")
                print(f"Received: {message} ({len(data)} bytes)")

                # Echo back with ACK prefix
                ack = f"ACK:{message}"
                conn.sendall(ack.encode("utf-8"))
                print(f"Sent: {ack}")
        except socket.timeout:
            print("Client timed out")
        except ConnectionResetError:
            print("Client disconnected")
        finally:
            conn.close()
            print(f"Connection from {addr[0]}:{addr[1]} closed")

    server.close()
    print("Server stopped")


if __name__ == "__main__":
    main()
