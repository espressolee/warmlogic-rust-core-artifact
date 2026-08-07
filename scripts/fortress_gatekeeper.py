import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from warm_logic.kernel.infra.rust import warm_logic_rust

    if warm_logic_rust.check_multi_arch_integrity():
        print("SILICON IDENTITY SCENARIO OK (not verification): Sovereign Fleet Membership Confirmed.")
        sys.exit(0)
    else:
        print("ALIEN HARDWARE DETECTED: Startup denied.")
        sys.exit(1)
except ImportError:
    print(" SECURITY CORE MISSING: Build warm_logic_rust first.")
    sys.exit(2)
except Exception as e:
    print(f"SECURITY CRITICAL FAILURE: {e}")
    sys.exit(3)
