import ctypes
import json
import os
import sys
from array import array
from pathlib import Path
from typing import Any

# Import strategy matches eval_bridge_v3.py:
# - Default: load the repo-local extension from warm_logic_rs/python_packages_v2
# - Docker / alternate envs: set WARM_LOGIC_RS_USE_INSTALLED=1 to import the installed wheel
# - Or set WARM_LOGIC_RS_PYTHON_PATH=/path/to/python_packages_dir to override explicitly
use_installed = os.environ.get("WARM_LOGIC_RS_USE_INSTALLED") == "1"
ext_path = os.environ.get("WARM_LOGIC_RS_PYTHON_PATH")
repo_root = os.getcwd()
if not use_installed:
    ext_path = ext_path or os.path.join(repo_root, "warm_logic_rs", "python_packages_v2")
    sys.path.insert(0, ext_path)
    sys.path.insert(1, repo_root)
else:
    sys.path.append(repo_root)

try:
    import warm_logic_rs

    print(f"Loaded warm_logic_rs from: {warm_logic_rs.__file__}")
except ImportError as e:
    print(f"Failed to load warm_logic_rs: {e}")
    sys.exit(1)


def ptr_pybytes_ctypes(b: bytes) -> int:
    pyapi = ctypes.pythonapi
    pyapi.PyBytes_AsString.restype = ctypes.c_void_p
    pyapi.PyBytes_AsString.argtypes = [ctypes.py_object]
    return int(pyapi.PyBytes_AsString(b))


def ptr_pybytearray_ctypes(b: bytearray) -> int:
    pyapi = ctypes.pythonapi
    pyapi.PyByteArray_AsString.restype = ctypes.c_void_p
    pyapi.PyByteArray_AsString.argtypes = [ctypes.py_object]
    return int(pyapi.PyByteArray_AsString(b))


def record_case(name: str, obj: Any, *, py_ptr: int | None = None) -> dict[str, Any]:
    mv = None
    try:
        mv = memoryview(obj)
    except TypeError:
        mv = None

    rust_ptr = int(warm_logic_rs.get_buffer_buf_ptr(obj))
    out: dict[str, Any] = {
        "name": name,
        "py_ptr": py_ptr,
        "rust_ptr": rust_ptr,
        "ptr_match": (py_ptr == rust_ptr) if py_ptr is not None else None,
        "type": str(type(obj)),
    }

    if mv is not None:
        out["memoryview"] = {
            "len": mv.nbytes,
            "readonly": mv.readonly,
            "itemsize": mv.itemsize,
            "ndim": mv.ndim,
            "shape": mv.shape,
            "strides": mv.strides,
            "c_contiguous": mv.c_contiguous,
            "f_contiguous": mv.f_contiguous,
            "contiguous": mv.contiguous,
        }

    # Zero-copy slice view should require C-contiguity.
    try:
        out["benchmark_zero_copy_buffer_len"] = int(warm_logic_rs.benchmark_zero_copy_buffer(obj))
        out["benchmark_zero_copy_buffer_error"] = None
    except Exception as e:  # noqa: BLE001
        out["benchmark_zero_copy_buffer_len"] = None
        out["benchmark_zero_copy_buffer_error"] = f"{type(e).__name__}: {e}"

    # Acquire buffer len_bytes should succeed for any exporter implementing buffer protocol.
    try:
        out["benchmark_acquire_buffer_len_bytes"] = int(warm_logic_rs.benchmark_acquire_buffer_len(obj))
        out["benchmark_acquire_buffer_error"] = None
    except Exception as e:  # noqa: BLE001
        out["benchmark_acquire_buffer_len_bytes"] = None
        out["benchmark_acquire_buffer_error"] = f"{type(e).__name__}: {e}"

    return out


def main() -> None:
    size = 1_000_000  # large enough to exercise contiguity without huge memory cost
    b = b"\x00" * size
    ba = bytearray(b)
    arr = array("B", b)

    mv_bytes = memoryview(b)
    mv_noncontig = mv_bytes[::2]

    cases: list[dict[str, Any]] = []

    cases.append(record_case("bytes", b, py_ptr=ptr_pybytes_ctypes(b)))
    cases.append(record_case("memoryview(bytes)", mv_bytes, py_ptr=ptr_pybytes_ctypes(b)))
    cases.append(record_case("bytearray", ba, py_ptr=ptr_pybytearray_ctypes(ba)))
    cases.append(record_case("memoryview(bytearray)", memoryview(ba), py_ptr=ptr_pybytearray_ctypes(ba)))
    addr_arr, _len = arr.buffer_info()
    cases.append(record_case("array('B')", arr, py_ptr=int(addr_arr)))
    cases.append(record_case("memoryview(bytes)[::2] (non-contig)", mv_noncontig, py_ptr=ptr_pybytes_ctypes(b)))

    out = {
        "metadata": {"size_bytes": size},
        "cases": cases,
    }

    out_dir = Path("out/bridge_eval/buffer_variants")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "buffer_variants.json"
    out_path.write_text(json.dumps(out, indent=2))

    print(f"Wrote: {out_path}")
    for c in cases:
        print(
            f"- {c['name']}: ptr_match={c['ptr_match']} c_contig={c.get('memoryview',{}).get('c_contiguous')} zero_copy_err={c['benchmark_zero_copy_buffer_error']}"
        )


if __name__ == "__main__":
    main()
