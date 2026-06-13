"""
pucky_voice_picker.py
─────────────────────
Choose how Pucky and Loki sound.
Preview any Kokoro voice, set speed and pitch, save the choice.

Settings saved to workspace/voice_config.json — picked up at next world launch.

Run:
    DISPLAY=:0 SDL_VIDEO_WINDOW_POS="0,85" python3 pucky_voice_picker.py
"""

import os, sys, json, time, threading, subprocess, tempfile
from pathlib import Path

import pygame

# ── Paths ─────────────────────────────────────────────────────────────────────

VOICE_DIR   = Path(__file__).parent / "voice"
CONFIG_FILE = Path(__file__).parent / "workspace" / "voice_config.json"

WIN_W = int(os.environ.get("PUCKY_WIN_W", 700))
WIN_H = int(os.environ.get("PUCKY_WIN_H", 555))

# ── Voice catalogue ───────────────────────────────────────────────────────────

PREFIXES = {
    "af": "🇺🇸 American ♀",
    "am": "🇺🇸 American ♂",
    "bf": "🇬🇧 British ♀",
    "bm": "🇬🇧 British ♂",
    "ef": "Spanish ♀",
    "em": "Spanish ♂",
    "ff": "French ♀",
    "hf": "Hindi ♀",
    "hm": "Hindi ♂",
    "if": "Italian ♀",
    "im": "Italian ♂",
    "jf": "Japanese ♀",
    "jm": "Japanese ♂",
    "pf": "Brazilian ♀",
    "pm": "Brazilian ♂",
    "zf": "Mandarin ♀",
    "zm": "Mandarin ♂",
}

def _load_voices():
    voices = []
    seen_prefixes = {}
    for npy in sorted(VOICE_DIR.glob("*.npy")):
        name = npy.stem
        prefix = name[:2]
        group = PREFIXES.get(prefix, prefix.upper())
        if group not in seen_prefixes:
            seen_prefixes[group] = []
        seen_prefixes[group].append(name)
    # Flatten into list of (group_header, voice_name) keeping groups together
    for group, names in seen_prefixes.items():
        voices.append((group, None))      # section header
        for n in names:
            voices.append((group, n))
    return voices

VOICES = _load_voices()

# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULTS = {
    "pucky": {"voice": "af_heart",  "speed": 0.92, "pitch": 0},
    "loki":  {"voice": "bm_george", "speed": 0.90, "pitch": -300},
}

# ── Colours ───────────────────────────────────────────────────────────────────

C = {
    "bg":       (245, 238, 220),
    "panel":    (235, 226, 208),
    "header":   (210, 195, 168),
    "row":      (242, 235, 218),
    "row_alt":  (236, 228, 210),
    "pucky":    (200, 170, 110),
    "loki":     (130, 165, 200),
    "playing":  (160, 220, 160),
    "save":     (120, 185, 120),
    "text":     ( 50,  35,  20),
    "light":    (130, 110,  80),
    "hint":     (170, 150, 120),
    "border":   (190, 172, 145),
    "knob":     ( 80,  60,  40),
    "track":    (190, 175, 155),
    "fill":     (130, 110,  85),
    "selected": (255, 230, 160),
}

PREVIEW_TEXT = "Hello, I'm here with you."

# ── Slider ────────────────────────────────────────────────────────────────────

