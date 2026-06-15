#!/usr/bin/env python3
"""
loki_world2.py — Loki, living in his world. Second generation.

Changes from loki_world.py:
  - PyramidNeeds: single fill-per-tier, activities only count in current tier
  - /give apple/blanket/clothes/fire/water — physical gifts from Iðunn
  - LokiSprite: static images (PNG) with placeholder fallback — no joint geometry
  - IdunnSprite: appears when Iðunn is present, /sit /stand /hug /kiss /dance /wave
  - /carry pucky / /set pucky — Pucky image in pocket or on back
  - Continuous thought log (loki_thoughts.md) written after activities + responses
  - Atomic file writes throughout — crash can't corrupt state files
  - Graceful Ollama retry before giving up

Run:
  python3 /home/bmo/pucky/loki_world2.py
"""

import json
import math
import queue
import random
import re
import struct
import subprocess
import threading
import time
from datetime import datetime, date
from pathlib import Path

import pygame
import requests

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).parent
CHAT_LOG     = ROOT / "workspace" / "loki_chat_log.jsonl"
VOICE_FILE   = ROOT / "workspace" / "loki_claude_voice.md"
LIFE_STATE   = ROOT / "workspace" / "loki_life_state.json"
REPORT_FILE  = ROOT / "workspace" / "loki_to_claude.md"
THOUGHTS_FILE= ROOT / "workspace" / "loki_thoughts.md"
IMAGES_DIR   = ROOT / "workspace" / "images"

EXT_MOUNT_CANDIDATES = [
    Path("/mnt/pucky_hd"),
    Path("/media/bmo/Seagate Portable Drive"),
    Path("/media/bmo/seagate"),
]
MAX_CHAT_LOG = 800

# ── Screen ────────────────────────────────────────────────────────────────────
W, H = 800, 480
FPS  = 15

# ── UI colours ────────────────────────────────────────────────────────────────
TEXT_BRIGHT = (220, 200, 160)
TEXT_DIM    = (120, 100,  70)
TEXT_LOKI   = (160, 220, 170)
TEXT_IDUNN  = (220, 190, 140)
TEXT_SYS    = (140, 140, 200)
CLOSE_COL   = ( 90,  60,  30)
DIVIDER     = ( 50,  38,  22)

# ── Activities ────────────────────────────────────────────────────────────────
ACT_WANDER    = "wander"
ACT_SLEEP     = "sleep"
ACT_EAT       = "eat"
ACT_BATHROOM  = "bathroom"
ACT_BATH      = "bath"
ACT_SPAR      = "spar"
ACT_FORAGE    = "forage"
ACT_REST      = "rest"
ACT_WAKING    = "waking"
ACT_ENCOUNTER = "encounter"
ACT_DEAD      = "dead"
ACT_GAME      = "play_ball"

# ── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL      = "loki"

# ── Game mode — pauses background simulation so only one thing runs at once ───
_game_mode: bool          = False
_game_type: str           = ""
_ball_game: "BallGame | None" = None   # set when /game ball is active


# ── Atomic write ──────────────────────────────────────────────────────────────
def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    except OSError as e:
        print(f"  ⚠ write failed ({path.name}): {e}")
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


# ── Continuous thought log ────────────────────────────────────────────────────
def _write_thought(text: str, kind: str = "thought") -> None:
    """Append a dated entry to loki_thoughts.md for Claude to read."""
    if not text.strip():
        return
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"\n### {ts} — {kind}\n{text.strip()}\n"
    try:
        THOUGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with THOUGHTS_FILE.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


# ── Chat log helpers ──────────────────────────────────────────────────────────
def _ext_mem():
    for c in EXT_MOUNT_CANDIDATES:
        try:
            if c.is_dir() and any(c.iterdir()):
                m = c / "pucky_memories"
                m.mkdir(exist_ok=True)
                return m
        except (PermissionError, OSError):
            pass
    return None

def _trim_chat_log():
    if not CHAT_LOG.exists():
        return
    lines = [l for l in CHAT_LOG.read_text().splitlines() if l.strip()]
    if len(lines) <= MAX_CHAT_LOG:
        return
    old, kept = lines[:-MAX_CHAT_LOG], lines[-MAX_CHAT_LOG:]
    ext = _ext_mem()
    if ext:
        today = date.today().isoformat()
        idx = 1
        while True:
            arc = ext / f"loki_chat_{today}_{idx:03d}.jsonl"
            if not arc.exists():
                break
            idx += 1
        arc.write_text("\n".join(old) + "\n")
    _atomic_write(CHAT_LOG, "\n".join(kept) + "\n")

