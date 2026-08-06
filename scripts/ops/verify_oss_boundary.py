#!/usr/bin/env python3
import os
import re
import sys

# Sensitive patterns to detect
PATTERNS = {
    "Private Key": r"-----BEGIN (RSA|EC|DSA|OPENSSH|PRIVATE) KEY-----",
    "Internal IP": r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2[0-9]|3[0-1])\.\d{1,3}\.\d{1,3}",
    "Generic Secret": r"(?i)(password|passwd|secret|access_key|api_key|token|auth_token)[\s:=]+['\"]?([a-zA-Z0-9_\-\.]{12,})['\"]?",
    "Absolute Path": r"file:///Users/[a-zA-Z0-9_\-]+/",
    "Email": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",  # Simple email check
}


def scan_file(filepath):
    violations = []
    try:
        with open(filepath, "r", errors="ignore") as f:
            content = f.read()
            for name, pattern in PATTERNS.items():
                matches = re.finditer(pattern, content)
                for match in matches:
                    line_no = content.count("\n", 0, match.start()) + 1
                    violations.append(
                        {
                            "type": name,
                            "line": line_no,
                            "match": match.group(0)[:50],  # Snippet
                        }
                    )
    except Exception as e:
        print(f"Skipping {filepath}: {e}")
    return violations


def main():
    print("WARMLOGIC OSS BOUNDARY VERIFIER")
    print("=" * 50)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, "../../.."))  # Resonance root
    oss_root = os.path.join(repo_root, "WarmLogic-OSS")

    if not os.path.exists(oss_root):
        print(f"ERROR: OSS root not found at {oss_root}")
        sys.exit(1)

    total_files = 0
    total_violations = 0

    # We ignore standard Git/Node/Python artifacts
    ignored_dirs = {".git", "__pycache__", "node_modules", ".venv", ".pytest_cache"}

    for root, dirs, files in os.walk(oss_root):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for file in files:
            if file.endswith(
                (
                    ".py",
                    ".md",
                    ".sh",
                    ".json",
                    ".yaml",
                    ".yml",
                    ".js",
                    ".ts",
                    ".html",
                    ".css",
                    ".txt",
                )
            ):
                path = os.path.join(root, file)
                rel_path = os.path.relpath(path, oss_root)
                file_violations = scan_file(path)

                total_files += 1
                if file_violations:
                    print(f"VIOLATION in {rel_path}:")
                    for v in file_violations:
                        print(f"  [{v['type']}] L{v['line']}: {v['match']}")
                    total_violations += len(file_violations)

    print("=" * 50)
    print(f"Scanned {total_files} files.")
    if total_violations == 0:
        print("VERDICT: OSS BOUNDARY SECURE (0 Leaks Detected)")
        sys.exit(0)
    else:
        print(f"VERDICT: OSS BOUNDARY COMPROMISED ({total_violations} Violations)")
        sys.exit(1)


if __name__ == "__main__":
    main()
