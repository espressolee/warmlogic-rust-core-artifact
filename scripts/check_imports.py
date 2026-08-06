import os

import warm_logic
import warm_logic.kernel.mesh.dht

print(f"warm_logic file: {warm_logic.__file__}")
print(f"dht file: {warm_logic.kernel.mesh.dht.__file__}")
print(f"CWD: {os.getcwd()}")
print(f"PYTHONPATH: {os.environ.get('PYTHONPATH')}")
