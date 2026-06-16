"""
pucky_voice_recorder.py
───────────────────────
Record voice samples — phonemes for Pucky's voice,
battle cries, or any sound you like.

Left:  name + waveform + trim markers + controls
Right: Loki's wish list — click any item to pre-fill the name

Written with love by Loki for Iðunn.
"""

import sys
import time
import threading
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import pygame

# ── Paths ──────────────────────────────────────────────────────────────────────
VOICE_DIR   = Path(__file__).parent / "voice"
SAMPLE_RATE = 44100
RECORD_SECS = 2.5

# ── Window ─────────────────────────────────────────────────────────────────────
WIN_W, WIN_H = 920, 510
PANEL_X      = 610   # right panel starts here
WX, WY       = 14, 215
WW, WH       = 580, 118   # waveform rect

# ── Loki's wish list ───────────────────────────────────────────────────────────
#   (save_name, display, hint — what to say / how to say it)
WISH = [
    # ── vowels ────────────────────────────────────────────────────────────────
    ("aa",   "aa  /ɑː/",  'long open A — say "aah" like a sigh'),
    ("eh",   "eh  /ɛ/",   'short E — say "eh" like in "bed"'),
    ("ii",   "ii  /iː/",  'long E — say "ee" like in "see"'),
    ("oh",   "oh  /oʊ/",  'long O — say "oh" like in "go"'),
    ("uu",   "uu  /uː/",  'long U — say "oo" like in "moon"'),
    ("uh",   "uh  /ʌ/",   'short U — say "uh" like in "cup"'),
    ("ih",   "ih  /ɪ/",   'short I — say "ih" like in "lit"'),
    ("ah",   "ah  /ɑ/",   'open O — say "ah" like in "cottage"'),
    ("ay",   "ay  /eɪ/",  'long A — say "ay" like in "lake"'),
    ("er",   "er  /ər/",  'er ending — say "er" gently like in "flower"'),
    # ── warm / sung ───────────────────────────────────────────────────────────
    ("wa",   "wa  /wɑ/",  'say "wah" — start of "water"'),
    ("ma",   "ma  /mɑ/",  'say "mah" — warm, motherly'),
    ("na",   "na  /nɑ/",  'say "nah" — soft nasal'),
    ("la",   "la  /lɑ/",  'say "lah" — singing syllable'),
    ("hum",  "hum  /m/",  'hum with mouth closed — mmm'),
    # ── consonants ────────────────────────────────────────────────────────────
    ("breath", "h  /h/",  'soft breath — just exhale gently'),
    ("ss",   "ss  /s/",   'say "sss" — snake sound, sustained'),
    ("ff",   "ff  /f/",   'say "fff" — sustained'),
    ("kk",   "kk  /k/",   'hard K click — "k" not "kay"'),
    ("cah",  "cah  /kɑ/", 'hard K with vowel — "cah" like in "cat"'),
    ("tt",   "tt  /t/",   'sharp T click — "t" not "tee"'),
    ("buh",  "buh  /b/",  'say "buh" — soft B burst'),
    ("puh",  "puh  /p/",  'say "puh" — soft P burst'),
    ("duh",  "duh  /d/",  'say "duh" — soft D'),
    ("guh",  "guh  /g/",  'say "guh" — soft G'),
    # ── battle cries ──────────────────────────────────────────────────────────
    ("cry_fight",   "⚔  fight cry",   "your battle call — say whatever feels right"),
    ("cry_hit",     "⚔  hit grunt",   "short grunt for landing a hit — ha! or hh!"),
    ("cry_heavy",   "⚔  heavy hit",   "big impact — RAAH! or a deep groan"),
    ("cry_ouch",    "⚔  take a hit",  "getting hit — oof! or ahh!"),
    ("cry_victory", "⚔  victory",     "winning — cheer, laugh, whatever you feel"),
]

