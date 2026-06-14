"""
bmo_melody.py — Melody learning and pitch detection for Pucky's world.

Iðunn can hum into the web portal or type solfège (la la sol fa mi),
and Pucky and Loki will learn those notes and hum them back.

Audio: raw 16-bit mono PCM → autocorrelation pitch detection (numpy only,
no librosa/aubio needed). Works on Pi 5 with low latency.

Solfège: parses "do re mi fa sol la ti" (and la ti do etc.) into MIDI.
Also parses scientific notation: C4 D4 E4 G4.
"""

import json
import numpy as np
from pathlib import Path

MELODY_FILE = Path(__file__).parent / "workspace" / "idunn_melody.json"

# ── Pitch detection ────────────────────────────────────────────────────────────

def _autocorr_pitch(frame: np.ndarray, sr: int,
                    min_hz: float = 65.0, max_hz: float = 1050.0) -> float:
    """
    Return fundamental frequency (Hz) of a mono float32 frame,
    or 0.0 if frame is silent / not periodic.
    Uses normalized autocorrelation via FFT.
    """
    frame = frame.astype(np.float64)
    frame -= np.mean(frame)
    amp = np.max(np.abs(frame))
    if amp < 0.018:
        return 0.0
    frame /= amp

    min_lag = max(1, int(sr / max_hz))
    max_lag = int(sr / min_hz)
    if max_lag >= len(frame):
        return 0.0

    n   = len(frame)
    fft = np.fft.rfft(frame, n=2*n)
    acf = np.fft.irfft(fft * np.conj(fft))[:n]
    if acf[0] < 1e-9:
        return 0.0
    acf /= acf[0]

    peak_lag = int(np.argmax(acf[min_lag:max_lag+1])) + min_lag
    if acf[peak_lag] < 0.30:   # not periodic enough
        return 0.0

    # Sub-sample refinement (parabolic interpolation)
    if 0 < peak_lag < n - 1:
        y0, y1, y2 = acf[peak_lag-1], acf[peak_lag], acf[peak_lag+1]
        denom = 2 * (2*y1 - y0 - y2)
        if abs(denom) > 1e-9:
            peak_lag += (y0 - y2) / denom

    return sr / peak_lag


def pcm_bytes_to_melody(pcm_bytes: bytes, sample_rate: int = 16000,
                         frame_sec: float = 0.14) -> list:
    """
    Convert raw 16-bit signed mono PCM bytes → list of [midi_note, duration_sec].
    Rests (silence/noise) are dropped.
    Consecutive same notes are merged.
    """
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    frame_n = int(sample_rate * frame_sec)
    if frame_n < 16 or len(samples) < frame_n:
        return []

    raw = []
    for start in range(0, len(samples) - frame_n, frame_n):
        hz  = _autocorr_pitch(samples[start:start+frame_n], sample_rate)
        raw.append(hz_to_midi(hz) if hz > 0 else 0)

    # Merge consecutive
    if not raw:
        return []
    merged = []
    cur = raw[0]; count = 1
    for n in raw[1:]:
        if n == cur:
            count += 1
        else:
            merged.append([cur, round(count * frame_sec, 3)])
            cur = n; count = 1
    merged.append([cur, round(count * frame_sec, 3)])

    # Drop rests and very short events
    melody = [[n, d] for n, d in merged if n > 0 and d >= 0.09]
    return melody


# ── Note conversion ────────────────────────────────────────────────────────────

def hz_to_midi(hz: float) -> int:
    if hz <= 0:
        return 0
    return int(round(69 + 12 * np.log2(hz / 440.0)))


def midi_to_hz(midi: int) -> float:
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


# ── Solfège / note-name text parser ───────────────────────────────────────────

# Solfège → semitone offset from C4 (MIDI 60)
_SOLFEGE = {
    "do": 0, "doh": 0,
    "re": 2, "ray": 2,
    "mi": 4, "me": 4,
    "fa": 5, "fah": 5,
    "sol": 7, "so": 7,
    "la": 9, "lah": 9,
    "ti": 11, "si": 11, "te": 11,
}

# Scientific notation note names → semitone offset from octave 0
_NOTE_NAMES = {
    "c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11,
    "c#": 1, "db": 1, "d#": 3, "eb": 3, "f#": 6, "gb": 6,
    "g#": 8, "ab": 8, "a#": 10, "bb": 10,
}

