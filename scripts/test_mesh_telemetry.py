import requests

BASE_URL = "http://127.0.0.1:5001"


def test_mesh_telemetry_endpoint():
    print("Testing Mesh Telemetry Endpoint...")
    r = requests.get(f"{BASE_URL}/api/mesh")
    assert r.status_code == 200
    data = r.json()

    print(f"Nodes found: {len(data)}")
    for node in data:
        print(f" - {node['node_id']} [{node['status']}] Latency: {node['latency']}")
        assert "node_id" in node
        assert "status" in node
        assert "latency" in node

    assert len(data) > 0, "No nodes returned. Expected at least the local peer or stub."
    print("Mesh telemetry verified.")


if __name__ == "__main__":
    try:
        test_mesh_telemetry_endpoint()
    except Exception as e:
        print(f"Test FAILED: {e}")
