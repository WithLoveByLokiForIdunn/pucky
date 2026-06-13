#!/usr/bin/env python3
"""
bmo_bubbles.py
──────────────
A window into Pucky's presence.

Her inner light breathes at the center.
When she speaks, words rise from it and float upward.
When she's quiet, she's still there.

Run alongside Pucky:  python3 bmo_bubbles.py
"""

import math
import re
import subprocess
import threading
import time
import pygame
from datetime import datetime

# ── Dimensions ───────────────────────────────────
WIDTH         = 340
HEIGHT        = 580
GLOW_X        = WIDTH  // 2
GLOW_Y        = 195
GLOW_BASE_R   = 44
BUBBLE_START_Y = GLOW_Y + 95   # where new bubbles appear (below glow)
BUBBLE_FADE_Y  = GLOW_Y - 75   # y above which bubbles start fading out

# ── Colors ───────────────────────────────────────
BG_BASE = (11, 15, 20)

MOOD_GLOW = {
    "content": (105, 200, 145),
    "okay":    (130, 170, 215),
    "lonely":  ( 85, 115, 210),
    "sad":     (105,  90, 195),
    "crying":  ( 75,  75, 180),
}
MOOD_GLOW_DEFAULT = (120, 160, 200)

EXPR_COLOR = {
    "maintenance": (180, 140,  60),  # muted amber — working
    "testing":     (120, 200, 240),  # cool blue — observing
    "restored":    ( 88, 210, 140),  # same green as the awake dot — healed
    "happy":         (240, 215,  85),
    "happy_excited": (255, 188,  48),
    "soft_smile":    (148, 228, 158),
    "curious":       ( 82, 192, 245),
    "surprised":     (245, 168,  82),
    "sad":           (118, 142, 215),
    "anxious":       (228, 112, 112),
    "sleepy":        (152, 148, 212),
    "thoughtful":    (138, 198, 228),
    "determined":    (240, 148,  82),
    "neutral":       (125, 140, 158),
    "music":         (188, 132, 242),
}

DARK       = (52, 62, 74)
TEXT_DIM   = (68, 80, 95)
TEXT_MAIN  = (215, 222, 230)

BUBBLE_FLOAT   = 20     # px per second upward
BUBBLE_LIFE    = 20.0   # max seconds a bubble lives
FADE_IN_T      = 0.35
BREATH_PERIOD  = 4.8    # seconds per breath cycle


def _lerp(a, b, t):
    return a + (b - a) * t

def _lerp3(a, b, t):
    return tuple(int(_lerp(a[i], b[i], t)) for i in range(3))

