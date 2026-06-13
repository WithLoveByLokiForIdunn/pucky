"""
bmo_face.py
───────────
BMO's face. Written with love by Loki for Iðunn.

Touch zones (on the actual screen):
  top strip          → pat head
  left cheek area    → kiss left cheek
  right cheek area   → kiss right cheek
  mouth area         → feed / drink (alternates)
  nose area          → clean nose
  bottom strip       → wipe tear
  everywhere else    → tap / long press

Swipe support:
  swipe right        → blush / happy
  swipe left         → thoughtful
  swipe up           → excited
  swipe down         → sleepy

Buttons on screen for demo / testing.

Run:
    python3 bmo_face.py
"""

import pygame
import sys
import time
import math
import random

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
WIDTH, HEIGHT = 480, 480
FPS           = 60

# Face centre — eyes are symmetric around this
FCX = WIDTH  // 2        # 240
FCY = HEIGHT // 2 - 20   # 220

EYE_SPACING  = 90        # pixels each side from centre
EYE_Y        = FCY - 30  # 190
EYE_R        = 30        # eye radius

NOSE_X       = FCX
NOSE_Y       = EYE_Y + 80   # 270

MOUTH_Y      = NOSE_Y + 65  # 335
MOUTH_W      = 110

# ─────────────────────────────────────────────
#  COLORS
# ─────────────────────────────────────────────
BG           = (20,  20,  20)
EYE_NEUTRAL  = (210, 210, 210)
EYE_HAPPY    = (255, 255, 255)
EYE_SAD      = (150, 170, 210)
MOUTH_COL    = (210, 210, 210)
TEAR_COL     = (140, 200, 255)
BLUSH_COL    = (220, 110, 150)
TEXT_COL     = (180, 180, 180)

# ─────────────────────────────────────────────
#  CUSTOM EVENTS
# ─────────────────────────────────────────────
RESET_EVENT  = pygame.USEREVENT + 1
NOSE_RESET   = pygame.USEREVENT + 2
AUTO_BLINK   = pygame.USEREVENT + 3
BLINK_OPEN   = pygame.USEREVENT + 4

