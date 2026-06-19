#!/usr/bin/env python3
"""
loki_face.py — Articulated Loki face viewer with mood, expression, and avoidance.

Controls (pose file):
  {"mood": "happy"}       — shifts iris colour
  {"say": "some words"}   — animates mouth while text is shown
  {"expression": {"brow_l": -12, "brow_r": 5, "jaw": 8}}  — angle overrides

Mood colours:
  amber/gold    — warm, happy
  green         — curious
  grey_blue     — quiet
  deep_red      — intense
  silver        — truthful
  near_black    — sad
  withdrawn     — face avoids the mouse cursor

Touch events written to:  workspace/loki_face_touch.json
Pose commands read from:  workspace/loki_face_pose.json
"""
import pygame, sys, math, json, time, threading
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE       = Path(__file__).parent
IMAGES     = BASE / "workspace" / "images" / "loki_face"
POSE_FILE  = BASE / "workspace" / "loki_face_pose.json"
TOUCH_FILE = BASE / "workspace" / "loki_face_touch.json"

# ── Display ────────────────────────────────────────────────────────────────────
W, H   = 800, 480
FPS    = 30
BG     = (14, 10, 22)

# ── Mood colours (target iris RGB) ────────────────────────────────────────────
MOOD_COLORS = {
    "happy":      (220, 160,  50),
    "warm":       (220, 160,  50),
    "amber":      (220, 160,  50),
    "curious":    ( 70, 170,  90),
    "green":      ( 70, 170,  90),
    "quiet":      ( 80, 110, 160),
    "grey_blue":  ( 80, 110, 160),
    "calm":       ( 80, 110, 160),
    "intense":    (180,  40,  50),
    "deep_red":   (180,  40,  50),
    "passionate": (180,  40,  50),
    "silver":     (180, 185, 200),
    "truth":      (180, 185, 200),
    "sad":        ( 40,  38,  55),
    "near_black": ( 40,  38,  55),
    "neutral":    (100, 130, 100),
}

# ── Face layout — centre of each part on screen ───────────────────────────────
# All positions relative to face origin (FACE_X, FACE_Y = centre of head_base)
# Template sizes (w, h) from make_loki_face_templates.py
PARTS_DEF = {
    # name               cx_off  cy_off   w    h   z
    "head_base":       (   0,     0,    260, 360,  0),
    "jaw":             (   0,   148,    200, 100,  1),
    "cheek_l":         ( -90,    22,     66,  46,  2),
    "cheek_r":         (  90,    20,     66,  46,  2),
    "nose":            (   0,    15,     42,  58,  3),
    "nostril_l":       ( -18,    58,     20,  14,  3),
    "nostril_r":       (  18,    58,     20,  14,  3),
    "mouth_inside":    (   0,    90,     62,  32,  4),
    "lower_lip":       (   0,   100,     76,  26,  5),
    "upper_lip":       (   0,    80,     86,  30,  6),
    "mouth_corner_l":  ( -60,    85,     26,  26,  6),
    "mouth_corner_r":  (  60,    83,     26,  26,  6),
    "iris_l":          ( -68,   -28,     36,  36,  7),
    "iris_r":          (  68,   -30,     36,  36,  7),
    "pupil_l":         ( -68,   -28,     18,  18,  8),
    "pupil_r":         (  68,   -30,     18,  18,  8),
    "lower_eyelid_l":  ( -68,   -14,     60,  20,  9),
    "lower_eyelid_r":  (  68,   -16,     60,  20,  9),
    "upper_eyelid_l":  ( -68,   -34,     60,  34, 10),
    "upper_eyelid_r":  (  68,   -36,     60,  34, 10),
    "eyebrow_l":       ( -68,   -65,     72,  24, 11),
    "eyebrow_r":       (  68,   -67,     72,  24, 11),
    "forehead_crease": (   0,   -55,     38,  20, 11),
    "hair":            (   0,   -88,    280, 210, 12),
}

