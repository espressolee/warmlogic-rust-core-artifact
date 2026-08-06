import ast
import os
import sys

# IGNORE_LIST: Internal modules or those we explicitly allow for now
IGNORE_LIST = {
    "warm_logic",
    "warm_logic_rs",
    "typing",
    "typing_extensions",  # Often backported, we'll decide on these later
}


def get_stdlib_names():
    if hasattr(sys, "stdlib_module_names"):
        return sys.stdlib_module_names
    # Fallback for older python (less accurate but sufficient for now)
    return set(sys.builtin_module_names) | {
        "argparse",
        "ast",
        "asyncio",
        "base64",
        "collections",
        "contextlib",
        "copy",
        "dataclasses",
        "datetime",
        "enum",
        "functools",
        "hashlib",
        "importlib",
        "inspect",
        "io",
        "json",
        "logging",
        "math",
        "multiprocessing",
        "os",
        "pathlib",
        "pickle",
        "platform",
        "random",
        "re",
        "shutil",
        "signal",
        "socket",
        "sqlite3",
        "ssl",
        "stat",
        "string",
        "subprocess",
        "sys",
        "tempfile",
        "threading",
        "time",
        "traceback",
        "types",
        "typing",
        "unittest",
        "uuid",
        "warnings",
        "weakref",
        "zipfile",
        "zoneinfo",
    }


STDLIB = get_stdlib_names()


def is_external(module_name):
    base_module = module_name.split(".")[0]
    if base_module in STDLIB:
        return False
    if base_module in IGNORE_LIST:
        return False
    # Special case for warm_logic siblings
    if base_module.startswith("warm_logic"):
        return False
    return True


def scan_file(filepath):
    external_deps = set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=filepath)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if is_external(alias.name):
                        external_deps.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and is_external(node.module):
                    external_deps.add(node.module)
    except Exception as e:
        print(f"Error parse {filepath}: {e}")

    return external_deps


def audit_kernel():
    root_dir = os.path.abspath("warm_logic/kernel")
    print(f" Scanning Kernel at: {root_dir}")
    print(f"ℹ Python Version: {sys.version.split()[0]}")

    infection_map = {}

    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.endswith(".py"):
                path = os.path.join(dirpath, f)
                deps = scan_file(path)
                if deps:
                    rel_path = os.path.relpath(path, os.getcwd())
                    infection_map[rel_path] = deps

    print("\n[INFECTION REPORT] External Dependencies Found:")
    if not infection_map:
        print("NONE. The Kernel is Pure.")
    else:
        for f, deps in infection_map.items():
            print(f"  - {f}: {', '.join(deps)}")

    # Summary of unique external libs
    all_external = set()
    for deps in infection_map.values():
        all_external.update(deps)

    print(f"\nUnique External Libs: {sorted(list(all_external))}")


if __name__ == "__main__":
    audit_kernel()
