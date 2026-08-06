from pathlib import Path


def project_root() -> Path:
    """Returns the root directory of the WarmLogic project."""
    return Path(os.getcwd())
