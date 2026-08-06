"""Generate SBOM Script Shim."""

from warm_logic.core.utils.codegen.generate_sbom import build_sbom, parse_lock

if __name__ == "__main__":
    import sys

    from warm_logic.core.utils.codegen.generate_sbom import main

    sys.exit(main())