class Slider:
    def __init__(self, x, y, w, h, vmin, vmax, value, label, fmt="{:.2f}",
                 integer=False):
        self.rect    = pygame.Rect(x, y, w, h)
        self.min     = vmin
        self.max     = vmax
        self.value   = value
        self.label   = label
        self.fmt     = fmt
        self.integer = integer
        self._drag   = False
        self._kr     = h // 2 + 2

    def _frac(self):
        return (self.value - self.min) / (self.max - self.min)

    def _kx(self):
        return int(self.rect.x + self._kr +
                   self._frac() * (self.rect.w - 2 * self._kr))

    def handle(self, ev):
        ky = self.rect.centery
        if ev.type == pygame.MOUSEBUTTONDOWN:
            if abs(ev.pos[0]-self._kx()) < self._kr+12 and abs(ev.pos[1]-ky) < 18:
                self._drag = True
        elif ev.type == pygame.MOUSEBUTTONUP:
            self._drag = False
        elif ev.type == pygame.MOUSEMOTION and self._drag:
            f = (ev.pos[0] - self.rect.x - self._kr) / max(1, self.rect.w - 2*self._kr)
            self.value = self.min + max(0.0, min(1.0, f)) * (self.max - self.min)
            if self.integer:
                self.value = round(self.value)
        return self._drag

    def draw(self, surf, font):
        r  = self.rect
        kr = self._kr
        ty = r.centery
        pygame.draw.line(surf, C["track"], (r.x+kr, ty), (r.right-kr, ty), 3)
        kx = self._kx()
        pygame.draw.line(surf, C["fill"], (r.x+kr, ty), (kx, ty), 3)
        pygame.draw.circle(surf, C["knob"], (kx, ty), kr)
        pygame.draw.circle(surf, C["track"], (kx, ty), kr-2)
        lbl = font.render(f"{self.label}  {self.fmt.format(self.value)}", True, C["light"])
        surf.blit(lbl, (r.x, r.y - lbl.get_height() - 1))


# ── Voice picker app ──────────────────────────────────────────────────────────