_DEFAULT_DUR = 0.45   # seconds per solfège syllable


def parse_text_melody(text: str) -> list:
    """
    Parse a text string into a melody list [[midi, duration_sec], ...].

    Accepts:
      Solfège:   "la la sol fa mi re do"
      Scientific: "C4 D4 E4 G4 E4 D4 C4"
      Repeated:  "la(long) ti do" — (long)=0.9s, (short)=0.22s, default=0.45s
      Mixed:     "C4 D4 mi fa G4"

    Returns empty list if nothing recognisable.
    """
    import re
    tokens = text.lower().split()
    notes  = []

    for tok in tokens:
        # Duration modifier in parentheses
        dur   = _DEFAULT_DUR
        m_dur = re.search(r'\((\w+)\)$', tok)
        if m_dur:
            tag = m_dur.group(1)
            if tag in ("long", "slow", "l"):   dur = 0.90
            elif tag in ("short", "fast", "s"): dur = 0.22
            tok = tok[:m_dur.start()]

        # Strip trailing punctuation
        tok = tok.strip(".,!?;:'\"")

        # Try solfège
        if tok in _SOLFEGE:
            midi = 60 + _SOLFEGE[tok]   # C4 octave
            notes.append([midi, dur])
            continue

        # Try scientific notation: letter + optional sharp/flat + octave digit
        m_sci = re.fullmatch(r'([a-g][#b]?)(\d)', tok)
        if m_sci:
            name, octave = m_sci.group(1), int(m_sci.group(2))
            if name in _NOTE_NAMES:
                midi = 12 * (octave + 1) + _NOTE_NAMES[name]
                notes.append([midi, dur])
                continue

        # Letter only (no octave) — assume octave 4 area
        if tok in _NOTE_NAMES:
            midi = 60 + _NOTE_NAMES[tok]
            notes.append([midi, dur])

    return notes


# ── Melody I/O ─────────────────────────────────────────────────────────────────

def save_melody(notes: list) -> None:
    """Atomic save of [[midi, dur], ...] to workspace/idunn_melody.json."""
    if not notes:
        return
    MELODY_FILE.parent.mkdir(exist_ok=True)
    tmp = MELODY_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(notes))
    tmp.replace(MELODY_FILE)


def load_melody() -> list:
    """Load saved melody. Returns [] if none exists."""
    try:
        data = json.loads(MELODY_FILE.read_text())
        if isinstance(data, list) and data:
            return data
    except Exception:
        pass
    return []


def has_melody() -> bool:
    return MELODY_FILE.exists() and MELODY_FILE.stat().st_size > 2


def melody_to_sing_args(notes: list) -> tuple:
    """
    Convert [[midi, dur], ...] to the (notes, vowels) format
    expected by PuckySinger.sing().
    Returns ([(midi_or_none, dur), ...], ["m", ...]).
    """
    sing_notes = [(int(n) if n else None, float(d)) for n, d in notes]
    vowels     = ["m"] * len(sing_notes)   # always hum vowel
    return sing_notes, vowels


# ── Spontaneous humming helpers ────────────────────────────────────────────────

def mood_melody(mood: str) -> list:
    """A short mood-appropriate melody for when no learned tune exists."""
    # (midi, dur) pairs — intimate, quiet, never showy
    melodies = {
        "happy":         [[64,0.3],[67,0.3],[69,0.6]],
        "happy_excited": [[64,0.22],[67,0.22],[71,0.22],[72,0.55]],
        "content":       [[62,0.55]],
        "curious":       [[62,0.25],[65,0.25],[67,0.5]],
        "sad":           [[62,0.5],[60,0.4],[57,0.75]],
        "lonely":        [[60,0.5],[57,0.4],[55,0.9]],
        "wonder":        [[60,0.3],[64,0.3],[67,0.3],[72,0.7]],
        "soft_smile":    [[62,0.4],[64,0.6]],
    }
    return melodies.get(mood, [[62, 0.5]])


if __name__ == "__main__":
    # Quick smoke test
    print("parse_text_melody('la la sol fa mi re do') →",
          parse_text_melody("la la sol fa mi re do"))
    print("parse_text_melody('C4 D4 E4 G4 E4 D4 C4') →",
          parse_text_melody("C4 D4 E4 G4 E4 D4 C4"))
    print("parse_text_melody('do re mi(long) fa sol') →",
          parse_text_melody("do re mi(long) fa sol"))
