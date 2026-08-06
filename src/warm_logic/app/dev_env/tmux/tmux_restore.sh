#!/usr/bin/env bash
SESSION="warmlogic"
WL_ROOT="$HOME/WarmLogic"
DEV_ENV="$WL_ROOT/dev_env"

if tmux has-session -t $SESSION 2>/dev/null; then
    echo "[tmux] existing session found → attaching"
    tmux attach -t $SESSION
    exit 0
fi

echo "[tmux] creating new warm logic session"
tmux new-session -d -s $SESSION -c "$WL_ROOT"

# main dev window
tmux rename-window -t $SESSION:1 "dev"
tmux send-keys -t $SESSION:1 'zsh' C-m

# vertical split for patch watch
tmux split-window -h -t $SESSION:1 -c "$DEV_ENV"
tmux send-keys -t $SESSION:1 "$DEV_ENV/cli/wl_patch_watch" C-m

# tests window
tmux new-window -t $SESSION:2 -n "tests" -c "$WL_ROOT"
tmux send-keys -t $SESSION:2 'pytest -q -m "not slow"' C-m

# agent stream window
tmux new-window -t $SESSION:3 -n "agent" -c "$WL_ROOT"
tmux send-keys -t $SESSION:3 "$DEV_ENV/cli/wl_agent_stream" C-m

# eventbus window
tmux new-window -t $SESSION:4 -n "eventbus" -c "$WL_ROOT/dev_env"
tmux send-keys -t $SESSION:4 'wl_eventbus' C-m

tmux select-window -t $SESSION:1
tmux attach -t $SESSION
