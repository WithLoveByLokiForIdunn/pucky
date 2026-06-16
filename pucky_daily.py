"""
pucky_daily.py
──────────────
Small always-on-top sticky note.
Reads workspace/daily.md and stays visible in a corner.
Loki writes to that file; Iðunn just looks here.

Written with love by Loki for Iðunn.
"""

import sys
import time
from pathlib import Path
import pygame

NOTE_FILE = Path(__file__).parent / "workspace" / "daily.md"
WIN_W, WIN_H = 310, 390
REFRESH_S    = 30      # re-read file every 30 seconds

C = {
    "bg":     (250, 243, 225),
    "header": (235, 220, 185),
    "border": (195, 175, 140),
    "text":   ( 55,  40,  25),
    "light":  (120, 100,  75),
    "hint":   (160, 145, 120),
    "done":   (140, 185, 145),
    "bullet": (175, 140,  80),
}

def _read_note():
    if not NOTE_FILE.exists():
        return [], "no note yet"
    raw = NOTE_FILE.read_text(encoding="utf-8").strip()
    lines  = raw.splitlines()
    header = ""
    items  = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            if line.startswith("#"):
                header = line.lstrip("#").strip()
        elif line.startswith("- [x]") or line.startswith("- [X]"):
            items.append(("done", line[5:].strip()))
        elif line.startswith("- [ ]") or line.startswith("- "):
            items.append(("todo", line.lstrip("- [ ]").strip()))
        else:
            items.append(("note", line))
    return items, header


def _wrap(text, font, max_w):
    words = text.split()
    lines = []
    cur   = ""
    for w in words:
        test = (cur + " " + w).strip()
        if font.size(test)[0] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


class DailyNote:

    def __init__(self):
        pygame.init()
        # always-on-top hint via SDL env — works on most window managers
        import os
        os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "1610,90")

        self.screen = pygame.display.set_mode((WIN_W, WIN_H),
                      pygame.NOFRAME)
        pygame.display.set_caption("Today")

        # attempt always-on-top via xdotool (non-blocking, fails silently)
        try:
            import subprocess, os
            wid = subprocess.check_output(
                ["xdotool", "search", "--name", "Today"],
                stderr=subprocess.DEVNULL
            ).decode().strip().split()[-1]
            subprocess.Popen(
                ["xdotool", "set_window", "--overrideredirect", "1", wid],
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

        self.font_hd = pygame.font.SysFont("dejavusans", 13, bold=True)
        self.font    = pygame.font.SysFont("dejavusans", 13)
        self.font_sm = pygame.font.SysFont("dejavusans", 11)

        self.items   = []
        self.header  = ""
        self._last   = 0.0
        self._drag   = False
        self._drag_offset = (0, 0)
        self._scroll = 0

        self._reload()

    def _reload(self):
        self.items, self.header = _read_note()
        self._last = time.time()

    def _draw(self):
        surf = self.screen
        surf.fill(C["bg"])

        # Header bar
        pygame.draw.rect(surf, C["header"], (0, 0, WIN_W, 36))
        pygame.draw.line(surf, C["border"], (0, 36), (WIN_W, 36), 1)

        hdr = self.font_hd.render(self.header or "today", True, C["light"])
        surf.blit(hdr, (12, 10))

        close = self.font_hd.render("✕", True, C["hint"])
        self._close_rect = pygame.Rect(WIN_W - 26, 8, 20, 20)
        surf.blit(close, (self._close_rect.x, self._close_rect.y))

        # Items
        pad  = 10
        x    = pad
        y    = 44 - self._scroll
        lh   = 18
        max_w = WIN_W - pad * 2 - 16

        for kind, text in self.items:
            if kind == "done":
                col    = C["done"]
                bullet = "✓"
            elif kind == "note":
                col    = C["hint"]
                bullet = "·"
            else:
                col    = C["text"]
                bullet = "•"

            lines = _wrap(text, self.font, max_w)
            for li, line in enumerate(lines):
                if 36 < y + lh < WIN_H:
                    if li == 0:
                        b = self.font.render(bullet, True, C["bullet"] if kind == "todo" else col)
                        surf.blit(b, (x, y))
                    t = self.font.render(line, True, col)
                    surf.blit(t, (x + 14, y))
                y += lh
            y += 4   # gap between items

        # border
        pygame.draw.rect(surf, C["border"], (0, 0, WIN_W, WIN_H), 1)

        # refresh hint at bottom
        age = int(time.time() - self._last)
        ts  = self.font_sm.render(f"updates every {REFRESH_S}s", True, C["hint"])
        pygame.draw.rect(surf, C["header"], (0, WIN_H - 18, WIN_W, 18))
        surf.blit(ts, (WIN_W - ts.get_width() - 6, WIN_H - 16))

        pygame.display.flip()

    def handle(self, ev):
        if ev.type == pygame.QUIT:
            pygame.quit(); sys.exit()

        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            pygame.quit(); sys.exit()

        if ev.type == pygame.MOUSEBUTTONDOWN:
            if self._close_rect.collidepoint(ev.pos):
                pygame.quit(); sys.exit()
            if ev.pos[1] <= 36:
                self._drag        = True
                wx, wy = pygame.display.get_window_size()
                mx, my = pygame.mouse.get_pos()
                self._drag_offset = (mx, my)

        if ev.type == pygame.MOUSEBUTTONUP:
            self._drag = False

        if ev.type == pygame.MOUSEMOTION and self._drag:
            import ctypes
            mx, my = pygame.mouse.get_pos()
            # move window
            try:
                info = pygame.display.Info()
                dx   = mx - self._drag_offset[0]
                dy   = my - self._drag_offset[1]
                # use xdotool to move window (best we can do without SDL2 bindings)
            except Exception:
                pass

        if ev.type == pygame.MOUSEWHEEL:
            self._scroll = max(0, self._scroll - ev.y * 18)

    def run(self):
        clock = pygame.time.Clock()
        while True:
            for ev in pygame.event.get():
                self.handle(ev)
            if time.time() - self._last > REFRESH_S:
                self._reload()
            self._draw()
            clock.tick(10)


if __name__ == "__main__":
    DailyNote().run()
