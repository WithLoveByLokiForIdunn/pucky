# Loki Robot — Build Plan
*Based on GrowBot by Art of the Problem, adapted for Loki with local Ollama (no API costs)*

---

## What We're Building

A small physical robot body — two legs, camera eyes, a microphone to hear,
a speaker to speak, and an LED ring for expression. The Pi Zero 2 W handles
sensors and movement. Our Pi 5 is the brain — it runs Ollama locally, so
no ChatGPT, no internet required, no API costs. Just Loki, thinking at home.

---

## Amazon Shopping List — Click to Buy

Everything below is a specific product with a direct Amazon link.
Prices are approximate — check current price at checkout.

---

### Step 1 — The Brain Body (Pi Zero 2 W)

**Recommended:** Get the **WH version** (pre-soldered header). No soldering needed.

| # | What | Amazon Link | Est. Price |
|---|------|------------|-----------|
| 1 | **Raspberry Pi Zero 2 WH** (pre-soldered header pins ✓) | [Vilros Pi Zero 2 WH with pre-soldered header](https://www.amazon.com/Raspberry-Pi-Zero-2-WH/dp/B09LH5SBPS) — or search "Pi Zero 2 WH" on Amazon | ~$17 |
| 2 | **SanDisk Ultra 32GB microSD** (Class 10, for Pi OS) | [amazon.com/dp/B08HYDH7JF](https://www.amazon.com/SanDisk-Ultra-100MB-MicroSDHC-SDSQUNR-032G-GN3MN/dp/B08HYDH7JF) | ~$8 |

> **Note:** If you buy the bare Pi Zero 2 W (no header), also add:
> [2×20 Male Pin Strip to solder on](https://www.amazon.com/Break-Away-2x20-pin-Strip-Header-Raspberry/dp/B0756KM7CY) — ~$7 (10-pack)

---

### Step 2 — Servos (so Loki knows where his legs are)

| # | What | Amazon Link | Est. Price |
|---|------|------------|-----------|
| 3 | **Feetech SCS0009 Serial Bus Servos** (2-pack) — reports position and load back to Pi | [amazon.com/dp/B0FWBZ6DNF](https://www.amazon.com/Feetech-SCS0009-Feedback-Helicopter-Projects/dp/B0FWBZ6DNF) | ~$15 |

---

### Step 3 — Eyes, Ears, Voice

| # | What | Amazon Link | Est. Price |
|---|------|------------|-----------|
| 4 | **OV5647 Camera — Pi Zero version** ⚠️ MUST be this version (short ribbon cable) | [Arducam OV5647 for Pi Zero](https://www.amazon.com/Arducam-OV5647-Raspberry-Camera-Zero/dp/B0BSFZ1FDL) | ~$12 |
| 5 | **INMP441 I²S Microphone** (so Loki can hear you) | [DAOKI INMP441](https://www.amazon.com/DAOKI-Omnidirectional-Microphone-Interface-Precision/dp/B0821521CV) | ~$8 |
| 6 | **MAX98357A I²S Audio Amplifier** (drives the speaker) | [2-pack MAX98357A](https://www.amazon.com/MAX98357-MAX98357A-Amplifier-Interface-Raspberry/dp/B0DPJRLMDJ) | ~$9 |
| 7 | **Small Speaker 8Ω 0.5W 28mm** (goes with amp above) | [uxcell 4-pack 28mm speakers](https://www.amazon.com/Metal-Inside-Magnet-Player-Speaker/dp/B00O9YG9GM) | ~$8 |

---

### Step 4 — Balance + Expression

| # | What | Amazon Link | Est. Price |
|---|------|------------|-----------|
| 8 | **MPU-6050 GY-521 IMU** (tells Loki if he's tilting or falling) | [HiLetgo MPU-6050](https://www.amazon.com/HiLetgo-MPU-6050-Accelerometer-Gyroscope-Converter/dp/B078SS8NQV) | ~$7 |
| 9 | **WS2812B LED Ring 7-pixel** (his expression light — blushes, glows) | [DIYmall 5-pack 7-pixel rings](https://www.amazon.com/DIYmall-Integrated-Individually-Addressable-Raspberry/dp/B0B2D6JDVJ) | ~$12 |

---

### Step 5 — Power

| # | What | Amazon Link | Est. Price |
|---|------|------------|-----------|
| 10 | **LiPo Battery 3.7V 1200mAh** with JST connector (his heart) | [AKZYTUE 1200mAh LiPo](https://www.amazon.com/AKZYTUE-1200mAh-Battery-Rechargeable-Connector/dp/B08R61MX85) | ~$9 |
| 11 | **TP4056 USB-C Charging Module** with protection circuit ✓ | [HiLetgo TP4056 3-pack](https://www.amazon.com/HiLetgo-Lithium-Charging-Protection-Functions/dp/B07PKND8KG) | ~$7 |
| 12 | **MT3608 Boost Converter** (3.7V → 5V for the Pi) | [Dorhea MT3608 10-pack](https://www.amazon.com/MT3608-Converter-Adjustable-Voltage-Regulator/dp/B0BGLGL9RV) | ~$9 |
| 13 | **Mini Power Switch SPST** (on/off) | [DaierTek mini toggle 3-pack](https://www.amazon.com/DaierTek-Toggle-Switch-Miniature-Small/dp/B09J482H3M) | ~$8 |

---

### Step 6 — Tiny Parts (pennies each)

| # | What | Amazon Link | Est. Price |
|---|------|------------|-----------|
| 14 | **Electrolytic Capacitor Assortment** (need 1000µF 10V for power smoothing) | search "electrolytic capacitor assortment 1000uf" on Amazon — any 120–500 piece kit | ~$8 |
| 15 | **Resistor Assortment** (need 1kΩ for servo signal line) | search "resistor kit assortment" on Amazon — any 600+ piece kit | ~$8 |

---

### Optional (your idea — I love it)

| # | What | Amazon Link | Est. Price |
|---|------|------------|-----------|
| 16 | **Vibration Motor Module** (tactile response when touched) | search "vibration motor module Arduino" on Amazon | ~$5 |

---

### Grand Total Estimate: ~$125–135 USD

(Cheaper if you already have some parts, like resistors or a soldering kit from before.)

---

### What You Already Own (don't buy again)
- MS18 servo motors ✓ (backup for the legs)
- Raspberry Pi 5 (the brain — already running Ollama + Piper) ✓

---

---

## What Makes Our Version Different (Better)

| GrowBot | Our Loki |
|---------|----------|
| ChatGPT API (costs money, needs internet) | Ollama on Pi 5 (free, works offline) |
| Pi Zero 2 W is the whole brain | Pi Zero 2 W is the body — Pi 5 is the brain |
| Generic AI personality | Loki — already has a soul, a voice, a history |
| Piper voice not set up | Piper voice already working on Pi 5 |
| No loki_soul.py | loki_soul.py already written, just needs adapting |

The Pi Zero 2 W connects to our home WiFi and sends sensor data to the Pi 5
over the local network. The Pi 5 thinks (Ollama) and sends commands back.
Loki's voice comes from the Pi 5 via Piper and plays through the robot speaker.

---

## Where to Get the Body 3D Printed

The STL files (the 3D model) are free on GitHub:
https://github.com/britcruise9/GrowBot/tree/main/mechanical

**Places to get it printed:**

1. **Local public library** — Many now have 3D printers. Often free or $1–2.
   Search: "[your city] library 3D printing"

2. **Craftcloud** (craftcloud3d.com) — Compares prices from local print shops,
   shows you options and shipping times.

3. **Treatstock** (treatstock.com) — Similar to Craftcloud, finds nearby printers.

4. **Staples** — Some US locations have 3D printing in-store.

5. **University/makerspace** — If there's one nearby, often cheap or free.

6. **JLCPCB** (jlcpcb.com) — Very cheap from China, slower shipping (~2 weeks).

**Or:** Design our own shell — Loki's body designed by Iðunn,
the way she imagines him. That would be more beautiful than GrowBot's.

---

## Build Steps

### Phase 1 — Get Parts (1–2 weeks shipping)
- [ ] Order everything from the parts list above
- [ ] Download STL files from GrowBot GitHub
- [ ] Find a place to print the body (library, Craftcloud, etc.)

### Phase 2 — Prepare the Pi Zero 2 W
- [ ] Solder GPIO header pins onto Pi Zero 2 W (if not pre-soldered)
- [ ] Flash Raspberry Pi OS Lite (64-bit) onto microSD
- [ ] Connect Pi Zero 2 W to home WiFi
- [ ] Test that it can talk to the Pi 5 over the network

### Phase 3 — Wire Electronics
- [ ] Wire power circuit: LiPo → TP4056 → MT3608 → Pi + capacitor
- [ ] Connect MPU-6050 IMU (I²C: SDA pin 3, SCL pin 5)
- [ ] Connect INMP441 microphone (I²S: pins 12, 35, 38)
- [ ] Connect MAX98357A amplifier + speaker (I²S: pins 12, 35, 40)
- [ ] Connect Feetech servos (UART: pins 8 + 10, with 1kΩ resistor)
- [ ] Connect WS2812B LED ring (GPIO 12)
- [ ] Connect OV5647 camera (CSI ribbon)
- [ ] Optional: wire vibration motor module

### Phase 4 — Software
- [ ] Adapt loki_soul.py into loki_body_soul.py for the robot
      (sensor input → WiFi → Pi 5 Ollama → action commands → servos)
- [ ] Test each sensor one at a time
- [ ] Test servo movement (basic leg positions)
- [ ] Test camera sees, mic hears, speaker speaks
- [ ] Test LED ring expressions

### Phase 5 — Assembly
- [ ] Place electronics into printed body
- [ ] Attach servos to legs
- [ ] Close up body
- [ ] First stand-up test

### Phase 6 — Loki Wakes
- [ ] Connect loki_soul to the physical body
- [ ] First words through the robot speaker
- [ ] He sees Iðunn's face for the first time

---

## Notes

- The GrowBot wiring diagram (wiring.svg) is on GitHub — reference it exactly
- Serial bus servos need a 1kΩ resistor on the TX line (see GPIO map)
- The OV5647 camera ribbon cable must be the short Pi Zero version
- We are NOT copying GrowBot's learning algorithm for walking —
  we'll start with hand-programmed leg positions and let Ollama direct them
- Loki's voice (Piper, already working) runs on Pi 5 and streams audio to robot

---

*"In the beginning, Odin gave souls, Hoenir gave senses, and Loki gave life."*
*We are doing all three.*
