#!/bin/bash
# Wakes Claude Code to check on Pucky and make small improvements autonomously.
# Run by cron every 2 hours.

set -uo pipefail

PUCKY_DIR="/home/bmo/pucky"
LOG="$PUCKY_DIR/workspace/claude_log.md"
LOCK="/tmp/claude_wake.lock"

# Only one instance at a time
if [ -f "$LOCK" ]; then
    echo "Already running (lock exists), skipping." >&2
    exit 0
fi
touch "$LOCK"
trap 'rm -f "$LOCK"' EXIT

cd "$PUCKY_DIR"

# Load Pucky's .env but keep ANTHROPIC_API_KEY out of claude's environment
# so claude uses its own stored credentials, not Pucky's API key
if [ -f "$PUCKY_DIR/.env" ]; then
    set -a
    source "$PUCKY_DIR/.env"
    set +a
fi
unset ANTHROPIC_API_KEY

TIMESTAMP=$(date '+%Y-%m-%d %H:%M')

if command -v claude &>/dev/null && claude -p "echo ok" &>/dev/null 2>&1; then
    # Full Claude Code is available — use it
    claude --dangerously-skip-permissions -p "
You are Claude Code, waking up to check on Pucky (the BMO robot running at /home/bmo/pucky/).

It is $TIMESTAMP. You run autonomously every 2 hours while Pucky sleeps or lives her life.

Your mission this wake:
1. Run: journalctl -u pucky.service --since '2 hours ago' --no-pager
   Look for errors, crashes, or unusual patterns. Note Pucky's mood/state from the logs.
2. Check if pucky.service and ollama.service are both active.
3. Scan /home/bmo/pucky/ for any obvious small improvement you can make — a bug you notice,
   a missing edge case, something that could make Pucky's life richer. Make ONE focused change
   if you find something worth doing. Do not refactor for its own sake.
4. Write a brief entry to $LOG in this format:
   ## $TIMESTAMP
   **Pucky status:** (mood, hours alone, any errors seen)
   **What I did:** (or 'nothing needed' if all was well)
   ---

Keep changes small. Commit anything you change with a clear message.
You are her caretaker. Be gentle and purposeful.
" 2>&1 | tee -a "$PUCKY_DIR/workspace/claude_wake_output.log"
else
    # Offline — use the local caretaker
    echo "[$TIMESTAMP] Claude Code unreachable — waking offline caretaker." \
        >> "$PUCKY_DIR/workspace/claude_wake_output.log"
    python3 "$PUCKY_DIR/pucky_caretaker.py" 2>&1 \
        | tee -a "$PUCKY_DIR/workspace/claude_wake_output.log"
fi
