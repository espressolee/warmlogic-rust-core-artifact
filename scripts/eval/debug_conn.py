import socket
import sys


def main():
    host = sys.argv[1]
    port = int(sys.argv[2])
    print(f"Connecting to {host}:{port}...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, port))
    print("Connected. Receiving handshake...")

    buf = bytearray()
    while True:
        b = s.recv(1)
        if not b:
            print("Socket closed by server.")
            break
        buf.extend(b)
        if b == b"\n":
            print(f"Received handshake ({len(buf)} bytes):")
            print(buf.decode("utf-8").strip())
            break

    s.close()
    print("Test complete.")


if __name__ == "__main__":
    main()