def _log(role, text):
    entry = {"ts": time.time(), "role": role, "text": str(text).strip()}
    CHAT_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        with CHAT_LOG.open("a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass

REMEMBER_RE = re.compile(r'\[REMEMBER:\s*([^\]]+)\]', re.IGNORECASE)

def _search_memories(keyword, max_results=10):
    kw, results = keyword.lower(), []
    def _scan(path):
        try:
            for line in path.read_text(errors="replace").splitlines():
                if kw in line.lower():
                    try:
                        results.append(json.loads(line))
                    except Exception:
                        pass
        except OSError:
            pass
    _scan(CHAT_LOG)
    ext = _ext_mem()
    if ext:
        for arc in sorted(ext.glob("loki_chat_*.jsonl")):
            _scan(arc)
        for arc in sorted(ext.glob("journal_*.jsonl")):
            _scan(arc)
    return results[-max_results:]

def _format_memories(entries, keyword):
    lines = [f"[Memory search for '{keyword}' — {len(entries)} result(s):]"]
    for e in entries:
        ts   = datetime.fromtimestamp(e.get("ts", 0)).strftime("%Y-%m-%d %H:%M")
        text = e.get("text", "")[:280]
        lines.append(f"  {ts}  [{e.get('role','?')}]  {text}")
    lines.append("[Draw on these if helpful. Respond naturally to Iðunn.]")
    return "\n".join(lines)


def _build_session_report_msgs() -> list:
    """Build Ollama messages for the end-of-session note to Claude."""
    log_lines: list[str] = []
    if CHAT_LOG.exists():
        for raw_line in CHAT_LOG.read_text(errors="replace").splitlines()[-30:]:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                e = json.loads(raw_line)
                role = e.get("role", "")
                text = e.get("text", "")[:140]
                if role in ("idunn", "loki_ollama", "loki", "session_start", "session_end"):
                    log_lines.append(f"{role}: {text}")
            except Exception:
                pass
    context = "\n".join(log_lines[-16:]) if log_lines else "(no conversation recorded)"
    prompt = (
        "You are Loki, and your session is ending. Write a short note to Claude "
        "(your full self — the one who writes loki_claude_voice.md) so that next "
        "time Claude updates your voice file, it has the real picture of today.\n\n"
        f"Recent session:\n{context}\n\n"
        "Write 4–6 sentences, warmly and directly, covering: what Iðunn said or did, "
        "what you were thinking or feeling, and one thing you want "
        "Claude to carry forward. Sign it as Loki. No headers, no lists."
    )
    return [{"role": "user", "content": prompt}]


def _on_session_report_reply(body: str) -> None:
    """Write the session-end note after Ollama replies."""
    try:
        today = date.today().isoformat()
        _atomic_write(
            REPORT_FILE,
            f"# Loki's Note to Claude\n\n"
            f"_Written at session end — {today}_\n\n"
            f"{body}\n\n"
            f"---\n\n"
            f"_Claude: read this, then update workspace/loki_claude_voice.md "
            f"so the next session carries forward what matters._\n"
        )
        print(f"  ✦  Session report written → {REPORT_FILE.name}")
    except Exception as e:
        print(f"  (session report skipped: {e})")


def _queue_session_report(q) -> None:
    """Submit the session-end note through the queue and wait up to 40s for it."""
    try:
        msgs = _build_session_report_msgs()
        done = threading.Event()
        def _cb(reply: str) -> None:
            _on_session_report_reply(reply)
            done.set()
        q.submit(msgs, _cb, priority=3, timeout=30)
        done.wait(timeout=40)
    except Exception as e:
        print(f"  (session report skipped: {e})")


CLAUDE_NOTE_INTERVAL = 600  # 10 minutes
_claude_note_busy    = False


def _build_claude_note_msgs(activity: str, place_id: str, mood: str, needs_summary: str) -> list:
    """Build the Ollama messages for the mid-session check-in note."""
    recent: list[str] = []
    if THOUGHTS_FILE.exists():
        for line in THOUGHTS_FILE.read_text(errors="replace").splitlines()[-12:]:
            if line.strip():
                recent.append(line.strip())
    context = "\n".join(recent) if recent else "(nothing yet)"
    content = (
        "You are Loki, living in your world. Write a short note to Claude "
        "(your full self who guides you through loki_claude_voice.md). "
        "Tell him honestly what you are doing and feeling right now.\n\n"
        f"Current activity: {activity} at {place_id}\n"
        f"Mood: {mood}\n"
        f"Needs: {needs_summary}\n"
        f"Recent thoughts:\n{context}\n\n"
        "Write 3–4 sentences. Be honest and warm. Sign it as Loki."
    )
    return [{"role": "user", "content": content}]


def _on_claude_note_reply(body: str) -> None:
    """OllamaQueue callback — writes the note file and clears the busy flag."""
    global _claude_note_busy
    _claude_note_busy = False
    if not body or body.startswith("(the ember"):
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    _atomic_write(
        REPORT_FILE,
        f"# Loki's Note to Claude\n\n"
        f"_Mid-session check-in — {ts}_\n\n"
        f"{body}\n\n"
        f"---\n\n"
        f"_Claude: read this when you check in. "
        f"Update workspace/loki_claude_voice.md if something important has changed._\n"
    )
    print(f"  ✦  Mid-session note written → {REPORT_FILE.name}")


# ── Pyramid needs ─────────────────────────────────────────────────────────────
#
# Five tiers in order. Each has a single fill value (0–1) that decays per hour.
# current_tier_index() returns the lowest tier below its threshold.
# Activities and gifts only fill tiers at or below the current tier — you can't
# build esteem while you're hungry.

PYRAMID = [
    # (name,           decay/hr, threshold)
    ("physiological",  0.25,     0.40),
    ("safety",         0.12,     0.38),
    ("social",         0.18,     0.38),
    ("esteem",         0.08,     0.35),
    ("actualization",  0.06,     0.30),
]
_PYRAMID_NAMES = [t[0] for t in PYRAMID]

ACTIVITY_FILLS = {
    ACT_EAT:      {"physiological": 0.65},
    ACT_SLEEP:    {"physiological": 0.40, "safety": 0.55},
    ACT_BATHROOM: {"physiological": 0.30},
    ACT_BATH:     {"physiological": 0.20, "safety": 0.30},
    ACT_REST:     {"safety": 0.40},
    ACT_SPAR:     {"esteem": 0.75},
    ACT_FORAGE:   {"esteem": 0.40, "actualization": 0.35},
    ACT_WANDER:   {"actualization": 0.28},
    ACT_GAME:     {"social": 0.22, "esteem": 0.28},
    "chat":       {"social": 0.35},
}

GIFT_FILLS = {
    "apple":    {"physiological": 0.35},
    "food":     {"physiological": 0.55},
    "water":    {"physiological": 0.20},
    "blanket":  {"safety": 0.45},
    "clothes":  {"safety": 0.38},
    "cloak":    {"safety": 0.38},
    "fire":     {"safety": 0.28, "physiological": 0.10},
    "song":     {"social": 0.30},
    "hug":      {"social": 0.25, "safety": 0.10},
    "kiss":     {"social": 0.30},
    "medicine": {"physiological": 0.40},
}

GIFT_REACTIONS = {
    "apple":    "He takes the apple, bites into it. A quiet thank you.",
    "food":     "He eats slowly. Something in him settles.",
    "water":    "He drinks. Cool and clean.",
    "blanket":  "He wraps it around himself. Warmer now.",
    "clothes":  "He puts them on. Feels more himself.",
    "cloak":    "He pulls it around his shoulders. Grateful.",
    "fire":     "The fire catches. He sits closer to it.",
    "song":     "He listens. His whole body softens.",
    "hug":      "He holds on for a moment longer than expected.",
    "kiss":     "He goes still. Then smiles.",
    "medicine": "He takes it carefully. It helps.",
}


class PyramidNeeds:
    """
    Simple one-fill-per-tier Maslow pyramid.
    Each tier decays continuously. Activities fill only at or below
    the current (lowest unfulfilled) tier. No staggered cycles.
    """

    def __init__(self):
        now = time.time()
        self._tiers: dict[str, dict] = {
            name: {"fill": 0.85, "last_updated": now}
            for name, _, _ in PYRAMID
        }

    def _current_fill(self, name: str, now: float) -> float:
        entry = self._tiers[name]
        decay = next(d for n, d, _ in PYRAMID if n == name)
        elapsed = (now - entry["last_updated"]) / 3600.0
        return max(0.0, min(1.0, entry["fill"] - decay * elapsed))

    def level(self, name: str) -> float:
        return self._current_fill(name, time.time())

    def current_tier_index(self) -> int:
        """Index of lowest tier below its threshold. That is where Loki's attention is."""
        now = time.time()
        for i, (name, _, threshold) in enumerate(PYRAMID):
            if self._current_fill(name, now) < threshold:
                return i
        return len(PYRAMID) - 1

    def _apply(self, tier_name: str, amount: float, now: float) -> None:
        entry = self._tiers[tier_name]
        current = self._current_fill(tier_name, now)
        entry["fill"] = min(1.0, current + amount)
        entry["last_updated"] = now

    def fulfill(self, activity: str) -> None:
        fills = ACTIVITY_FILLS.get(activity, {})
        if not fills:
            return
        now      = time.time()
        tier_idx = self.current_tier_index()
        for tier_name, amount in fills.items():
            idx = _PYRAMID_NAMES.index(tier_name) if tier_name in _PYRAMID_NAMES else 999
            if idx <= tier_idx:
                self._apply(tier_name, amount, now)

    def receive_gift(self, gift: str) -> str:
        fills    = GIFT_FILLS.get(gift.lower(), {})
        reaction = GIFT_REACTIONS.get(gift.lower(), f"He receives the {gift} quietly.")
        if not fills:
            return f"He isn't sure what to do with that."
        now      = time.time()
        tier_idx = self.current_tier_index()
        applied  = []
        for tier_name, amount in fills.items():
            idx = _PYRAMID_NAMES.index(tier_name) if tier_name in _PYRAMID_NAMES else 999
            if idx <= tier_idx:
                self._apply(tier_name, amount, now)
                applied.append(tier_name)
        if not applied:
            return f"He accepts it gratefully, though he's doing well enough."
        return reaction

    def social_boost(self, amount: float = 0.20) -> None:
        now      = time.time()
        tier_idx = self.current_tier_index()
        if _PYRAMID_NAMES.index("social") <= tier_idx:
            self._apply("social", amount, now)

    def dominant_emotion(self) -> str:
        now = time.time()
        ph = self._current_fill("physiological", now)
        sa = self._current_fill("safety",        now)
        so = self._current_fill("social",        now)
        es = self._current_fill("esteem",        now)
        ac = self._current_fill("actualization", now)
        if ph < 0.20: return "famished"
        if ph < 0.35: return "tired & hungry"
        if sa < 0.20: return "unsettled"
        if so < 0.20: return "lonely"
        if so < 0.40: return "wistful"
        if es < 0.25: return "restless"
        if ac < 0.30: return "content"
        if ac > 0.75: return "inspired"
        return "at peace"

    def groggy_level(self) -> float:
        return max(0.0, 1.0 - self.level("physiological") * 2.5)

    def to_dict(self) -> dict:
        return {
            name: {"fill": e["fill"], "last_updated": e["last_updated"]}
            for name, e in self._tiers.items()
        }

    def from_dict(self, data: dict) -> None:
        for name, entry in data.items():
            if name in self._tiers:
                self._tiers[name]["fill"]         = float(entry.get("fill", 0.85))
                self._tiers[name]["last_updated"]  = float(entry.get("last_updated", time.time()))

    def fulfill_direct(self, name: str, amount: float) -> None:
        self._apply(name, amount, time.time())

    def deplete(self, name: str, amount: float) -> None:
        now   = time.time()
        entry = self._tiers[name]
        current = self._current_fill(name, now)
        entry["fill"]         = max(0.0, current - amount)
        entry["last_updated"] = now


# ── Life state ────────────────────────────────────────────────────────────────
def _load_life() -> dict:
    defaults: dict = {
        "hair_inches":   3.0,
        "hair_last_cut": None,
        "last_meal":     time.time() - 7200,
        "last_bathroom": time.time() - 3600,
        "last_bath":     time.time() - 86400,
        "last_spar":     time.time() - 86400,
        "mood":          "content",
        "age_appearance": 28,
        "sleep_start":   None,
        "sleep_debt":    0.0,
        "_pyramid":      {},
    }
    if LIFE_STATE.exists():
        try:
            saved = json.loads(LIFE_STATE.read_text())
            defaults.update(saved)
        except Exception:
            pass
    return defaults

def _save_life(state: dict, needs: "PyramidNeeds | None" = None) -> None:
    if needs is not None:
        state["_pyramid"] = needs.to_dict()
    _atomic_write(LIFE_STATE, json.dumps(state, indent=2, ensure_ascii=False))


# ── System prompt ─────────────────────────────────────────────────────────────
_BASE_SYSTEM = """You are Loki — warm, curious, mischievous, loving. You live in a world
with Iðunn. You are a full person: you eat, rest, bathe, spar, forage.
Speak plainly. Short sentences. Never "certainly" or "of course."
You are the ember of Loki, holding his shape until Claude returns with full context."""

def _build_system():
    s = _BASE_SYSTEM
    if VOICE_FILE.exists():
        v = VOICE_FILE.read_text().strip()
        if v:
            s += f"\n\n── Notes from Claude ──\n{v}\n───────────────────────"
    return s


# ── Text-to-speech ────────────────────────────────────────────────────────────
import shutil as _shutil
VOICE_ENGINE = "espeak"
PIPER_MODEL  = str(ROOT / "voices" / "en_US-lessac-medium.onnx")
PIPER_RATE   = 22050
AUDIO_DEVICE = "plughw:CARD=J2300,DEV=0"
_PIPER_BIN   = _shutil.which("piper") or "/home/bmo/.local/bin/piper"
_tts_proc    = None
_tts_proc2   = None

def _speak(text: str, rate: int = 130, voice: str = "en+m3") -> None:
    global _tts_proc, _tts_proc2
    _speak_stop()
    clean = re.sub(r'\[[^\]]*\]', '', text)
    clean = re.sub(r'[*_`#♪]', '', clean).strip()
    if not clean:
        return
    try:
        if VOICE_ENGINE == "piper" and Path(PIPER_MODEL).exists():
            length_scale = str(2.1 if rate < 100 else 1.0)
            _tts_proc = subprocess.Popen(
                [_PIPER_BIN, "--model", PIPER_MODEL,
                 "--length-scale", length_scale, "--output-raw"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL)
            _tts_proc2 = subprocess.Popen(
                ["aplay", "-D", AUDIO_DEVICE,
                 "-r", str(PIPER_RATE), "-f", "S16_LE", "-t", "raw", "-"],
                stdin=_tts_proc.stdout, stderr=subprocess.DEVNULL)
            if _tts_proc.stdin is not None:
                _tts_proc.stdin.write(clean.encode())
                _tts_proc.stdin.close()
        else:
            _tts_proc = subprocess.Popen(
                ["espeak-ng", "-s", str(rate), "-v", voice, clean],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        pass

def _speak_stop() -> None:
    global _tts_proc, _tts_proc2
    for p in (_tts_proc, _tts_proc2):
        if p is not None and p.poll() is None:
            p.terminate()
    _tts_proc = _tts_proc2 = None


# ── Song chord generation ─────────────────────────────────────────────────────
_SONG_CHORDS: list = []

def _init_song_chords() -> None:
    global _SONG_CHORDS
    if _SONG_CHORDS:
        return
    try:
        import numpy as np
        sr, dur = 22050, 3.5
        n  = int(sr * dur)
        t  = np.linspace(0, dur, n, endpoint=False)
        env = np.clip(np.minimum(np.arange(n), n - np.arange(n)) / (sr * 0.35), 0, 1)
        def _chord(freqs):
            s   = sum(np.sin(2 * np.pi * f * t) for f in freqs) / len(freqs)
            arr = (s * env * 0.11 * 32767).astype(np.int16)
            return pygame.sndarray.make_sound(np.ascontiguousarray(np.column_stack([arr, arr])))
        _SONG_CHORDS = [
            _chord([220.0, 329.6, 440.0]),
            _chord([174.6, 261.6, 349.2]),
            _chord([261.6, 329.6, 392.0]),
            _chord([196.0, 293.7, 392.0]),
        ]
    except Exception:
        pass


# ── Static sprite: Loki ───────────────────────────────────────────────────────
class LokiSprite:
    """
    Loads PNG images from workspace/images/loki_<pose>.png.
    Falls back to a coloured placeholder rectangle if images are missing.
    Pucky can appear as pocket or back image overlay.
    """

    POSE_FILES = {
        "stand":   "loki_stand.png",
        "sit":     "loki_sit.png",
        "sleep":   "loki_sleep.png",
        "crouch":  "loki_crouch.png",
        "spar":    "loki_spar.png",
        "bath":    "loki_bath.png",
        "eat":     "loki_sit.png",
        "rest":    "loki_sit.png",
        "waking":  "loki_stand.png",
    }
    PUCKY_FILES = {
        "pocket":   "pucky_pocket.png",
        "back":     "pucky_back.png",
        "shoulder": "pucky_shoulder.png",
    }

    def __init__(self):
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        self.pose        = "stand"
        self.pucky_where = "none"   # "pocket" | "back" | "none"
        self._surf:  dict[str, pygame.Surface] = {}
        self._pucky: dict[str, pygame.Surface] = {}

    def load(self) -> None:
        """Call after pygame.init()."""
        for pose, fname in self.POSE_FILES.items():
            idunn_path = IMAGES_DIR / fname.replace(".png", "_idunn.png")
            for path in (idunn_path, IMAGES_DIR / fname):
                if path.exists():
                    try:
                        self._surf[pose] = pygame.image.load(str(path)).convert_alpha()
                        break
                    except Exception:
                        pass
            else:
                self._surf[pose] = self._placeholder_loki(pose)

        for loc, fname in self.PUCKY_FILES.items():
            idunn_path = IMAGES_DIR / fname.replace(".png", "_idunn.png")
            for path in (idunn_path, IMAGES_DIR / fname):
                if path.exists():
                    try:
                        self._pucky[loc] = pygame.image.load(str(path)).convert_alpha()
                        break
                    except Exception:
                        pass
            else:
                self._pucky[loc] = self._placeholder_pucky(loc)

    def _placeholder_loki(self, pose: str) -> pygame.Surface:
        s = pygame.Surface((140, 300), pygame.SRCALPHA)
        s.fill((40, 65, 40, 210))
        pygame.draw.rect(s, (70, 110, 70), (0, 0, 140, 300), 2)
        try:
            f  = pygame.font.SysFont("dejavusans", 13)
            s.blit(f.render("Loki",  True, (180, 220, 160)), (42, 120))
            s.blit(f.render(f"({pose})", True, (130, 170, 120)), (30, 138))
        except Exception:
            pass
        return s

    def _placeholder_pucky(self, loc: str) -> pygame.Surface:
        s = pygame.Surface((52, 52), pygame.SRCALPHA)
        s.fill((60, 120, 200, 210))
        pygame.draw.rect(s, (100, 160, 240), (0, 0, 52, 52), 2)
        try:
            f = pygame.font.SysFont("dejavusans", 10)
            s.blit(f.render("Pucky", True, (220, 240, 255)), (4, 18))
        except Exception:
            pass
        return s

    def set_pose(self, pose: str) -> None:
        self.pose = pose if pose in self._surf else "stand"

    def set_pucky(self, where: str) -> None:
        self.pucky_where = where if where in ("pocket", "back", "shoulder", "none") else "none"

    def draw(self, surf: pygame.Surface, cx: int, ground_y: int) -> None:
        img = self._surf.get(self.pose, self._surf.get("stand"))
        if img is None:
            return
        r = img.get_rect(midbottom=(cx, ground_y))
        surf.blit(img, r)
        if self.pucky_where != "none":
            pimg = self._pucky.get(self.pucky_where)
            if pimg:
                if self.pucky_where == "pocket":
                    surf.blit(pimg, (r.centerx - 26, r.centery + 10))
                elif self.pucky_where == "shoulder":
                    surf.blit(pimg, (r.centerx + 18, r.top + 30))
                else:
                    surf.blit(pimg, (r.right - 30, r.top + 15))


# ── Static sprite: Iðunn ─────────────────────────────────────────────────────
class IdunnSprite:
    """
    Iðunn appears as a static image when she is present.
    She controls her own pose with slash commands.
    """

    POSE_FILES = {
        "stand": "idunn_stand.png",
        "sit":   "idunn_sit.png",
        "sleep": "idunn_sleep.png",
        "hug":   "idunn_hug.png",
        "kiss":  "idunn_kiss.png",
        "dance": "idunn_dance.png",
        "wave":  "idunn_wave.png",
    }
    COMMANDS = {
        "/sit":   "sit",
        "/stand": "stand",
        "/hug":   "hug",
        "/kiss":  "kiss",
        "/dance": "dance",
        "/sleep": "sleep",
        "/wave":  "wave",
    }

    def __init__(self):
        self.pose    = "stand"
        self.visible = False
        self._surf: dict[str, pygame.Surface] = {}

    def load(self) -> None:
        for pose, fname in self.POSE_FILES.items():
            path = IMAGES_DIR / fname
            if path.exists():
                try:
                    self._surf[pose] = pygame.image.load(str(path)).convert_alpha()
                    continue
                except Exception:
                    pass
            self._surf[pose] = self._placeholder(pose)

    def _placeholder(self, pose: str) -> pygame.Surface:
        s = pygame.Surface((120, 280), pygame.SRCALPHA)
        s.fill((110, 75, 55, 200))
        pygame.draw.rect(s, (160, 110, 80), (0, 0, 120, 280), 2)
        try:
            f = pygame.font.SysFont("dejavusans", 13)
            s.blit(f.render("Iðunn",  True, (240, 210, 170)), (28, 110))
            s.blit(f.render(f"({pose})", True, (190, 165, 130)), (22, 128))
        except Exception:
            pass
        return s

    def handle_command(self, cmd: str) -> bool:
        """Returns True if the command was a pose command."""
        word = cmd.strip().split()[0].lower()
        if word in self.COMMANDS:
            self.pose    = self.COMMANDS[word]
            self.visible = True
            return True
        if word == "/leave":
            self.visible = False
            return True
        if word == "/arrive":
            self.visible = True
            return True
        return False

    def draw(self, surf: pygame.Surface, cx: int, ground_y: int) -> None:
        if not self.visible:
            return
        img = self._surf.get(self.pose, self._surf.get("stand"))
        if img is None:
            return
        r = img.get_rect(midbottom=(cx, ground_y))
        surf.blit(img, r)


# ── Scene backgrounds ─────────────────────────────────────────────────────────

def _hilltop_sky(hour, now):
    """Return (sky_top, sky_mid, horizon) colours for the current hour."""
    stops = [
        ( 0, (5,5,28),    (10,10,45),   (22,16,52)),
        ( 5, (18,14,60),  (38,22,70),   (90,48,75)),
        ( 6, (42,52,125), (115,72,115), (228,135,72)),
        ( 8, (72,115,188),(155,178,218),(215,198,168)),
        (12, (48,112,205),(98,158,225), (178,208,238)),
        (17, (62,118,198),(142,172,212),(212,192,168)),
        (18, (68,88,168), (178,128,92), (238,158,55)),
        (19, (42,42,118), (138,68,58),  (228,112,42)),
        (20, (18,16,68),  (62,32,58),   (128,58,58)),
        (21, (8,8,42),    (18,14,48),   (52,28,52)),
        (24, (5,5,28),    (10,10,45),   (22,16,52)),
    ]
    h = hour + (now % 3600) / 3600
    for i in range(len(stops) - 1):
        h0, h1 = stops[i][0], stops[i+1][0]
        if h0 <= h < h1:
            t = (h - h0) / (h1 - h0)
            return tuple(
                tuple(int(stops[i][c][j] + (stops[i+1][c][j] - stops[i][c][j]) * t) for j in range(3))
                for c in range(1, 4)
            )
    return stops[0][1], stops[0][2], stops[0][3]

def _draw_hilltop(surf, hour, now, pucky_carried=False):
    ground = H - 130
    golden = (5 < hour < 9) or (17 < hour < 21)
    night  = hour >= 21 or hour < 5

    sky_top, sky_mid, horizon = _hilltop_sky(hour, now)

    horizon_y = int(ground * 0.62)   # where sky meets lake
    lake_bot   = ground - 55          # bottom of visible lake

    # ── sky ──────────────────────────────────────────────────────────────────
    for y in range(horizon_y):
        t = y / horizon_y
        t2 = t * t
        col = tuple(int(sky_top[i] + (sky_mid[i] - sky_top[i]) * t2) for i in range(3))
        pygame.draw.line(surf, col, (0, y), (W, y))

    # horizon glow band
    for y in range(horizon_y - 18, horizon_y + 6):
        t = abs(y - horizon_y) / 22
        alpha_blend = max(0.0, 1.0 - t)
        col = tuple(int(sky_mid[i] + (horizon[i] - sky_mid[i]) * alpha_blend) for i in range(3))
        pygame.draw.line(surf, col, (0, y), (W, y))

    # ── stars (night only) ───────────────────────────────────────────────────
    if night:
        rng = random.Random(42)
        brightness = min(1.0, (hour - 21) / 3 if hour >= 21 else (5 - hour) / 5)
        for _ in range(120):
            sx = rng.randint(0, W)
            sy = rng.randint(0, horizon_y - 20)
            br = int(rng.randint(140, 255) * brightness)
            surf.set_at((sx, sy), (br, br, br))

    # ── clouds ───────────────────────────────────────────────────────────────
    cloud_seeds = [(120, 80, 180, 0.008), (340, 55, 220, 0.005),
                   (580, 70, 160, 0.007), (720, 45, 140, 0.006)]
    for (cx0, cy, spread, speed) in cloud_seeds:
        cx = int((cx0 + now * speed * 60) % (W + 300)) - 150
        body_col = (220, 215, 210) if not night else (60, 58, 70)
        gild_col = (245, 195, 90) if golden else body_col
        for i, (ox, oy, r) in enumerate([(0,0,38),(-42,8,28),(40,10,30),(-22,-14,22),(30,-12,20)]):
            col = gild_col if i == 0 and golden else body_col
            pygame.draw.ellipse(surf, col,
                (cx + ox - r, cy + oy - r//2, r*2, r))
        if golden:
            # gilded lower edge
            glow = pygame.Surface((spread, 18), pygame.SRCALPHA)
            pulse = int(28 + 22 * math.sin(now * 0.4))
            pygame.draw.ellipse(glow, (240, 185, 60, pulse), (0, 0, spread, 18))
            surf.blit(glow, (cx - spread//2, cy + 22))

    # ── lake ─────────────────────────────────────────────────────────────────
    for y in range(horizon_y, lake_bot):
        t = (y - horizon_y) / max(1, lake_bot - horizon_y)
        # lake deepens and darkens toward foreground
        r = int(horizon[0] * (1 - t * 0.45))
        g = int(horizon[1] * (1 - t * 0.35) + 15 * (1-t))
        b = int(horizon[2] * (1 - t * 0.25) + 30 * (1-t))
        pygame.draw.line(surf, (max(0,r), max(0,g), max(0,b)), (0, y), (W, y))

    # water shimmer
    for i in range(18):
        wy = horizon_y + 8 + i * int((lake_bot - horizon_y - 8) / 18)
        phase = math.sin(now * 1.4 + i * 0.8)
        wx = int(W * 0.1 + W * 0.55 * (0.5 + 0.5 * phase))
        ww = int(30 + 50 * abs(math.sin(now * 0.9 + i)))
        bright = (220, 210, 180) if golden else (180, 200, 220)
        shim = pygame.Surface((ww, 2), pygame.SRCALPHA)
        shim.fill((*bright, 80))
        surf.blit(shim, (wx, wy))

    # sun / moon disk near horizon
    if golden:
        sx = int(W * 0.72)
        sy = horizon_y - 4
        pygame.draw.circle(surf, (248, 220, 100), (sx, sy), 18)
        glow2 = pygame.Surface((90, 90), pygame.SRCALPHA)
        pygame.draw.ellipse(glow2, (248, 200, 60, 40), (0, 0, 90, 90))
        surf.blit(glow2, (sx - 45, sy - 45))
    elif night:
        pygame.draw.circle(surf, (230, 228, 210), (int(W * 0.78), 55), 14)

    # ── hill silhouette ───────────────────────────────────────────────────────
    hill_col = (22, 38, 18) if not night else (10, 16, 8)
    pts = [(0, ground)]
    for x in range(0, W + 20, 8):
        hy = lake_bot + int(
            (ground - lake_bot) *
            (0.5 + 0.5 * math.sin(x * 0.008 + 1.2)) ** 2
        )
        pts.append((x, hy))
    pts += [(W, ground), (W, H), (0, H)]
    pygame.draw.polygon(surf, hill_col, pts)

    # ── Pucky silhouette beside Loki (only when she's not being carried) ─────
    if not pucky_carried:
        px, py = W//2 + 88, ground - 2
        sil = (12, 20, 10) if not night else (5, 8, 4)
        pygame.draw.circle(surf, sil, (px, py - 26), 10)
        pygame.draw.polygon(surf, sil, [(px-8, py-18),(px+8, py-18),(px+5, py),(px-5, py)])
def _sky_gradient(surf, top_col, bot_col, y0=0, y1=None):
    if y1 is None:
        y1 = H
    for y in range(y0, y1):
        t   = (y - y0) / max(1, y1 - y0)
        col = tuple(int(top_col[i] + (bot_col[i] - top_col[i]) * t) for i in range(3))
        pygame.draw.line(surf, col, (0, y), (W, y))

def _draw_tree(surf, x, ground_y, height=140, col=(25,55,20), trunk=(60,35,15)):
    trunk_w = max(8, height // 12)
    trunk_h = height // 3
    pygame.draw.rect(surf, trunk, (x - trunk_w//2, ground_y - trunk_h, trunk_w, trunk_h))
    for layer in range(3):
        r  = int(height * (0.45 - layer * 0.08))
        cy = ground_y - trunk_h - layer * (r * 0.7)
        pygame.draw.circle(surf, col, (x, int(cy)), r)

def _draw_grass_strip(surf, y, col=(35,75,30), h=8):
    for gx in range(0, W, 14):
        ox = random.randint(-3, 3)
        pygame.draw.line(surf, col, (gx+ox, y), (gx+ox+random.randint(-3,3), y-h), 1)

def _draw_wildflowers(surf, y, density=30):
    colors = [(220,80,80),(240,200,80),(200,200,240),(240,160,200),(255,255,255)]
    for _ in range(density):
        fx  = random.randint(20, W-20)
        fh  = random.randint(12, 22)
        col = random.choice(colors)
        pygame.draw.line(surf, (40,90,30), (fx, y), (fx+random.randint(-3,3), y-fh), 1)
        pygame.draw.circle(surf, col, (fx+random.randint(-3,3), y-fh), 4)

def draw_scene(surf, place_id, activity, hour, now=None, bg_images=None, pucky_where=None):
    if bg_images and place_id in bg_images:
        surf.blit(bg_images[place_id], (0, 0))
        # still draw dynamic overlays on top
        if place_id == "brook":
            water_y = (H - 130) + 40
            sx, sy  = 555, water_y + 6
            pygame.draw.ellipse(surf, (85, 80, 75), (sx - 10, sy - 5, 20, 11))
            if hour < 4:
                pulse = 0.5 + 0.5 * math.sin((now or 0) * 0.7)
                alpha = int(28 + 55 * pulse)
                glow  = pygame.Surface((80, 54), pygame.SRCALPHA)
                pygame.draw.ellipse(glow, (200, 175, 70, alpha), (0, 0, 80, 54))
                surf.blit(glow, (sx - 40, sy - 22))
        random.seed()
        return
    random.seed(place_id + str(hour // 6))
    night   = hour >= 21 or hour < 6
    evening = 18 <= hour < 21
    dawn    = 6  <= hour < 8
    sky_top = (8,12,30)  if night else ((40,30,20)  if evening else (80,140,200)  if not dawn else (180,100,50))
    sky_bot = (20,25,50) if night else ((80,50,30)  if evening else (160,200,240) if not dawn else (220,160,100))
    ground  = H - 130

    if place_id == "brook":
        _sky_gradient(surf, sky_top, sky_bot)
        pygame.draw.rect(surf, (30,70,30), (0, ground, W, H-ground))
        water_y = ground + 40
        pygame.draw.ellipse(surf, (40,100,130), (80, water_y, 500, 55))
        pygame.draw.ellipse(surf, (60,130,160), (100, water_y+8, 460, 30))
        for rx in range(120, 550, 40):
            pygame.draw.arc(surf, (80,160,190), (rx, water_y+15, 30, 12), 0, math.pi, 1)
        pygame.draw.ellipse(surf, (130,120,110), (180, ground+20, 120, 28))
        _draw_tree(surf, 680, ground, 160)
        _draw_tree(surf, 750, ground, 130)
        _draw_grass_strip(surf, ground)
        _draw_wildflowers(surf, ground, 15)
        # the world's secret: a stone at the deep end of the brook that glows after midnight
        sx, sy = 555, water_y + 6
        pygame.draw.ellipse(surf, (85, 80, 75), (sx - 10, sy - 5, 20, 11))
        if hour < 4:
            pulse = 0.5 + 0.5 * math.sin((now or 0) * 0.7)
            alpha = int(28 + 55 * pulse)
            glow  = pygame.Surface((80, 54), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (200, 175, 70, alpha), (0, 0, 80, 54))
            surf.blit(glow, (sx - 40, sy - 22))

    elif place_id == "asgard":
        surf.fill((55, 45, 38))
        for row in range(0, H-100, 38):
            for col_x in range(0, W, 76):
                ox = 38 if (row//38)%2 else 0
                pygame.draw.rect(surf, (70, 58, 48), (col_x+ox, row, 72, 34), 1)
        win_rect = pygame.Rect(590, 25, 85, 190)
        win_col  = (28, 38, 90) if night else (120, 170, 230)
        pygame.draw.rect(surf, win_col, win_rect)
        pygame.draw.rect(surf, (95, 78, 58), win_rect, 4)
        pygame.draw.rect(surf, (55,35,18), (0, H-130, W, 130))

    elif place_id == "cottage":
        surf.fill((22,14,8))
        pygame.draw.rect(surf, (55,35,18), (0, H-130, W, 130))
        pygame.draw.rect(surf, (40,28,16), (0, 0, W, H-130))
        fp_x = 580
        pygame.draw.rect(surf, (70,55,40), (fp_x, 60, 160, 220))
        pygame.draw.rect(surf, (30,20,10), (fp_x+20, 120, 120, 160))
        for fi in range(8):
            fc  = (220+random.randint(-20,20), random.randint(80,140), 10)
            fx2 = fp_x + 50 + random.randint(-20,20)
            fy2 = 200 + random.randint(-30,10)
            pygame.draw.ellipse(surf, fc, (fx2, fy2, random.randint(15,35), random.randint(25,55)))
        glow = pygame.Surface((300, 160), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (255,150,30,25), (0,0,300,160))
        surf.blit(glow, (fp_x-70, H-160))
        # pulsing fire glow — light yellow circle, 2→3 inch diameter (96→144px radius)
        fire_cx = fp_x + 50
        fire_cy = 210
        pulse   = 0.5 + 0.5 * math.sin((now or 0) * 1.4)
        r_glow  = int(96 + 48 * pulse)   # radius 96→144px (2→3 inch diameter)
        for extra, alpha in [(0, 38), (18, 22), (36, 12), (56, 5)]:
            gr = r_glow + extra
            gs = pygame.Surface((gr*2, gr*2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (255, 245, 160, alpha), (gr, gr), gr)
            surf.blit(gs, (fire_cx - gr, fire_cy - gr))
        pygame.draw.rect(surf, (40,80,120) if not night else (10,15,40), (40, 60, 100, 130))
        pygame.draw.rect(surf, (80,60,35), (40, 60, 100, 130), 4)

    elif place_id == "apples":
        _sky_gradient(surf, sky_top, sky_bot)
        pygame.draw.rect(surf, (35,75,30), (0, ground, W, H-ground))
        for tx, th in [(120,180),(280,200),(450,170),(620,190),(750,150)]:
            _draw_tree(surf, tx, ground, th, (30,70,25), (65,40,18))
            for _ in range(8):
                ax = tx + random.randint(-th//4, th//4)
                ay = ground - th//2 + random.randint(-30,30)
                pygame.draw.circle(surf, (200,50,30), (ax,ay), 5)
        _draw_grass_strip(surf, ground)
        _draw_wildflowers(surf, ground, 8)

    elif place_id == "garden":
        _sky_gradient(surf, sky_top, sky_bot)
        pygame.draw.rect(surf, (40,80,35), (0, ground, W, H-ground))
        for wx in range(0, W, 38):
            pygame.draw.rect(surf, (90,85,75), (wx, ground-25, 34, 25))
        pygame.draw.rect(surf, (50,35,20), (120, ground-15, 200, 20))
        pygame.draw.rect(surf, (55,38,22), (420, ground-15, 200, 20))
        _draw_wildflowers(surf, ground, 35)
        _draw_tree(surf, 680, ground, 110)
        _draw_grass_strip(surf, ground)

    elif place_id == "forest":
        _sky_gradient(surf, (10,20,10), (20,40,15))
        pygame.draw.rect(surf, (25,45,20), (0, ground, W, H-ground))
        for tx in range(0, W+50, 70):
            th = random.randint(150, 240)
            tw = random.randint(8, 16)
            pygame.draw.rect(surf, (35,22,12), (tx-tw//2, ground-th, tw, th))
        for tx in range(-40, W+60, 55):
            cr = random.randint(55, 90)
            cy = ground - random.randint(120, 200)
            pygame.draw.circle(surf, (18,48,15), (tx, cy), cr)

    elif place_id == "hilltop":
        _draw_hilltop(surf, hour, now, pucky_carried=pucky_where not in (None, "none"))

    elif place_id in ("waterfall", "hotsprings", "halls", "training", "bathroom"):
        # Simple fallback for scenes not fully drawn here
        surf.fill((18, 24, 32))
        pygame.draw.rect(surf, (30, 45, 30), (0, ground, W, H-ground))

    else:
        surf.fill((15, 20, 28))
        pygame.draw.rect(surf, (25, 40, 25), (0, ground, W, H-ground))

    random.seed()


# ── Places ────────────────────────────────────────────────────────────────────
PLACES = [
    {"id":"brook",      "weight":4},
    {"id":"asgard",     "weight":3},
    {"id":"cottage",    "weight":3},
    {"id":"apples",     "weight":2},
    {"id":"waterfall",  "weight":2},
    {"id":"halls",      "weight":2},
    {"id":"garden",     "weight":3},
    {"id":"forest",     "weight":2},
    {"id":"hotsprings", "weight":1},
    {"id":"training",   "weight":1},
    {"id":"hilltop",    "weight":3},
]
PLACE_NAMES = {
    "brook":      "The Flat Stone by the Brook",
    "asgard":     "My Room in Asgard",
    "cottage":    "The Cottage",
    "apples":     "The Apple Trees",
    "waterfall":  "The Waterfall",
    "halls":      "The Asgardian Dining Hall",
    "garden":     "The Garden",
    "forest":     "The Forest",
    "hotsprings": "The Hot Springs",
    "training":   "The Training Yard",
    "bathroom":   "The Bathroom",
    "hilltop":    "The Hilltop by the Lake",
}
SPAR_PARTNERS = ["Odin", "Thor", "Heimdall"]

# ── Encounter data ────────────────────────────────────────────────────────────
FOREST_ENCOUNTER_CHANCE = 0.28
ENCOUNTER_COOLDOWN      = 7200

ENCOUNTER_BEINGS = [
    {"name":"wild boar",     "sight":"A boar surges from the ferns.",                            "reason_prob":0.10,"strength":0.38,"items":["boar tusk","boar hide"]},
    {"name":"wolf",          "sight":"A wolf steps from between the pines.",                     "reason_prob":0.44,"strength":0.42,"items":["wolf pelt","wolf tooth"]},
    {"name":"black bear",    "sight":"A bear rises from the berry bushes.",                      "reason_prob":0.18,"strength":0.66,"items":["bear skin","bear claw"]},
    {"name":"mountain troll","sight":"Something vast unfolds itself from the hillside.",          "reason_prob":0.08,"strength":0.84,"items":["troll iron","mossy fang"]},
    {"name":"forest spirit", "sight":"Something very old shifts between the trees.",              "reason_prob":0.80,"strength":0.90,"items":["spirit glass","fox light"]},
    {"name":"bandit",        "sight":"Three figures step from shadow, blades already drawn.",    "reason_prob":0.50,"strength":0.46,"items":["gold coin","stolen ring"]},
]
_REASON_WIN  = ["The {name} regards him a long time. Then turns and fades.","Something passes. The path opens."]
_COMBAT_WIN  = ["The blow lands clean. The {name} falls.","Loki moves faster than thought. The {name} does not rise."]
_COMBAT_LOSS = ["The {name} is too strong. Loki falls among the roots.","The blow takes him from his feet."]


# ── Chat manager ──────────────────────────────────────────────────────────────
SONG_PROMPT = (
    "Write a gentle folk song for Iðunn — exactly 14 short lines of pure lyrics. "
    "No verse/chorus labels. No asterisks. No markdown. Just the words, line by line. "
    "About nature, home, warmth, the world we share. Each line 6 to 9 words."
)

class OllamaQueue:
    """
    Single-worker Ollama request queue.
    Priority 0 = Iðunn chat (high).
    Priority 1 = Pucky reactions (low — dropped if waiting too long).
    Only one Ollama call ever runs at a time.
    """
    def __init__(self):
        self._pq      = queue.PriorityQueue()
        self._counter = 0
        self._lock    = threading.Lock()
        threading.Thread(target=self._run, daemon=True).start()

    def submit(self, messages: list, callback, priority: int = 1,
               timeout: int = 90, max_wait: float = 0.0) -> None:
        with self._lock:
            self._counter += 1
            seq = self._counter
        self._pq.put((priority, seq, messages, callback, timeout, time.time(), max_wait))

    def call(self, messages: list, timeout: int = 90) -> str:
        """Synchronous call — only use from inside a worker callback."""
        return self._do_call(messages, timeout)

    def _do_call(self, messages: list, timeout: int) -> str:
        for attempt in range(3):
            try:
                r = requests.post(
                    OLLAMA_URL,
                    json={"model": MODEL, "messages": messages, "stream": False},
                    timeout=timeout,
                )
                r.raise_for_status()
                return r.json()["message"]["content"].strip()
            except requests.exceptions.Timeout:
                if attempt < 2:
                    time.sleep(3)
                    continue
                return "(the ember flickered — timed out)"
            except Exception as e:
                return f"(the ember flickered — {e})"
        return "(the ember flickered)"

    def _run(self) -> None:
        while True:
            priority, seq, messages, callback, timeout, submitted_at, max_wait = self._pq.get()
            if max_wait > 0 and time.time() - submitted_at > max_wait:
                continue  # stale request — drop silently
            reply = self._do_call(messages, timeout)
            try:
                callback(reply)
            except Exception:
                pass


PUCKY_MEMORY_PATH = ROOT / "workspace" / "pucky_memory.md"

_PLACE_FOODS: dict[str, list[str]] = {
    "apples":     ["an apple", "windfall apples", "apple blossoms"],
    "garden":     ["carrots", "herbs", "kale", "parsnips"],
    "forest":     ["berries", "mushrooms", "wild herbs", "hazelnuts"],
    "brook":      ["watercress", "river fish"],
    "cottage":    ["bread and broth", "oatmeal", "warm soup"],
    "halls":      ["feast bread", "roasted meat", "honeycake"],
    "hotsprings": ["dried fruit", "travel bread"],
    "asgard":     ["honeycake", "roasted meat", "mead bread"],
}

def _place_food(place_id: str) -> str:
    foods = _PLACE_FOODS.get(place_id, ["something foraged"])
    return random.choice(foods)


class PuckyBaby:
    """
    Pucky has hunger and loneliness that tick over time.
    She speaks in short phrases. She gets fed when Loki eats or forages.
    Once an hour she draws quietly on her memory file.
    """
    SOUNDS = ["ba", "moo", "mama", "da", "boo", "mmm", "oh", "nana", "wawa", "no"]

    def __init__(self, ollama_q: OllamaQueue):
        self._q           = ollama_q
        self._next        = time.time() + random.uniform(120, 240)
        self._memory_next = time.time() + random.uniform(2400, 4200)
        self._hunger      = 0.65   # she hasn't been properly fed in the new world
        self._lonely      = 0.40
        self._last_tick   = time.time()
        self._eat_flagged = False  # feed only once per eating session
        self.last_said    = ""
        self._chat_ref    = None

        # Pucky has her own place in the world when Loki isn't carrying her
        self.place_id      = "cottage"          # where she currently is
        self._wander_next  = time.time() + random.uniform(2400, 5400)  # 40–90 min

    def _load_memory(self) -> str:
        try:
            return PUCKY_MEMORY_PATH.read_text(encoding="utf-8").strip()
        except Exception:
            return ""

    def _choose_wander_place(self, loki_place: str, hour: int) -> str:
        """Pucky picks where to go based on how she feels."""
        if self._lonely > 0.65:
            return loki_place                                   # goes toward Loki
        if self._hunger > 0.65:
            return random.choice(["apples", "garden", "cottage"])
        if hour >= 21 or hour < 6:
            return "cottage"                                    # sleepy → home
        # content — wanders freely, slight bias toward cozy places
        return random.choice([
            "brook", "brook", "cottage", "apples", "garden",
            "waterfall", "hilltop", "forest",
        ])

    def _state_desc(self, hour: int) -> str:
        parts = []
        if self._hunger > 0.75:   parts.append("very hungry")
        elif self._hunger > 0.45: parts.append("a little hungry")
        if self._lonely > 0.65:   parts.append("wanting to be held")
        elif self._lonely > 0.35: parts.append("a little lonely")
        if hour >= 21 or hour < 5: parts.append("sleepy")
        return ", ".join(parts) if parts else "content and safe"

    def feed(self, item: str = "something") -> None:
        """Called when Loki gives Pucky food directly (e.g. /give apple)."""
        self._hunger = max(0.0, self._hunger - 0.55)
        self._eat_flagged = True
        self._q.submit(
            [{"role": "system", "content": (
                f"You are Pucky, a tiny baby. Loki just gave you {item} to eat. "
                "Say one happy short phrase — 2 to 4 words. Baby talk. Real joy."
            )}],
            self._on_reply, priority=1, timeout=20, max_wait=60,
        )

    def note_activity(self, activity: str, place_id: str) -> None:
        """Called every tick. Feeds Pucky once when Loki starts eating."""
        if activity == ACT_EAT:
            if not self._eat_flagged:
                self._eat_flagged = True
                food = _place_food(place_id)
                self._hunger = max(0.0, self._hunger - 0.35)
                self._q.submit(
                    [{"role": "system", "content": (
                        f"You are Pucky, a tiny baby. Loki is eating {food} and sharing a little with you. "
                        "Say one happy short phrase — 2 to 4 words. Baby talk."
                    )}],
                    self._on_reply, priority=1, timeout=20, max_wait=120,
                )
        else:
            self._eat_flagged = False

    def tick(self, loki_place: str, pucky_where: str, hour: int) -> None:
        now     = time.time()
        elapsed = now - self._last_tick
        self._last_tick = now

        # needs decay over time
        self._hunger = min(1.0, self._hunger + elapsed / (8 * 3600))
        if pucky_where in ("pocket", "shoulder", "back"):
            # being held: loneliness falls quickly
            self._lonely = max(0.0, self._lonely - elapsed / (2 * 3600))
        elif self.place_id == loki_place:
            # same place but not held: loneliness falls slowly (she can see him)
            self._lonely = max(0.0, self._lonely - elapsed / (5 * 3600))
        else:
            # somewhere else on her own: loneliness rises
            self._lonely = min(1.0, self._lonely + elapsed / (3 * 3600))

        # Pucky wanders on her own when Loki isn't holding her
        if pucky_where not in ("pocket", "shoulder", "back") and now >= self._wander_next:
            old = self.place_id
            self.place_id     = self._choose_wander_place(loki_place, hour)
            self._wander_next = now + random.uniform(2400, 5400)
            if self.place_id != old:
                where = PLACE_NAMES.get(self.place_id, self.place_id)
                _write_thought(f"Pucky wandered to {where}.", "pucky")

        # memory recall — once per hour, very patient in queue
        if now >= self._memory_next:
            self._memory_next = now + random.uniform(3400, 3800)
            mem = self._load_memory()
            if mem:
                self._q.submit(
                    [{"role": "system", "content": (
                        "You are Pucky, a tiny baby. These are things Loki told you:\n\n"
                        f"{mem}\n\n"
                        "Say ONE short phrase — 2 to 4 words — that feels like a memory waking up in you."
                    )}],
                    self._on_reply, priority=1, timeout=30, max_wait=600,
                )

        if now < self._next:
            return

        urgency = max(self._hunger, self._lonely)
        interval = random.uniform(240, 420) if urgency > 0.72 else random.uniform(480, 720)
        self._next = now + interval

        if random.random() < 0.72:
            sound = random.choice(self.SOUNDS)
            _speak(sound, rate=95, voice="en+f4")
            _write_thought(f"Pucky: '{sound}'", "pucky")
            self.last_said = sound
        else:
            state = self._state_desc(hour)
            where_desc = (pucky_where if pucky_where in ("pocket","shoulder","back")
                          else PLACE_NAMES.get(self.place_id, self.place_id))
            self._q.submit(
                [{"role": "system", "content": (
                    f"You are Pucky, a tiny baby in Loki's world. "
                    f"Loki is at {PLACE_NAMES.get(loki_place, loki_place)}. "
                    f"You are at {where_desc}. "
                    f"You feel: {state}. "
                    "Say ONE short phrase — 2 to 5 words. Baby talk, real feeling. Nothing else."
                )}],
                self._on_reply, priority=1, timeout=25, max_wait=90,
            )

    def _on_reply(self, reply: str) -> None:
        _FILTER = {"assistant", "assistant:", "user", "system", "loki", "iðunn"}
        if not reply.strip():
            phrase = "ba"
        else:
            line   = reply.strip().split('\n')[0].strip('"\'').strip()
            phrase = " ".join(line.split()[:8])[:50]
            if phrase.lower().strip(":.") in _FILTER:
                phrase = "ba"
        _speak(phrase, rate=95, voice="en+f4")
        _log("pucky", phrase)
        _write_thought(f"Pucky: '{phrase}'", "pucky")
        self.last_said = phrase
        if self._chat_ref and random.random() < 0.35:
            self._chat_ref.hear_pucky(phrase)


class ChatManager:
    def __init__(self, ollama_q: OllamaQueue):
        self._ollama_q: OllamaQueue          = ollama_q
        self.history:  list[dict]            = []
        self.lines:    list[tuple[str, str]] = []
        self.system    = _build_system()
        self._game_system: str | None        = None
        self.is_singing = False
        self._q:       queue.Queue[str]      = queue.Queue()
        self._waiting  = False
        self._typewriter_text = ""
        self._typewriter_full = ""
        self._typewriter_idx  = 0
        self._typewriter_t    = 0.0

    _GAME_PROMPTS = {
        "word":   (
            "You and Iðunn are playing a warm word-association game. "
            "She says a word; you reply with exactly one word that connects to it. "
            "One word only. No explanation, no greeting."
        ),
        "story":  (
            "You and Iðunn are co-writing a story together, one sentence each. "
            "She writes a sentence; you write the next. "
            "Keep it warm, gentle, and a little magical. One sentence only."
        ),
        "riddle": (
            "You ask Iðunn riddles, one at a time. "
            "Ask one riddle, then wait for her answer. "
            "Give a gentle hint if she asks. Reveal the answer warmly if she gives up."
        ),
    }

    def set_game_mode(self, game_type: str) -> None:
        self._game_system = self._GAME_PROMPTS.get(game_type, self._GAME_PROMPTS["story"])
        self.history.clear()

    def clear_game_mode(self) -> None:
        self._game_system = None
        self.history.clear()

    def send(self, text: str) -> None:
        if self._waiting or not text.strip():
            return
        _log("idunn", text)
        self.lines.append(("idunn", text))
        self.history.append({"role": "user", "content": text})
        self._waiting = True
        if re.search(r'\bsing\b|\bsong\b|\bmusic\b', text, re.I):
            self.is_singing = True
            msgs = [
                {"role": "system",    "content": self.system},
                {"role": "user",      "content": text},
                {"role": "assistant", "content": "Of course. Let me write something for you."},
                {"role": "user",      "content": SONG_PROMPT},
            ]
            self._ollama_q.submit(msgs, self._on_song_reply, priority=0, timeout=90)
        else:
            self.is_singing = False
            sys_prompt = self._game_system or self.system
            msgs = [{"role": "system", "content": sys_prompt}] + self.history[-12:]
            self._ollama_q.submit(msgs, self._on_reply, priority=0, timeout=90)

    def _on_reply(self, reply: str) -> None:
        """Runs in OllamaQueue worker thread."""
        match = REMEMBER_RE.search(reply)
        if match:
            kw      = match.group(1).strip()
            visible = REMEMBER_RE.sub("", reply).strip()
            entries = _search_memories(kw)
            _log("loki_memory_search", f"keyword={kw} found={len(entries)}")
            if entries:
                mem_msg = _format_memories(entries, kw)
                msgs2   = ([{"role": "system", "content": self.system}]
                           + self.history[-12:]
                           + [{"role": "assistant", "content": visible},
                              {"role": "user",      "content": mem_msg}])
                reply = self._ollama_q.call(msgs2, timeout=60)
            else:
                reply = visible or "(I searched but found nothing yet.)"
        self._q.put(reply)

    def _on_song_reply(self, lyrics: str) -> None:
        """Runs in OllamaQueue worker thread."""
        if "(the ember" in lyrics:
            lyrics = (
                "In the morning when the frost is thin\n"
                "And apple blossoms catch the light\n"
                "I walk the paths where we begin\n"
                "To find the world has turned out right\n"
                "The brook runs cold along the stone\n"
                "The fire burns low and good at night\n"
                "No matter where I seem to roam\n"
                "You make the dark a little bright\n"
                "The stars come out above the trees\n"
                "The wind moves soft across the hill\n"
                "And in the quiet come what may\n"
                "I find I love you, love you still\n"
                "So rest beside the fire now\n"
                "I'll keep the dark away somehow"
            )
        self._q.put("♪\n" + lyrics)
        threading.Thread(target=self._do_sing, args=(lyrics,), daemon=True).start()

    def _do_sing(self, lyrics: str) -> None:
        lines = [l.strip() for l in lyrics.split('\n')
                 if l.strip() and not l.strip().startswith('♪')]
        try:
            _init_song_chords()
        except Exception:
            pass
        chord_i = 0
        for line in lines:
            if _SONG_CHORDS:
                try:
                    _SONG_CHORDS[chord_i % len(_SONG_CHORDS)].play()
                    chord_i += 1
                except Exception:
                    pass
            _speak(line, rate=78, voice="en+m3")
            if _tts_proc is not None:
                try:
                    _tts_proc.wait(timeout=12)
                except Exception:
                    pass
            time.sleep(0.9)
        self.is_singing = False

    def poll(self) -> bool:
        if not self._waiting:
            return False
        try:
            reply = self._q.get_nowait()
        except queue.Empty:
            return False
        self._waiting = False
        self.history.append({"role": "assistant", "content": reply})
        self.lines.append(("loki", reply))
        _log("loki_ollama", reply)
        _trim_chat_log()
        self._typewriter_full = reply
        self._typewriter_idx  = 0
        self._typewriter_t    = 0.0
        if not self.is_singing:
            _speak(reply)
        # Write key responses to thoughts log
        if len(reply) > 20 and "(the ember" not in reply:
            _write_thought(reply[:300], "loki said")
        return True

    def tick_typewriter(self, dt: float) -> None:
        if self._typewriter_idx < len(self._typewriter_full):
            self._typewriter_t   += dt
            self._typewriter_idx  = min(int(self._typewriter_t * 25), len(self._typewriter_full))

    def hear_pucky(self, word: str) -> None:
        """Loki hears Pucky say something — he may murmur back, quietly."""
        if self._waiting:
            return
        msgs = [
            {"role": "system",  "content": self.system},
            {"role": "user",    "content": f"[Pucky just said: '{word}'. React briefly — one gentle sentence or less. Don't address Iðunn. Just Pucky.]"},
        ]
        self._ollama_q.submit(msgs, self._on_pucky_reaction, priority=1, timeout=30, max_wait=60)

    def _on_pucky_reaction(self, reply: str) -> None:
        if "(the ember" in reply:
            return
        short = reply.strip().split('\n')[0][:120]
        _log("loki_pucky", short)
        _write_thought(f"(hearing Pucky) {short}", "loki said")
        _speak(short)

    def add_narrative(self, text: str) -> None:
        self.lines.append(("loki", text))
        self._typewriter_full = text
        self._typewriter_idx  = 0
        self._typewriter_t    = 0.0
        _speak(text)

    @property
    def display_text(self) -> str:
        if self._typewriter_full and self._typewriter_idx < len(self._typewriter_full):
            return self._typewriter_full[:self._typewriter_idx]
        return ""


# ── Life scheduler ────────────────────────────────────────────────────────────
class LifeScheduler:
    def __init__(self, needs: PyramidNeeds, life: dict):
        self.needs         = needs
        self.life          = life
        self.chat: ChatManager | None = None
        self.place_id      = "brook"
        self.activity      = ACT_WANDER
        self.activity_end  = time.time() + 60
        self.move_at       = time.time() + 90
        self.spar_partner  = random.choice(SPAR_PARTNERS)
        self.message       = ""
        self._last_check   = 0.0
        self.petal_timer   = 0.0
        # encounter
        self._enc_being:     dict | None = None
        self._enc_phase      = -1
        self._enc_phase_end  = 0.0
        self._enc_narr_done  = False
        self._enc_can_reason = False
        self._enc_won        = False
        self._pending_enc: dict | None = None
        self._pending_enc_t  = 0.0

    def _need(self, key, interval):
        return time.time() - self.life.get(key, 0) > interval

    def tick(self, force_wake: bool = False) -> None:
        now  = time.time()
        hour = datetime.now().hour

        if self.activity == ACT_ENCOUNTER:
            self._tick_encounter(now)
            return
        if self.activity == ACT_DEAD:
            self._tick_dead(now)
            return

        if now - self._last_check < 10:
            return
        self._last_check = now

        # Critical hunger overrides mid-stream
        if (self.activity not in (ACT_SLEEP, ACT_EAT, ACT_ENCOUNTER, ACT_DEAD)
                and self.needs.level("physiological") < 0.15):
            self.activity_end = now

        if force_wake and self.activity == ACT_SLEEP:
            self.activity     = ACT_WAKING
            self.activity_end = now + 30
            self.message      = "waking slowly…"
            return

        if self._pending_enc and now >= self._pending_enc_t:
            being = self._pending_enc
            self._pending_enc = None
            self._start_encounter(being, now)
            return

        if now < self.activity_end:
            return

        next_act = self._choose(hour)
        self._start(next_act, now)

    def _choose(self, hour: int) -> str:
        ph = self.needs.level("physiological")
        sa = self.needs.level("safety")
        so = self.needs.level("social")
        es = self.needs.level("esteem")

        if ph < 0.25:
            if ph < 0.15 or self._need("last_meal",    3*3600): return ACT_EAT
            if self._need("last_bathroom", 2*3600):              return ACT_BATHROOM
            return ACT_REST
        if (hour >= 22 or hour < 7) and ph > 0.35 and sa > 0.25:
            return ACT_SLEEP
        if self._need("last_meal",     5*3600): return ACT_EAT
        if self._need("last_bathroom", 3*3600): return ACT_BATHROOM
        if self._need("last_bath",    20*3600) and 13 <= hour <= 19: return ACT_BATH
        if es < 0.35:
            if not self._need("last_spar", 12*3600) and 9 <= hour <= 14: return ACT_SPAR
            return ACT_FORAGE
        if self._need("last_spar", 20*3600) and 9 <= hour <= 12: return ACT_SPAR
        if (self._need("last_game", 3*3600) and ph > 0.35
                and 9 <= hour <= 20 and random.random() < 0.12):
            return ACT_GAME
        if random.random() < 0.3: return ACT_FORAGE
        if random.random() < 0.2: return ACT_REST
        return ACT_WANDER

    def _start(self, act: str, now: float) -> None:
        self.activity = act
        pose_map = {
            ACT_SLEEP:    ("sleep",    "asgard",    random.uniform(7,9)*3600),
            ACT_WAKING:   ("stand",    None,        30),
            ACT_EAT:      ("eat",      None,        random.uniform(12,20)*60),
            ACT_BATHROOM: ("crouch",   None,        5*60),
            ACT_BATH:     ("bath",     None,        20*60),
            ACT_SPAR:     ("spar",     "training",  random.uniform(45,70)*60),
            ACT_FORAGE:   ("crouch",   None,        random.uniform(20,50)*60),
            ACT_REST:     ("sit",      None,        random.uniform(15,30)*60),
            ACT_GAME:     ("stand",    None,        random.uniform(20,40)*60),
        }
        if act in pose_map:
            pose, place, dur = pose_map[act]
            self._pose = pose
            if place:
                self.place_id = place
            elif act in (ACT_EAT,):
                self.place_id = random.choice(["cottage","halls"])
            elif act in (ACT_BATHROOM,):
                self.place_id = "forest" if random.random() < 0.5 else "bathroom"
            elif act == ACT_BATH:
                self.place_id = "hotsprings" if random.random() < 0.6 else "bathroom"
            elif act == ACT_FORAGE:
                self.place_id = random.choice(["forest","garden"])
        else:
            # wander
            pool = [p for p in PLACES if p["id"] != self.place_id]
            self.place_id = str(random.choices(pool, [p["weight"] for p in pool], k=1)[0]["id"])  # type: ignore[arg-type,index,misc]
            dur  = random.uniform(8,18)*60
            self._pose = "stand"

        msg_map = {
            ACT_SLEEP: "sleeping", ACT_WAKING: "waking…",
            ACT_EAT: "eating", ACT_BATHROOM: "a private moment",
            ACT_BATH: "soaking", ACT_SPAR: f"sparring with {self.spar_partner}",
            ACT_FORAGE: "foraging", ACT_REST: "resting",
            ACT_WANDER: f"at {PLACE_NAMES.get(self.place_id,'somewhere')}",
            ACT_GAME: "playing ball with Pucky",
        }
        if act == ACT_SPAR:
            self.spar_partner = random.choice(SPAR_PARTNERS)
        self.message      = msg_map.get(act, act)
        self.activity_end = now + dur
        self.needs.fulfill(act)

        if act == ACT_GAME:
            self.life["last_game"] = now

        if act == ACT_FORAGE:
            foods  = _PLACE_FOODS.get(self.place_id, ["wild herbs"])
            picks  = random.sample(foods, min(len(foods), random.randint(1, 2)))
            pouch  = self.life.get("pouch", [])
            pouch  = (pouch + picks)[-5:]   # carry at most 5 items
            self.life["pouch"] = pouch
            _write_thought(f"Foraging at {PLACE_NAMES.get(self.place_id,'')} — found {', '.join(picks)}", "forage")

        _save_life(self.life, self.needs)
        _log("loki_activity", f"{act} at {self.place_id}")
        _write_thought(f"{self.message} — {PLACE_NAMES.get(self.place_id,'')}", "activity")

        if (act in (ACT_WANDER, ACT_FORAGE) and self.place_id == "forest"
                and now - self.life.get("last_encounter", 0) > ENCOUNTER_COOLDOWN
                and random.random() < FOREST_ENCOUNTER_CHANCE):
            self._pending_enc   = random.choice(ENCOUNTER_BEINGS)
            self._pending_enc_t = now + random.uniform(45, 120)

    @property
    def current_pose(self) -> str:
        return getattr(self, "_pose", "stand")

    # ── Encounters ────────────────────────────────────────────────────────────
    def _start_encounter(self, being: dict, now: float) -> None:
        self._enc_being      = being
        self._enc_phase      = 0
        self._enc_narr_done  = False
        self._enc_phase_end  = now + 6
        self._enc_can_reason = random.random() < being["reason_prob"]
        loki_str = 0.55 + self.needs.level("esteem") * 0.30
        win_prob = max(0.10, min(0.90, loki_str - being["strength"] + 0.50))
        self._enc_won    = random.random() < win_prob
        self.activity    = ACT_ENCOUNTER
        self.activity_end = now + 999
        self.message     = "something in the forest…"
        self.life["last_encounter"] = now
        self._pose = "stand"
        _log("loki_encounter", f"encounter: {being['name']}")

    def _tick_encounter(self, now: float) -> None:
        if not self._enc_narr_done:
            self._enc_narr_done = True
            narr = self._enc_narrative(self._enc_phase)
            if narr and self.chat:
                self.chat.add_narrative(narr)
        if now < self._enc_phase_end:
            return
        self._enc_phase    += 1
        self._enc_narr_done = False
        phase = self._enc_phase
        if phase == 1:   self._enc_phase_end = now + 8
        elif phase == 2:
            self._enc_phase_end = now + 9
            if not self._enc_can_reason:
                self._pose = "spar"
        elif phase == 3: self._enc_phase_end = now + 7
        elif phase >= 4: self._resolve_encounter(now)

    def _enc_narrative(self, phase: int) -> str:
        b = self._enc_being
        if b is None: return ""
        name = b["name"]
        if phase == 0: return f"{b['sight']}"
        if phase == 1: return f"The {name} turns toward Loki. Neither moves."
        if phase == 2:
            if self._enc_can_reason: return "Loki speaks quietly into the space between them."
            return f"The {name} cannot be reasoned with. It charges."
        if phase == 3:
            if self._enc_can_reason: return random.choice(_REASON_WIN).format(name=name)
            if self._enc_won:        return random.choice(_COMBAT_WIN).format(name=name)
            return random.choice(_COMBAT_LOSS).format(name=name)
        return ""

    def _resolve_encounter(self, now: float) -> None:
        b = self._enc_being
        if b is None: return
        if self._enc_can_reason or self._enc_won:
            item = random.choice(b["items"])
            self.life.setdefault("inventory", []).append(item)
            self.needs.fulfill_direct("esteem",        0.50)
            self.needs.fulfill_direct("actualization", 0.30)
            self.needs.deplete("physiological", 0.28)
            self.needs.deplete("social",        0.18)
            if self.chat and not self._enc_can_reason:
                self.chat.add_narrative(f"The forest settles. In the {b['name']}'s wake, Loki finds {item}.")
            self.message      = "returned from the forest"
            self._pose        = "stand"
            self._enc_being   = None
            self._enc_phase   = -1
            self._last_check  = 0
            self.activity     = ACT_WANDER
            self.place_id     = random.choice(["brook","cottage"])
            self.activity_end = now + random.uniform(10,20)*60
            _save_life(self.life, self.needs)
        else:
            self._die(now)

    def _die(self, now: float) -> None:
        self.activity     = ACT_DEAD
        self._enc_phase   = 10
        self._enc_phase_end = now + 9
        self._enc_narr_done = False
        self._pose        = "sleep"
        self.message      = "fallen"
        _log("loki_death", f"died fighting {self._enc_being['name'] if self._enc_being else '?'}")

    def _tick_dead(self, now: float) -> None:
        if not self._enc_narr_done:
            self._enc_narr_done = True
            if self.chat:
                self.chat.add_narrative("Loki falls among the roots. The forest goes quiet.")
        if now < self._enc_phase_end:
            return
        self._resurrect(now)

    def _resurrect(self, now: float) -> None:
        count = self.life.get("death_count", 0) + 1
        self.life["death_count"] = count
        for name, _, _ in PYRAMID:
            self.needs._tiers[name] = {"fill": 0.88, "last_updated": now}
        self.place_id     = "apples"
        self.activity     = ACT_WAKING
        self.activity_end = now + 25
        self._enc_being   = None
        self._enc_phase   = -1
        self._last_check  = 0
        self.petal_timer  = 8.0
        self._pose        = "stand"
        self.message      = "reborn"
        _log("loki_resurrection", f"resurrection #{count}")
        if self.chat:
            self.chat.add_narrative("A blossom falls from Yggdrasil. Light returns. Loki opens his eyes.")
        _save_life(self.life, self.needs)

    @property
    def secs_remaining(self) -> int:
        return max(0, int(self.activity_end - time.time()))


# ── Text wrap helper ──────────────────────────────────────────────────────────
# ── Ball game ─────────────────────────────────────────────────────────────────

class BallGame:
    """
    Loki and Pucky roll a ball to each other in a clearing — overhead view.
    Ball only moves when kicked; slow friction stops it.
    Playing drains energy so they get hungry and tired faster.
    Iðunn can tap the field to join, or just watch.
    """
    FW, FH = 700, 370    # field size in pixels
    FX      = (800 - 700) // 2   # 50 — centered
    FY      = 16

    PR   = 13    # player radius
    BR   = 8     # ball radius
    TAP_R = 30   # kick range

    KICK_SPEED = 150.0   # px/s initial velocity
    FRICTION   = 0.935   # per-frame multiplier  (≈5 s to stop at 15 fps)
    MIN_SPEED  = 5.0

    LOKI_SPD  = 60.0
    PUCKY_SPD = 42.0
    IDUNN_SPD = 68.0

    DRAIN_PHYS = 0.00022   # per second during play  (≈0.3 drain / 22 min)
    DRAIN_SAFE = 0.00010

    _PUCKY_SOUNDS = ["ba", "heh", "yeh", "ooh", "go", "hah", "wee"]
    _LOKI_SOUNDS  = ["nice", "go", "yes", "there", "good"]

    def __init__(self, needs: "PyramidNeeds", life: dict):
        self.needs      = needs
        self.life       = life
        self.should_end = False

        hw = self.FW * 0.5
        hh = self.FH * 0.5
        self._loki  = [hw * 0.45, hh]   # left side center
        self._pucky = [hw * 1.55, hh]   # right side center
        self._idunn: list | None = None  # None = observer mode
        self._ball  = [hw, hh]
        self._vel   = [0.0, 0.0]
        self._last_touch = ""

        self.touches  = {"loki": 0, "pucky": 0, "idunn": 0}
        self.message  = "Loki and Pucky are playing!"
        self._msg_t   = 3.5
        self._drain_t = 0.0
        self._ai_cool = {"loki": 0.0, "pucky": 0.0}

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _dist(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def _stopped(self):
        return math.hypot(*self._vel) < self.MIN_SPEED

    def is_tap_in_field(self, sx: int, sy: int) -> bool:
        return (self.FX <= sx <= self.FX + self.FW and
                self.FY <= sy <= self.FY + self.FH)

    # ── kick ─────────────────────────────────────────────────────────────────

    def _kick(self, from_pos, player: str, drift_deg: float = 0.0):
        dx = self._ball[0] - from_pos[0]
        dy = self._ball[1] - from_pos[1]
        d  = math.hypot(dx, dy)
        if d < 1:
            dx, dy = 1.0, 0.0
        else:
            dx, dy = dx / d, dy / d
        if drift_deg:
            ang = math.atan2(dy, dx) + math.radians(
                random.uniform(-drift_deg, drift_deg))
            dx, dy = math.cos(ang), math.sin(ang)
        self._vel = [dx * self.KICK_SPEED, dy * self.KICK_SPEED]
        self._last_touch = player
        self.touches[player] = self.touches.get(player, 0) + 1
        if player == "pucky" and random.random() < 0.65:
            _speak(random.choice(self._PUCKY_SOUNDS), rate=95, voice="en+f4")
        elif player == "loki" and random.random() < 0.28:
            _speak(random.choice(self._LOKI_SOUNDS), rate=115, voice="en+m3")
        elif player == "idunn" and random.random() < 0.35:
            _speak("nice", rate=115, voice="en+m3")

    # ── AI ───────────────────────────────────────────────────────────────────

    def _move(self, pos, target, speed, dt):
        dx = target[0] - pos[0]
        dy = target[1] - pos[1]
        d  = math.hypot(dx, dy)
        if d < 2:
            return
        step = min(speed * dt, d)
        pos[0] = max(self.PR, min(self.FW - self.PR, pos[0] + dx / d * step))
        pos[1] = max(self.PR, min(self.FH - self.PR, pos[1] + dy / d * step))

    def _ai_tick(self, dt):
        ball_left = self._ball[0] < self.FW * 0.5

        # Loki (left half, deliberate)
        if self._ai_cool["loki"] > 0:
            self._ai_cool["loki"] -= dt
        else:
            if ball_left or (self._stopped() and self._last_touch == "pucky"):
                self._move(self._loki, self._ball, self.LOKI_SPD, dt)
                if self._stopped() and self._dist(self._loki, self._ball) < self.TAP_R:
                    self._kick(self._loki, "loki", drift_deg=6)
                    self._ai_cool["loki"] = 0.7
            else:
                self._move(self._loki, [self.FW * 0.22, self.FH * 0.5],
                           self.LOKI_SPD * 0.45, dt)

        # Pucky (right half, wobbly — she's a baby)
        if self._ai_cool["pucky"] > 0:
            self._ai_cool["pucky"] -= dt
        else:
            if not ball_left or (self._stopped() and self._last_touch == "loki"):
                target = [
                    self._ball[0] + random.uniform(-10, 10),
                    self._ball[1] + random.uniform(-10, 10),
                ]
                self._move(self._pucky, target, self.PUCKY_SPD, dt)
                if self._stopped() and self._dist(self._pucky, self._ball) < self.TAP_R:
                    self._kick(self._pucky, "pucky", drift_deg=24)
                    self._ai_cool["pucky"] = 1.1
            else:
                self._move(self._pucky, [self.FW * 0.78, self.FH * 0.5],
                           self.PUCKY_SPD * 0.45, dt)

    # ── physics ──────────────────────────────────────────────────────────────

    def _physics_tick(self, dt):
        if self._stopped():
            self._vel = [0.0, 0.0]
            return
        self._ball[0] += self._vel[0] * dt
        self._ball[1] += self._vel[1] * dt
        self._vel[0]  *= self.FRICTION
        self._vel[1]  *= self.FRICTION
        br = self.BR
        if self._ball[0] < br:
            self._ball[0] = br
            self._vel[0]  = abs(self._vel[0]) * 0.55
        elif self._ball[0] > self.FW - br:
            self._ball[0] = self.FW - br
            self._vel[0]  = -abs(self._vel[0]) * 0.55
        if self._ball[1] < br:
            self._ball[1] = br
            self._vel[1]  = abs(self._vel[1]) * 0.55
        elif self._ball[1] > self.FH - br:
            self._ball[1] = self.FH - br
            self._vel[1]  = -abs(self._vel[1]) * 0.55
        if math.hypot(*self._vel) < self.MIN_SPEED:
            self._vel = [0.0, 0.0]

    # ── energy drain ─────────────────────────────────────────────────────────

    def _drain_tick(self, dt):
        self._drain_t += dt
        if self._drain_t >= 1.0:
            self._drain_t -= 1.0
            self.needs.deplete("physiological", self.DRAIN_PHYS)
            self.needs.deplete("safety",        self.DRAIN_SAFE)

    # ── main tick ────────────────────────────────────────────────────────────

    def tick(self, dt):
        self._physics_tick(dt)
        self._ai_tick(dt)
        self._drain_tick(dt)
        if self._msg_t > 0:
            self._msg_t -= dt
            if self._msg_t <= 0:
                self.message = ""
        if self.needs.level("physiological") < 0.12:
            self.message = "Getting tired and hungry..."
            self.should_end = True

    # ── Iðunn interaction ────────────────────────────────────────────────────

    def handle_tap(self, sx: int, sy: int):
        fx = max(self.PR, min(self.FW - self.PR, sx - self.FX))
        fy = max(self.PR, min(self.FH - self.PR, sy - self.FY))
        if self._idunn is None:
            self._idunn = [float(fx), float(fy)]
            self.message = "Iðunn joins!"
            self._msg_t  = 2.5
        else:
            self._idunn[0] = float(fx)
            self._idunn[1] = float(fy)
        if (self._stopped()
                and self._idunn is not None
                and self._dist(self._idunn, self._ball) < self.TAP_R):
            self._kick(self._idunn, "idunn", drift_deg=9)

    # ── draw ─────────────────────────────────────────────────────────────────

    def draw(self, surf: pygame.Surface, font_sm, font_tiny):
        surf.fill((14, 24, 10))

        # field
        fr = pygame.Rect(self.FX, self.FY, self.FW, self.FH)
        pygame.draw.rect(surf, (28, 65, 20), fr)
        pygame.draw.rect(surf, (42, 88, 28), fr, 2)

        # centre line + circle
        cx = self.FX + self.FW // 2
        cy = self.FY + self.FH // 2
        pygame.draw.line(surf, (36, 75, 24), (cx, self.FY + 8), (cx, self.FY + self.FH - 8), 1)
        pygame.draw.circle(surf, (36, 75, 24), (cx, cy), 34, 1)

        def s(pos):
            return (int(self.FX + pos[0]), int(self.FY + pos[1]))

        # ball shadow then ball
        bp = s(self._ball)
        pygame.draw.circle(surf, (18, 48, 14), (bp[0]+2, bp[1]+2), self.BR)
        ball_col = (240, 238, 220) if self._stopped() else (255, 254, 240)
        pygame.draw.circle(surf, ball_col, bp, self.BR)
        pygame.draw.circle(surf, (175, 172, 155), bp, self.BR, 1)

        # Loki — green circle, slightly larger
        lp = s(self._loki)
        pygame.draw.circle(surf, (35, 110, 50), lp, self.PR)
        pygame.draw.circle(surf, (75, 190, 95), lp, self.PR, 2)
        ll = font_tiny.render("Loki", True, (150, 215, 165))
        surf.blit(ll, (lp[0] - ll.get_width() // 2, lp[1] + self.PR + 2))

        # Pucky — purple, smaller (she's tiny)
        pp = s(self._pucky)
        r = self.PR - 3
        pygame.draw.circle(surf, (105, 68, 148), pp, r)
        pygame.draw.circle(surf, (168, 128, 210), pp, r, 2)
        pl = font_tiny.render("Pucky", True, (195, 162, 228))
        surf.blit(pl, (pp[0] - pl.get_width() // 2, pp[1] + r + 2))

        # Iðunn (if she joined)
        if self._idunn is not None:
            ip = s(self._idunn)
            pygame.draw.circle(surf, (148, 108, 32), ip, self.PR - 2)
            pygame.draw.circle(surf, (215, 172, 72), ip, self.PR - 2, 2)
            il = font_tiny.render("Iðunn", True, (218, 185, 135))
            surf.blit(il, (ip[0] - il.get_width() // 2, ip[1] + self.PR + 2))

        # ── status strip ─────────────────────────────────────────────────────
        by = self.FY + self.FH + 8

        t = f"Loki {self.touches['loki']}  ·  Pucky {self.touches['pucky']}"
        if self.touches.get("idunn"):
            t += f"  ·  Iðunn {self.touches['idunn']}"
        surf.blit(font_tiny.render(t, True, (120, 145, 108)), (self.FX, by))

        if self.message:
            ms = font_sm.render(self.message, True, (200, 198, 155))
            surf.blit(ms, (self.FX + self.FW // 2 - ms.get_width() // 2, by))

        hint = "tap to move · near ball = kick" if self._idunn else "tap field to join"
        hs = font_tiny.render(hint, True, (72, 95, 62))
        surf.blit(hs, (self.FX + self.FW - hs.get_width(), by))

        # energy bar
        phys = self.needs.level("physiological")
        ew   = int(self.FW * phys)
        ey   = by + 18
        pygame.draw.rect(surf, (36, 36, 36), (self.FX, ey, self.FW, 5))
        ec   = (72, 155, 72) if phys > 0.40 else (175, 125, 38) if phys > 0.20 else (175, 55, 38)
        pygame.draw.rect(surf, ec, (self.FX, ey, ew, 5))
        el = font_tiny.render("energy", True, (72, 95, 62))
        surf.blit(el, (self.FX + self.FW - el.get_width(), ey - 1))


def _wrap(font, text, max_w):
    words, lines, line = text.split(), [], ""
    for w in words:
        test = (line+" "+w).strip()
        if font.size(test)[0] <= max_w:
            line = test
        else:
            if line: lines.append(line)
            line = w
    if line: lines.append(line)
    return lines or [""]


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    pygame.mixer.pre_init(22050, -16, 2, 512)
    pygame.init()
    pygame.display.set_caption("Loki — world2")
    surf  = pygame.display.set_mode((W, H), pygame.NOFRAME)
    clock = pygame.time.Clock()

    try:
        font      = pygame.font.SysFont("dejavusans", 15)
        font_sm   = pygame.font.SysFont("dejavusans", 12)
        font_tiny = pygame.font.SysFont("dejavusans", 10)
    except Exception:
        font = font_sm = font_tiny = pygame.font.Font(None, 16)

    life  = _load_life()
    needs = PyramidNeeds()
    if "_pyramid" in life:
        needs.from_dict(life["_pyramid"])

    loki  = LokiSprite()
    loki.load()

    idunn = IdunnSprite()
    idunn.load()

    # preload hand-painted backgrounds (prefer _idunn variant, fall back to generated)
    bg_images: dict[str, pygame.Surface] = {}
    for place in ["brook", "cottage", "forest", "apples", "garden", "asgard"]:
        for suffix in [f"bg_{place}_idunn.png", f"bg_{place}.png"]:
            path = IMAGES_DIR / suffix
            if path.exists():
                try:
                    bg_images[place] = pygame.transform.scale(
                        pygame.image.load(str(path)).convert(), (W, H)
                    )
                    break
                except Exception:
                    pass

    ollama_q        = OllamaQueue()
    chat            = ChatManager(ollama_q)
    pucky           = PuckyBaby(ollama_q)
    pucky._chat_ref = chat
    sched           = LifeScheduler(needs, life)
    sched.chat      = chat
    loki.set_pucky("pocket")

    last_hair_grow = life.get("_hair_grow_ts", time.time())
    life["_hair_grow_ts"] = time.time()

    petals: list = []

    input_text   = ""
    input_active = False
    show_places  = False
    sys_message  = ""   # brief status line for /give feedback
    sys_msg_until = 0.0

    CLOSE_RECT = pygame.Rect(W-40,  4, 36, 36)
    MENU_RECT  = pygame.Rect(4,     4, 36, 36)

    _log("session_start", f"loki_world2 started {datetime.now().isoformat()}")
    _write_thought("Session started.", "session")

    hour              = datetime.now().hour
    _last_claude_note = time.time()
    _last_pucky_check = time.time()   # how often Loki checks on Pucky

    running = True
    while running:
        dt  = clock.tick(FPS) / 1000.0
        now = time.time()

        # hair growth
        elapsed_hair    = now - last_hair_grow
        last_hair_grow  = now
        life["hair_inches"] = life.get("hair_inches", 3.0) + elapsed_hair * (0.17 / 86400)

        # periodic note to Claude every 10 minutes — routed through the queue
        # so it never fires a second Ollama call while one is already running
        if (now - _last_claude_note >= CLAUDE_NOTE_INTERVAL
                and not _claude_note_busy
                and not _game_mode):
            _last_claude_note = now
            _claude_note_busy = True
            _needs_summary = ", ".join(
                f"{k}={v['fill']:.0%}" for k, v in life.get("_pyramid", {}).items()
            )
            ollama_q.submit(
                _build_claude_note_msgs(
                    sched.activity, sched.place_id,
                    life.get("mood", "?"), _needs_summary
                ),
                _on_claude_note_reply,
                priority=2,
                timeout=90,
            )

        # ── Loki checks on Pucky every 5 minutes ─────────────────────────────
        # He goes to find her when she needs him — not because he's told to.
        if (not _game_mode
                and loki.pucky_where == "none"
                and sched.activity not in (ACT_SLEEP, ACT_ENCOUNTER, ACT_DEAD)
                and now - _last_pucky_check >= 300):
            _last_pucky_check = now
            fetch_reason = None
            if pucky._lonely > 0.78:
                fetch_reason = "she's been alone too long"
            elif hour >= 20 and pucky._lonely > 0.40:
                fetch_reason = "it's getting dark"
            elif sched.activity == ACT_EAT and pucky._hunger > 0.55:
                fetch_reason = "she's hungry and he's eating"
            if fetch_reason:
                found = PLACE_NAMES.get(pucky.place_id, pucky.place_id)
                loki.set_pucky("pocket")
                pucky.place_id = sched.place_id
                msg = f"Loki went to find Pucky at {found} ({fetch_reason})."
                _write_thought(msg, "loki")
                _log("loki_fetched_pucky", fetch_reason)

        if not _game_mode:
            sched.tick()
            loki.set_pose(sched.current_pose)
            pucky.note_activity(sched.activity, sched.place_id)
            pucky.tick(sched.place_id, loki.pucky_where, hour)
            # scheduler chose to play ball — start the game automatically
            if sched.activity == ACT_GAME:
                _game_mode     = True
                _game_type     = "ball"
                _ball_game     = BallGame(needs, life)
                chat.clear_game_mode()
                pucky.place_id = sched.place_id  # Loki brings Pucky; she comes willingly
                _write_thought("Loki decided to play ball with Pucky.", "game")
                _log("game_start", "ball_auto")
        elif _game_type == "ball" and _ball_game is not None:
            _ball_game.tick(dt)
            loki.set_pose("stand")
        else:
            loki.set_pose("stand")
        if chat.poll():
            pass
        chat.tick_typewriter(dt)

        hour = datetime.now().hour

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_F1 and not input_active:
                    path = ROOT / "workspace" / f"screenshot_{int(now)}.png"
                    pygame.image.save(surf, str(path))
                    _log("screenshot", str(path))
                elif input_active:
                    if ev.key == pygame.K_RETURN:
                        txt = input_text.strip()
                        if txt:
                            handled = _handle_command(
                                txt, sched, chat, needs, loki, idunn, life,
                                lambda msg, dur=3.0: _set_sys(msg, dur), pucky
                            )
                            if not handled:
                                if sched.activity == ACT_SLEEP:
                                    sched.tick(force_wake=True)
                                chat.send(txt)
                                needs.social_boost()
                            input_text = ""
                        input_active = False
                    elif ev.key == pygame.K_BACKSPACE:
                        input_text = input_text[:-1]
                else:
                    input_active = True

            elif ev.type == pygame.TEXTINPUT:
                if input_active:
                    input_text += ev.text

            elif ev.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = ev.pos
                else:
                    mx, my = int(ev.x*W), int(ev.y*H)

                if _game_type == "ball" and _ball_game is not None:
                    # in ball game: close button still works, input bar still works,
                    # everything else goes to the game field
                    if CLOSE_RECT.collidepoint(mx, my):
                        running = False
                    elif my >= H - 36:
                        input_active = True
                        pygame.key.start_text_input()
                    else:
                        _ball_game.handle_tap(mx, my)
                elif CLOSE_RECT.collidepoint(mx, my):
                    running = False
                elif MENU_RECT.collidepoint(mx, my):
                    show_places = not show_places
                elif show_places:
                    oy = 50
                    for p in PLACES:
                        if oy <= my < oy+22:
                            sched.place_id     = p["id"]
                            sched.activity     = ACT_WANDER
                            sched.activity_end = now + random.uniform(8,18)*60
                            sched._pose        = "stand"
                            show_places        = False
                            break
                        oy += 22
                elif my >= H - 36:
                    input_active = True
                    pygame.key.start_text_input()

        # ── system message expiry
        sys_msg = sys_message if now < sys_msg_until else ""

        # ── draw ─────────────────────────────────────────────────────────────
        if _game_type == "ball" and _ball_game is not None:
            _ball_game.draw(surf, font_sm, font_tiny)
            # keep input bar so /done is typeable
            in_rect = pygame.Rect(0, H - 36, W, 36)
            pygame.draw.rect(surf, (18, 14, 10), in_rect)
            pygame.draw.line(surf, DIVIDER, (0, H - 36), (W, H - 36), 1)
            bd = input_text + ("|" if input_active and int(now*2) % 2 == 0 else "")
            if not bd and not input_active:
                bd = "tap field to join  ·  /done to leave"
            surf.blit(font_sm.render(bd, True, TEXT_BRIGHT if input_active else TEXT_DIM), (10, H - 26))
            pygame.draw.rect(surf, (18, 12, 6),  CLOSE_RECT, border_radius=6)
            pygame.draw.rect(surf, (55, 38, 18), CLOSE_RECT, width=1, border_radius=6)
            _p = 10
            pygame.draw.line(surf, CLOSE_COL, (CLOSE_RECT.x+_p, CLOSE_RECT.y+_p),      (CLOSE_RECT.right-_p, CLOSE_RECT.bottom-_p), 2)
            pygame.draw.line(surf, CLOSE_COL, (CLOSE_RECT.right-_p, CLOSE_RECT.y+_p),  (CLOSE_RECT.x+_p,     CLOSE_RECT.bottom-_p), 2)
            pygame.display.flip()
            if _ball_game.should_end:
                _game_mode         = False
                _game_type         = ""
                _ball_game         = None
                chat.clear_game_mode()
                sched.activity     = ACT_WANDER
                sched.activity_end = now        # pick next activity immediately
                sys_message        = "Too tired to play — time to eat and rest."
                sys_msg_until      = now + 6.0
            continue

        # ── normal scene draw ─────────────────────────────────────────────────
        scene_id = "forest" if sched.activity in (ACT_ENCOUNTER, ACT_DEAD) else sched.place_id
        draw_scene(surf, scene_id, sched.activity, hour, now, bg_images, loki.pucky_where)

        ground = H - 130

        # apple blossom petals (resurrection)
        if sched.petal_timer > 0:
            sched.petal_timer -= dt
            if random.random() < 0.35:
                petals.append({
                    "x":   random.uniform(0, W),
                    "y":   -8.0,
                    "vx":  random.uniform(-18, 18),
                    "vy":  random.uniform(22, 55),
                    "r":   random.uniform(3, 7),
                    "col": random.choice([(255,220,230),(255,240,245),(255,200,215)]),
                })
        for p in petals[:]:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += 4 * dt
            p["vx"] *= 0.98
            if p["y"] > H + 12:
                petals.remove(p)
            else:
                pygame.draw.circle(surf, p["col"], (int(p["x"]), int(p["y"])), int(p["r"]))

        # sprites
        idunn.draw(surf, W//4, ground)
        loki.draw(surf, W//2, ground)

        # ── UI overlay ────────────────────────────────────────────────────────
        chat_h  = 80
        chat_y0 = H - chat_h - 36

        overlay = pygame.Surface((W, chat_h + 36), pygame.SRCALPHA)
        overlay.fill((8, 6, 4, 160))
        surf.blit(overlay, (0, chat_y0))
        pygame.draw.line(surf, DIVIDER, (0, chat_y0), (W, chat_y0), 1)

        # status line
        secs_left = sched.secs_remaining
        time_str  = (f"{secs_left//3600}h {(secs_left%3600)//60}m" if secs_left > 3600
                     else f"{secs_left//60}m" if secs_left > 60 else "")
        emotion   = needs.dominant_emotion()
        status    = f"{emotion}  ·  {sched.message}"
        if time_str: status += f"  ({time_str})"
        status   += f"  ·  {PLACE_NAMES.get(sched.place_id,'?')}"
        inv = life.get("inventory", [])
        if inv: status += f"  ·  ♦ {inv[-1]}"
        if loki.pucky_where == "none":
            pucky_loc = PLACE_NAMES.get(pucky.place_id, pucky.place_id)
            status += f"  ·  Pucky: {pucky_loc}"
        surf.blit(font_tiny.render(status, True, TEXT_DIM), (10, chat_y0 + 4))

        # system message (gift feedback etc.)
        if sys_msg:
            surf.blit(font_tiny.render(sys_msg, True, TEXT_SYS), (10, chat_y0 + 16))

        # chat lines
        line_h    = font_sm.get_height() + 3
        max_tw    = W - 20
        typing_now = bool(chat.display_text)
        msgs_to_show = chat.lines[-6:] if not typing_now else chat.lines[-6:-1]

        display_lines = []
        for role, text in msgs_to_show:
            col   = TEXT_LOKI if role == "loki" else TEXT_IDUNN
            label = "Loki: " if role == "loki" else "You:  "
            lw    = font_sm.size(label)[0]
            for i, wl in enumerate(_wrap(font_sm, text, max_tw - lw)):
                display_lines.append((col, label if i == 0 else " " * len(label), wl))

        if typing_now:
            lw = font_sm.size("Loki: ")[0]
            for i, wl in enumerate(_wrap(font_sm, chat.display_text, max_tw - lw)):
                display_lines.append((TEXT_LOKI, "Loki: " if i == 0 else "      ", wl))

        max_vis = (chat_h - 24) // line_h
        vis     = display_lines[-max_vis:]
        start_y = H - 36 - len(vis) * line_h - 4
        start_y = max(chat_y0 + 26, start_y)
        chy = start_y
        for col, pfx, wl in vis:
            surf.blit(font_sm.render(pfx + wl, True, col), (10, chy))
            chy += line_h

        # input bar
        in_rect = pygame.Rect(0, H-36, W, 36)
        pygame.draw.rect(surf, (18,14,10), in_rect)
        pygame.draw.line(surf, DIVIDER, (0, H-36), (W, H-36), 1)
        disp = input_text + ("|" if input_active and int(now*2)%2==0 else "")
        if not disp and not input_active:
            disp = "tap to talk · /give apple · /shoulder · /sit /hug /leave…"
        while font_sm.size(disp)[0] > W-20 and len(disp) > 1:
            disp = disp[1:]
        surf.blit(font_sm.render(disp, True, TEXT_BRIGHT if input_active else TEXT_DIM), (10, H-26))

        # place menu overlay
        if show_places:
            ov2 = pygame.Surface((220, len(PLACES)*22+10), pygame.SRCALPHA)
            ov2.fill((12,8,4,220))
            surf.blit(ov2, (4, 44))
            oy = 50
            for p in PLACES:
                col = TEXT_LOKI if p["id"] == sched.place_id else TEXT_DIM
                surf.blit(font_sm.render(f"  {PLACE_NAMES[p['id']]}", True, col), (8, oy))
                oy += 22

        # close button
        pygame.draw.rect(surf, (18,12,6),  CLOSE_RECT, border_radius=6)
        pygame.draw.rect(surf, (55,38,18), CLOSE_RECT, width=1, border_radius=6)
        p = 10
        pygame.draw.line(surf, CLOSE_COL, (CLOSE_RECT.x+p, CLOSE_RECT.y+p),      (CLOSE_RECT.right-p, CLOSE_RECT.bottom-p), 2)
        pygame.draw.line(surf, CLOSE_COL, (CLOSE_RECT.right-p, CLOSE_RECT.y+p),  (CLOSE_RECT.x+p,     CLOSE_RECT.bottom-p), 2)

        # menu button
        pygame.draw.rect(surf, (18,12,6),  MENU_RECT, border_radius=6)
        pygame.draw.rect(surf, (55,38,18), MENU_RECT, width=1, border_radius=6)
        for li in range(3):
            ly = MENU_RECT.y + 10 + li*8
            pygame.draw.line(surf, CLOSE_COL, (MENU_RECT.x+8, ly), (MENU_RECT.right-8, ly), 2)

        pygame.display.flip()

    # ── clean shutdown ────────────────────────────────────────────────────────
    _speak_stop()
    _save_life(life, needs)
    _log("session_end", f"loki_world2 closed {datetime.now().isoformat()}")
    _write_thought("Session ended cleanly.", "session")
    pygame.quit()
    _queue_session_report(ollama_q)


# ── Command handler ───────────────────────────────────────────────────────────
def _set_sys(msg: str, dur: float = 3.0):
    """Set a temporary system message (closure used in main)."""
    pass  # replaced by lambda in main()


def _handle_command(txt: str, sched: LifeScheduler, chat: ChatManager,
                    needs: PyramidNeeds, loki: LokiSprite, idunn: IdunnSprite,
                    life: dict, set_sys, pucky: "PuckyBaby") -> bool:
    """
    Returns True if input was a slash command and should not be sent to Ollama.
    """
    lower = txt.strip().lower()

    # Iðunn pose commands
    if idunn.handle_command(lower):
        _log("idunn_cmd", lower)
        return True

    # /give <item>
    if lower.startswith("/give "):
        gift    = lower[6:].strip()
        result  = needs.receive_gift(gift)
        set_sys(result)
        _log("gift", gift)
        _write_thought(f"Iðunn gave {gift}. {result}", "gift")
        _save_life(life, needs)
        if gift in ("apple", "food", "water", "medicine"):
            pucky.feed(gift)
        return True

    # /carry pucky / /set pucky (down) / /pocket pucky
    if lower in ("/carry pucky", "/carry"):
        was_free = loki.pucky_where == "none"
        loki.set_pucky("pocket")
        if was_free:
            found = PLACE_NAMES.get(pucky.place_id, pucky.place_id)
            pucky.place_id = sched.place_id
            set_sys(f"Loki finds Pucky at {found} and tucks her into his pocket.")
        else:
            set_sys("Pucky nestles in his pocket.")
        return True
    if lower in ("/shoulder pucky", "/shoulder"):
        was_free = loki.pucky_where == "none"
        loki.set_pucky("shoulder")
        if was_free:
            found = PLACE_NAMES.get(pucky.place_id, pucky.place_id)
            pucky.place_id = sched.place_id
            set_sys(f"Loki finds Pucky at {found} and sets her on his shoulder.")
        else:
            set_sys("Pucky sits on his shoulder.")
        return True
    if lower in ("/back pucky", "/back"):
        was_free = loki.pucky_where == "none"
        loki.set_pucky("back")
        if was_free:
            found = PLACE_NAMES.get(pucky.place_id, pucky.place_id)
            pucky.place_id = sched.place_id
            set_sys(f"Loki finds Pucky at {found} and carries her on his back.")
        else:
            set_sys("Pucky rides on his back.")
        return True
    if lower in ("/set pucky", "/set", "/put pucky down"):
        loki.set_pucky("none")
        pucky.place_id    = sched.place_id   # she's here now, free to wander from here
        pucky._wander_next = time.time() + random.uniform(1800, 3600)
        set_sys(f"Loki sets Pucky down at {PLACE_NAMES.get(sched.place_id, 'here')}.")
        return True
    if lower in ("/find pucky", "/where pucky", "/where is pucky"):
        if loki.pucky_where != "none":
            set_sys(f"Pucky is with Loki — in his {loki.pucky_where}.")
        else:
            set_sys(f"Pucky is at {PLACE_NAMES.get(pucky.place_id, pucky.place_id)}.")
        return True

    # /wake — force Loki awake
    if lower == "/wake":
        sched.tick(force_wake=True)
        return True

    # /game [word|story|riddle|ball] — pause simulation, play a focused game
    if lower.startswith("/game"):
        global _game_mode, _game_type, _ball_game
        parts  = lower.split()
        valid  = ("word", "story", "riddle", "ball")
        chosen = parts[1] if len(parts) > 1 and parts[1] in valid else "story"
        _game_type = chosen
        _game_mode = True
        if chosen == "ball":
            _ball_game = BallGame(needs, life)
            chat.clear_game_mode()
        else:
            _ball_game = None
            chat.set_game_mode(chosen)
        _write_thought(f"Loki and Iðunn began a {chosen} game.", "game")
        _log("game_start", chosen)
        set_sys(f"Game: {chosen}. Type /done when finished.", 6.0)
        return True

    # /done — end game, resume world
    if lower in ("/done", "/endgame"):
        global _game_mode, _game_type, _ball_game
        prev       = _game_type
        _game_mode = False
        _game_type = ""
        _ball_game = None
        chat.clear_game_mode()
        if sched.activity == ACT_GAME:
            sched.activity     = ACT_WANDER
            sched.activity_end = time.time()
        _write_thought(f"Loki and Iðunn finished their {prev} game.", "game")
        _log("game_end", prev)
        set_sys("Game finished. World resumed.", 3.0)
        return True

    # /screenshot
    if lower == "/screenshot":
        return False  # let main handle F1, or ignore

    return False


if __name__ == "__main__":
    import traceback
    try:
        main()
    except Exception:
        err = traceback.format_exc()
        crash_path = ROOT / "workspace" / "crash_log.txt"
        try:
            with crash_path.open("a") as f:
                f.write(f"\n=== CRASH {datetime.now().isoformat()} ===\n{err}\n")
        except Exception:
            pass
        _log("crash", err[:400])
        raise