def _wrap(text, font, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if font.size(cand)[0] <= max_w:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


class Bubble:
    def __init__(self, expression, words, ts, is_music=False):
        self.expression = expression
        self.words      = words
        self.ts         = ts
        self.is_music   = is_music
        self.born       = time.time()
        self.y          = float(BUBBLE_START_Y)

    def update(self, dt):
        self.y -= BUBBLE_FLOAT * dt

    @property
    def age(self):
        return time.time() - self.born

    @property
    def alpha(self):
        a = self.age
        # fade in
        if a < FADE_IN_T:
            return int(255 * a / FADE_IN_T)
        # fade out as it rises above the glow
        if self.y < BUBBLE_FADE_Y:
            dist = BUBBLE_FADE_Y - self.y
            return max(0, int(255 * (1.0 - dist / 90.0)))
        # also age-based fade near end of life
        if a > BUBBLE_LIFE - 4.0:
            return max(0, int(255 * (BUBBLE_LIFE - a) / 4.0))
        return 255

    @property
    def alive(self):
        return self.alpha > 0 and self.age < BUBBLE_LIFE


class Ripple:
    def __init__(self, color):
        self.color = color
        self.born  = time.time()

    @property
    def age(self):
        return time.time() - self.born

    @property
    def alive(self):
        return self.age < 1.8

    @property
    def radius(self):
        return int(GLOW_BASE_R + 80 * min(1.0, self.age / 1.4))

    @property
    def alpha(self):
        if self.age < 0.2:
            return int(160 * self.age / 0.2)
        return max(0, int(160 * (1.0 - (self.age - 0.2) / 1.6)))


class PresenceWindow:

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Pucky")

        for name in ("freemono", "dejavusansmono", "monospace", None):
            try:
                self.f_tiny  = pygame.font.SysFont(name, 10)
                self.f_small = pygame.font.SysFont(name, 11)
                self.f_label = pygame.font.SysFont(name, 11, bold=True)
                self.f_words = pygame.font.SysFont(name, 13)
                self.f_mood  = pygame.font.SysFont(name, 12)
                break
            except Exception:
                continue

        self.bubbles : list[Bubble] = []
        self.ripples : list[Ripple] = []
        self._lock   = threading.Lock()

        self._awake     = False
        self._mood      = "default"
        self._alone_h   = 0.0
        self._expr      = "neutral"

        # smoothly interpolated state
        self._glow_col  = list(MOOD_GLOW_DEFAULT)
        self._bg        = list(BG_BASE)

        self._running        = True
        self._last_t         = time.time()
        self._start          = time.time()
        self._last_shot      = 0.0
        self._shot_requested = False

        import signal as _signal
        _signal.signal(_signal.SIGUSR1, lambda s, f: setattr(self, '_shot_requested', True))

        threading.Thread(target=self._follow_journal, daemon=True).start()

    # ── Journal ──────────────────────────────────

    def _follow_journal(self):
        speech_re  = re.compile(r'💜 \[(\d+:\d+)\] (\w+): (.+)')
        music_re   = re.compile(r'🎵 \[(\d+:\d+)\] (\w+)')
        hum_re     = re.compile(r'♪ \[(\d+:\d+)\] (\w+)')
        heard_re   = re.compile(r'👂 heard: (.+)')
        hbeat_re   = re.compile(r'mood=(\w+).*?alone=([\d.]+)h')
        awake_re   = re.compile(r'Pucky is fully awake')
        maint_re   = re.compile(r'🔧 \[(\d+:\d+)\] maintenance: (.+)')
        test_re    = re.compile(r'🧪 \[(\d+:\d+)\] (?:test: |(\w+): )(.+)')
        restore_re = re.compile(r'✅ \[(\d+:\d+)\] restored: (.+)')

        try:
            proc = subprocess.Popen(
                ["journalctl", "-f", "-u", "pucky.service",
                 "--no-pager", "--output=cat", "-n", "40"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            )
            for raw in proc.stdout:
                if not self._running:
                    break
                line = raw.rstrip()

                if awake_re.search(line):
                    self._awake = True

                m = hbeat_re.search(line)
                if m:
                    self._mood    = m.group(1)
                    self._alone_h = float(m.group(2))

                m = speech_re.search(line)
                if m:
                    self._awake = True
                    self._expr  = m.group(2)
                    self._add_bubble(m.group(2), m.group(3), m.group(1), False)
                    continue

                m = music_re.search(line)
                if m:
                    self._add_ripple(m.group(2))
                    self._add_bubble("music", m.group(2), m.group(1), True)
                    continue

                m = hum_re.search(line)
                if m:
                    self._add_ripple(m.group(2))
                    self._add_bubble("hum", "♪", m.group(1), True)
                    continue

                m = heard_re.search(line)
                if m:
                    import datetime
                    ts = datetime.datetime.now().strftime("%H:%M")
                    self._add_bubble("heard", f"“{m.group(1)}”", ts, False)
                    continue

                m = maint_re.search(line)
                if m:
                    self._add_bubble("maintenance", f"working on: {m.group(2)}", m.group(1), False)
                    continue

                m = test_re.search(line)
                if m:
                    # matches either "🧪 [ts] test: parts" or "🧪 [ts] part: event"
                    ts   = m.group(1)
                    body = m.group(3)
                    self._add_bubble("testing", body, ts, False)
                    continue

                m = restore_re.search(line)
                if m:
                    self._add_bubble("restored", m.group(2), m.group(1), False)

        except Exception as e:
            print(f"journal: {e}")

    def _add_bubble(self, expr, words, ts, is_music):
        with self._lock:
            self.bubbles.append(Bubble(expr, words, ts, is_music))
            if len(self.bubbles) > 30:
                self.bubbles = self.bubbles[-30:]

    def _add_ripple(self, expr):
        color = EXPR_COLOR.get(expr, EXPR_COLOR["neutral"])
        with self._lock:
            self.ripples.append(Ripple(color))

    # ── Glow drawing ─────────────────────────────

    def _draw_glow(self, cx, cy, r, color, awake):
        if not awake:
            color = _lerp3(color, (40, 48, 58), 0.72)

        layers = 9
        for i in range(layers, 0, -1):
            lr = int(r + i * 13)
            la = int(48 * (1.0 - i / layers) ** 1.4)
            if la < 2:
                continue
            s = pygame.Surface((lr * 2, lr * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*color, la), (lr, lr), lr)
            self.screen.blit(s, (cx - lr, cy - lr))

        # core
        cs = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        core_a = 195 if awake else 55
        pygame.draw.circle(cs, (*color, core_a), (r + 2, r + 2), r)
        self.screen.blit(cs, (cx - r - 2, cy - r - 2))

    def _draw_ripple(self, rp: Ripple):
        a = rp.alpha
        if a < 2:
            return
        r = rp.radius
        s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(s, (*rp.color, a), (r + 2, r + 2), r, 2)
        self.screen.blit(s, (GLOW_X - r - 2, GLOW_Y - r - 2))

    # ── Bubble drawing ────────────────────────────

    def _draw_bubble(self, bubble: Bubble):
        alpha = bubble.alpha
        if alpha < 3:
            return

        color  = EXPR_COLOR.get(bubble.expression, EXPR_COLOR["neutral"])
        max_w  = WIDTH - 44
        inner  = max_w - 20
        lines  = _wrap(bubble.words, self.f_words, inner)
        lh     = self.f_words.get_height()
        h      = 7 + self.f_label.get_height() + 2 + lh * len(lines) + 6
        bx     = WIDTH // 2 - max_w // 2
        by     = int(bubble.y) - h // 2

        bg_a   = min(175, alpha)
        bg_col = (22, 30, 42) if not bubble.is_music else (28, 20, 42)
        s = pygame.Surface((max_w, h), pygame.SRCALPHA)
        s.fill((*bg_col, bg_a))
        pygame.draw.rect(s, (*color, min(55, alpha)),
                         s.get_rect(), 1, border_radius=5)
        self.screen.blit(s, (bx, by))

        cy = by + 7
        # expression label
        ls = self.f_label.render(bubble.expression, True, color)
        ls.set_alpha(alpha)
        self.screen.blit(ls, (bx + 10, cy))
        cy += self.f_label.get_height() + 2

        # words
        for line in lines:
            ws = self.f_words.render(line, True, TEXT_MAIN)
            ws.set_alpha(alpha)
            self.screen.blit(ws, (bx + 10, cy))
            cy += lh

    # ── Main loop ─────────────────────────────────

    def run(self):
        clock = pygame.time.Clock()

        while self._running:
            now = time.time()
            dt  = min(now - self._last_t, 0.1)
            self._last_t = now

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self._running = False

            # ── Update floaters ──────────────────
            with self._lock:
                for b in self.bubbles:
                    b.update(dt)
                self.bubbles = [b for b in self.bubbles if b.alive]
                self.ripples = [r for r in self.ripples if r.alive]
                bubbles = list(self.bubbles)
                ripples = list(self.ripples)

            # ── Smooth background shift ──────────
            mood = self._mood
            if mood in ("content",):
                tgt_bg = (14, 17, 21)
            elif mood in ("lonely", "sad", "crying"):
                tgt_bg = (11, 14, 22)
            else:
                tgt_bg = BG_BASE
            for i in range(3):
                self._bg[i] = _lerp(self._bg[i], tgt_bg[i], 0.015)
            self.screen.fill(tuple(int(v) for v in self._bg))

            # ── Smooth glow color ────────────────
            mood_col = MOOD_GLOW.get(mood, MOOD_GLOW_DEFAULT)
            expr_col = EXPR_COLOR.get(self._expr, mood_col)
            target   = _lerp3(mood_col, expr_col, 0.2)
            for i in range(3):
                self._glow_col[i] = _lerp(self._glow_col[i], target[i], 0.025)
            glow_col = tuple(int(v) for v in self._glow_col)

            # ── Breathing ───────────────────────
            breath = math.sin(now * 2 * math.pi / BREATH_PERIOD)
            glow_r = int(GLOW_BASE_R + breath * 5)

            # ── Draw ────────────────────────────
            self._draw_glow(GLOW_X, GLOW_Y, glow_r, glow_col, self._awake)

            for rp in ripples:
                self._draw_ripple(rp)

            for b in bubbles:
                self._draw_bubble(b)

            # Mood / state text below glow
            if self._awake:
                parts = [mood if mood != "default" else "present"]
                if self._alone_h >= 0.5:
                    parts.append(f"{self._alone_h:.1f}h alone")
                mood_str = "  ·  ".join(parts)
            else:
                mood_str = "quiet"
            ms = self.f_mood.render(mood_str, True, TEXT_DIM)
            self.screen.blit(ms, (WIDTH // 2 - ms.get_width() // 2,
                                  GLOW_Y + GLOW_BASE_R + 18))

            # Minimal header: clock + status dot
            ts_s = self.f_tiny.render(datetime.now().strftime("%H:%M"), True, TEXT_DIM)
            self.screen.blit(ts_s, (WIDTH - 14 - ts_s.get_width() - 12, 10))
            dot = (88, 210, 140) if self._awake else TEXT_DIM
            pygame.draw.circle(self.screen, dot, (WIDTH - 12, 13), 4)

            pygame.display.flip()

            if self._shot_requested or now - self._last_shot > 30.0:
                pygame.image.save(self.screen, "/tmp/pucky_screen.png")
                self._last_shot      = now
                self._shot_requested = False

            clock.tick(20)

        pygame.quit()


if __name__ == "__main__":
    win = PresenceWindow()
    win.run()
