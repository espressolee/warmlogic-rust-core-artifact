import os
import re
from pathlib import Path


def fix_file(file_path):
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return

    lines = content.split("\n")
    new_lines = []

    for i, line in enumerate(lines):
        new_lines.append(line)
        # Check if line ends with : and is likely a def/class/if/else/try/except header
        # and the next line (if exists) is NOT indented or is empty
        if line.strip().endswith(":"):
            # Look ahead
            if i + 1 >= len(lines):
                # EOF, need indent
                indent = get_indent(line) + "    "
                new_lines.append(f"{indent}...")
            else:
                next_line = lines[i + 1]
                if not next_line.strip():
                    # Empty line checking further ahead is complex,
                    # but simple heuristic: if next significant line is not indented more, we need a block
                    # For now, let's just insert '...' if the very next line is empty or de-indented?
                    # A safer approach for "stubs" described in the report (where usually it's def func(): [EOF] or next def)
                    pass

    # Actually, a regex approach for "def/class ... :\n(?! \s)" might be better.
    # Let's try to parse line by line and detect "def/class" logic more robustly

    # Simpler approach:
    # Read strict output from the previous vulture report? No, that's brittle.
    # Let's parse the file.
    pass


def robust_fix(file_path):
    """
    Reads the file, finds def/class ending in :, checks if body exists.
    If body is missing (next line not indented relative to def), inserts `    ...`.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except:
        return False

    lines = content.splitlines()
    fixed_lines = []

    for i, line in enumerate(lines):
        fixed_lines.append(line)
        stripped = line.strip()

        # We only care about def/class/if/else/elif/try/except stubs
        if stripped.endswith(":") and (
            stripped.startswith("def ")
            or stripped.startswith("class ")
            or stripped.startswith("@")
        ):
            # Calculate current indent
            current_indent = len(line) - len(line.lstrip())
            target_indent = current_indent + 4

            # Check next line
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                next_stripped = next_line.strip()

                # If next line is empty, we check the one after?
                # Or just assume if it's empty, we might need a docstring or pass.
                # But the error says "expected an indented block".
                # This usually happens when the next line is NON-EMPTY and NOT INDENTED.
                # Or if it IS empty and then the next token is dedented.

                if next_stripped and (
                    len(next_line) - len(next_line.lstrip()) <= current_indent
                ):
                    # Next line is code (not empty) and has same or less indent -> Missing block
                    fixed_lines.append(" " * target_indent + "...")
                elif not next_stripped:
                    # Next line is empty. Check if we hit EOF or another dedented block soon.
                    # For safety, let's just add `...` if it's a stub file.
                    # But we don't want to break existing valid code with empty lines.

                    # Look ahead for the next non-empty line
                    found_next = False
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip():
                            if len(lines[j]) - len(lines[j].lstrip()) <= current_indent:
                                # Found dedented code -> insert block
                                fixed_lines.append(" " * target_indent + "...")
                            found_next = True
                            break
                    if not found_next:
                        # EOF after empty lines -> insert block
                        fixed_lines.append(" " * target_indent + "...")
            else:
                # EOF immediately -> insert block
                fixed_lines.append(" " * target_indent + "...")

    new_content = "\n".join(fixed_lines) + "\n"
    if new_content != content:
        print(f"Fixing {file_path}")
        file_path.write_text(new_content, encoding="utf-8")
        return True
    return False


if __name__ == "__main__":
    root = Path("warm_logic/kernel")
    count = 0
    for f in root.rglob("*.py"):
        if robust_fix(f):
            count += 1
    print(f"Fixed {count} files.")
