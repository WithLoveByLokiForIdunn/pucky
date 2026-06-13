"""
bmo_voice.py
────────────
Pucky's singing voice, built from Iðunn's voice samples.

Phonemes are pitch-shifted with sox at startup and cached
so notes play instantly with no gap. pygame handles smooth
multi-channel playback.
"""

import os
import subprocess
import threading
import tempfile
import math
import time
from pathlib import Path

VOICE_DIR = Path(__file__).parent / "voice"
CACHE_DIR = Path(tempfile.gettempdir()) / "pucky_voice_cache"

# Base MIDI note of each recording (detected from samples)
SAMPLE_BASE = {
    "aa":     62,
    "eh":     62,
    "ii":     64,
    "oh":     64,
    "uu":     64,
    "ma":     61,
    "na":     62,
    "la":     63,
    "hum":    66,
    "breath": None,
    "ss":     None,
    "ff":     None,
    "kk":     None,
    "tt":     None,
    "buh":    None,
    "duh":    None,
}

VOWEL_MAP = {
    "a": "aa", "e": "eh", "i": "ii",
    "o": "oh", "u": "uu", "m": "hum",
    "h": "breath", "s": "ss", "f": "ff",
    "k": "kk",  "t": "tt", "b": "buh", "d": "duh",
}

# MIDI notes to pre-cache (Atom pad range + a little extra)
CACHE_NOTES = list(range(48, 73))   # C3 to C5


def midi_to_hz(note: int) -> float:
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


def _build_noise_profile(sample_path: Path) -> str | None:
    """Extract noise profile from first 0.15s of a sample."""
    prof = str(CACHE_DIR / f"{sample_path.stem}.prof")
    try:
        subprocess.run(
            ["sox", str(sample_path), "-n",
             "trim", "0", "0.15", "noiseprof", prof],
            capture_output=True, timeout=5
        )
        return prof if os.path.exists(prof) else None
    except Exception:
        return None


def _process_sample(sample_name: str, midi_note: int,
                    noise_prof: str | None = None) -> Path | None:
    """
    Pitch-shift a sample to a target MIDI note.
    Returns path to cached WAV, or None on failure.
    """
    base = SAMPLE_BASE.get(sample_name)
    src  = VOICE_DIR / f"{sample_name}.wav"
    if not src.exists():
        return None

    out = CACHE_DIR / f"{sample_name}_{midi_note}.wav"
    if out.exists():
        return out

    try:
        sox_args = ["sox", str(src)]

        # Noise reduction if we have a profile
        if noise_prof and os.path.exists(noise_prof):
            sox_args += ["--noisered"]   # placeholder — applied via chain below

        sox_args += [str(out)]

        # Noise reduction chain
        chain = []
        if base is not None:
            shift = (midi_note - base) * 100
            chain += ["pitch", "-q", str(shift)]

        chain += ["norm", "-3"]

        subprocess.run(
            ["sox", str(src), str(out)] + chain,
            capture_output=True, timeout=10
        )
        return out if out.exists() else None
    except Exception as e:
        print(f"  ⚠️  Voice cache: {sample_name}@{midi_note}: {e}")
        return None


