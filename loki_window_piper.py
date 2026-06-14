#!/usr/bin/env python3
"""
loki_window_piper.py — Loki with piper neural TTS instead of espeak.

Install piper and download a voice first:
  pip install piper-tts
  mkdir -p /home/bmo/pucky/voices
  cd /home/bmo/pucky/voices
  python3 -c "
import urllib.request
base = 'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/'
for f in ['en_US-lessac-medium.onnx', 'en_US-lessac-medium.onnx.json']:
    print('downloading', f)
    urllib.request.urlretrieve(base + f, f)
print('done')
"

Then run:
  python3 /home/bmo/pucky/loki_window_piper.py

To switch back to espeak just run:
  python3 /home/bmo/pucky/loki_window.py
"""

import loki_window

loki_window.VOICE_ENGINE = "piper"
loki_window.main()