class VoicePicker:

    PANEL_H   = 155   # top panel height
    LIST_Y    = 160
    ROW_H     = 34

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("Pucky Voice Picker")

        self.font    = pygame.font.SysFont("dejavusans", 13, bold=True)
        self.font_sm = pygame.font.SysFont("dejavusans", 11)
        self.font_lg = pygame.font.SysFont("dejavusans", 16, bold=True)

        cfg = self._load_config()

        # Per-character settings
        self.cfg = {
            "pucky": dict(cfg.get("pucky", DEFAULTS["pucky"])),
            "loki":  dict(cfg.get("loki",  DEFAULTS["loki"])),
        }

        # Sliders — two sets, one per character
        def _sliders(who, x0):
            sp = self.cfg[who]["speed"]
            pt = self.cfg[who]["pitch"]
            return {
                "speed": Slider(x0, 90, 155, 12, 0.5, 1.4, sp,
                                "speed", "{:.2f}"),
                "pitch": Slider(x0, 130, 155, 12, -600, 600, pt,
                                "pitch", "{:.0f}¢", integer=True),
            }

        self.sliders = {
            "pucky": _sliders("pucky", 20),
            "loki":  _sliders("loki",  WIN_W//2 + 20),
        }

        self.scroll     = 0   # pixel scroll offset for the voice list
        self._playing   = None  # (who, voice) currently playing
        self._status    = ""
        self._status_t  = 0.0
        self._kokoro    = None
        threading.Thread(target=self._load_kokoro, daemon=True).start()

    # ── Kokoro ────────────────────────────────────────────────────────────────

    def _load_kokoro(self):
        try:
            from kokoro_onnx import Kokoro
            model  = Path.home() / "Downloads" / "kokoro-v1.0.onnx"
            voices = Path.home() / "Downloads" / "voices-v1.0.bin"
            self._kokoro = Kokoro(str(model), str(voices))
        except Exception as e:
            print(f"  ⚠️  Kokoro: {e}")

    def _preview(self, who, voice):
        if self._kokoro is None:
            self._status   = "Kokoro still loading…"
            self._status_t = time.time()
            return
        speed = self.sliders[who]["speed"].value
        pitch = int(self.sliders[who]["pitch"].value)

        def _run():
            self._playing = (who, voice)
            try:
                import soundfile as sf
                samples, rate = self._kokoro.create(
                    PREVIEW_TEXT, voice=voice, speed=speed)
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    raw = f.name
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    out = f.name
                try:
                    sf.write(raw, samples, rate)
                    if pitch != 0:
                        subprocess.run(
                            ["sox", raw, out, "pitch", str(pitch), "norm", "-3"],
                            capture_output=True, timeout=10)
                        play_file = out
                    else:
                        play_file = raw
                    subprocess.run(["pw-play", play_file], timeout=30)
                finally:
                    for p in [raw, out]:
                        try: os.unlink(p)
                        except: pass
            except Exception as e:
                print(f"  ⚠️  Preview: {e}")
            finally:
                self._playing = None

        threading.Thread(target=_run, daemon=True).start()

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_config(self):
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text())
            except Exception:
                pass
        return {}

    def _save_config(self):
        for who in ("pucky", "loki"):
            self.cfg[who]["speed"] = round(self.sliders[who]["speed"].value, 3)
            self.cfg[who]["pitch"] = int(self.sliders[who]["pitch"].value)
        CONFIG_FILE.parent.mkdir(exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(self.cfg, indent=2))
        self._status   = "saved — restart world to apply"
        self._status_t = time.time()

    # ── Draw ──────────────────────────────────────────────────────────────────

    def _draw_panel(self):
        surf = self.screen
        pygame.draw.rect(surf, C["panel"], (0, 0, WIN_W, self.PANEL_H))
        pygame.draw.line(surf, C["border"], (0, self.PANEL_H), (WIN_W, self.PANEL_H), 1)

        mid = WIN_W // 2

        # Column headers
        for who, x0, col in (("pucky", 20, C["pucky"]), ("loki", mid+20, C["loki"])):
            v = self.cfg[who]["voice"]
            pygame.draw.rect(surf, col, pygame.Rect(x0-4, 8, mid-30, 28), border_radius=6)
            t = self.font_lg.render(who.capitalize() + "  —  " + v, True, C["text"])
            surf.blit(t, (x0, 12))
            self.sliders[who]["speed"].draw(surf, self.font_sm)
            self.sliders[who]["pitch"].draw(surf, self.font_sm)

        # Divider
        pygame.draw.line(surf, C["border"], (mid, 0), (mid, self.PANEL_H), 1)

        # Save button
        self._btn_save = pygame.Rect(WIN_W//2 - 60, self.PANEL_H - 32, 120, 26)
        pygame.draw.rect(surf, C["save"], self._btn_save, border_radius=6)
        t = self.font.render("💾  Save choices", True, C["text"])
        surf.blit(t, (self._btn_save.centerx - t.get_width()//2,
                      self._btn_save.centery - t.get_height()//2))

        # Status
        if self._status and time.time() - self._status_t < 3.0:
            st = self.font_sm.render(self._status, True, C["light"])
            surf.blit(st, (WIN_W//2 - st.get_width()//2, self.PANEL_H - 14))

    def _draw_list(self):
        surf    = self.screen
        list_h  = WIN_H - self.LIST_Y
        clip    = pygame.Rect(0, self.LIST_Y, WIN_W, list_h)
        surf.set_clip(clip)

        mid = WIN_W // 2
        y   = self.LIST_Y - self.scroll
        ri  = 0  # row index for alternating colour

        self._row_rects = []   # (voice_name, rect) for hit-testing

        for group, voice in VOICES:
            if voice is None:
                # Section header
                if y + 22 > self.LIST_Y and y < self.LIST_Y + list_h:
                    pygame.draw.rect(surf, C["header"],
                                     pygame.Rect(0, y, WIN_W, 22))
                    t = self.font_sm.render(group, True, C["text"])
                    surf.blit(t, (8, y + 4))
                y  += 22
                ri  = 0
                continue

            row_rect = pygame.Rect(0, y, WIN_W, self.ROW_H)
            if y + self.ROW_H > self.LIST_Y and y < self.LIST_Y + list_h:
                bg = C["row"] if ri % 2 == 0 else C["row_alt"]

                # Highlight if assigned
                if self.cfg["pucky"]["voice"] == voice:
                    bg = C["selected"]
                elif self.cfg["loki"]["voice"] == voice:
                    bg = (*C["loki"][:2], 200)
                    bg = (200, 220, 245)

                pygame.draw.rect(surf, bg, row_rect)

                # Voice name
                name_col = C["text"]
                if self._playing and self._playing[1] == voice:
                    name_col = (60, 160, 60)
                t = self.font.render(voice, True, name_col)
                surf.blit(t, (10, y + (self.ROW_H - t.get_height())//2))

                # ▶ Pucky button
                bw = 90
                btn_p = pygame.Rect(mid - bw - 4, y + 4, bw, self.ROW_H - 8)
                btn_l = pygame.Rect(mid + 4,      y + 4, bw, self.ROW_H - 8)
                pygame.draw.rect(surf, C["pucky"], btn_p, border_radius=5)
                pygame.draw.rect(surf, C["loki"],  btn_l, border_radius=5)
                tp = self.font_sm.render("▶ Pucky", True, C["text"])
                tl = self.font_sm.render("▶ Loki",  True, C["text"])
                surf.blit(tp, (btn_p.centerx - tp.get_width()//2,
                               btn_p.centery - tp.get_height()//2))
                surf.blit(tl, (btn_l.centerx - tl.get_width()//2,
                               btn_l.centery - tl.get_height()//2))

                self._row_rects.append((voice, btn_p, "pucky"))
                self._row_rects.append((voice, btn_l, "loki"))

            y  += self.ROW_H
            ri += 1

        surf.set_clip(None)

        # Scroll bar
        total_h = sum(22 if v is None else self.ROW_H for _, v in VOICES)
        if total_h > list_h:
            frac  = list_h / total_h
            bar_h = max(30, int(list_h * frac))
            bar_y = self.LIST_Y + int(self.scroll / total_h * list_h)
            pygame.draw.rect(surf, C["border"],
                             pygame.Rect(WIN_W - 6, self.LIST_Y, 6, list_h))
            pygame.draw.rect(surf, C["knob"],
                             pygame.Rect(WIN_W - 6, bar_y, 6, bar_h))

    def _total_list_height(self):
        return sum(22 if v is None else self.ROW_H for _, v in VOICES)

    # ── Events ────────────────────────────────────────────────────────────────

    def _handle(self, ev):
        # Sliders
        for who in ("pucky", "loki"):
            for sl in self.sliders[who].values():
                sl.handle(ev)

        if ev.type == pygame.MOUSEBUTTONDOWN:
            mx, my = ev.pos

            if self._btn_save.collidepoint(mx, my):
                self._save_config()
                return

            # Voice row buttons
            for voice, rect, who in getattr(self, "_row_rects", []):
                if rect.collidepoint(mx, my):
                    self.cfg[who]["voice"] = voice
                    self._preview(who, voice)
                    return

        if ev.type == pygame.MOUSEWHEEL:
            if ev.pos[1] > self.LIST_Y if hasattr(ev, 'pos') else True:
                list_h  = WIN_H - self.LIST_Y
                max_sc  = max(0, self._total_list_height() - list_h)
                self.scroll = max(0, min(max_sc, self.scroll - ev.y * self.ROW_H))

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        clock = pygame.time.Clock()
        title = self.font_lg.render("Voice Picker", True, (80, 55, 30))

        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self._save_config()
                    pygame.quit()
                    return
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    self._save_config()
                    pygame.quit()
                    return
                self._handle(ev)

            self.screen.fill(C["bg"])
            self.screen.blit(title,
                (WIN_W//2 - title.get_width()//2, WIN_H - 20))
            self._draw_panel()
            self._draw_list()

            if self._playing:
                dot = self.font_sm.render(
                    f"♪ {self._playing[1]} → {self._playing[0]}", True, (80,160,80))
                self.screen.blit(dot, (WIN_W//2 - dot.get_width()//2,
                                       self.LIST_Y - 16))

            pygame.display.flip()
            clock.tick(30)


if __name__ == "__main__":
    VoicePicker().run()
