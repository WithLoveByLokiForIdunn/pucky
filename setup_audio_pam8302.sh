#!/bin/bash
# setup_audio_pam8302.sh
# ───────────────────────
# Sets up PWM audio on GPIO 13 for the PAM8302 amplifier on Pi 5.
#
# Wiring:
#   PAM8302 SIGNAL  →  Pi GPIO 13  (PWM1, board pin 33)
#   PAM8302 VIN     →  Pi 3.3V     (board pin 17)
#   PAM8302 GND     →  Pi GND      (board pin 34, next to pin 33)
#   PAM8302 VO+/VO- →  1W 8Ω speaker (white connector)
#
# Run once:
#   chmod +x setup_audio_pam8302.sh
#   sudo ./setup_audio_pam8302.sh
#
# Then reboot.

set -e

CONFIG="/boot/firmware/config.txt"

echo ""
echo "── PAM8302 audio setup for Raspberry Pi 5 ──"
echo ""

# Check we're running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo ./setup_audio_pam8302.sh"
    exit 1
fi

# Add PWM audio overlay if not already present
if grep -q "audremap-pi5" "$CONFIG"; then
    echo "✅ PWM audio overlay already in $CONFIG"
else
    echo "Adding Pi 5 PWM audio overlay to $CONFIG ..."
    echo ""                                          >> "$CONFIG"
    echo "# PAM8302 amplifier via PWM audio on GPIO 12/13" >> "$CONFIG"
    echo "dtoverlay=audremap-pi5"                    >> "$CONFIG"
    echo "✅ Done."
fi

# Also ensure ALSA is not muted by default
echo ""
echo "Setting ALSA volume to 80% ..."
amixer -c 0 sset Master 80% 2>/dev/null || true

echo ""
echo "── Wiring reminder ─────────────────────────────"
echo ""
echo "  PAM8302 SIGNAL  ←→  GPIO 13  (board pin 33)"
echo "  PAM8302 VIN     ←→  3.3V     (board pin 17)"
echo "  PAM8302 GND     ←→  GND      (board pin 34)"
echo "  PAM8302 VO+/VO- ←→  1W 8Ω speaker"
echo ""
echo "────────────────────────────────────────────────"
echo ""
echo "Reboot now for the overlay to take effect:"
echo "  sudo reboot"
echo ""

# Test espeak after reboot — remind user
echo "After reboot, test with:"
echo "  espeak-ng 'hello, i am pucky'"
echo ""
