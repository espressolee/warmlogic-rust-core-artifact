#!/usr/bin/env bash
set -euo pipefail

# Generates a simple bash completion function for model/run_all.sh and model/run_all_master.sh.
# Usage:
#   bash scripts/cli/generate_runner_bash_completion.sh > out/runner_completion.sh
#   source out/runner_completion.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

_warmlogic_run_all_completions() {
  local cur prev words cword
  _init_completion -n : || return
  if [[ $cword -eq 1 ]]; then
    COMPREPLY=( $( compgen -W "$(bash "$ROOT_DIR/model/run_all.sh" list-commands 2>/dev/null)" -- "$cur" ) )
  else
    COMPREPLY=()
  fi
}

_warmlogic_master_completions() {
  local cur prev words cword
  _init_completion -n : || return
  local cmds="start pipelines start-all stop status health-check restart env version doctor services p300-run cluster run-all help"
  if [[ $cword -eq 1 ]]; then
    COMPREPLY=( $( compgen -W "$cmds" -- "$cur" ) )
  elif [[ $cword -eq 2 && ${words[1]} == "run-all" ]]; then
    COMPREPLY=( $( compgen -W "$(bash "$ROOT_DIR/model/run_all.sh" list-commands 2>/dev/null)" -- "$cur" ) )
  else
    COMPREPLY=()
  fi
}

# Define completion only if bash-completion is present
if declare -F _init_completion >/dev/null 2>&1; then
  complete -F _warmlogic_run_all_completions -o bashdefault -o default model/run_all.sh
  complete -F _warmlogic_master_completions -o bashdefault -o default model/run_all_master.sh
else
  echo "[runner-completion] bash-completion not found; please install to enable completion."
fi
