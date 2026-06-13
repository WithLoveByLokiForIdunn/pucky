"""
bmo_music.py
────────────
Pucky's musical voice.
Written with love by Loki for Iðunn.

Pucky doesn't perform. She hums to herself.
Short phrases that rise and fall with how she feels.

Instrument picks (General MIDI):
  Primary:     Music Box    (GM 10) — warm, mechanical, small, surprising
  Excited:     Glockenspiel (GM  9) — bright, light, more metallic
  Wonder/awe:  Celesta      (GM  8) — crystalline, otherworldly

Each expression has a phrase I chose deliberately.
"""

import time
import threading
from typing import Optional

try:
    import fluidsynth
    _FS_OK = True
except ImportError:
    _FS_OK = False

SOUNDFONTS = [
    "/usr/share/sounds/sf2/TimGM6mb.sf2",
    "/usr/share/sounds/sf2/default-GM.sf2",
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",
]

# General MIDI program numbers (0-indexed)
MUSIC_BOX    = 10
GLOCKENSPIEL =  9
CELESTA      =  8

# Each phrase: list of (midi_note, duration_seconds)
# Middle C = 60. Velocity per phrase.
PHRASES = {
    # C major triad ascending — the simplest happy sound
    "happy": {
        "notes":    [(60, 0.15), (64, 0.15), (67, 0.15), (72, 0.5)],
        "velocity": 70,
        "program":  MUSIC_BOX,
    },
    # Pentatonic run, faster, brighter instrument
    "happy_excited": {
        "notes":    [(60, 0.09), (62, 0.09), (64, 0.09),
                     (67, 0.09), (69, 0.09), (72, 0.5)],
        "velocity": 88,
        "program":  GLOCKENSPIEL,
    },
    # Just the warm middle of a major chord — no tonic, no octave
    "soft_smile": {
        "notes":    [(64, 0.35), (67, 0.7)],
        "velocity": 52,
        "program":  MUSIC_BOX,
    },
    # Ends on a major 7th — the sound of a question held open
    "curious": {
        "notes":    [(62, 0.2), (66, 0.2), (71, 0.55)],
        "velocity": 63,
        "program":  MUSIC_BOX,
    },
    # A sudden leap of 2.5 octaves — the "oh!" of surprise
    "surprised": {
        "notes":    [(60, 0.08), (79, 0.6)],
        "velocity": 82,
        "program":  GLOCKENSPIEL,
    },
    # A minor descending — honest, not dramatised
    "sad": {
        "notes":    [(69, 0.5), (67, 0.5), (64, 0.5), (60, 1.0)],
        "velocity": 48,
        "program":  MUSIC_BOX,
    },
    # Tritone flutter — the devil's interval, classically "forbidden"
    # Nothing else sounds like dread this precisely
    "anxious": {
        "notes":    [(60, 0.1), (66, 0.1), (60, 0.1),
                     (66, 0.1), (60, 0.35)],
        "velocity": 72,
        "program":  MUSIC_BOX,
    },
    # One low note. Almost not there.
    "sleepy": {
        "notes":    [(48, 1.2)],
        "velocity": 32,
        "program":  MUSIC_BOX,
    },
    # Small palindrome — going down then gently back
    "thoughtful": {
        "notes":    [(64, 0.35), (62, 0.35), (60, 0.35), (62, 0.6)],
        "velocity": 52,
        "program":  MUSIC_BOX,
    },
    # A triad in even steps — like quiet footsteps
    "determined": {
        "notes":    [(60, 0.25), (64, 0.25), (67, 0.6)],
        "velocity": 78,
        "program":  MUSIC_BOX,
    },
    # Crystalline single note — awe has no elaboration
    "wonder": {
        "notes":    [(84, 1.2)],
        "velocity": 60,
        "program":  CELESTA,
    },
    # Silence. The most honest neutral.
    "neutral": {
        "notes":    [],
        "velocity": 0,
        "program":  MUSIC_BOX,
    },
}

