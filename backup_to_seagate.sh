#!/bin/bash
# Nightly backup of Pucky's world to the Seagate.
# Runs via cron. Safe to run any time — rsync only copies changes.

DRIVE="/mnt/pucky_hd"
SRC="/home/bmo/pucky/"
DEST="$DRIVE/pucky_backup/"
LOG="$DRIVE/pucky_backup/backup.log"

# Only run if the drive is mounted
if ! mountpoint -q "$DRIVE"; then
    echo "$(date '+%Y-%m-%d %H:%M') — Seagate not mounted, backup skipped." >> /home/bmo/pucky/workspace/backup.log
    exit 0
fi

echo "$(date '+%Y-%m-%d %H:%M') — Backup started." >> "$LOG"

rsync -a --delete \
    --exclude="__pycache__/" \
    --exclude="*.pyc" \
    --exclude=".git/" \
    "$SRC" "$DEST" >> "$LOG" 2>&1

echo "$(date '+%Y-%m-%d %H:%M') — Backup done." >> "$LOG"

# Daily list history — additive copy, never deletes old lists
DAILY_SRC="$SRC/workspace/daily_history/"
DAILY_DEST="$DRIVE/daily_list_history/"
if [ -d "$DAILY_SRC" ]; then
    mkdir -p "$DAILY_DEST"
    rsync -a "$DAILY_SRC" "$DAILY_DEST" >> "$LOG" 2>&1
    echo "$(date '+%Y-%m-%d %H:%M') — Daily list history synced." >> "$LOG"
fi
