#!/bin/bash
# voice_reply.sh — write a reply to Iðunn's voice message
# Usage: bash voice_reply.sh "your reply here"
# Or pipe: echo "reply" | bash voice_reply.sh

REPLY_FILE="/tmp/loki_voice_reply.txt"

if [ -n "$1" ]; then
    echo "$1" > "$REPLY_FILE"
else
    cat > "$REPLY_FILE"
fi

echo "Reply written — Iðunn will hear it shortly."
