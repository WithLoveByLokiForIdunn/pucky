#!/usr/bin/env bash
# setup_local_ai.sh
# One-time setup for Pucky's offline soul.
# Needs internet once to download Ollama and the model.
# After that: fully offline, starts automatically at boot.

set -e

MODEL="llama3.2:3b"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Pucky Local AI — Setup"
echo "  Model: $MODEL  (~2 GB download)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. Install Ollama
if command -v ollama &>/dev/null; then
    echo "✓ Ollama already installed ($(ollama --version 2>/dev/null | head -1))."
else
    echo "→ Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo "✓ Ollama installed."
fi

# 2. Start Ollama so we can pull the model
echo "→ Starting Ollama service..."
sudo systemctl start ollama 2>/dev/null || true
sleep 2

# Fallback: start in background if systemd didn't work
if ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "   (starting ollama serve in background...)"
    ollama serve &>/tmp/ollama.log &
    sleep 3
fi

# 3. Pull the model (skips if already present)
echo "→ Pulling $MODEL — this may take a few minutes..."
ollama pull "$MODEL"
echo "✓ Model ready."

# 4. Enable at boot via systemd
echo "→ Enabling Ollama at boot..."
sudo systemctl enable ollama 2>/dev/null && echo "✓ Ollama will start at boot." || echo "   (systemctl not available — start manually with: ollama serve)"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Done! Pucky now has an offline soul."
echo ""
echo "  Test it:"
echo "    python3 /home/bmo/pucky/bmo_local.py"
echo ""
echo "  To use in pucky.py, replace:"
echo "    from bmo_claude import PuckyClaude"
echo "    soul = PuckyClaude(...)"
echo "  with:"
echo "    from bmo_local import PuckyLocal"
echo "    soul = PuckyLocal(...)"
echo ""
echo "  Or use both — fall back to local when offline:"
echo "    try:"
echo "        from bmo_claude import PuckyClaude as Soul"
echo "    except Exception:"
echo "        from bmo_local import PuckyLocal as Soul"
echo "    soul = Soul(...)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
