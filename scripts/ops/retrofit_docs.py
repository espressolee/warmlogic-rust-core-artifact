#!/usr/bin/env python3
import os


def retrofit_file(path):
    print(f"Retrofitting {path}...")
    with open(path, "r", errors="ignore") as f:
        content = f.read()

    lines = content.splitlines()
    if not lines:
        return

    # Check if tags already exist
    if (
        "AGENT_FOCUS" in content
        and "Summary" in content
        and "Technical Debt" in content
    ):
        print(f"  - Tags already present in {path}. Skipping.")
        return

    # Look for the first H1 header
    h1_index = -1
    for i, line in enumerate(lines):
        if line.startswith("# "):
            h1_index = i
            break

    # Prepare tag blocks
    # We try to infer some context from the filename if possible, otherwise use placeholders
    focus = "Research & Development"
    if "ops" in path or "spec" in path:
        focus = "Operations & Infrastructure"
    elif "protocol" in path:
        focus = "Core Protocol & Governance"

    summary = "System-generated summary placeholder. Requires manual refinement."
    debt = "Technical debt status pending review."

    tag_block = [
        "",
        f"> **AGENT_FOCUS**: {focus}",
        f"> **Summary**: {summary}",
        f"> **Technical Debt**: {debt}",
        "",
    ]

    if h1_index == -1:
        print(f"  - No H1 header found in {path}. Prepending tags at the top.")
        # Prepend to the top
        new_lines = tag_block + lines
    else:
        # Insert after H1
        new_lines = lines[: h1_index + 1] + tag_block + lines[h1_index + 1 :]

    with open(path, "w") as f:
        f.write("\n".join(new_lines) + "\n")
    print(f"  - Retrofitted {path} successfully.")


def main():
    target_dirs = ["docs", "spec"]
    for target_dir in target_dirs:
        if not os.path.exists(target_dir):
            continue
        for root, dirs, files in os.walk(target_dir):
            if "archive" in root:
                continue
            for file in files:
                if file.endswith(".md") and not file.startswith("._"):
                    retrofit_file(os.path.join(root, file))


if __name__ == "__main__":
    main()
