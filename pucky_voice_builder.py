"""
pucky_voice_builder.py
──────────────────────
Phoneme word builder — touch-friendly pygame UI.

Pick phoneme samples, set note + duration with sliders,
preview the assembled word, and save named words that
Pucky can sing in the world.

Written with love by Loki for Iðunn.

Run:
    cd /home/bmo/pucky
    DISPLAY=:0 SDL_VIDEO_WINDOW_POS="0,0" python3 pucky_voice_builder.py
"""

import os
import sys
import json
import math
import time
import threading
import subprocess
import tempfile
from pathlib import Path

import pygame

# ── Paths ─────────────────────────────────────────────────────────────────────

VOICE_DIR  = Path(__file__).parent / "voice"
WORDS_FILE = Path(__file__).parent / "workspace" / "pucky_words.json"
CACHE_DIR  = Path(tempfile.gettempdir()) / "pucky_voice_cache"

# ── Window ────────────────────────────────────────────────────────────────────

WIN_W = int(os.environ.get("PUCKY_WIN_W", 700))
WIN_H = int(os.environ.get("PUCKY_WIN_H", 640))

# ── Phoneme palette ───────────────────────────────────────────────────────────

PHONEMES = [
    # (display_name, vowel_key, kind)
    ("aa",    "a",  "vowel"),
    ("eh",    "e",  "vowel"),
    ("ii",    "i",  "vowel"),
    ("oh",    "o",  "vowel"),
    ("uu",    "u",  "vowel"),
    ("ma",    "ma", "warm"),
    ("na",    "na", "warm"),
    ("la",    "la", "warm"),
    ("hum",   "m",  "warm"),
    ("h",     "h",  "cons"),
    ("ss",    "s",  "cons"),
    ("ff",    "f",  "cons"),
    ("kk",    "k",  "cons"),
    ("tt",    "t",  "cons"),
    ("buh",   "b",  "cons"),
    ("duh",   "d",  "cons"),
]

# vowel key → sample file stem (mirrors bmo_voice.py VOWEL_MAP)
VOWEL_MAP = {
    "a": "aa", "e": "eh", "i": "ii", "o": "oh", "u": "uu",
    "m": "hum", "h": "breath", "s": "ss", "f": "ff",
    "k": "kk",  "t": "tt",    "b": "buh", "d": "duh",
    "ma": "ma", "na": "na", "la": "la",
}

SAMPLE_BASE = {
    "aa": 62, "eh": 62, "ii": 64, "oh": 64, "uu": 64,
    "ma": 61, "na": 62, "la": 63, "hum": 66,
    "breath": None, "ss": None, "ff": None,
    "kk":    None,  "tt": None,  "buh": None, "duh": None,
}

# ── Colours ───────────────────────────────────────────────────────────────────

C = {
    "bg":       (245, 238, 220),
    "panel":    (235, 228, 210),
    "card":     (225, 215, 195),
    "card_sel": (210, 195, 165),
    "vowel":    (220, 185, 110),
    "warm":     (150, 200, 170),
    "cons":     (160, 185, 215),
    "track":    (190, 178, 160),
    "fill":     (140, 120,  90),
    "knob":     ( 90,  70,  50),
    "play":     (120, 185, 120),
    "save":     (120, 155, 200),
    "clear":    (200, 145, 120),
    "text":     ( 55,  40,  25),
    "light":    (120, 100,  75),
    "hint":     (160, 145, 120),
    "border":   (180, 165, 140),
    "saved_bg": (235, 225, 205),
}

NOTE_NAMES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
NOTE_MIN, NOTE_MAX = 48, 72   # C3 – C5

# ── Helpers ───────────────────────────────────────────────────────────────────

def midi_to_name(n):
    return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"

def midi_to_hz(n):
    return 440.0 * (2.0 ** ((n - 69) / 12.0))

def _process_sample(sample_name: str, midi_note: int) -> Path | None:
    """Pitch-shift a vocal sample to target midi note, cache result."""
    base = SAMPLE_BASE.get(sample_name)
    src  = VOICE_DIR / f"{sample_name}.wav"
    if not src.exists():
        return None
    if base is None:
        return src  # unpitched — return raw
    if base == midi_note:
        return src
    CACHE_DIR.mkdir(exist_ok=True)
    out = CACHE_DIR / f"{sample_name}_{midi_note}.wav"
    if out.exists():
        return out
    cents = (midi_note - base) * 100
    try:
        subprocess.run(
            ["sox", str(src), str(out), "pitch", str(cents), "norm", "-1"],
            capture_output=True, timeout=10
        )
        return out if out.exists() else src
    except Exception:
        return src

