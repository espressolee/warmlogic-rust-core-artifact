import os
import sys

print("CWD:", os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
print("Path:", sys.path)

try:
    import warm_logic

    print("Found warm_logic at:", warm_logic.__file__)
except ImportError as e:
    print("Failed to import warm_logic:", e)

try:
    import warm_logic.kernel

    print("Found warm_logic.kernel at:", warm_logic.kernel.__file__)
except ImportError as e:
    print("Failed to import warm_logic.kernel:", e)

try:
    import warm_logic.kernel.rust_loader

    print("Found rust_loader at:", warm_logic.kernel.rust_loader.__file__)
except ImportError as e:
    print("Failed to import rust_loader:", e)

try:
    from warm_logic.kernel.mesh.dht import SovereignDHT

    print("Successfully imported SovereignDHT")
except ImportError as e:
    print("Failed to import SovereignDHT:", e)