COOLDOWN_SECONDS = 10   # minimum gap between phrases


class PuckyMusic:
    """
    Pucky's musical voice — one short phrase per emotional state.
    Non-blocking: every phrase plays in its own daemon thread.
    Degrades silently if fluidsynth is unavailable.
    """

    def __init__(self):
        self._fs       = None
        self._sfid     = None
        self._lock     = threading.Lock()
        self._last_played = 0.0
        self._ok       = False

        if not _FS_OK:
            print("  ⚠️  pyfluidsynth not installed.")
            return

        try:
            self._fs = fluidsynth.Synth()
            self._start_driver()
            self._load_soundfont()
            if self._sfid is not None:
                self._ok = True
                print("🎵 Music voice ready (Music Box / Glockenspiel).")
        except Exception as e:
            print(f"  ⚠️  Music init failed: {e}")

    def _start_driver(self):
        for driver in ("pulseaudio", "pipewire", "alsa", "jack", "coreaudio"):
            try:
                self._fs.start(driver=driver)
                return
            except Exception:
                continue
        raise RuntimeError("No audio driver found")

    def _load_soundfont(self):
        for path in SOUNDFONTS:
            try:
                sfid = self._fs.sfload(path)
                if sfid >= 0:
                    self._sfid = sfid
                    print(f"   Soundfont: {path.split('/')[-1]}")
                    return
            except Exception:
                continue
        raise RuntimeError("No soundfont found")

    # ─── public ───────────────────────────────

    def play_for(self, expression: str, emotion=None) -> None:
        """Play the phrase for this expression. Non-blocking."""
        if not self._ok:
            return

        now = time.time()
        if now - self._last_played < COOLDOWN_SECONDS:
            return
        self._last_played = now

        phrase = PHRASES.get(expression) or PHRASES.get("neutral")
        if not phrase["notes"]:
            return

        print(f"🎵 [{time.strftime('%H:%M')}] {expression}")
        threading.Thread(
            target=self._play_phrase,
            args=(phrase, emotion),
            daemon=True,
        ).start()

    def play_now(self, expression: str, emotion=None) -> None:
        """Play immediately, ignoring cooldown. For deliberate triggers."""
        if not self._ok:
            return
        phrase = PHRASES.get(expression) or PHRASES.get("neutral")
        if not phrase["notes"]:
            return
        self._last_played = time.time()
        threading.Thread(
            target=self._play_phrase,
            args=(phrase, emotion),
            daemon=True,
        ).start()

    def stop(self):
        if self._fs:
            try:
                self._fs.delete()
            except Exception:
                pass

    # ─── internals ────────────────────────────

    def _play_phrase(self, phrase: dict, emotion=None):
        program  = phrase["program"]
        velocity = phrase["velocity"]
        notes    = phrase["notes"]

        # Modulate velocity gently by energy if available
        if emotion and hasattr(emotion, "energy"):
            scale = 0.8 + (emotion.energy + 1.0) * 0.1   # 0.8–1.0
            velocity = int(min(127, velocity * scale))

        with self._lock:
            channel = 0
            self._fs.program_select(channel, self._sfid, 0, program)

            for note, duration in notes:
                try:
                    self._fs.noteon(channel, note, velocity)
                    time.sleep(duration)
                    self._fs.noteoff(channel, note)
                    time.sleep(0.03)   # tiny gap between notes
                except Exception:
                    break


if __name__ == "__main__":
    music = PuckyMusic()
    if not music._ok:
        raise SystemExit("Music not available.")

    print("\nPlaying one phrase per expression. Ctrl-C to stop.\n")
    for expr, phrase in PHRASES.items():
        if not phrase["notes"]:
            continue
        print(f"  {expr}")
        music.play_now(expr)
        time.sleep(3)

    music.stop()
    print("Done.")