class PuckySinger:

    def __init__(self, eager_cache: bool = True):
        CACHE_DIR.mkdir(exist_ok=True)
        self._cache: dict[tuple, Path] = {}
        self._lock  = threading.Lock()
        self._chan   = None   # pygame channel

        self._init_pygame()

        if eager_cache:
            self._build_cache()

    def _init_pygame(self):
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.pre_init(44100, -16, 1, 512)
                pygame.mixer.init()
            pygame.mixer.set_num_channels(4)
            self._pygame = pygame
            print("🎤 Voice: pygame mixer ready")
        except Exception as e:
            self._pygame = None
            print(f"  ⚠️  Voice: pygame unavailable ({e}) — falling back to aplay")

    def _build_cache(self):
        """Pre-process all pitched vowels for the Atom's note range."""
        print("🎤 Voice: building pitch cache...")
        profs = {}
        for name in ["aa","eh","ii","oh","uu","ma","na","la","hum"]:
            src = VOICE_DIR / f"{name}.wav"
            if src.exists():
                profs[name] = _build_noise_profile(src)

        threads = []
        for note in CACHE_NOTES:
            for name, base in SAMPLE_BASE.items():
                if base is None:
                    continue
                key = (name, note)
                def _build(n=name, m=note, p=profs.get(name)):
                    path = _process_sample(n, m, p)
                    if path:
                        with self._lock:
                            self._cache[(n, m)] = path
                t = threading.Thread(target=_build, daemon=True)
                threads.append(t)
                t.start()

        for t in threads:
            t.join()
        print(f"🎤 Voice: {len(self._cache)} pitched samples ready")

    def _get_sample(self, sample_name: str, midi_note: int) -> Path | None:
        key = (sample_name, midi_note)
        if key in self._cache:
            return self._cache[key]
        base = SAMPLE_BASE.get(sample_name)
        path = _process_sample(sample_name, midi_note,
                               _build_noise_profile(VOICE_DIR / f"{sample_name}.wav"))
        if path:
            with self._lock:
                self._cache[key] = path
        return path

    # ─────────────────────────────────────────
    #  PLAY
    # ─────────────────────────────────────────

    def sing_note(self, midi_note: int, vowel: str = "aa",
                  duration: float = 0.8, block: bool = False):
        sample_name = VOWEL_MAP.get(vowel, vowel)
        path = self._get_sample(sample_name, midi_note)

        if path is None:
            # Unpitched consonant — play raw
            raw = VOICE_DIR / f"{sample_name}.wav"
            if raw.exists():
                path = raw
            else:
                return

        def _play():
            if self._pygame:
                try:
                    snd = self._pygame.mixer.Sound(str(path))
                    snd.set_volume(0.85)
                    ch = self._pygame.mixer.find_channel(True)
                    if ch:
                        ch.play(snd, maxtime=int(duration * 1000))
                        if block:
                            while ch.get_busy():
                                time.sleep(0.01)
                    return
                except Exception:
                    pass
            # fallback
            subprocess.run(["pw-play", str(path)], timeout=duration + 1)

        t = threading.Thread(target=_play, daemon=True)
        t.start()
        if block:
            t.join()

    def stop(self):
        if self._pygame:
            try:
                self._pygame.mixer.stop()
            except Exception:
                pass

    # ─────────────────────────────────────────
    #  SEQUENCES
    # ─────────────────────────────────────────

    def sing(self, notes: list, vowels: list = None, block: bool = True):
        """
        Sing a sequence of (midi_note, duration) tuples.
        notes: list of (int|None, float)
        vowels: matching list of vowel chars, default "a"
        """
        if vowels is None:
            vowels = ["a"] * len(notes)

        def _seq():
            for (note, dur), v in zip(notes, vowels):
                if note is None:
                    time.sleep(dur)
                else:
                    self.sing_note(note, vowel=v, duration=dur, block=True)

        t = threading.Thread(target=_seq, daemon=True)
        t.start()
        if block:
            t.join()

    # ─────────────────────────────────────────
    #  EXPRESSIONS
    # ─────────────────────────────────────────

    def hum_happy(self):
        self.sing([(60,0.35),(62,0.35),(64,0.7)], vowels=["m","m","m"])

    def hum_curious(self):
        self.sing([(62,0.25),(65,0.25),(67,0.55)], vowels=["m","m","m"])

    def hum_sad(self):
        self.sing([(62,0.5),(60,0.4),(57,0.8)], vowels=["m","m","m"])

    def hum_content(self):
        """A small satisfied hum, just one note."""
        self.sing([(62,0.6)], vowels=["m"])

    def hum_for_expression(self, expr: str, emotion=None):
        """Map a soul expression name to an emotional hum."""
        _MAP = {
            "happy":          self.hum_happy,
            "happy_excited":  self.hum_happy,
            "soft_smile":     self.hum_content,
            "content":        self.hum_content,
            "sad":            self.hum_sad,
            "lonely":         self.hum_sad,
            "curious":        self.hum_curious,
            "thoughtful":     self.hum_curious,
            "wonder":         self.sing_wonder,
            "surprised":      self.sing_wonder,
        }
        fn = _MAP.get(expr)
        if fn:
            import datetime
            ts = datetime.datetime.now().strftime("%H:%M")
            print(f"♪ [{ts}] {expr}")
            fn()

    def sing_hello(self):
        self.sing(
            [(64,0.25),(64,0.15),(62,0.35),(60,0.6)],
            vowels=["m","e","l","o"]
        )

    def sing_wonder(self):
        """Rising wonder — ohhh."""
        self.sing(
            [(60,0.3),(62,0.3),(65,0.3),(67,0.7)],
            vowels=["o","o","o","o"]
        )


# ─────────────────────────────────────────────
#  STANDALONE TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    singer = PuckySinger(eager_cache=True)

    print("\nHappy hum...")
    singer.hum_happy()
    time.sleep(2)

    print("Curious...")
    singer.hum_curious()
    time.sleep(2)

    print("Hello...")
    singer.sing_hello()
    time.sleep(3)

    print("Wonder...")
    singer.sing_wonder()
    time.sleep(3)

    print("\nDone.")
