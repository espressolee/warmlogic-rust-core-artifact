#!/usr/bin/env python3
"""
Paper 09: semantic-correctness verification for `Vec<u8>` extraction and BytesVec.

Goal:
- Provide hard evidence that the "fast path" performance fixes do not change byte content.
- Exercise a small matrix of Python input containers and view shapes.

This script is intended to be run twice:
- once under a stock PyO3 wheel venv
- once under the patched PyO3 wheel venv

It writes a JSON report under out/bridge_eval/<run-id>/vec_u8_semantics.json and exits
non-zero on any unexpected mismatch.
"""

from __future__ import annotations

import argparse
import array as _array
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


# Import strategy (match eval_bridge_v3.py):
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
    print(f"ERROR: Cannot import warm_logic_rs: {e}")
    sys.exit(1)


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha3_256(b: bytes) -> bytes:
    return hashlib.sha3_256(b).digest()


@dataclass(frozen=True)
class Variant:
    name: str
    make_obj: Callable[[bytes], Any]
    expected_bytes: Callable[[bytes], bytes]
    vec_ok: bool
    bytesvec_ok: bool
    pybytes_ok: bool


def _build_variants() -> list[Variant]:
    def _id(x: bytes) -> bytes:
        return x

    return [
        Variant(
            name="bytes",
            make_obj=lambda b: b,
            expected_bytes=_id,
            vec_ok=True,
            bytesvec_ok=True,
            pybytes_ok=True,
        ),
        Variant(
            name="bytearray",
            make_obj=lambda b: bytearray(b),
            expected_bytes=lambda b: bytes(bytearray(b)),
            vec_ok=True,
            bytesvec_ok=True,
            pybytes_ok=False,
        ),
        Variant(
            name="memoryview(bytes)",
            make_obj=lambda b: memoryview(b),
            expected_bytes=lambda b: bytes(memoryview(b)),
            vec_ok=True,
            bytesvec_ok=True,
            pybytes_ok=False,
        ),
        Variant(
            name="memoryview(bytearray)",
            make_obj=lambda b: memoryview(bytearray(b)),
            expected_bytes=lambda b: bytes(memoryview(bytearray(b))),
            vec_ok=True,
            bytesvec_ok=True,
            pybytes_ok=False,
        ),
        Variant(
            name="memoryview(bytes)[::2]",
            make_obj=lambda b: memoryview(b)[::2],
            expected_bytes=lambda b: bytes(memoryview(b)[::2]),
            vec_ok=True,
            bytesvec_ok=True,
            pybytes_ok=False,
        ),
        Variant(
            name="array('B')",
            make_obj=lambda b: _array.array("B", b),
            expected_bytes=lambda b: _array.array("B", b).tobytes(),
            vec_ok=True,
            bytesvec_ok=True,
            pybytes_ok=False,
        ),
        # Sequence fallbacks (should be accepted by Vec<u8> extraction, but NOT by BytesVec).
        Variant(
            name="list[int] (0..255)",
            make_obj=lambda b: list(b),
            expected_bytes=lambda b: bytes(list(b)),
            vec_ok=True,
            bytesvec_ok=False,
            pybytes_ok=False,
        ),
        Variant(
            name="array('I') values (0..255)",
            make_obj=lambda b: _array.array("I", list(b)),
            expected_bytes=lambda b: bytes(list(b)),
            vec_ok=True,
            bytesvec_ok=False,  # BytesVec requires bytes/buffer(u8); array('I') is not u8 buffer.
            pybytes_ok=False,
        ),
    ]


def _expect_raises(fn: Callable[[], Any]) -> tuple[str | None, str | None]:
    try:
        fn()
        return "expected exception, but call succeeded", None
    except Exception as e:  # noqa: BLE001
        # We intentionally do not pin exact exception types/messages here; the contract is
        # semantic accept/reject + byte equality, not framework-specific wording.
        return None, type(e).__name__


