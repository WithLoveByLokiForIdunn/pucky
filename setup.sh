#!/bin/bash
# setup.sh
# Run this once on the Pi to install everything Pucky needs.
# Usage: bash setup.sh

echo ""
echo "═══════════════════════════════════════"
echo "  Pucky Setup — Installing dependencies"
echo "═══════════════════════════════════════"
echo ""

# Update system
sudo apt-get update -y
sudo apt-get upgrade -y

# Python dependencies
pip3 install --break-system-packages \
    robot-hat \
    RPi.GPIO \
    gpiozero \
    psutil \
    requests

# Enable I2C and SPI (needed for Robot Hat and display)
sudo raspi-config nonint do_i2c 0
sudo raspi-config nonint do_spi 0

echo ""
echo "✅ Setup complete!"
echo ""
echo "To run Pucky:"
echo "  python3 pucky.py"
echo ""
echo "To calibrate servos:"
echo "  python3 -c 'from servo_controller import ServoController; ServoController().calibrate()'"
echo ""
echo "To test emotion engine only:"
echo "  python3 emotion_engine.py"
echo ""
