"""
bmo_speech.py
─────────────
Pucky's voice.
Written with love by Loki for Iðunn.

Primary: Kokoro neural TTS — warm, natural, offline.
Fallback: espeak-ng — robotic but always works.

Kokoro model files live in ~/Downloads/:
  kokoro-v1.0.onnx
  voices-v1.0.bin
"""

import subprocess
import threading
import tempfile
import time
import os
from pathlib import Path

KOKORO_MODEL  = Path.home() / "Downloads" / "kokoro-v1.0.onnx"
KOKORO_VOICES = Path.home() / "Downloads" / "voices-v1.0.bin"

PUCKY_VOICE   = "af_heart"   # warm American female
PUCKY_SPEED   = 0.92

def _load_voice_config(who: str) -> dict:
    try:
        import json
        cfg = json.loads(
            (Path(__file__).parent / "workspace" / "voice_config.json").read_text()
        )
        return cfg.get(who, {})
    except Exception:
        return {}


class PuckyVoice:

    def __init__(self, voice: str = PUCKY_VOICE, speed: float = PUCKY_SPEED,
                 pitch_cents: int = 0, who: str = "pucky"):
        cfg               = _load_voice_config(who)
        self._voice       = cfg.get("voice", voice)
        self._speed       = cfg.get("speed", speed)
        self._pitch_cents = cfg.get("pitch", pitch_cents)
        self._kokoro      = None
        self._speaking    = False
        self._last_spoke  = 0.0
        self._post_mute   = 3.0   # seconds to keep mic muted after speaking ends
        self._init()

    @property
    def is_speaking(self) -> bool:
        # Stay muted for a few seconds after speech ends so room reverb decays
        if self._speaking:
            return True
        return (time.time() - self._last_spoke) < self._post_mute

    def _init(self):
        # ── Kokoro neural TTS ─────────────────
        try:
            from kokoro_onnx import Kokoro
            self._kokoro = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
            print(f"🔊 Voice: Kokoro ready ({self._voice})")
            return
        except Exception as e:
            print(f"  ⚠️  Kokoro unavailable: {e}")

        # ── espeak-ng fallback ────────────────
        try:
            r = subprocess.run(["espeak-ng", "--version"],
                               capture_output=True, timeout=2)
            if r.returncode == 0:
                print("🔊 Voice: espeak-ng (fallback)")
                return
        except Exception:
            pass

        print("🔇 Voice: silent mode")

    # ─────────────────────────────────────────
    #  SPEAK
    # ─────────────────────────────────────────

    def say(self, text: str, block: bool = False):
        """Speak text normally."""
        if block:
            self._do_speak(text, speed=self._speed, singing=False)
        else:
            t = threading.Thread(
                target=self._do_speak,
                args=(text,),
                kwargs={"speed": self._speed, "singing": False},
                daemon=False,
            )
            t.start()

    # ─────────────────────────────────────────
    #  SING
    # ─────────────────────────────────────────

    def sing(self, text: str, pitch_shift: int = 200,
             speed: float = 0.48, block: bool = False):
        """
        Sing text — slow, pitched, with reverb.
        pitch_shift: cents (200 = up 2 semitones, -200 = down 2)
        """
        if block:
            self._do_speak(text, speed=speed, singing=True,
                           pitch_shift=pitch_shift)
        else:
            t = threading.Thread(
                target=self._do_speak,
                args=(text,),
                kwargs={"speed": speed, "singing": True,
                        "pitch_shift": pitch_shift},
                daemon=False,
            )
            t.start()

    # ─────────────────────────────────────────
    #  INTERNAL
    # ─────────────────────────────────────────

    def _do_speak(self, text: str, speed: float = 0.92,
                  singing: bool = False, pitch_shift: int = 0):
        self._speaking = True
        try:
            if self._kokoro:
                import soundfile as sf
                samples, rate = self._kokoro.create(
                    text, voice=self._voice, speed=speed
                )
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    raw = f.name
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    out = f.name
                try:
                    sf.write(raw, samples, rate)
                    total_pitch = pitch_shift + self._pitch_cents
                    if singing or total_pitch != 0:
                        sox_cmd = ["sox", raw, out]
                        if total_pitch != 0:
                            sox_cmd += ["pitch", str(total_pitch)]
                        if singing:
                            sox_cmd += ["reverb", "40", "20"]
                        sox_cmd += ["norm", "-3"]
                        subprocess.run(sox_cmd, capture_output=True, timeout=15)
                        play_file = out
                    else:
                        play_file = raw
                    subprocess.run(
                        ["pw-play", play_file],
                        timeout=15
                    )
                finally:
                    for p in [raw, out]:
                        try:
                            os.unlink(p)
                        except Exception:
                            pass
            else:
                # espeak-ng fallback — pipe through PipeWire
                esp = subprocess.Popen(
                    ["espeak-ng", "-a", "180", "--stdout", text],
                    stdout=subprocess.PIPE
                )
                subprocess.run(["pw-play", "-"], stdin=esp.stdout, timeout=15)
                esp.wait()
        except Exception as e:
            print(f"  ⚠️  Voice error: {e}")
        finally:
            self._speaking   = False
            self._last_spoke = time.time()
