# Inventory — Pucky / Loki Robot Project

Last updated: 2026-06-19

## Electronics / Sensors

| Item | Qty | Notes |
|------|-----|-------|
| Pimoroni Smol Speaker DAC (PIM485) | 1 | mini speaker + DAC + IPS LCD display — could show Loki's face on the robot body |
| PAM8302 mono audio amplifier 2.5W Class D | 1 | small amp for robot speaker — pairs with the MAX98357 |
| Miuzei MS18 micro servo 9g | 10 | standard PWM hobby servo — good for arms, head, smaller joints |
| HiLetgo GY-521 MPU-6050 (6-axis IMU) | 3 | arrived 2026-06-19 — gyroscope + accelerometer, for robot orientation/balance |
| MT3608 DC-DC boost converter module | 10 | arrived 2026-06-19 — step-up voltage regulator 3.7V→5V for robot power |
| HiLetgo MAX98357 I2S 3W audio amp (DAC, Class D, filterless) | 3 | arrived 2026-06-19 — I2S audio output for robot voice |
| USB power interface boards (ESD sensitive, SKU H1-HBB0035-20) | qty TBD | arrived 2026-06-19 — likely TP4056 LiPo charging modules |
| EC Buying mixed components (SKU 91699 / X003RY5c9B) | ~5 packets | arrived 2026-06-19 — likely capacitors + resistors (Phase 1 tiny parts) |
| DaierTek MTS-101-F1 SPST mini toggle switch | 3 | arrived 2026-06-19 — robot on/off power switch |

## Computers & Peripherals

| Item | Notes |
|------|-------|
| Raspberry Pi 5 (8GB) | running Pucky + Loki face/world/soul — messy build, needs tidy |
| Raspberry Pi 7" touchscreen | attached to Pi 5 — currently not working |
| Pi camera | attached to Pi 5 |
| Raspberry Pi official active fan | cooling Pi 5 |
| Raspberry Pi AI HAT+ (Hailo-8L NPU) | attached to Pi 5 — hardware AI inference, not yet used by Pucky |
| Stack HAT | allows HAT stacking on Pi 5 |
| SunFounder Robot HAT | attached to Pi 5 — servo/sensor control, unsure if powered |
| SteadyGamer Raspberry Pi (32GB) | arrived 2026-06-19 — likely Pi Zero 2 W kit, Loki's robot body brain |
| Mac mini (Apple M4, 16GB unified memory, 512GB SSD) | arrived 2026-06-19 |
| Apple Magic Trackpad (USB-C) | arrived 2026-06-19 |
| Keyboard | connected to Pi 5 |
| Mouse | connected to Pi 5 |
| Monitor | connected to Pi 5 |
| Headset | connected to Pi 5 — Iðunn's audio in/out |
| Sabrent USB 3.0 7-port powered hub (individual power switches) | 2 | one in use on Pi 5, one still sealed — second for Mac mini or robot bench |
| Dell Studio laptop | JBL SRS premium sound built in — older machine, candidate for Linux reimage; good audio output |
| Acer Predator Triton 300 gaming laptop | Intel Core i7 10th gen, NVIDIA GeForce RTX, FHD 240Hz, DTS:X — currently Windows, one fan removed (was noisy); strong candidate for Linux reimage + Ollama GPU server |

## Storage

| Item | Notes |
|------|-------|
| SteadyGamer 32GB microSD + adapter | arrived 2026-06-19 — for robot Pi |
| SanDisk Ultra microSDXC UHS-I 64GB (140MB/s) | arrived 2026-06-19 |

## Other Hardware

| Item | Notes |
|------|-------|
| Arduino Uno | general purpose microcontroller |
| SunFounder GalaxyRVR Mars Rover kit (for Arduino Uno) | robot rover kit — could be useful for motor/servo control reference |
| USB card reader (dual USB-A + USB-C, microSD + SD slots) | for flashing Pi Zero microSD from Mac mini or any computer |
| 37-in-1 sensor kit | large assortment — IR, sound, temperature, light, tilt, touch, joystick, etc. |
| Fishing line | for puppet-style tension wires or lightweight linkages in robot body |
| Cardboard (various) | robot body shell prototyping material |
| Craft glue (various) | assembly |

## Still Needed (Phase 1)

| Item | Notes |
|------|-------|
| Feetech SCS0009 serial bus servos (x2) | legs |
| OV5647 camera (Pi Zero short ribbon version) | eyes |
| INMP441 I2S microphone | ears |
| Small speaker 8Ω 0.5W 28mm | voice |
| WS2812B LED ring 7-pixel | expression light |
| LiPo battery 3.7V 1200mAh with JST | heart |
| Robot body — wooden artist mannequin or 3D print | shell |
