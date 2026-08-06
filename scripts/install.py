import os
import shutil
import subprocess
import sys


def run_command(cmd, env=None):
    try:
        subprocess.check_call(cmd, shell=True, env=env)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing: {cmd}")
        return False


def install_warmlogic():
    print("WarmLogic Installation Script")
    print("================================")

    # 1. Check Python Version
    python_version = sys.version_info
    print(
        f"🔹 Python version: {python_version.major}.{python_version.minor}.{python_version.micro}"
    )
    if python_version.major < 3 or (
        python_version.major == 3 and python_version.minor < 9
    ):
        print("Error: WarmLogic requires Python 3.9+")
        return False

    # 2. Virtual Environment Check/Setup
    in_venv = sys.prefix != sys.base_prefix
    if not in_venv:
        print("Not in a virtual environment. Creating .venv...")
        if not os.path.exists(".venv"):
            if not run_command(f"{sys.executable} -m venv .venv"):
                print("Failed to create virtual environment.")
                return False

        # Determine the python executable in the new venv
        venv_python = os.path.join(".venv", "bin", "python")
        if os.name == "nt":
            venv_python = os.path.join(".venv", "Scripts", "python.exe")

        print(f"Relaunching installation inside .venv...")
        return run_command(f"{venv_python} {__file__}")

    # 3. Check for 'uv' or 'pip'
    has_uv = shutil.which("uv") is not None
    install_cmd = f"{sys.executable} -m pip install ."
    if has_uv:
        install_cmd = "uv pip install ."

    print(f"Using {'uv' if has_uv else 'pip'} for installation...")

    # 4. Install dependencies
    print("Installing dependencies...")
    if not run_command(install_cmd):
        return False

    # 5. Setup Environment
    if not os.path.exists(".env"):
        print("Creating .env from example...")
        if os.path.exists(".env.example"):
            shutil.copy(".env.example", ".env")
        else:
            with open(".env", "w") as f:
                import secrets as _s
                f.write(f"SOVEREIGN_COCKPIT_KEY={_s.token_urlsafe(32)}\n")
                f.write("COCKPIT_HTTP_PORT=5001\n")

    # 6. Verify Installation
    print("Verifying installation...")
    verify_cmd = f"{sys.executable} -c 'import warm_logic; print(\"WarmLogic core imported\")'"
    if not run_command(verify_cmd):
        return False

    print("\nWarmLogic Installation Complete!")
    print("\nNext Steps:")
    print(f"1. Activate environment: source .venv/bin/activate")
    print(f"2. Run the dashboard: {sys.executable} scripts/start_cockpit_web.py")
    print(f"3. Explore the CLI: {sys.executable} -m warm_logic.app.cli.wlctl --help")

    return True


if __name__ == "__main__":
    success = install_warmlogic()
    sys.exit(0 if success else 1)
