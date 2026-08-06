import os
import pathlib


def count_lines(root_dir):
    stats = {}
    total_lines = 0
    total_files = 0

    # Extensions to map to languages
    ext_map = {
        ".py": "Python",
        ".rs": "Rust",
        ".md": "Markdown",
        ".json": "JSON",
        ".yaml": "YAML",
        ".yml": "YAML",
        ".html": "HTML",
        ".sh": "Shell",
        ".c": "C",
        ".cpp": "C++",
        ".h": "C Header",
        ".js": "JavaScript",
        ".ts": "TypeScript",
    }

    ignore_dirs = {
        ".git",
        "venv",
        "target",
        "node_modules",
        "__pycache__",
        "tmp",
        "proofs",
        "archives",
        "data",
        "model",
        ".venv",
        "experiments",
    }

    for root, dirs, files in os.walk(root_dir):
        # Filter directories
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        for file in files:
            ext = pathlib.Path(file).suffix
            if ext in ext_map:
                lang = ext_map[ext]
                path = os.path.join(root, file)
                try:
                    with open(path, "r", errors="ignore") as f:
                        lines = len(f.readlines())
                        if lang not in stats:
                            stats[lang] = {"files": 0, "lines": 0}
                        stats[lang]["files"] += 1
                        stats[lang]["lines"] += lines
                        total_lines += lines
                        total_files += 1
                except Exception:
                    pass

    print(f"{'Language':<15} {'Files':<10} {'Lines':<10}")
    print("-" * 35)
    for lang, data in sorted(stats.items(), key=lambda x: x[1]["lines"], reverse=True):
        print(f"{lang:<15} {data['files']:<10} {data['lines']:<10}")
    print("-" * 35)
    print(f"{'TOTAL':<15} {total_files:<10} {total_lines:<10}")


if __name__ == "__main__":
    count_lines(".")
