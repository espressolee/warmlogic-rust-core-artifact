import http.client
import json
import os
import threading
import time

from warm_logic.kernel.substrate.stitch_server import StitchServer


def test_stitch_wan_resync():
    print("Starting WAN Re-sync Simulation...")

    server = StitchServer(host="127.0.0.1", port=8046)
    server.start()
    time.sleep(1)  # Wait for start

    # Pre-populate buffer
    server.broadcast("Init", {"seq": 1})
    server.broadcast("Init", {"seq": 2})

    print("Subscriber A connecting with Last-Event-ID: 1...")
    headers = {"Last-Event-ID": "1"}
    conn = http.client.HTTPConnection("127.0.0.1", 8046)
    conn.request("GET", "/stream", headers=headers)
    resp = conn.getresponse()

    def read_event(r):
        lines = []
        while True:
            l = r.readline().decode().strip()
            if not l:  # End of event block (\n\n)
                if lines:
                    break
                continue
            lines.append(l)
        return lines

    # Read replayed event (Init seq: 2)
    event1 = read_event(resp)
    print(f"Subscriber A replayed: {event1}")
    if any("id: 2" in l for l in event1):
        print("SUCCESS: Re-sync replayed missed event 2")
    else:
        print(f"FAILURE: Expected id: 2 in {event1}")
        return

    # Broadcast more while connected
    server.broadcast("Update", {"seq": 3})
    event2 = read_event(resp)
    print(f"Subscriber A received live: {event2}")

    if any("id: 3" in l for l in event2):
        print("SUCCESS: Subscriber A received live event 3")
    else:
        print(f"FAILURE: Expected id: 3 in {event2}")


if __name__ == "__main__":
    test_stitch_wan_resync()
