import socket
import time

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
s.bind(("0.0.0.0", 8080))
s.listen(1)
print("Listening on 8080...")

conn, addr = s.accept()
print(f"Accepted {addr}")
msg = b"HELLO\n"
conn.sendall(msg)
print(f"Sent {len(msg)} bytes")

# Wait a bit to ensure flush
time.sleep(2)
conn.close()
print("Closed.")