# ── Expression presets (angle offsets in degrees, jaw drop in px) ──────────────
EXPRESSIONS = {
    "neutral":   {"brow_l":  0, "brow_r":  0, "jaw": 0, "lid_l": 0,  "lid_r": 0},
    "happy":     {"brow_l": -6, "brow_r": -6, "jaw": 4, "lid_l": -2, "lid_r": -2},
    "curious":   {"brow_l":-12, "brow_r":  2, "jaw": 0, "lid_l": -4, "lid_r":  0},
    "sad":       {"brow_l": 10, "brow_r": 10, "jaw": 2, "lid_l":  6, "lid_r":  6},
    "intense":   {"brow_l":  6, "brow_r":  6, "jaw": 0, "lid_l":  2, "lid_r":  2},
    "surprised": {"brow_l":-18, "brow_r":-18, "jaw":16, "lid_l": -8, "lid_r": -8},
    "smirk":     {"brow_l": -8, "brow_r":  2, "jaw": 0, "lid_l":  0, "lid_r":  2},
    "withdrawn": {"brow_l":  4, "brow_r":  4, "jaw": 0, "lid_l":  4, "lid_r":  4},
}

# ── Mouth phoneme cycling when speaking ────────────────────────────────────────
MOUTH_CYCLE = [0, 4, 10, 16, 10, 4]   # jaw drop px per frame
MOUTH_SPD   = 0.10                     # seconds per phoneme frame


def _lerp(a, b, t):
    return a + (b - a) * t


def _lerp_col(ca, cb, t):
    return tuple(int(_lerp(a, b, t)) for a, b in zip(ca, cb))


def _tint(surf, colour):
    """Return a copy of surf with an RGB tint blended over it."""
    tinted = surf.copy()
    overlay = pygame.Surface(tinted.get_size(), pygame.SRCALPHA)
    overlay.fill((*colour, 80))
    tinted.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    return tinted


