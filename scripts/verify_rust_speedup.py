import time
import hashlib
import time
import hashlib
from warm_logic import warm_logic_rs


def python_merkle_hash(left: str, right: str) -> str:
    # Double SHA256 (Bitcoin standard)
    h1 = hashlib.sha256((left + right).encode()).digest()
    h2 = hashlib.sha256(h1).digest()
    return h2.hex()


def benchmark():
    iterations = 100000
    left = "a" * 64
    right = "b" * 64

    print(f"Benchmarking Merkle Hash ({iterations} iterations)...")

    # Python
    start = time.time()
    for _ in range(iterations):
        python_merkle_hash(left, right)
    py_time = time.time() - start
    print(f"Python Time: {py_time:.4f}s")

    # Rust
    start = time.time()
    for _ in range(iterations):
        warm_logic_rs.merkle_hash(left, right)
    rs_time = time.time() - start
    print(f"Rust Time:   {rs_time:.4f}s")

    speedup = py_time / rs_time
    print(f"Speedup:     {speedup:.2f}x")

    if speedup > 3.0:  # Expecting massive gains
        print("P999 Optimization Goal MET")
    else:
        print("Optimization Insufficient")


if __name__ == "__main__":
    benchmark()
