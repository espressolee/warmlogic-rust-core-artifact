import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
print(f"Connecting to {host}:{port}...")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
s.connect((host, port))
print("Connected. Receiving...")

data = b""
while True:
    try:
        chunk = s.recv(1024)
        if not chunk:
            print("EOF")
            break
        data += chunk
        print(f"Received chunk: {chunk}")
        if b"\n" in data:
            print("Got newline.")
            break
    except Exception as e:
        print(e)
        break

print(f"Total: {data}")
s.close()