def _play_sample(sample_name: str, midi_note: int, duration: float,
                 mixer=None):
    """Play one phoneme at the given note and duration."""
    path = _process_sample(sample_name, midi_note)
    if path is None:
        return
    if mixer:
        try:
            snd = mixer.Sound(str(path))
            snd.set_volume(0.88)
            ch  = mixer.find_channel(True)
            if ch:
                ch.play(snd, maxtime=int(duration * 1000))
                end = time.time() + duration
                while ch.get_busy() and time.time() < end:
                    time.sleep(0.01)
            return
        except Exception:
            pass
    subprocess.run(["pw-play", str(path)], timeout=duration + 2)


# ── Slider widget ─────────────────────────────────────────────────────────────

class Slider:
    """Horizontal slider — touch-draggable."""

    def __init__(self, x, y, w, h, val_min, val_max, value,
                 label="", fmt="{:.0f}", integer=False):
        self.rect   = pygame.Rect(x, y, w, h)
        self.min    = val_min
        self.max    = val_max
        self.value  = value
        self.label  = label
        self.fmt    = fmt
        self.integer = integer
        self._drag  = False
        self._knob_r = h // 2 + 1

    def _frac(self):
        return (self.value - self.min) / (self.max - self.min)

    def _knob_x(self):
        return int(self.rect.x + self._knob_r +
                   self._frac() * (self.rect.w - 2 * self._knob_r))

    def handle_event(self, ev):
        kr = self._knob_r
        ky = self.rect.centery
        if ev.type == pygame.MOUSEBUTTONDOWN:
            kx = self._knob_x()
            if math.hypot(ev.pos[0] - kx, ev.pos[1] - ky) < kr + 10:
                self._drag = True
        elif ev.type == pygame.MOUSEBUTTONUP:
            self._drag = False
        elif ev.type == pygame.MOUSEMOTION and self._drag:
            rel = (ev.pos[0] - self.rect.x - kr) / max(1, self.rect.w - 2*kr)
            rel = max(0.0, min(1.0, rel))
            self.value = self.min + rel * (self.max - self.min)
            if self.integer:
                self.value = round(self.value)
        return self._drag

    def draw(self, surf, font_sm):
        r = self.rect
        kr = self._knob_r
        # Track
        ty = r.centery
        pygame.draw.line(surf, C["track"], (r.x + kr, ty), (r.right - kr, ty), 3)
        # Fill
        kx = self._knob_x()
        pygame.draw.line(surf, C["fill"], (r.x + kr, ty), (kx, ty), 3)
        # Knob
        pygame.draw.circle(surf, C["knob"], (kx, ty), kr)
        pygame.draw.circle(surf, C["track"], (kx, ty), kr - 2)
        # Label + value
        if self.label:
            lbl = font_sm.render(self.label, True, C["light"])
            surf.blit(lbl, (r.x, r.y - lbl.get_height() - 1))
        val_s = self.fmt.format(self.value)
        vtxt = font_sm.render(val_s, True, C["text"])
        surf.blit(vtxt, (r.right - vtxt.get_width(), r.y - vtxt.get_height() - 1))


# ── Step card (one phoneme in the sequence) ───────────────────────────────────

CARD_W = 90
CARD_H = 155