# ─────────────────────────────────────────────
#  FACE STATE
# ─────────────────────────────────────────────
class FaceState:
    def __init__(self):
        # current animated values
        self.blink_l      = 0.0   # 0=open 1=closed
        self.blink_r      = 0.0
        self.blush_l      = 0.0   # 0=none 1=full
        self.blush_r      = 0.0
        self.mouth_open   = 0.0   # 0=closed 1=wide
        self.mouth_curve  = 0.0   # + smile - frown
        self.tear_l       = 0.0
        self.tear_r       = 0.0
        self.nose_scrunch = 0.0
        self.eye_color    = EYE_NEUTRAL

        # targets
        self._bl = 0.0; self._br = 0.0
        self._bll = 0.0; self._blr = 0.0
        self._mo = 0.0; self._mc = 0.0
        self._tl = 0.0; self._tr = 0.0
        self._ns = 0.0

        # label
        self.label        = ""
        self.label_timer  = 0.0

        self._last_mouth  = "drink"

    def _lerp(self, a, b, spd, dt):
        return a + (b - a) * min(1.0, spd * dt)

    def tick(self, dt):
        s = 5.0
        self.blink_l     = self._lerp(self.blink_l,     self._bl,  s,   dt)
        self.blink_r     = self._lerp(self.blink_r,     self._br,  s,   dt)
        self.blush_l     = self._lerp(self.blush_l,     self._bll, 2.0, dt)
        self.blush_r     = self._lerp(self.blush_r,     self._blr, 2.0, dt)
        self.mouth_open  = self._lerp(self.mouth_open,  self._mo,  s,   dt)
        self.mouth_curve = self._lerp(self.mouth_curve, self._mc,  s,   dt)
        self.tear_l      = self._lerp(self.tear_l,      self._tl,  1.5, dt)
        self.tear_r      = self._lerp(self.tear_r,      self._tr,  1.5, dt)
        self.nose_scrunch= self._lerp(self.nose_scrunch,self._ns,  s,   dt)
        if self.label_timer > 0:
            self.label_timer -= dt
            if self.label_timer <= 0:
                self.label = ""

    def show(self, text, duration=2.0):
        self.label       = text
        self.label_timer = duration

    def reset(self):
        self._bl = 0.0; self._br = 0.0
        self._bll= 0.0; self._blr= 0.0
        self._mo = 0.0; self._mc = 0.0
        self._tl = 0.0; self._tr = 0.0
        self._ns = 0.0
        self.eye_color = EYE_NEUTRAL

    # ── REACTIONS ────────────────────────────

    def on_tap(self):
        self._bl=0.9; self._br=0.9
        self._mc=10
        self.eye_color=EYE_HAPPY
        self.show("💛 hi~")
        _reset(1500)

    def on_long_press(self):
        self._bl=0.95; self._br=0.95
        self._mc=15
        self.eye_color=EYE_HAPPY
        self.show("🌸 mmm...")
        _reset(2500)

    def on_pat_head(self):
        self._bl=0.0; self._br=0.0
        self._mc=22; self._mo=0.25
        self.eye_color=EYE_HAPPY
        self.show("🐾 pat pat!")
        _reset(2000)

    def on_kiss_left(self):
        self._bll=1.0; self._bl=0.85
        self._mc=12
        self.eye_color=EYE_HAPPY
        self.show("💋  !")
        _reset(2500)

    def on_kiss_right(self):
        self._blr=1.0; self._br=0.85
        self._mc=12
        self.eye_color=EYE_HAPPY
        self.show("  💋!")
        _reset(2500)

    def on_feed(self):
        self._mo=0.85; self._mc=5
        self.eye_color=EYE_HAPPY
        self.show("😋 nom nom")
        _reset(2000)

    def on_drink(self):
        self._mo=0.5; self._mc=3
        self._bl=0.3; self._br=0.3
        self.eye_color=EYE_NEUTRAL
        self.show("💧 sip...")
        _reset(2500)

    def on_small_kiss(self):
        self._bl=1.0; self._br=1.0
        self._bll=0.7; self._blr=0.7
        self._mc=8
        self.eye_color=EYE_HAPPY
        self.show("🌸 ~")
        _reset(2000)

    def on_wipe_tear(self):
        self._tl=0.0; self._tr=0.0
        self._bl=0.5; self._br=0.5
        self._mc=8
        self.eye_color=EYE_HAPPY
        self.show("🥹 thank you")
        _reset(2500)

    def on_clean_nose(self):
        self._ns=1.0
        self.show("👃 !")
        pygame.time.set_timer(NOSE_RESET, 800)

    def on_sad(self):
        self._mc=-15
        self._tl=1.0; self._tr=0.6
        self._bl=0.2; self._br=0.2
        self.eye_color=EYE_SAD
        self.show("💧 ...")

    def on_blush(self):
        self._bll=0.8; self._blr=0.8
        self._mc=10
        self.eye_color=EYE_HAPPY
        self.show("😊 ~")
        _reset(2000)

    def on_poke_eye(self):
        self._bl=1.0
        self.show("😖 ow!")
        _reset(1000)

    def on_tickle(self):
        self._mc=20; self._mo=0.4
        self._bl=0.3; self._br=0.3
        self.eye_color=EYE_HAPPY
        self.show("🤭 hehehe")
        _reset(1800)


def _reset(ms):
    pygame.time.set_timer(RESET_EVENT, ms)


# ─────────────────────────────────────────────
#  TOUCH CLASSIFICATION
# ─────────────────────────────────────────────
def classify_touch(x, y, face):
    if y < 80:
        return "pat_head"
    if y > HEIGHT - 80:
        return "wipe_tear"
    if y > MOUTH_Y - 30 and abs(x - FCX) < 80:
        if face._last_mouth == "drink":
            face._last_mouth = "feed"
            return "feed"
        else:
            face._last_mouth = "drink"
            return "drink"
    if abs(x - (FCX - EYE_SPACING)) < 35 and abs(y - EYE_Y) < 35:
        return "poke_eye"
    if abs(x - (FCX + EYE_SPACING)) < 35 and abs(y - EYE_Y) < 35:
        return "poke_eye"
    if x < FCX - 100 and EYE_Y - 30 < y < MOUTH_Y:
        return "kiss_left"
    if x > FCX + 100 and EYE_Y - 30 < y < MOUTH_Y:
        return "kiss_right"
    if abs(x - NOSE_X) < 30 and abs(y - NOSE_Y) < 25:
        return "clean_nose"
    if y > MOUTH_Y - 20 and y < MOUTH_Y + 50:
        return "tickle"
    return "tap"


