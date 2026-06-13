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
