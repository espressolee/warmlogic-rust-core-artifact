import os
import sys

print(f"Python Executable: {sys.executable}")
print(f"CWD: {os.getcwd()}")
print(f"Path: {sys.path}")

try:
    import warm_logic

    print(f"Imported warm_logic: {warm_logic}")
    print(f"   file: {warm_logic.__file__}")
except ImportError as e:
    print(f"Failed to import warm_logic: {e}")

try:
    import warm_logic.kernel.ops.governance

    print(f"Imported warm_logic.kernel.ops.governance: {warm_logic.kernel.ops.governance}")
    print(f"   file: {getattr(warm_logic.kernel.ops.governance, '__file__', 'no file')}")
    print(f"   path: {getattr(warm_logic.kernel.ops.governance, '__path__', 'no path')}")
except ImportError as e:
    print(f"Failed to import warm_logic.kernel.ops.governance: {e}")

try:
    from warm_logic.kernel.ops.governance import ethics_triage

    print(f"Imported ethics_triage: {ethics_triage}")
except ImportError as e:
    print(f"Failed to import ethics_triage: {e}")

try:
    from warm_logic.kernel.base.core import utils

    print(f"Imported core.utils: {utils}")
    from warm_logic.kernel.base.core.utils import ops

    print(f"Imported core.utils.ops: {ops}")
except ImportError as e:
    print(f"Failed to import core.utils: {e}")
