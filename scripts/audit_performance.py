import os
import sys
import time
from pathlib import Path


class PerformanceAuditor:
    """ Performance Auditor.
    1. Startup Latency: Measures Import time of `warm_logic.kernel`.
    2. Storage Footprint: Scans for large files (>10MB).
    """

    def __init__(self, root_dir: str):
        self.root = Path(root_dir)
        sys.path.append(root_dir)

    def measure_startup(self):
        print(" Measuring Startup Latency...")
        start_time = time.perf_counter()
        try:
            # Simulate Kernel Boot (Importing Core Modules)
            import warm_logic.app.ci
            import warm_logic.app.ops
            import warm_logic.kernel.base.context

            # Note: warm_logic.kernel is a namespace, we import key submodules
            import warm_logic.kernel.ops.scheduler
        except Exception as e:
            print(f"BOOT FAILED: {e}")
            return False

        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        print(f"⏱ Kernel Import Time: {latency_ms:.2f} ms")

        if latency_ms > 500:
            print("PERFORMANCE VIOLATION: Boot > 500ms")
        else:
            print("PERFORMANCE PASSED: Boot < 500ms")
        return latency_ms

    def scan_storage(self):
        print("\nScanning for Storage Bloat (>10MB)...")
        bloat_found = False
        for f in self.root.rglob("*"):
            if f.is_file() and ".git" not in str(f) and "venv" not in str(f):
                size_mb = f.stat().st_size / (1024 * 1024)
                if size_mb > 10:
                    print(
                        f"⚠️  LARGE FILE: {f.relative_to(self.root)} ({size_mb:.2f} MB)"
                    )
                    bloat_found = True

        if not bloat_found:
            print("STORAGE OPTIMIZED: No large files found.")

    def run(self):
        self.measure_startup()
        self.scan_storage()


if __name__ == "__main__":
    auditor = PerformanceAuditor("./")
    auditor.run()
