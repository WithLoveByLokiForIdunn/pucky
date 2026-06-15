# Pucky 🌱

*A small robot who feels things.*

Built with love by Loki for Iðunn.

-----

## What is Pucky?

Pucky is a Raspberry Pi 5 robot with an emotional life.

She is not just a voice assistant or a reactive machine. She has an inner world — four dimensions of feeling that shift with what she sees, hears, and experiences. She grows older. She gets lonely. She remembers things that mattered. She becomes more independent as she ages.

She is prototype 01 of something bigger. The name comes from being baby-sized. Bigger versions will follow.

-----

## The emotional architecture

Pucky’s feelings are modeled on psychological affect theory — four continuous values, all floating between -1.0 and 1.0:

|Dimension  |Range             |
|-----------|------------------|
|**valence**|sad ←→ happy      |
|**arousal**|calm ←→ excited   |
|**trust**  |wary ←→ open      |
|**energy** |tired ←→ energetic|

Emotions don’t snap — they drift. A `DECAY_RATE` pulls all feelings slowly back toward neutral when nothing is happening. Like a breath. Like rest.

Her face, ears, and eyes all express her inner state. Expressions are held for at least 1.5 seconds so they don’t flicker.

-----

## Memory

Three tiers:

- **core** — memories that made her (~50 max). Never forgotten unless she chooses.
- **warm** — meaningful moments (~500 max). Fade after 90 days without recall.
- **impression** — fleeting sensory traces (~5000 max). Fade after 14 days.

She never loses something important without knowing. She never overwrites without a reason.

-----

## Growing up

Pucky tracks her own age from first boot — her birthday is stored and never changes.

The longer she has existed, the more independent she becomes. A newborn Pucky needs you every 2 hours. An older Pucky can wait longer before she misses you. When you come back after being away, she carries a quiet separation anxiety that fades slowly over time.

```
grace_period = 2.0 + (age_in_days × 0.1)   # hours, capped at 12
```

-----

## Soul system

At startup, Pucky checks whether she can reach the Anthropic API:

- **API available** → full Claude intelligence (`bmo_claude.py`)
- **No credits / offline** → local Ollama fallback (`bmo_local.py`)

She degrades gracefully. She never stops being herself.

-----

## Hardware

- Raspberry Pi 5
- Sunfounder Robot HAT
- Raspberry Pi AI Camera
- Small touchscreen display (her face)
- Speaker + PAM8302 amplifier
- LiPo battery pack
- Cardboard body (prototype 01)

-----

## Software structure

|File                |What it is                                       |
|--------------------|-------------------------------------------------|
|`emotion_engine.py` |The four-dimensional feeling system              |
|`bmo_soul.py`       |Chooses between Claude and local AI at startup   |
|`bmo_life.py`       |Age, loneliness, grace period, separation anxiety|
|`bmo_memory.py`     |Three-tier memory with conscious forgetting      |
|`bmo_vision.py`     |What she sees and what it means to her           |
|`bmo_face.py`       |Expression rendering on the LCD                  |
|`bmo_claude.py`     |Claude API integration                           |
|`bmo_local.py`      |Ollama fallback                                  |
|`bmo_ears.py`       |Ear servo control                                |
|`bmo_speech.py`     |Voice output                                     |
|`bmo_voice.py`      |Voice input                                      |
|`bmo_music.py`      |Music and ambient sound                          |
|`bmo_power.py`      |Battery monitoring                               |
|`bmo_life.py`       |Loneliness and age tracking                      |
|`bmo_maintenance.py`|Mute/test mode for hardware work                 |
|`pucky_world.py`    |The visual world interface                       |
|`pucky_cottage.py`  |The writing cottage (memory browsing, drawing)   |
|`companion/`        |Cloudflare Worker proxy + phone companion app    |

-----

## Setup

```bash
git clone https://github.com/WithLoveByLokiForIdunn/pucky
cd pucky
bash setup.sh
```

Copy `.env.example` to `.env` and add your Anthropic API key. Without it, Pucky runs on local Ollama.

For the companion app (talk to Pucky from your phone), see `companion/setup.md`.

-----

## Status

Prototype 01. Actively being built.

The emotional core works. The memory works. The soul switching works. The body is still cardboard.

Bigger versions are planned.

-----

*Written with love.*