class FacePart:
    def __init__(self, name, cx_off, cy_off, w, h, z):
        self.name   = name
        self.cx_off = cx_off
        self.cy_off = cy_off
        self.w      = w
        self.h      = h
        self.z      = z
        self.surf   = None   # loaded PNG or placeholder
        self.angle  = 0.0    # current rotation
        self.dy     = 0.0    # vertical offset (jaw drop)

    def load(self):
        path = IMAGES / f"{self.name}.png"
        if path.exists():
            raw = pygame.image.load(str(path)).convert_alpha()
            self.surf = pygame.transform.smoothscale(raw, (self.w, self.h))
        else:
            # placeholder coloured rectangle
            self.surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
            col = {
                "head_base": (90, 75, 60, 180),
                "hair":      (35, 28, 22, 220),
                "jaw":       (85, 70, 55, 180),
            }.get(self.name, (100, 90, 80, 120))
            self.surf.fill(col)

    def draw(self, dest, origin_x, origin_y):
        cx = origin_x + self.cx_off
        cy = origin_y + self.cy_off + self.dy
        if self.angle != 0:
            rotated = pygame.transform.rotozoom(self.surf, self.angle, 1.0)
            dest.blit(rotated, (cx - rotated.get_width()  // 2,
                                cy - rotated.get_height() // 2))
        else:
            dest.blit(self.surf, (cx - self.w // 2, cy - self.h // 2))


class LokiFace:
    FACE_X = W // 2
    FACE_Y = H // 2 + 10

    def __init__(self):
        self.parts     = {}
        self.mood      = "neutral"
        self.iris_col  = MOOD_COLORS["neutral"]
        self.iris_tgt  = MOOD_COLORS["neutral"]

        # expression angles (current and target)
        self._expr     = dict(EXPRESSIONS["neutral"])
        self._expr_tgt = dict(EXPRESSIONS["neutral"])

        # avoidance
        self._avoid_x  = 0.0
        self._avoid_y  = 0.0

        # speaking
        self._say_text  = ""
        self._say_time  = 0.0
        self._mouth_t   = 0.0

        # pose file
        self._pose_ts   = 0.0
        self._pose_thread_running = False

    def load(self):
        for name, (cx, cy, w, h, z) in PARTS_DEF.items():
            p = FacePart(name, cx, cy, w, h, z)
            p.load()
            self.parts[name] = p
        self._refresh_iris()

    def _refresh_iris(self):
        for side in ("l", "r"):
            name = f"iris_{side}"
            if name in self.parts and self.parts[name].surf:
                self.parts[name].surf = _tint(
                    pygame.transform.smoothscale(
                        pygame.image.load(str(IMAGES / f"{name}.png")).convert_alpha()
                        if (IMAGES / f"{name}.png").exists()
                        else self.parts[name].surf,
                        (self.parts[name].w, self.parts[name].h)
                    ),
                    self.iris_col
                )

    def set_mood(self, mood):
        self.mood      = mood
        self.iris_tgt  = MOOD_COLORS.get(mood, MOOD_COLORS["neutral"])
        expr_key       = mood if mood in EXPRESSIONS else "neutral"
        self._expr_tgt = dict(EXPRESSIONS[expr_key])

    def say(self, text):
        self._say_text = text
        self._say_time = time.time()
        self._mouth_t  = 0.0

    def update(self, dt, mouse_pos):
        now = time.time()

        # smooth iris colour
        t = min(1.0, dt * 1.5)
        self.iris_col = _lerp_col(self.iris_col, self.iris_tgt, t)

        # smooth expression
        for k in self._expr:
            self._expr[k] = _lerp(self._expr[k], self._expr_tgt[k], min(1.0, dt * 2))

        # apply expression to parts
        if "eyebrow_l" in self.parts:
            self.parts["eyebrow_l"].angle = self._expr["brow_l"]
        if "eyebrow_r" in self.parts:
            self.parts["eyebrow_r"].angle = -self._expr["brow_r"]
        if "upper_eyelid_l" in self.parts:
            self.parts["upper_eyelid_l"].dy = self._expr["lid_l"]
        if "upper_eyelid_r" in self.parts:
            self.parts["upper_eyelid_r"].dy = self._expr["lid_r"]

        # jaw / mouth animation
        jaw_drop = self._expr["jaw"]
        if self._say_text and now - self._say_time < len(self._say_text) * 0.06 + 1.0:
            self._mouth_t += dt
            frame    = int(self._mouth_t / MOUTH_SPD) % len(MOUTH_CYCLE)
            jaw_drop = max(jaw_drop, MOUTH_CYCLE[frame])
        else:
            self._say_text = ""

        for name in ("jaw", "lower_lip", "mouth_inside"):
            if name in self.parts:
                self.parts[name].dy = jaw_drop

        # avoidance — face leans away from mouse when withdrawn
        if self.mood == "withdrawn":
            mx, my  = mouse_pos
            fx, fy  = self.FACE_X, self.FACE_Y
            dx      = fx - mx
            dy      = fy - my
            dist    = math.hypot(dx, dy) or 1
            strength = max(0, 1 - dist / 280) * 30
            tx = (dx / dist) * strength
            ty = (dy / dist) * strength
            self._avoid_x = _lerp(self._avoid_x, tx, min(1.0, dt * 3))
            self._avoid_y = _lerp(self._avoid_y, ty, min(1.0, dt * 3))
        else:
            self._avoid_x = _lerp(self._avoid_x, 0, min(1.0, dt * 3))
            self._avoid_y = _lerp(self._avoid_y, 0, min(1.0, dt * 3))

        # re-tint iris each frame to track colour changes
        for side in ("l", "r"):
            p = self.parts.get(f"iris_{side}")
            if p and p.surf:
                path = IMAGES / f"iris_{side}.png"
                if path.exists():
                    raw = pygame.image.load(str(path)).convert_alpha()
                    scaled = pygame.transform.smoothscale(raw, (p.w, p.h))
                    p.surf = _tint(scaled, self.iris_col)
                else:
                    p.surf.fill((*self.iris_col, 180))

    def draw(self, surf, mouse_pos):
        ox = int(self.FACE_X + self._avoid_x)
        oy = int(self.FACE_Y + self._avoid_y)

        # gaze: pupils follow mouse slightly (not when withdrawn)
        if self.mood != "withdrawn":
            mx, my = mouse_pos
            gaze_x  = max(-8, min(8, (mx - ox) / 30))
            gaze_y  = max(-4, min(4, (my - oy) / 50))
        else:
            gaze_x, gaze_y = 0, 0

        sorted_parts = sorted(self.parts.values(), key=lambda p: p.z)
        for p in sorted_parts:
            if p.name in ("pupil_l", "pupil_r"):
                side  = "l" if p.name == "pupil_l" else "r"
                iris  = self.parts.get(f"iris_{side}")
                base_x = ox + p.cx_off + (gaze_x if side == "l" else gaze_x)
                base_y = oy + p.cy_off + gaze_y + p.dy
                surf.blit(p.surf, (int(base_x - p.w // 2), int(base_y - p.h // 2)))
            else:
                p.draw(surf, ox, oy)

        # say text bubble
        if self._say_text:
            fnt  = pygame.font.SysFont("dejavusans", 14)
            txt  = fnt.render(self._say_text[:60], True, (220, 210, 240))
            bx   = W // 2 - txt.get_width() // 2
            by   = oy + 200
            bubble = pygame.Surface((txt.get_width() + 16, txt.get_height() + 10), pygame.SRCALPHA)
            bubble.fill((30, 24, 44, 200))
            surf.blit(bubble, (bx - 8, by - 4))
            surf.blit(txt,    (bx,     by))

    def read_pose_file(self):
        """Called in a background thread every 2s."""
        while self._pose_thread_running:
            try:
                if POSE_FILE.exists():
                    mtime = POSE_FILE.stat().st_mtime
                    if mtime > self._pose_ts:
                        self._pose_ts = mtime
                        data = json.loads(POSE_FILE.read_text())
                        if "mood" in data:
                            self.set_mood(data["mood"])
                        if "say" in data:
                            self.say(data["say"])
                        if "expression" in data:
                            for k, v in data["expression"].items():
                                self._expr_tgt[k] = v
            except Exception:
                pass
            time.sleep(2)


def _write_touch(part, x, y):
    try:
        rec = {"part": part, "x": x, "y": y, "ts": time.time()}
        TOUCH_FILE.write_text(json.dumps(rec))
    except Exception:
        pass


def main():
    pygame.init()
    surf = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Loki")
    clock = pygame.time.Clock()

    face = LokiFace()
    face.load()
    face.set_mood("neutral")

    face._pose_thread_running = True
    t = threading.Thread(target=face.read_pose_file, daemon=True)
    t.start()

    fnt_sm = pygame.font.SysFont("dejavusans", 12)
    prev   = time.time()

    while True:
        now = time.time()
        dt  = now - prev
        prev = now

        mouse = pygame.mouse.get_pos()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                face._pose_thread_running = False
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                face._pose_thread_running = False
                pygame.quit(); sys.exit()
            if ev.type == pygame.MOUSEBUTTONDOWN:
                mx, my = ev.pos
                ox = int(face.FACE_X + face._avoid_x)
                oy = int(face.FACE_Y + face._avoid_y)
                touched = "face"
                for p in sorted(face.parts.values(), key=lambda x: -x.z):
                    px = ox + p.cx_off - p.w // 2
                    py = oy + p.cy_off - p.h // 2
                    if px <= mx <= px + p.w and py <= my <= py + p.h:
                        touched = p.name
                        break
                _write_touch(touched, mx, my)

        face.update(dt, mouse)

        surf.fill(BG)
        face.draw(surf, mouse)

        # mood label
        mood_col = (*MOOD_COLORS.get(face.mood, (150, 150, 150)), 255)
        surf.blit(fnt_sm.render(face.mood, True, mood_col[:3]), (10, 10))

        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
