# Copyright 2026 espressolee
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from pathlib import Path
import importlib
import sys

_version_file = Path(__file__).parent / "VERSION"
__version__ = _version_file.read_text().strip() if _version_file.exists() else "0.0.0"


def _ensure_warm_logic_rs_importable() -> None:
    """
    Some environments ship a broken user-site `warm_logic_rs` wrapper that raises
    NameError on import. Prefer a working site-package module when that happens.
    """
    if "warm_logic_rs" in sys.modules:
        return

    try:
        module = importlib.import_module("warm_logic_rs")
        if hasattr(module, "SovereignStore") or hasattr(module, "RustZKProofGenerator"):
            return
    except Exception:
        pass

    original_path = list(sys.path)
    filtered_path = [p for p in original_path if "/.local/lib/python" not in p]
    if filtered_path == original_path:
        return

    try:
        sys.modules.pop("warm_logic_rs", None)
        sys.path[:] = filtered_path
        module = importlib.import_module("warm_logic_rs")
        if hasattr(module, "SovereignStore") or hasattr(module, "RustZKProofGenerator"):
            sys.modules["warm_logic_rs"] = module
    except Exception:
        sys.modules.pop("warm_logic_rs", None)
    finally:
        sys.path[:] = original_path


_ensure_warm_logic_rs_importable()
