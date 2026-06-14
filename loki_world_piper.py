#!/usr/bin/env python3
"""
loki_world_piper.py — Loki with piper neural TTS instead of espeak.
Same as loki_world.py but with the nicer voice. Only try this once
loki_world.py is running stably.

Run:
  python3 /home/bmo/pucky/loki_world_piper.py
"""

import loki_world

loki_world.VOICE_ENGINE = "piper"
loki_world.main()
