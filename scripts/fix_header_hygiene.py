import os
from pathlib import Path


def fix_headers():
    root_dir = Path("src")
    header_py = Path("LICENSE_HEADER_PY").read_text()

    # Common C-style comment artifacts to strip
    garbage_patterns = [
        "/*",
        " * ",
        " */",
        " * Copyright",
        " * Licensed",
        " * You may obtain",
        " * See the License",
        " * limitations",
    ]

    count = 0
    for py_file in root_dir.rglob("*.py"):
        content = py_file.read_text().splitlines()

        # 1. Filter out garbage lines (C-style comments)
        clean_lines = []
        for line in content:
            is_garbage = False
            stripped = line.strip()
            # Check for C-style artifacts
            if stripped == "/*" or stripped == "*/":
                is_garbage = True
            elif stripped.startswith("* ") or stripped.startswith("/*"):
                is_garbage = True

            if not is_garbage:
                clean_lines.append(line)

        # 2. Check if valid header exists
        content_str = "\n".join(clean_lines)
        if "Licensed under the Apache License" not in content_str:
            new_content = header_py + "\n" + content_str
        else:
            new_content = content_str

        # 3. Write back
        py_file.write_text(new_content + "\n")
        count += 1

    print(f"Fixed headers in {count} Python files.")


if __name__ == "__main__":
    fix_headers()