def _check_kv_set_get(
    *, kv: Any, set_fn: Callable[[str, Any], Any], label: str, value_obj: Any, expected: bytes
) -> str | None:
    key = "k"
    set_fn(key, value_obj)
    got = kv.get_bytes(key)
    if got is None:
        return f"{label}: get returned None"
    if not isinstance(got, (bytes, bytearray)):
        return f"{label}: get returned non-bytes type: {type(got)}"
    got_b = bytes(got)
    if got_b != expected:
        return (
            f"{label}: bytes mismatch (len got={len(got_b)} exp={len(expected)}; "
            f"sha256 got={_sha256_hex(got_b)} exp={_sha256_hex(expected)})"
        )
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="paper09_vec_u8_semantics")
    args = parser.parse_args()

    variants = _build_variants()
    sizes = [0, 1, 1024]

    # Deterministic "key" for hashing-based semantic checks.
    key = "k" * 32
    key_bytes = key.encode("utf-8")

    cases: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    for size in sizes:
        payload = bytes((i % 256 for i in range(size)))

        for v in variants:
            obj = v.make_obj(payload)
            expected = v.expected_bytes(payload)

            # 1) Vec<u8> extraction: stateful store roundtrip via SovereignKV.set_vec/get_bytes.
            api = "SovereignKV.set_vec"
            label = f"[{size}B] {api} <- {v.name}"
            expected_outcome = "accept" if v.vec_ok else "reject"
            observed_outcome = "reject"
            observed_exc_type: str | None = None
            observed_error: str | None = None
            try:
                kv = warm_logic_rs.SovereignKV()
                if v.vec_ok:
                    err = _check_kv_set_get(
                        kv=kv, set_fn=kv.set_vec, label=label, value_obj=obj, expected=expected
                    )
                    observed_outcome = "accept"
                    if err is not None:
                        observed_error = err
                        failures.append({"case": label, "error": err})
                        ok = False
                    else:
                        ok = True
                else:
                    # If we ever add a variant where vec_ok=False, enforce rejection.
                    rej, exc_type = _expect_raises(lambda: kv.set_vec("k", obj))
                    observed_exc_type = exc_type
                    observed_outcome = "accept" if rej is not None else "reject"
                    if rej is not None:
                        observed_error = rej
                        failures.append({"case": label, "error": rej})
                        ok = False
                    else:
                        ok = True
            except Exception as e:  # noqa: BLE001
                observed_exc_type = type(e).__name__
                observed_error = f"exception: {type(e).__name__}: {e}"
                failures.append({"case": label, "error": observed_error})
                ok = False
            cases.append(
                {
                    "case": label,
                    "size_bytes": size,
                    "api": api,
                    "variant": v.name,
                    "expected": expected_outcome,
                    "observed": observed_outcome,
                    "exc_type": observed_exc_type,
                    "ok": ok,
                    "error": observed_error,
                }
            )

            # 2) BytesVec extractor: stateful store roundtrip via SovereignKV.set_bytesvec/get_bytes.
            api = "SovereignKV.set_bytesvec"
            label = f"[{size}B] {api} <- {v.name}"
            expected_outcome = "accept" if v.bytesvec_ok else "reject"
            observed_outcome = "reject"
            observed_exc_type = None
            observed_error = None
            try:
                kv = warm_logic_rs.SovereignKV()
                if v.bytesvec_ok:
                    err = _check_kv_set_get(
                        kv=kv, set_fn=kv.set_bytesvec, label=label, value_obj=obj, expected=expected
                    )
                    observed_outcome = "accept"
                    if err is not None:
                        observed_error = err
                        failures.append({"case": label, "error": err})
                        ok = False
                    else:
                        ok = True
                else:
                    rej, exc_type = _expect_raises(lambda: kv.set_bytesvec("k", obj))
                    observed_exc_type = exc_type
                    observed_outcome = "accept" if rej is not None else "reject"
                    if rej is not None:
                        observed_error = rej
                        failures.append({"case": label, "error": rej})
                        ok = False
                    else:
                        ok = True
            except Exception as e:  # noqa: BLE001
                observed_exc_type = type(e).__name__
                observed_error = f"exception: {type(e).__name__}: {e}"
                failures.append({"case": label, "error": observed_error})
                ok = False
            cases.append(
                {
                    "case": label,
                    "size_bytes": size,
                    "api": api,
                    "variant": v.name,
                    "expected": expected_outcome,
                    "observed": observed_outcome,
                    "exc_type": observed_exc_type,
                    "ok": ok,
                    "error": observed_error,
                }
            )

            # 3) PyBytes-only API: SovereignKV.set_bytes should accept only bytes.
            api = "SovereignKV.set_bytes"
            label = f"[{size}B] {api} <- {v.name}"
            expected_outcome = "accept" if v.pybytes_ok else "reject"
            observed_outcome = "reject"
            observed_exc_type = None
            observed_error = None
            try:
                kv = warm_logic_rs.SovereignKV()
                if v.pybytes_ok:
                    err = _check_kv_set_get(
                        kv=kv, set_fn=kv.set_bytes, label=label, value_obj=obj, expected=expected
                    )
                    observed_outcome = "accept"
                    if err is not None:
                        observed_error = err
                        failures.append({"case": label, "error": err})
                        ok = False
                    else:
                        ok = True
                else:
                    rej, exc_type = _expect_raises(lambda: kv.set_bytes("k", obj))
                    observed_exc_type = exc_type
                    observed_outcome = "accept" if rej is not None else "reject"
                    if rej is not None:
                        observed_error = rej
                        failures.append({"case": label, "error": rej})
                        ok = False
                    else:
                        ok = True
            except Exception as e:  # noqa: BLE001
                observed_exc_type = type(e).__name__
                observed_error = f"exception: {type(e).__name__}: {e}"
                failures.append({"case": label, "error": observed_error})
                ok = False
            cases.append(
                {
                    "case": label,
                    "size_bytes": size,
                    "api": api,
                    "variant": v.name,
                    "expected": expected_outcome,
                    "observed": observed_outcome,
                    "exc_type": observed_exc_type,
                    "ok": ok,
                    "error": observed_error,
                }
            )

            # 4) Hash-based semantic check for Vec<u8> conversion (content, not just len).
            # This uses sign_bytes_vec(private_key, message: Vec<u8>) and compares to hashlib.
            api = "sign_bytes_vec"
            label = f"[{size}B] {api} digest <- {v.name}"
            expected_outcome = "accept" if v.vec_ok else "reject"
            observed_outcome = "reject"
            observed_exc_type = None
            observed_error = None
            try:
                if v.vec_ok:
                    got = warm_logic_rs.sign_bytes_vec(key, obj)
                    if not isinstance(got, (bytes, bytearray)):
                        observed_outcome = "accept"
                        observed_error = f"returned non-bytes type: {type(got)}"
                        failures.append({"case": label, "error": observed_error})
                        ok = False
                    else:
                        observed_outcome = "accept"
                        got_b = bytes(got)
                        exp_b = _sha3_256(key_bytes + expected)
                        if got_b != exp_b:
                            observed_error = (
                                "digest mismatch "
                                f"(sha256 got={_sha256_hex(got_b)} exp={_sha256_hex(exp_b)})"
                            )
                            failures.append({"case": label, "error": observed_error})
                            ok = False
                        else:
                            ok = True
                else:
                    # If we ever add vec_ok=False variants, enforce rejection here too.
                    rej, exc_type = _expect_raises(lambda: warm_logic_rs.sign_bytes_vec(key, obj))
                    observed_exc_type = exc_type
                    observed_outcome = "accept" if rej is not None else "reject"
                    if rej is not None:
                        observed_error = rej
                        failures.append({"case": label, "error": rej})
                        ok = False
                    else:
                        ok = True
            except Exception as e:  # noqa: BLE001
                observed_exc_type = type(e).__name__
                observed_error = f"exception: {type(e).__name__}: {e}"
                failures.append({"case": label, "error": observed_error})
                ok = False
            cases.append(
                {
                    "case": label,
                    "size_bytes": size,
                    "api": api,
                    "variant": v.name,
                    "expected": expected_outcome,
                    "observed": observed_outcome,
                    "exc_type": observed_exc_type,
                    "ok": ok,
                    "error": observed_error,
                }
            )

    out_dir = Path("out/bridge_eval") / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "vec_u8_semantics.json"
    payload = {
        "metadata": {
            "run_id": args.run_id,
            "timestamp": time.time(),
            "python": sys.version,
            "module_file": getattr(warm_logic_rs, "__file__", None),
            "use_installed": use_installed,
            "python_path": ext_path if not use_installed else None,
            "sizes": sizes,
            "variants": [v.name for v in variants],
            "variant_expectations": {
                v.name: {
                    "vec_ok": v.vec_ok,
                    "bytesvec_ok": v.bytesvec_ok,
                    "pybytes_ok": v.pybytes_ok,
                }
                for v in variants
            },
        },
        "cases": cases,
        "failures": failures,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote: {out_path}")

    if failures:
        print("\nFAILURES:")
        for f in failures[:20]:
            print(f"- {f['case']}: {f['error']}")
        if len(failures) > 20:
            print(f"... ({len(failures) - 20} more)")
        raise SystemExit(1)

    print("OK: all semantic checks passed")


if __name__ == "__main__":
    main()