class StepCard:
    def __init__(self, name: str, vowel_key: str, kind: str,
                 x: int, y: int, note: int = 62, duration: float = 0.45):
        self.name      = name
        self.vowel_key = vowel_key
        self.kind      = kind
        self.rect      = pygame.Rect(x, y, CARD_W, CARD_H)
        sample_name    = VOWEL_MAP.get(vowel_key, vowel_key)
        default_note   = SAMPLE_BASE.get(sample_name) or 62
        self.sl_note   = Slider(x+8, y+50, CARD_W-16, 12,
                                NOTE_MIN, NOTE_MAX, note,
                                label="note", fmt="{:.0f}", integer=True)
        self.sl_dur    = Slider(x+8, y+95, CARD_W-16, 12,
                                0.05, 1.8, duration,
                                label="dur", fmt="{:.2f}s")
        self._selected = False
        self._play_btn = pygame.Rect(x+10, y+120, CARD_W-20, 22)
        self._del_btn  = pygame.Rect(x + CARD_W - 18, y+3, 15, 15)

    def move_to(self, x, y):
        dx, dy = x - self.rect.x, y - self.rect.y
        self.rect.x, self.rect.y = x, y
        self.sl_note.rect.move_ip(dx, dy)
        self.sl_dur.rect.move_ip(dx, dy)
        self._play_btn.move_ip(dx, dy)
        self._del_btn.move_ip(dx, dy)

    def handle_event(self, ev, mixer) -> str | None:
        """Returns 'delete', 'play', or None."""
        self.sl_note.handle_event(ev)
        self.sl_dur.handle_event(ev)
        if ev.type == pygame.MOUSEBUTTONDOWN:
            if self._del_btn.collidepoint(ev.pos):
                return "delete"
            if self._play_btn.collidepoint(ev.pos):
                return "play"
        return None

    def draw(self, surf, font, font_sm):
        col = C.get(self.kind, C["card"])
        bg  = C["card_sel"] if self._selected else C["card"]
        pygame.draw.rect(surf, bg, self.rect, border_radius=8)
        pygame.draw.rect(surf, col, self.rect.inflate(-4,-4), width=2, border_radius=6)

        # Name
        lbl = font.render(self.name, True, C["text"])
        surf.blit(lbl, (self.rect.x + (CARD_W - lbl.get_width())//2,
                        self.rect.y + 8))
        # Note name
        note_s = midi_to_name(int(self.sl_note.value))
        ns = font_sm.render(note_s, True, C["light"])
        surf.blit(ns, (self.rect.x + (CARD_W - ns.get_width())//2,
                       self.rect.y + 26))

        self.sl_note.draw(surf, font_sm)
        self.sl_dur.draw(surf, font_sm)

        # Play button
        pygame.draw.rect(surf, C["play"], self._play_btn, border_radius=5)
        pt = font_sm.render("▶", True, C["text"])
        surf.blit(pt, (self._play_btn.centerx - pt.get_width()//2,
                       self._play_btn.centery - pt.get_height()//2))

        # Delete X
        pygame.draw.rect(surf, C["clear"], self._del_btn, border_radius=3)
        xt = font_sm.render("✕", True, (240, 240, 240))
        surf.blit(xt, (self._del_btn.x + 1, self._del_btn.y))


# ── Main app ──────────────────────────────────────────────────────────────────

class VoiceBuilder:

    # Layout constants
    PALETTE_Y  = 45
    PALETTE_H  = 100
    SEQ_Y      = 150
    SEQ_H      = CARD_H + 20
    CTRL_Y     = SEQ_Y + SEQ_H + 8
    CTRL_H     = 90
    SAVED_Y    = CTRL_Y + CTRL_H + 8

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("Pucky Voice Builder")

        try:
            pygame.mixer.pre_init(44100, -16, 1, 512)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(8)
            self.mixer = pygame.mixer
        except Exception:
            self.mixer = None

        self.font    = pygame.font.SysFont("dejavusans", 14, bold=True)
        self.font_sm = pygame.font.SysFont("dejavusans", 11)
        self.font_lg = pygame.font.SysFont("dejavusans", 17, bold=True)

        self.steps: list[StepCard] = []
        self.scroll_x   = 0      # horizontal scroll offset for sequence
        self.words       = self._load_words()
        self.name_buf    = ""
        self.name_active = False
        self._playing    = False
        self._status     = ""
        self._status_t   = 0.0

        # Pre-build palette button rects
        self._build_palette()

    # ─── Palette ──────────────────────────────────────────────────────────────

    def _build_palette(self):
        """Build rects for all phoneme buttons in two rows."""
        cols = 8
        btn_w = WIN_W // cols
        btn_h = 44
        self._pal_rects = []
        for i, ph in enumerate(PHONEMES):
            row = i // cols
            col = i % cols
            x = col * btn_w
            y = self.PALETTE_Y + row * btn_h
            self._pal_rects.append(pygame.Rect(x, y, btn_w - 2, btn_h - 2))

    # ─── Words persistence ────────────────────────────────────────────────────

    def _load_words(self) -> dict:
        if WORDS_FILE.exists():
            try:
                return json.loads(WORDS_FILE.read_text())
            except Exception:
                pass
        return {}

    def _save_words(self):
        WORDS_FILE.parent.mkdir(exist_ok=True)
        WORDS_FILE.write_text(json.dumps(self.words, indent=2, ensure_ascii=False))

    # ─── Sequence helpers ─────────────────────────────────────────────────────

    def _add_phoneme(self, ph_index: int):
        name, vowel_key, kind = PHONEMES[ph_index]
        sample_name = VOWEL_MAP.get(vowel_key, vowel_key)
        default_note = SAMPLE_BASE.get(sample_name) or 62
        card = StepCard(name, vowel_key, kind,
                        x=0, y=self.SEQ_Y + 8,
                        note=default_note, duration=0.45)
        self.steps.append(card)
        self._reflow()

    def _reflow(self):
        """Reposition cards side by side with scroll."""
        for i, card in enumerate(self.steps):
            x = 8 + i * (CARD_W + 6) - self.scroll_x
            card.move_to(x, self.SEQ_Y + 8)

    def _seq_width(self):
        return len(self.steps) * (CARD_W + 6)

    # ─── Playback ─────────────────────────────────────────────────────────────

    def _play_sequence(self, steps=None):
        if self._playing:
            return
        if steps is None:
            steps = self.steps
        if not steps:
            return
        snapshot = [(VOWEL_MAP.get(s.vowel_key, s.vowel_key),
                     int(s.sl_note.value),
                     s.sl_dur.value) for s in steps]

        def _run():
            self._playing = True
            for sample_name, note, dur in snapshot:
                _play_sample(sample_name, note, dur, self.mixer)
                time.sleep(max(0.0, dur - 0.02))
            self._playing = False

        threading.Thread(target=_run, daemon=True).start()

    def _play_one(self, card: StepCard):
        sample_name = VOWEL_MAP.get(card.vowel_key, card.vowel_key)
        note = int(card.sl_note.value)
        dur  = card.sl_dur.value
        threading.Thread(
            target=_play_sample,
            args=(sample_name, note, dur, self.mixer),
            daemon=True
        ).start()

    # ─── Save / load word ─────────────────────────────────────────────────────

    def _save_word(self):
        name = self.name_buf.strip()
        if not name or not self.steps:
            return
        self.words[name] = [
            {"sample": VOWEL_MAP.get(s.vowel_key, s.vowel_key),
             "vowel":  s.vowel_key,
             "note":   int(s.sl_note.value),
             "dur":    round(s.sl_dur.value, 3)}
            for s in self.steps
        ]
        self._save_words()
        self._status   = f"saved  \"{name}\""
        self._status_t = time.time()
        self.name_buf  = ""

    def _load_word(self, name: str):
        data = self.words.get(name, [])
        self.steps = []
        for item in data:
            sample = item.get("sample", "aa")
            # Reverse-look up kind
            vowel = item.get("vowel", "a")
            kind  = "vowel"
            for pn, pvk, pk in PHONEMES:
                if pvk == vowel:
                    kind = pk
                    break
            display = item.get("vowel", sample)
            for pn, pvk, pk in PHONEMES:
                if pvk == vowel:
                    display = pn
                    break
            card = StepCard(display, vowel, kind, x=0, y=self.SEQ_Y+8,
                            note=item.get("note", 62),
                            duration=item.get("dur", 0.45))
            self.steps.append(card)
        self._reflow()

    # ─── Draw ─────────────────────────────────────────────────────────────────

    def _draw_palette(self):
        surf = self.screen
        # Section label
        lbl = self.font_sm.render("phonemes — tap to add", True, C["hint"])
        surf.blit(lbl, (6, self.PALETTE_Y - 16))

        for i, (rect, (name, _, kind)) in enumerate(zip(self._pal_rects, PHONEMES)):
            col = C.get(kind, C["card"])
            pygame.draw.rect(surf, col, rect, border_radius=6)
            pygame.draw.rect(surf, C["border"], rect, width=1, border_radius=6)
            t = self.font.render(name, True, C["text"])
            surf.blit(t, (rect.centerx - t.get_width()//2,
                          rect.centery - t.get_height()//2))

    def _draw_sequence(self):
        surf = self.screen
        # Background
        seq_rect = pygame.Rect(0, self.SEQ_Y, WIN_W, self.SEQ_H)
        pygame.draw.rect(surf, C["panel"], seq_rect)
        pygame.draw.line(surf, C["border"], (0, self.SEQ_Y),
                         (WIN_W, self.SEQ_Y), 1)
        pygame.draw.line(surf, C["border"], (0, self.SEQ_Y + self.SEQ_H),
                         (WIN_W, self.SEQ_Y + self.SEQ_H), 1)

        if not self.steps:
            hint = self.font_sm.render(
                "tap a phoneme above to start building a word →", True, C["hint"])
            surf.blit(hint, (WIN_W//2 - hint.get_width()//2,
                             self.SEQ_Y + self.SEQ_H//2 - 8))
            return

        # Clip to sequence area
        clip = surf.get_clip()
        surf.set_clip(seq_rect)
        for card in self.steps:
            if -CARD_W < card.rect.x < WIN_W:
                card.draw(surf, self.font, self.font_sm)
        surf.set_clip(clip)

        # Scroll arrows if needed
        if self.scroll_x > 0:
            arrow = self.font.render("◀", True, C["text"])
            surf.blit(arrow, (2, self.SEQ_Y + self.SEQ_H//2 - 10))
        if self._seq_width() - self.scroll_x > WIN_W:
            arrow = self.font.render("▶", True, C["text"])
            surf.blit(arrow, (WIN_W - 18, self.SEQ_Y + self.SEQ_H//2 - 10))

    def _draw_controls(self):
        surf = self.screen
        y0 = self.CTRL_Y
        # Row 1: Play, Clear
        btn_play  = pygame.Rect(8,       y0+4,  160, 36)
        btn_clear = pygame.Rect(180,     y0+4,  100, 36)

        pygame.draw.rect(surf, C["play"], btn_play, border_radius=8)
        t = self.font.render("▶  Play word", True, C["text"])
        surf.blit(t, (btn_play.centerx - t.get_width()//2,
                      btn_play.centery - t.get_height()//2))

        pygame.draw.rect(surf, C["clear"], btn_clear, border_radius=8)
        t = self.font.render("Clear", True, C["text"])
        surf.blit(t, (btn_clear.centerx - t.get_width()//2,
                      btn_clear.centery - t.get_height()//2))

        # Row 2: Name field + Save
        y1 = y0 + 48
        lbl = self.font_sm.render("name:", True, C["hint"])
        surf.blit(lbl, (8, y1 + 8))

        name_rect = pygame.Rect(60, y1+2, 240, 30)
        pygame.draw.rect(surf, (255,252,245) if self.name_active else C["card"],
                         name_rect, border_radius=5)
        pygame.draw.rect(surf, C["fill"] if self.name_active else C["border"],
                         name_rect, width=2, border_radius=5)
        nt = self.font.render(self.name_buf + ("|" if self.name_active else ""),
                              True, C["text"])
        surf.blit(nt, (name_rect.x + 6, name_rect.centery - nt.get_height()//2))

        btn_save = pygame.Rect(312, y1+2, 100, 30)
        pygame.draw.rect(surf, C["save"], btn_save, border_radius=6)
        t = self.font.render("💾 Save", True, C["text"])
        surf.blit(t, (btn_save.centerx - t.get_width()//2,
                      btn_save.centery - t.get_height()//2))

        # Status
        if self._status and time.time() - self._status_t < 2.5:
            st = self.font_sm.render(self._status, True, C["light"])
            surf.blit(st, (420, y1 + 8))

        self._btn_play  = btn_play
        self._btn_clear = btn_clear
        self._name_rect = name_rect
        self._btn_save  = btn_save

    def _draw_saved(self):
        surf = self.screen
        y0   = self.SAVED_Y
        if y0 >= WIN_H - 10:
            return
        available_h = WIN_H - y0
        pygame.draw.rect(surf, C["saved_bg"],
                         pygame.Rect(0, y0, WIN_W, available_h))
        pygame.draw.line(surf, C["border"], (0, y0), (WIN_W, y0), 1)

        lbl = self.font_sm.render("saved words:", True, C["hint"])
        surf.blit(lbl, (6, y0 + 4))

        self._saved_btns = []
        x = 6
        y = y0 + 22
        for name in list(self.words.keys()):
            bw  = self.font.size(name)[0] + 36
            btn = pygame.Rect(x, y, bw, 28)
            if btn.right > WIN_W - 6:
                x, y = 6, y + 34
                btn  = pygame.Rect(x, y, bw, 28)
                if y + 28 > WIN_H - 4:
                    break
            pygame.draw.rect(surf, C["card"], btn, border_radius=6)
            pygame.draw.rect(surf, C["border"], btn, width=1, border_radius=6)
            t = self.font.render(f"▶ {name}", True, C["text"])
            surf.blit(t, (btn.x + 6, btn.centery - t.get_height()//2))
            self._saved_btns.append((btn, name))
            x += bw + 6

    def _draw_title(self):
        t = self.font_lg.render("Pucky Voice Builder", True, C["title"])
        self.screen.blit(t, (WIN_W//2 - t.get_width()//2, 8))

    # ─── Event handling ───────────────────────────────────────────────────────

    def _handle_event(self, ev):
        # ── Keyboard ─────────────────────────────────
        if ev.type == pygame.KEYDOWN:
            if self.name_active:
                if ev.key == pygame.K_BACKSPACE:
                    self.name_buf = self.name_buf[:-1]
                elif ev.key == pygame.K_RETURN:
                    self._save_word()
                    self.name_active = False
                elif ev.unicode and ev.unicode.isprintable():
                    self.name_buf += ev.unicode
                return
            if ev.key == pygame.K_SPACE:
                self._play_sequence()
            elif ev.key == pygame.K_DELETE or ev.key == pygame.K_BACKSPACE:
                if self.steps:
                    self.steps.pop()
                    self._reflow()

        # ── Mouse down ───────────────────────────────
        if ev.type == pygame.MOUSEBUTTONDOWN:
            mx, my = ev.pos

            # Palette
            for i, rect in enumerate(self._pal_rects):
                if rect.collidepoint(mx, my):
                    self._add_phoneme(i)
                    return

            # Sequence cards
            for i, card in enumerate(self.steps):
                action = card.handle_event(ev, self.mixer)
                if action == "delete":
                    self.steps.pop(i)
                    self._reflow()
                    return
                if action == "play":
                    self._play_one(card)
                    return

            # Controls
            if hasattr(self, "_btn_play") and self._btn_play.collidepoint(mx, my):
                self._play_sequence()
                return
            if hasattr(self, "_btn_clear") and self._btn_clear.collidepoint(mx, my):
                self.steps.clear()
                self.scroll_x = 0
                return
            if hasattr(self, "_name_rect") and self._name_rect.collidepoint(mx, my):
                self.name_active = True
                return
            if hasattr(self, "_btn_save") and self._btn_save.collidepoint(mx, my):
                self._save_word()
                return
            # Saved word buttons
            for btn, name in getattr(self, "_saved_btns", []):
                if btn.collidepoint(mx, my):
                    self._load_word(name)
                    self._play_sequence()
                    return
            # Click elsewhere → deactivate name field
            self.name_active = False

        # Slider events for cards
        if ev.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONUP):
            for card in self.steps:
                card.handle_event(ev, self.mixer)

        # ── Scroll sequence ──────────────────────────
        if ev.type == pygame.MOUSEWHEEL:
            my = pygame.mouse.get_pos()[1]
            if self.SEQ_Y <= my <= self.SEQ_Y + self.SEQ_H:
                self.scroll_x = max(0, min(
                    self.scroll_x - ev.x * 30,
                    max(0, self._seq_width() - WIN_W + 20)
                ))
                self._reflow()

    # ─── Main loop ────────────────────────────────────────────────────────────

    def run(self):
        clock = pygame.time.Clock()
        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit()
                    return
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    pygame.quit()
                    return
                self._handle_event(ev)

            self.screen.fill(C["bg"])
            self._draw_title()
            self._draw_palette()
            self._draw_sequence()
            self._draw_controls()
            self._draw_saved()

            # Playing indicator
            if self._playing:
                dot = self.font_sm.render("♪ playing", True, C["play"])
                self.screen.blit(dot, (WIN_W - dot.get_width() - 8, 10))

            pygame.display.flip()
            clock.tick(30)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = VoiceBuilder()
    app.run()
