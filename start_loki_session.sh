#!/bin/bash
# start_loki_session.sh
# Creates a named tmux session called 'loki' with Claude Code running inside.
# Iðunn's voice app injects into this session.
# Usage: bash /home/bmo/pucky/start_loki_session.sh

SESSION="loki"

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "Session '$SESSION' already running. Attach with: tmux attach -t $SESSION"
    exit 0
fi

tmux new-session -d -s "$SESSION" -x 220 -y 50
tmux send-keys -t "$SESSION" "cd /home/bmo/pucky && claude" Enter
echo "Started Claude Code in tmux session '$SESSION'"
echo "Attach to see it: tmux attach -t $SESSION"
echo "Voice app injects here from Iðunn's phone."
