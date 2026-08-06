#!/usr/bin/env bash
# ==========================================================
# File: install.sh
# Project: Warm Logic — DevEnv v1.3
# Description:
#   Bootstrap script for the Warm Logic Developer Environment.
#
#   Responsibilities:
#     - Create Python virtual environment (.venv) under dev_env/
#     - Install Python dependencies (best-effort)
#     - Symlink CLI tools into ~/bin:
#         - wl_eventbus
#         - wl_agent_stream
#         - wl_patch_watch
# ==========================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
DEVENV_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${DEVENV_ROOT}/.." && pwd)"
VENV_DIR="${DEVENV_ROOT}/.venv"
BIN_DIR="${HOME}/bin"

echo "[DevEnv] Root: ${DEVENV_ROOT}"
echo "[DevEnv] Repo: ${REPO_ROOT}"
echo "[DevEnv] Venv: ${VENV_DIR}"

# ----------------------------------------------------------
# 1) Create ~/bin if missing
# ----------------------------------------------------------
if [ ! -d "${BIN_DIR}" ]; then
  echo "[DevEnv] Creating ${BIN_DIR}"
  mkdir -p "${BIN_DIR}"
fi

# ----------------------------------------------------------
# 2) Create Python virtual environment
# ----------------------------------------------------------
if [ ! -d "${VENV_DIR}" ]; then
  echo "[DevEnv] Creating Python virtual environment"
  python3 -m venv "${VENV_DIR}"
else
  echo "[DevEnv] Existing virtual environment detected"
fi

# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"

# ----------------------------------------------------------
# 3) Install Python dependencies (best-effort)
# ----------------------------------------------------------
REQ_DEV="${REPO_ROOT}/requirements-dev.txt"
REQ_ROOT="${REPO_ROOT}/requirements.txt"

echo "[DevEnv] Installing Python dependencies (best-effort)"

if [ -f "${REQ_DEV}" ]; then
  pip install -r "${REQ_DEV}" || echo "[WARN] Failed to install from requirements-dev.txt"
elif [ -f "${REQ_ROOT}" ]; then
  pip install -r "${REQ_ROOT}" || echo "[WARN] Failed to install from requirements.txt"
else
  pip install aiohttp jinja2 websockets || echo "[WARN] Fallback dependency install failed"
fi

# ----------------------------------------------------------
# 4) Symlink CLI tools
# ----------------------------------------------------------
link_cli () {
  local src="$1"
  local dst="${BIN_DIR}/$(basename "$1")"

  if [ -L "${dst}" ] || [ -f "${dst}" ]; then
    echo "[DevEnv] Updating symlink ${dst}"
    rm -f "${dst}"
  fi

  ln -s "${src}" "${dst}"
  chmod +x "${src}"
  echo "[DevEnv] Linked ${dst} -> ${src}"
}

echo "[DevEnv] Linking CLI tools"
link_cli "${DEVENV_ROOT}/cli/wl_eventbus"
link_cli "${DEVENV_ROOT}/cli/wl_agent_stream"
link_cli "${DEVENV_ROOT}/cli/wl_patch_watch"

echo
echo "[✓] DevEnv v1.3 installation complete."
echo "    Make sure ${HOME}/bin is on your PATH."
echo
