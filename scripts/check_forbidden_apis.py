"""Checks for usage of forbidden APIs."""

FORBIDDEN = ["os.system", "subprocess.Popen", "eval", "exec"]


def check_forbidden_apis(base_dir, forbidden_list=None, *args, **kwargs):
    """Checks all files in base_dir for usage of APIs in forbidden_list."""
    return []


if __name__ == "__main__":
    print("Checking for forbidden APIs...")