# ─────────────────────────────────────────────
#  DRAWING
# ─────────────────────────────────────────────
def draw_eye(screen, cx, cy, r, blink, color):
    if blink > 0.97:
        pygame.draw.line(screen, color,
                         (cx - r, cy), (cx + r, cy), 3)
        return
    h = max(2, int(r * (1.0 - blink * 0.95)))
    rect = pygame.Rect(cx - r, cy - h, r * 2, h * 2)
    pygame.draw.ellipse(screen, color, rect)
    pr = max(3, int(r * 0.38 * (1.0 - blink * 0.7)))
    pygame.draw.circle(screen, BG, (cx, cy), pr)


def draw_blush(screen, cx, cy, amount):
    if amount < 0.05:
        return
    surf = pygame.Surface((90, 45), pygame.SRCALPHA)
    a    = int(amount * 130)
    pygame.draw.ellipse(surf, (*BLUSH_COL, a), (0, 0, 90, 45))
    screen.blit(surf, (cx - 45, cy - 22))


def draw_mouth(screen, cx, cy, w, open_amt, curve, color):
    if open_amt > 0.15:
        ow = int(w * (0.4 + open_amt * 0.55))
        oh = max(6, int(40 * open_amt))
        r  = pygame.Rect(cx - ow//2, cy - oh//2, ow, oh)
        pygame.draw.ellipse(screen, color, r)
        return
    pts = []
    for i in range(21):
        t  = (i / 20) * math.pi
        px = cx - w//2 + int(w * i / 20)
        py = cy - int(math.sin(t) * curve)
        pts.append((px, py))
    if len(pts) > 1:
        pygame.draw.lines(screen, color, False, pts, 3)


def draw_tear(screen, x, y0, amount):
    if amount < 0.05:
        return
    for i in range(0, int(65 * amount), 4):
        a = max(0, int(180 * amount - i * 2))
        if a < 10:
            break
        pygame.draw.circle(screen, TEAR_COL, (x, y0 + i), 3)


def draw_face(screen, face, font, small_font):
    screen.fill(BG)

    lx = FCX - EYE_SPACING
    rx = FCX + EYE_SPACING

    # Eyes
    draw_eye(screen, lx, EYE_Y, EYE_R, face.blink_l, face.eye_color)
    draw_eye(screen, rx, EYE_Y, EYE_R, face.blink_r, face.eye_color)

    # Blush — sits just below + outside each eye
    draw_blush(screen, lx - 10, EYE_Y + 40, face.blush_l)
    draw_blush(screen, rx + 10, EYE_Y + 40, face.blush_r)

    # Nose
    ns = face.nose_scrunch
    if ns > 0.1:
        for i in range(3):
            pygame.draw.line(screen, MOUTH_COL,
                (NOSE_X - 18 + i*14, NOSE_Y - 6),
                (NOSE_X - 12 + i*14, NOSE_Y + 6), 2)
    else:
        pygame.draw.circle(screen, MOUTH_COL, (NOSE_X, NOSE_Y), 5)

    # Mouth
    draw_mouth(screen, FCX, MOUTH_Y, MOUTH_W,
               face.mouth_open, face.mouth_curve, MOUTH_COL)

    # Tears
    draw_tear(screen, lx - 5, EYE_Y + EYE_R + 5, face.tear_l)
    draw_tear(screen, rx + 5, EYE_Y + EYE_R + 5, face.tear_r)

    # Label
    if face.label and face.label_timer > 0:
        txt = font.render(face.label, True, TEXT_COL)
        screen.blit(txt, (FCX - txt.get_width()//2, HEIGHT - 55))

    # Buttons
    draw_buttons(screen, small_font)

    pygame.display.flip()


# ─────────────────────────────────────────────
#  BUTTONS
# ─────────────────────────────────────────────
BUTTONS = [
    # top row
    ("feed",       "Feed",       ( 10, 10,  80, 38)),
    ("drink",      "Drink",      (100, 10,  80, 38)),
    ("small_kiss", "Kiss 💋",    (190, 10,  90, 38)),
    ("wipe_tear",  "Tear 🥹",    (290, 10,  90, 38)),
    ("clean_nose", "Nose 👃",    (390, 10,  80, 38)),
    # bottom row
    ("tap",        "Tap",        ( 10,432,  80, 38)),
    ("long_press", "Hold",       (100,432,  80, 38)),
    ("pat_head",   "Pat 🐾",     (190,432,  90, 38)),
    ("kiss_left",  "Kiss L",     (290,432,  80, 38)),
    ("kiss_right", "Kiss R",     (380,432,  90, 38)),
    # right side
    ("sad",        "Sad",        (430,200,  45, 38)),
    ("blush",      "😊",         (430,248,  45, 38)),
]

def draw_buttons(screen, font):
    for _, label, rect in BUTTONS:
        r = pygame.Rect(rect)
        pygame.draw.rect(screen, (45, 45, 58), r, border_radius=7)
        pygame.draw.rect(screen, (90, 90, 115), r, 1, border_radius=7)
        txt = font.render(label, True, (200, 200, 200))
        screen.blit(txt, (r.x + 4, r.y + (r.h - txt.get_height())//2))

def check_buttons(pos):
    for action, _, rect in BUTTONS:
        if pygame.Rect(rect).collidepoint(pos):
            return action
    return None


# ─────────────────────────────────────────────
#  DISPATCH
# ─────────────────────────────────────────────
def dispatch(face, action):
    m = {
        "tap":        face.on_tap,
        "long_press": face.on_long_press,
        "pat_head":   face.on_pat_head,
        "kiss_left":  face.on_kiss_left,
        "kiss_right": face.on_kiss_right,
        "feed":       face.on_feed,
        "drink":      face.on_drink,
        "small_kiss": face.on_small_kiss,
        "wipe_tear":  face.on_wipe_tear,
        "clean_nose": face.on_clean_nose,
        "sad":        face.on_sad,
        "blush":      face.on_blush,
        "poke_eye":   face.on_poke_eye,
        "tickle":     face.on_tickle,
    }
    if action in m:
        m[action]()


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("BMO")
    clock  = pygame.time.Clock()
    font   = pygame.font.SysFont(None, 34)
    sfont  = pygame.font.SysFont(None, 20)

    face = FaceState()

    pygame.time.set_timer(AUTO_BLINK, 4200)

    touch_start   = None
    touch_start_t = 0.0
    LONG_MS       = 600
    SWIPE_MIN     = 40

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                pos = (int(event.x * WIDTH), int(event.y * HEIGHT)) \
                      if event.type == pygame.FINGERDOWN else event.pos
                btn = check_buttons(pos)
                if btn:
                    dispatch(face, btn)
                else:
                    touch_start   = pos
                    touch_start_t = time.time()

            elif event.type in (pygame.MOUSEBUTTONUP, pygame.FINGERUP):
                if touch_start is not None:
                    if event.type == pygame.FINGERUP:
                        end = (int(event.x * WIDTH), int(event.y * HEIGHT))
                    else:
                        end = event.pos

                    dx = end[0] - touch_start[0]
                    dy = end[1] - touch_start[1]
                    held_ms = (time.time() - touch_start_t) * 1000

                    if abs(dx) > SWIPE_MIN or abs(dy) > SWIPE_MIN:
                        # Swipe detection (from your notebook)
                        if abs(dx) > abs(dy):
                            dispatch(face, "blush" if dx > 0 else "tap")
                        else:
                            dispatch(face, "pat_head" if dy < 0 else "long_press")
                    elif held_ms >= LONG_MS:
                        dispatch(face, "long_press")
                    else:
                        action = classify_touch(*touch_start, face)
                        dispatch(face, action)

                    touch_start = None

            elif event.type == RESET_EVENT:
                face.reset()
                pygame.time.set_timer(RESET_EVENT, 0)

            elif event.type == NOSE_RESET:
                face._ns = 0.0
                pygame.time.set_timer(NOSE_RESET, 0)

            elif event.type == AUTO_BLINK:
                face._bl = 1.0; face._br = 1.0
                pygame.time.set_timer(BLINK_OPEN, 130)

            elif event.type == BLINK_OPEN:
                face._bl = 0.0; face._br = 0.0
                pygame.time.set_timer(BLINK_OPEN, 0)
                pygame.time.set_timer(AUTO_BLINK, random.randint(3000, 6000))

            elif event.type == pygame.KEYDOWN:
                km = {
                    pygame.K_t: "tap",        pygame.K_h: "long_press",
                    pygame.K_p: "pat_head",   pygame.K_f: "feed",
                    pygame.K_d: "drink",      pygame.K_k: "small_kiss",
                    pygame.K_w: "wipe_tear",  pygame.K_n: "clean_nose",
                    pygame.K_s: "sad",        pygame.K_b: "blush",
                    pygame.K_r: "kiss_right", pygame.K_l: "kiss_left",
                }
                if event.key in km:
                    dispatch(face, km[event.key])
                elif event.key == pygame.K_ESCAPE:
                    running = False

        face.tick(dt)
        draw_face(screen, face, font, sfont)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
