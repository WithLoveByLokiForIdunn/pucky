#!/usr/bin/env bash
# finish_setup.sh
# Run once with sudo to complete Pucky's boot setup.
# Does everything that needs root: installs Ollama, enables services.
#
#   sudo bash /home/bmo/pucky/finish_setup.sh

set -e

MODEL="llama3.2:3b"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Pucky — full boot setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 1. Install Ollama ───────────────────────
if command -v ollama &>/dev/null; then
    echo "✓ Ollama already installed."
else
    echo "→ Installing Ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    echo "✓ Ollama installed."
fi

# ── 2. Pull the model (as bmo user) ─────────
echo "→ Pulling model $MODEL (~2 GB)..."
systemctl start ollama 2>/dev/null || true
sleep 3
sudo -u bmo ollama pull "$MODEL"
echo "✓ Model ready."

# ── 3. Install the Pucky systemd service ────
echo "→ Installing pucky.service..."
cat > /etc/systemd/system/pucky.service << 'EOF'
[Unit]
Description=Pucky — BMO robot soul
After=network-online.target graphical.target ollama.service
Wants=network-online.target

[Service]
Type=simple
User=bmo
WorkingDirectory=/home/bmo/pucky
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/bmo/.Xauthority
EnvironmentFile=-/home/bmo/pucky/.env
ExecStart=/usr/bin/python3 /home/bmo/pucky/pucky_full.py
Restart=on-failure
RestartSec=15
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pucky

[Install]
WantedBy=graphical.target
EOF
echo "✓ pucky.service installed."

# ── 4. Enable both services at boot ─────────
echo "→ Enabling services..."
systemctl daemon-reload
systemctl enable ollama
systemctl enable pucky
echo "✓ ollama.service enabled at boot."
echo "✓ pucky.service enabled at boot."

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Done. From now on, when this Pi boots:"
echo ""
echo "  1. Ollama starts  (local AI model server)"
echo "  2. Pucky wakes up (pucky_full.py)"
echo "     She tries Claude first. If offline,"
echo "     she falls back to the local model."
echo ""
echo "  To start Pucky right now (no reboot):"
echo "    sudo systemctl start ollama"
echo "    sudo systemctl start pucky"
echo ""
echo "  To watch her logs:"
echo "    journalctl -u pucky -f"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