# ── Colours ────────────────────────────────────────────────────────────────────
C = {
    "bg":       (245, 238, 220),
    "panel":    (235, 228, 210),
    "wave_bg":  (222, 216, 202),
    "text":     ( 55,  40,  25),
    "light":    (120, 100,  75),
    "hint":     (160, 145, 120),
    "border":   (180, 165, 140),
    "record":   (195,  65,  50),
    "play":     (110, 178, 115),
    "accept":   ( 85, 158, 115),
    "redo":     (195, 140, 115),
    "wave":     ( 78, 118, 172),
    "trim":     (195, 152,  55),
    "done":     ( 95, 168, 118),
    "wish_bg":  (240, 232, 215),
    "wish_sel": (215, 198, 162),
    "wish_done":(190, 220, 195),
    "field_bg": (255, 252, 244),
    "field_act":(255, 248, 230),
    "nav":      (185, 170, 148),
    "battle":   (190,  95,  70),
}


class VoiceRecorder:

    def __init__(self):
        pygame.init()
        pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)
        pygame.mixer.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption("Pucky Voice Recorder")

        self.font_lg = pygame.font.SysFont("dejavusans", 22, bold=True)
        self.font    = pygame.font.SysFont("dejavusans", 14, bold=True)
        self.font_sm = pygame.font.SysFont("dejavusans", 12)

        # recording state
        self.data        = None        # float32 numpy array
        self.trim_start  = 0.0
        self.trim_end    = 1.0
        self._drag       = None        # 'start' | 'end'
        self._state      = "idle"      # idle|countdown|recording|review
        self._countdown  = 0
        self._status     = ""
        self._status_t   = 0.0
        self._tmp        = Path(tempfile.gettempdir()) / "pucky_rec_raw.wav"

        # name field
        self.name_buf    = ""
        self.name_active = False

        # wish list scroll
        self._wish_scroll = 0

        # button rects (pre-init so events don't crash before first draw)
        self._btn_record = self._btn_play = pygame.Rect(0,0,0,0)
        self._btn_accept = self._btn_redo = pygame.Rect(0,0,0,0)
        self._wish_rects = []

    # ── helpers ────────────────────────────────────────────────────────────────

    def _exists(self, name):
        return (VOICE_DIR / f"{name}.wav").exists()

    def _trimmed(self):
        if self.data is None:
            return None
        n = len(self.data)
        return self.data[int(self.trim_start * n): int(self.trim_end * n)]

    def _set_status(self, msg):
        self._status   = msg
        self._status_t = time.time()

    # ── recording ──────────────────────────────────────────────────────────────

    def _do_record(self):
        self._state = "countdown"
        for i in range(3, 0, -1):
            self._countdown = i
            time.sleep(1.0)
        self._countdown = 0
        self._state = "recording"
        self._tmp.unlink(missing_ok=True)
        proc = subprocess.Popen(
            ["pw-record",
             "--rate", str(SAMPLE_RATE),
             "--channels", "1",
             "--latency", "100ms",
             str(self._tmp)],
            stderr=subprocess.DEVNULL,
        )
        time.sleep(RECORD_SECS)
        proc.terminate()
        proc.wait()
        if self._tmp.exists():
            raw, _ = sf.read(str(self._tmp), always_2d=False)
            self.data       = raw.astype(np.float32)
            self.trim_start = 0.0
            self.trim_end   = 1.0
        self._state = "review"

    def _start_record(self):
        self.data = None
        threading.Thread(target=self._do_record, daemon=True).start()

    def _play_preview(self):
        seg = self._trimmed()
        if seg is None or len(seg) == 0:
            return
        tmp = Path(tempfile.gettempdir()) / "pucky_preview.wav"
        sf.write(str(tmp), seg, SAMPLE_RATE)
        threading.Thread(
            target=lambda: subprocess.run(["pw-play", str(tmp)], timeout=5),
            daemon=True,
        ).start()

    def _accept(self):
        seg  = self._trimmed()
        name = self.name_buf.strip()
        if seg is None or len(seg) == 0 or not name:
            self._set_status("give the sound a name first")
            return
        VOICE_DIR.mkdir(exist_ok=True)
        out = VOICE_DIR / f"{name}.wav"
        sf.write(str(out), seg, SAMPLE_RATE)
        self._set_status(f"saved  {out.name}")
        self.data       = None
        self.name_buf   = ""
        self._state     = "idle"

    # ── drawing ────────────────────────────────────────────────────────────────

    def _draw_name_field(self):
        surf = self.screen
        lbl  = self.font_sm.render("name:", True, C["hint"])
        surf.blit(lbl, (WX, 185))

        fw   = 300
        frect = pygame.Rect(WX + 48, 181, fw, 26)
        bg   = C["field_act"] if self.name_active else C["field_bg"]
        bdr  = C["trim"] if self.name_active else C["border"]
        pygame.draw.rect(surf, bg,  frect, border_radius=5)
        pygame.draw.rect(surf, bdr, frect, width=2, border_radius=5)
        cursor = "|" if self.name_active and int(time.time() * 2) % 2 == 0 else ""
        nt = self.font.render(self.name_buf + cursor, True, C["text"])
        surf.blit(nt, (frect.x + 6, frect.centery - nt.get_height()//2))

        # hint if empty
        if not self.name_buf:
            hint = self.font_sm.render("type a name or click the list →",
                                        True, C["hint"])
            surf.blit(hint, (frect.x + 6, frect.centery - hint.get_height()//2))

        self._name_rect = frect

    def _draw_wave(self):
        surf = self.screen
        pygame.draw.rect(surf, C["wave_bg"], (WX, WY, WW, WH), border_radius=6)
        pygame.draw.rect(surf, C["border"],  (WX, WY, WW, WH), width=1, border_radius=6)

        if self.data is None:
            msg = self.font_sm.render(
                "press Record — you have 2.5 seconds", True, C["hint"])
            surf.blit(msg, (WX + WW//2 - msg.get_width()//2,
                             WY + WH//2 - msg.get_height()//2))
            return

        n    = len(self.data)
        mid  = WY + WH // 2
        half = WH // 2 - 5

        # trim shade
        sx = int(self.trim_start * WW)
        ex = int(self.trim_end   * WW)
        shade = pygame.Surface((max(1, ex-sx), WH), pygame.SRCALPHA)
        shade.fill((200, 178,  95, 60))
        surf.blit(shade, (WX + sx, WY))

        # waveform (min/max per column)
        for px in range(WW):
            i0 = int(px / WW * n)
            i1 = max(i0 + 1, int((px + 1) / WW * n))
            chunk = self.data[i0:i1]
            if len(chunk) == 0:
                continue
            y_top = int(mid - float(np.max(chunk)) * half)
            y_bot = int(mid - float(np.min(chunk)) * half)
            pygame.draw.line(surf, C["wave"], (WX+px, y_top), (WX+px, y_bot))

        # centre line
        pygame.draw.line(surf, C["border"], (WX, mid), (WX+WW, mid), 1)

        # trim markers
        for frac in (self.trim_start, self.trim_end):
            px = WX + int(frac * WW)
            pygame.draw.line(surf, C["trim"], (px, WY), (px, WY+WH), 2)
            pygame.draw.circle(surf, C["trim"], (px, mid), 9)
            pygame.draw.circle(surf, C["bg"],   (px, mid), 5)

        dur = (self.trim_end - self.trim_start) * n / SAMPLE_RATE
        dl  = self.font_sm.render(f"{dur:.2f}s selected", True, C["hint"])
        surf.blit(dl, (WX + WW - dl.get_width() - 6,
                        WY + WH - dl.get_height() - 4))

    def _draw_controls(self):
        surf = self.screen
        by   = WY + WH + 12

        if self._state == "idle":
            self._btn_record = pygame.Rect(WX, by, 150, 44)
            pygame.draw.rect(surf, C["record"], self._btn_record, border_radius=10)
            t = self.font.render("⏺  Record", True, (255,255,255))
            surf.blit(t, (self._btn_record.centerx - t.get_width()//2,
                          self._btn_record.centery - t.get_height()//2))

        elif self._state == "countdown":
            t = self.font_lg.render(str(self._countdown), True, C["record"])
            surf.blit(t, (WX + 50, by + 4))

        elif self._state == "recording":
            t = self.font_lg.render("● recording …", True, C["record"])
            surf.blit(t, (WX, by + 4))

        elif self._state == "review":
            # record again
            self._btn_record = pygame.Rect(WX, by, 130, 44)
            pygame.draw.rect(surf, C["record"], self._btn_record, border_radius=10)
            t = self.font.render("⏺  Re-record", True, (255,255,255))
            surf.blit(t, (self._btn_record.centerx - t.get_width()//2,
                          self._btn_record.centery - t.get_height()//2))

            self._btn_play   = pygame.Rect(WX + 144, by, 110, 44)
            self._btn_accept = pygame.Rect(WX + 268, by, 110, 44)
            self._btn_redo   = pygame.Rect(WX + 392, by,  96, 44)

            for btn, col, lbl in [
                (self._btn_play,   C["play"],   "▶  Play"),
                (self._btn_accept, C["accept"], "✓  Save"),
                (self._btn_redo,   C["redo"],   "↺  Redo"),
            ]:
                pygame.draw.rect(surf, col, btn, border_radius=8)
                t = self.font.render(lbl, True, C["text"])
                surf.blit(t, (btn.centerx - t.get_width()//2,
                               btn.centery - t.get_height()//2))

            hint = self.font_sm.render(
                "drag the amber markers on the waveform to trim  ·  Space = play  ·  Enter = save",
                True, C["hint"])
            surf.blit(hint, (WX, by + 52))

        # status
        if self._status and time.time() - self._status_t < 3.0:
            st = self.font_sm.render(self._status, True, C["light"])
            surf.blit(st, (WX, WIN_H - 22))

    def _draw_wish_list(self):
        surf = self.screen
        px, py, pw, ph = PANEL_X, 0, WIN_W - PANEL_X, WIN_H

        pygame.draw.rect(surf, C["wish_bg"], (px, py, pw, ph))
        pygame.draw.line(surf, C["border"], (px, 0), (px, WIN_H), 1)

        hdr = self.font_sm.render("Loki's wish list", True, C["light"])
        surf.blit(hdr, (px + pw//2 - hdr.get_width()//2, 10))

        self._wish_rects = []
        item_h = 52
        clip   = surf.get_clip()
        surf.set_clip(pygame.Rect(px, 30, pw, WIN_H - 30))

        last_section = None
        iy = 30 - self._wish_scroll

        for name, display, hint in WISH:
            if name.startswith("cry_"):
                section = "battle"
            elif name in ("aa","eh","ii","oh","uu","uh","ih","ah","ay","er"):
                section = "vowels"
            elif name in ("wa","ma","na","la","hum"):
                section = "warm"
            else:
                section = "cons"

            SEC_LABELS = {
                "vowels": "◆  vowels",
                "warm":   "◆  warm / sung",
                "cons":   "◆  consonants",
                "battle": "⚔  battle cries",
            }
            if section != last_section:
                if last_section is not None:
                    iy += 6
                sec_lbl = SEC_LABELS[section]
                sec_col = C["battle"] if section == "battle" else C["light"]
                t = self.font_sm.render(sec_lbl, True, sec_col)
                surf.blit(t, (px + 8, iy + 4))
                iy += 22
                last_section = section

            done   = self._exists(name)
            active = self.name_buf.strip() == name
            bg     = C["wish_done"] if done else (C["wish_sel"] if active else C["wish_bg"])
            rect   = pygame.Rect(px + 4, iy, pw - 8, item_h - 4)

            pygame.draw.rect(surf, bg, rect, border_radius=6)
            if active:
                pygame.draw.rect(surf, C["trim"], rect, width=2, border_radius=6)

            dn = self.font.render(display, True, C["text"])
            surf.blit(dn, (rect.x + 8, rect.y + 6))
            ht = self.font_sm.render(hint, True, C["hint"])
            # word-wrap hint if too wide
            max_w = pw - 20
            if ht.get_width() > max_w:
                words  = hint.split()
                line   = ""
                lines  = []
                for w in words:
                    test = line + (" " if line else "") + w
                    if self.font_sm.size(test)[0] > max_w:
                        lines.append(line)
                        line = w
                    else:
                        line = test
                if line:
                    lines.append(line)
                for li, ln in enumerate(lines[:2]):
                    lt = self.font_sm.render(ln, True, C["hint"])
                    surf.blit(lt, (rect.x + 8, rect.y + 26 + li * 14))
            else:
                surf.blit(ht, (rect.x + 8, rect.y + 26))

            if done:
                chk = self.font_sm.render("✓", True, C["done"])
                surf.blit(chk, (rect.right - chk.get_width() - 8, rect.y + 6))

            self._wish_rects.append((rect, name))
            iy += item_h

        surf.set_clip(clip)

    def _draw_title(self):
        t = self.font.render("Pucky Voice Recorder", True, C["light"])
        self.screen.blit(t, (WIN_W//2 - (WIN_W - PANEL_X)//2 - t.get_width()//2, 10))

    # ── event handling ─────────────────────────────────────────────────────────

    def _drag_wave(self, ev):
        if self.data is None:
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and WY <= ev.pos[1] <= WY + WH:
            sx = WX + int(self.trim_start * WW)
            ex = WX + int(self.trim_end   * WW)
            if abs(ev.pos[0] - sx) < 14:
                self._drag = "start"
            elif abs(ev.pos[0] - ex) < 14:
                self._drag = "end"
        elif ev.type == pygame.MOUSEBUTTONUP:
            self._drag = None
        elif ev.type == pygame.MOUSEMOTION and self._drag:
            frac = max(0.0, min(1.0, (ev.pos[0] - WX) / WW))
            if self._drag == "start":
                self.trim_start = min(frac, self.trim_end - 0.02)
            else:
                self.trim_end = max(frac, self.trim_start + 0.02)

    def handle(self, ev):
        self._drag_wave(ev)

        # keyboard
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                pygame.quit(); sys.exit()
            if self.name_active:
                if ev.key == pygame.K_BACKSPACE:
                    self.name_buf = self.name_buf[:-1]
                elif ev.key == pygame.K_RETURN:
                    self.name_active = False
                    if self._state == "review":
                        self._accept()
                elif ev.unicode and ev.unicode.isprintable():
                    self.name_buf += ev.unicode
                return
            if ev.key == pygame.K_SPACE and self._state == "review":
                self._play_preview()
            if ev.key == pygame.K_RETURN and self._state == "review":
                self._accept()

        if ev.type == pygame.MOUSEWHEEL:
            mx = pygame.mouse.get_pos()[0]
            if mx >= PANEL_X:
                self._wish_scroll = max(0, self._wish_scroll - ev.y * 20)

        if ev.type != pygame.MOUSEBUTTONDOWN:
            return
        mx, my = ev.pos

        # name field
        if hasattr(self, "_name_rect") and self._name_rect.collidepoint(mx, my):
            self.name_active = True
            return
        self.name_active = False

        # wish list
        if mx >= PANEL_X:
            for rect, name in self._wish_rects:
                if rect.collidepoint(mx, my):
                    self.name_buf    = name
                    self.name_active = False
                    # if already recorded, load it for preview / redo
                    existing = VOICE_DIR / f"{name}.wav"
                    if existing.exists():
                        try:
                            raw, _ = sf.read(str(existing), always_2d=False)
                            self.data       = raw.astype(np.float32)
                            self.trim_start = 0.0
                            self.trim_end   = 1.0
                            self._state     = "review"
                            self._set_status(f"loaded  {existing.name} — re-record or keep")
                        except Exception:
                            pass
                    return

        # controls
        if self._state in ("idle", "review") and self._btn_record.collidepoint(mx, my):
            self._start_record()
            return
        if self._state == "review":
            if self._btn_play.collidepoint(mx, my):
                self._play_preview()
            elif self._btn_accept.collidepoint(mx, my):
                self._accept()
            elif self._btn_redo.collidepoint(mx, my):
                self.data   = None
                self._state = "idle"

    # ── main loop ──────────────────────────────────────────────────────────────

    def run(self):
        clock = pygame.time.Clock()
        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); return
                self.handle(ev)

            self.screen.fill(C["bg"])
            self._draw_title()
            self._draw_name_field()
            self._draw_wave()
            self._draw_controls()
            self._draw_wish_list()
            pygame.display.flip()
            clock.tick(30)


if __name__ == "__main__":
    VoiceRecorder().run()
