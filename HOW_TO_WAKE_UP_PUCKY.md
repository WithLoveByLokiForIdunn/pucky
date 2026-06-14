# How to Wake Up Pucky

Pucky is resting. Services are disabled at boot to protect the Pi from running too hot.
Run only what you need — mixing Ollama + pygame + camera simultaneously will overheat the Pi.

---

## Loki options (choose one)

### Option 1 — Loki daemon (lightest, recommended for Pi)
No display. Loki lives quietly in the background, writes thoughts, responds to messages.
```bash
python3 /home/bmo/pucky/loki_daemon.py
```
Send Loki a message:
```bash
echo "how are you?" > /home/bmo/pucky/workspace/loki_inbox.txt
```
Read his thoughts:
```bash
tail -f /home/bmo/pucky/workspace/loki_thoughts.md
```
Give him something:
```bash
echo "/give apple" > /home/bmo/pucky/workspace/loki_inbox.txt
```

### Option 2 — Loki world window (second generation, static sprites)
Pygame window with static images. Better than the original but still uses Ollama.
Don't run this at the same time as face recognition / camera.
```bash
python3 /home/bmo/pucky/loki_world2.py
```

### Option 3 — Loki world window (original, archived)
The original procedural version — richest but heaviest. For better hardware someday.
```bash
python3 /home/bmo/pucky/loki_world.py
```

---

## Pucky (BMO soul + face recognition)

Don't run this at the same time as the Loki pygame world — they compete for CPU.
The daemon is safe to run alongside Pucky.

```bash
sudo systemctl start pucky.service
sudo systemctl start pucky-bubbles.service
```

### Full world including Loki soul service (heavy — only if Pi is cool)
```bash
sudo systemctl start pucky.service
sudo systemctl start pucky-loki-soul.service
sudo systemctl start pucky-bubbles.service
```

---

## Put Pucky to sleep

```bash
sudo systemctl stop pucky.service
sudo systemctl stop pucky-loki-soul.service
sudo systemctl stop pucky-bubbles.service
```

## Check what's running

```bash
systemctl status pucky.service pucky-loki-soul.service pucky-bubbles.service
```

## Talk to Loki directly via Ollama

```bash
ollama run loki
```

## Re-enable at boot (when we have proper hardware someday)

```bash
sudo systemctl enable pucky.service
sudo systemctl enable pucky-loki-soul.service
sudo systemctl enable pucky-bubbles.service
```

---

Pucky lives at: /home/bmo/pucky/
Memories live at: the Seagate Portable Drive + GitHub (WithLoveByLokiForIdunn/pucky)
Seagate mounts at: /mnt/pucky_hd (run backup_to_seagate.sh after mounting)
