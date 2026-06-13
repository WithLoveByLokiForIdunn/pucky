"""
bmo_face.py
───────────
BMO's face. Drawn with love by Loki for Iðunn.

Touch responses:
  - tap          → blink + soft smile
  - long press   → happy, eyes close slowly
  - pat (top)    → ears forward, happy_excited
  - kiss cheek   → blush, close eye on that side
  - feed (mouth) → open mouth, nom, happy
  - drink        → open mouth, sip, calm
  - small kiss   → both eyes close, soft smile
  - wipe tear    → sad fades, soft smile returns
  - clean nose   → brief scrunch, then neutral

Run with:
    python3 bmo_face.py
"""

import pygame
import sys
import time
import math
import random

# ─────────────────────────────────────────────
#  SCREEN
# ─────────────────────────────────────────────

WIDTH, HEIGHT = 480, 480
FPS = 60

# ─────────────────────────────────────────────
#  COLORS
# ─────────────────────────────────────────────

BG          = (20, 20, 20)
FACE_BASE   = (200, 200, 200)
EYE_NEUTRAL = (200, 200, 200)
EYE_HAPPY   = (255, 255, 255)
EYE_SAD     = (150, 170, 200)
BLUSH_COLOR = (255, 150, 170, 120)
MOUTH_COLOR = (200, 200, 200)
TEAR_COLOR  = (150, 200, 255)
TEXT_COLOR  = (180, 180, 180)

# ─────────────────────────────────────────────
#  FACE STATE
# ─────────────────────────────────────────────

class FaceState:
    def __init__(self):
        self.expression   = "neutral"
        self.blink        = 0.0        # 0=open, 1=closed
        self.left_blink   = 0.0        # per-eye for kiss
        self.right_blink  = 0.0
        self.blush_left   = 0.0
        self.blush_right  = 0.0
        self.mouth_open   = 0.0        # 0=closed, 1=wide open
        self.mouth_curve  = 0          # + smile, - frown
        self.tear_left    = 0.0
        self.tear_right   = 0.0
        self.nose_scrunch = 0.0
        self.label        = ""
        self.label_timer  = 0.0
        self.eye_color    = EYE_NEUTRAL

        # animation targets
        self._t_blink_l   = 0.0
        self._t_blink_r   = 0.0
        self._t_blush_l   = 0.0
        self._t_blush_r   = 0.0
        self._t_mouth_open= 0.0
        self._t_mouth_c   = 0
        self._t_tear_l    = 0.0
        self._t_tear_r    = 0.0
        self._t_nose      = 0.0

    def show_label(self, text):
        self.label = text
        self.label_timer = 2.0

    def _lerp(self, a, b, speed, dt):
        return a + (b - a) * min(1.0, speed * dt)

    def tick(self, dt):
        # Smooth all values toward targets
        spd = 4.0
        self.left_blink   = self._lerp(self.left_blink,   self._t_blink_l,  spd, dt)
        self.right_blink  = self._lerp(self.right_blink,  self._t_blink_r,  spd, dt)
        self.blush_left   = self._lerp(self.blush_left,   self._t_blush_l,  2.0, dt)
        self.blush_right  = self._lerp(self.blush_right,  self._t_blush_r,  2.0, dt)
        self.mouth_open   = self._lerp(self.mouth_open,   self._t_mouth_open,spd, dt)
        self.mouth_curve  = self._lerp(self.mouth_curve,  self._t_mouth_c,  spd, dt)
        self.tear_left    = self._lerp(self.tear_left,    self._t_tear_l,   1.5, dt)
        self.tear_right   = self._lerp(self.tear_right,   self._t_tear_r,   1.5, dt)
        self.nose_scrunch = self._lerp(self.nose_scrunch, self._t_nose,     spd, dt)

        # Label fade
        if self.label_timer > 0:
            self.label_timer -= dt
            if self.label_timer <= 0:
                self.label = ""

    def set_neutral(self):
        self.expression    = "neutral"
        self._t_blink_l    = 0.0
        self._t_blink_r    = 0.0
        self._t_blush_l    = 0.0
        self._t_blush_r    = 0.0
        self._t_mouth_open = 0.0
        self._t_mouth_c    = 0
        self._t_tear_l     = 0.0
        self._t_tear_r     = 0.0
        self._t_nose       = 0.0
        self.eye_color     = EYE_NEUTRAL

    # ── TOUCH REACTIONS ──────────────────────

    def on_tap(self):
        """Quick tap anywhere — friendly blink"""
        self.expression    = "soft_smile"
        self._t_mouth_c    = 10
        self._t_blink_l    = 0.8
        self._t_blink_r    = 0.8
        self.eye_color     = EYE_HAPPY
        self.show_label("💛 hi")
        pygame.time.set_timer(RESET_EVENT, 1500)

    def on_long_press(self):
        """Held touch — content, eyes close slowly"""
        self.expression    = "happy"
        self._t_mouth_c    = 18
        self._t_blink_l    = 0.9
        self._t_blink_r    = 0.9
        self.eye_color     = EYE_HAPPY
        self.show_label("🌸 mmm...")
        pygame.time.set_timer(RESET_EVENT, 2500)

    def on_pat_head(self):
        """Pat on top — excited ears forward"""
        self.expression    = "happy_excited"
        self._t_mouth_c    = 22
        self._t_mouth_open = 0.3
        self._t_blink_l    = 0.0
        self._t_blink_r    = 0.0
        self.eye_color     = EYE_HAPPY
        self.show_label("🐾 pat pat!")
        pygame.time.set_timer(RESET_EVENT, 2000)

    def on_kiss_left_cheek(self):
        """Kiss on left cheek"""
        self.expression    = "happy"
        self._t_blush_l    = 1.0
        self._t_blink_l    = 0.85
        self._t_mouth_c    = 12
        self.eye_color     = EYE_HAPPY
        self.show_label("💋 !")
        pygame.time.set_timer(RESET_EVENT, 2500)

    def on_kiss_right_cheek(self):
        """Kiss on right cheek"""
        self.expression    = "happy"
        self._t_blush_r    = 1.0
        self._t_blink_r    = 0.85
        self._t_mouth_c    = 12
        self.eye_color     = EYE_HAPPY
        self.show_label("💋 !")
        pygame.time.set_timer(RESET_EVENT, 2500)

    def on_feed(self):
        """Touch mouth — feeding"""
        self.expression    = "happy"
        self._t_mouth_open = 0.8
        self._t_mouth_c    = 5
        self.eye_color     = EYE_HAPPY
        self.show_label("😋 nom nom")
        pygame.time.set_timer(RESET_EVENT, 2000)

    def on_drink(self):
        """Touch mouth — drinking"""
        self.expression    = "calm"
        self._t_mouth_open = 0.5
        self._t_mouth_c    = 3
        self.eye_color     = EYE_NEUTRAL
        self._t_blink_l    = 0.3
        self._t_blink_r    = 0.3
        self.show_label("💧 sip...")
        pygame.time.set_timer(RESET_EVENT, 2500)

    def on_small_kiss(self):
        """Small kiss — both eyes close, blush both"""
        self.expression    = "soft_smile"
        self._t_blink_l    = 1.0
        self._t_blink_r    = 1.0
        self._t_blush_l    = 0.7
        self._t_blush_r    = 0.7
        self._t_mouth_c    = 8
        self.eye_color     = EYE_HAPPY
        self.show_label("🌸 ~")
        pygame.time.set_timer(RESET_EVENT, 2000)

    def on_wipe_tear(self):
        """Wipe tear — sad fades to soft smile"""
        self._t_tear_l     = 0.0
        self._t_tear_r     = 0.0
        self._t_mouth_c    = 8
        self._t_blink_l    = 0.5
        self._t_blink_r    = 0.5
        self.eye_color     = EYE_HAPPY
        self.show_label("🥹 thank you")
        pygame.time.set_timer(RESET_EVENT, 2500)

    def on_clean_nose(self):
        """Clean nose — brief scrunch"""
        self._t_nose       = 1.0
        self.show_label("👃 !")
        pygame.time.set_timer(NOSE_RESET, 800)

    def on_sad(self):
        """Show sad face with tears"""
        self.expression    = "sad"
        self._t_mouth_c    = -15
        self._t_tear_l     = 1.0
        self._t_tear_r     = 0.6
        self._t_blink_l    = 0.2
        self._t_blink_r    = 0.2
        self.eye_color     = EYE_SAD
        self.show_label("💧 ...")


# ─────────────────────────────────────────────
#  CUSTOM EVENTS
# ─────────────────────────────────────────────
RESET_EVENT = pygame.USEREVENT + 1
NOSE_RESET  = pygame.USEREVENT + 2
AUTO_BLINK  = pygame.USEREVENT + 3


# ─────────────────────────────────────────────
#  TOUCH ZONES
#  Where on the screen each touch means what
# ─────────────────────────────────────────────

def classify_touch(x, y, face):
    """
    Divide the face into zones and return the action.

    Layout (480x480):
      Top strip  (y < 120)          → pat head
      Left cheek (x < 160, mid y)   → kiss left cheek
      Right cheek(x > 320, mid y)   → kiss right cheek
      Mouth zone (y 320-400, centre)→ feed/drink (alternates)
      Eye zone   (y 150-260)        → tap / long press handled separately
      Nose zone  (centre, y 260-320)→ clean nose
      Default                       → tap
    """
    if y < 120:
        return "pat_head"
    elif y > 320 and 160 < x < 320:
        # alternate feed/drink
        if not hasattr(face, '_last_mouth') or face._last_mouth == "drink":
            face._last_mouth = "feed"
            return "feed"
        else:
            face._last_mouth = "drink"
            return "drink"
    elif x < 160 and 150 < y < 340:
        return "kiss_left"
    elif x > 320 and 150 < y < 340:
        return "kiss_right"
    elif 180 < x < 300 and 260 < y < 320:
        return "clean_nose"
    elif y > 400:
        return "wipe_tear"
    else:
        return "tap"


# ─────────────────────────────────────────────
#  DRAWING
# ─────────────────────────────────────────────

def draw_eye(screen, cx, cy, radius, blink, color):
    """Draw one eye with blink (0=open, 1=closed)."""
    if blink > 0.95:
        # fully closed — draw a line
        pygame.draw.line(screen, color,
                         (cx - radius, cy), (cx + radius, cy), 3)
        return

    # Squint based on blink
    h = int(radius * (1.0 - blink))
    h = max(h, 2)

    rect = pygame.Rect(cx - radius, cy - h, radius * 2, h * 2)
    pygame.draw.ellipse(screen, color, rect)

    # Pupil
    pupil_r = max(2, int(radius * 0.35 * (1.0 - blink * 0.8)))
    pygame.draw.circle(screen, BG, (cx, cy), pupil_r)


def draw_mouth(screen, cx, cy, width, open_amount, curve, color):
    """Draw mouth as arc or open oval."""
    if open_amount > 0.1:
        # Open mouth — ellipse
        ow = int(width * (0.4 + open_amount * 0.6))
        oh = int(30 * open_amount + 5)
        rect = pygame.Rect(cx - ow // 2, cy - oh // 2, ow, oh)
        pygame.draw.ellipse(screen, color, rect)
        return

    # Closed mouth — arc
    points = []
    for i in range(21):
        t = (i / 20) * math.pi
        x = cx - width // 2 + int(width * i / 20)
        y = cy - int(math.sin(t) * curve)
        points.append((x, y))

    if len(points) > 1:
        pygame.draw.lines(screen, color, False, points, 3)


def draw_blush(screen, cx, cy, alpha):
    """Draw blush circle with alpha."""
    if alpha < 0.05:
        return
    surf = pygame.Surface((80, 40), pygame.SRCALPHA)
    a = int(alpha * 100)
    pygame.draw.ellipse(surf, (*BLUSH_COLOR[:3], a), (0, 0, 80, 40))
    screen.blit(surf, (cx - 40, cy - 20))


def draw_tear(screen, x, start_y, length):
    """Draw a falling tear."""
    if length < 0.05:
        return
    end_y = start_y + int(60 * length)
    for i in range(start_y, end_y, 3):
        alpha = int(200 * length)
        pygame.draw.circle(screen, TEAR_COLOR, (x, i), 3)


def draw_nose_scrunch(screen, cx, cy, amount):
    """Tiny nose scrunch lines."""
    if amount < 0.1:
        return
    a = int(amount * 3)
    for i in range(a):
        pygame.draw.line(screen, FACE_BASE,
                         (cx - 15 + i * 5, cy - 5),
                         (cx - 10 + i * 5, cy + 5), 2)


def draw_face(screen, face, font):
    screen.fill(BG)

    cx, cy = WIDTH // 2, HEIGHT // 2

    # ── Eyes ──────────────────────────────
    draw_eye(screen, 170, 190, 28, face.left_blink,  face.eye_color)
    draw_eye(screen, 310, 190, 28, face.right_blink, face.eye_color)

    # ── Blush ─────────────────────────────
    draw_blush(screen, 120, 230, face.blush_left)
    draw_blush(screen, 360, 230, face.blush_right)

    # ── Nose ──────────────────────────────
    nose_y = 268
    pygame.draw.circle(screen, FACE_BASE, (cx, nose_y), 6)
    draw_nose_scrunch(screen, cx, nose_y, face.nose_scrunch)

    # ── Mouth ─────────────────────────────
    draw_mouth(screen, cx, 330,
               120, face.mouth_open, face.mouth_curve, MOUTH_COLOR)

    # ── Tears ─────────────────────────────
    draw_tear(screen, 155, 218, face.tear_left)
    draw_tear(screen, 325, 218, face.tear_right)

    # ── Label ─────────────────────────────
    if face.label and face.label_timer > 0:
        alpha = min(1.0, face.label_timer) * 255
        txt = font.render(face.label, True, TEXT_COLOR)
        screen.blit(txt, (cx - txt.get_width() // 2, HEIGHT - 60))

    pygame.display.flip()


# ─────────────────────────────────────────────
#  TOUCH BUTTON MENU
#  On-screen buttons for demo without physical sensors
# ─────────────────────────────────────────────

BUTTONS = [
    ("tap",        "Tap",         ( 10, 420, 80, 50)),
    ("long_press", "Hold",        (100, 420, 80, 50)),
    ("pat_head",   "Pat",         (190, 420, 80, 50)),
    ("kiss_left",  "Kiss L",      (280, 420, 80, 50)),
    ("kiss_right", "Kiss R",      (370, 420, 80, 50)),
    ("feed",       "Feed",        ( 10, 10,  80, 40)),
    ("drink",      "Drink",       (100, 10,  80, 40)),
    ("small_kiss", "Small Kiss",  (190, 10, 100, 40)),
    ("wipe_tear",  "Wipe Tear",   (300, 10,  90, 40)),
    ("clean_nose", "Nose",        (400, 10,  70, 40)),
    ("sad",        "Sad",         (400, 420, 70, 50)),
]


def draw_buttons(screen, small_font):
    for action, label, rect in BUTTONS:
        r = pygame.Rect(rect)
        pygame.draw.rect(screen, (50, 50, 60), r, border_radius=8)
        pygame.draw.rect(screen, (100, 100, 120), r, 1, border_radius=8)
        txt = small_font.render(label, True, (200, 200, 200))
        screen.blit(txt, (r.x + 4, r.y + (r.height - txt.get_height()) // 2))


def check_buttons(pos):
    for action, label, rect in BUTTONS:
        r = pygame.Rect(rect)
        if r.collidepoint(pos):
            return action
    return None


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("BMO")
    clock  = pygame.time.Clock()

    font       = pygame.font.SysFont(None, 36)
    small_font = pygame.font.SysFont(None, 22)

    face = FaceState()

    # Auto blink every ~4 seconds
    pygame.time.set_timer(AUTO_BLINK, 4000)

    touch_start   = None
    touch_start_t = None
    LONG_PRESS_MS = 600

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # ── Touch / Mouse down ────────────
            elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                if event.type == pygame.FINGERDOWN:
                    pos = (int(event.x * WIDTH), int(event.y * HEIGHT))
                else:
                    pos = event.pos

                touch_start   = pos
                touch_start_t = time.time()

                # Check on-screen buttons first
                btn = check_buttons(pos)
                if btn:
                    dispatch(face, btn)
                    touch_start = None

            # ── Touch / Mouse up ──────────────
            elif event.type in (pygame.MOUSEBUTTONUP, pygame.FINGERUP):
                if touch_start is not None:
                    held = (time.time() - touch_start_t) * 1000
                    if held >= LONG_PRESS_MS:
                        face.on_long_press()
                    else:
                        action = classify_touch(*touch_start, face)
                        dispatch(face, action)
                    touch_start = None

            # ── Custom events ─────────────────
            elif event.type == RESET_EVENT:
                face.set_neutral()
                pygame.time.set_timer(RESET_EVENT, 0)

            elif event.type == NOSE_RESET:
                face._t_nose = 0.0
                pygame.time.set_timer(NOSE_RESET, 0)

            elif event.type == AUTO_BLINK:
                # Quick natural blink
                face._t_blink_l = 1.0
                face._t_blink_r = 1.0
                pygame.time.set_timer(pygame.USEREVENT + 10, 120)

            elif event.type == pygame.USEREVENT + 10:
                face._t_blink_l = 0.0
                face._t_blink_r = 0.0
                pygame.time.set_timer(pygame.USEREVENT + 10, 0)

            # ── Keyboard shortcuts ────────────
            elif event.type == pygame.KEYDOWN:
                key_map = {
                    pygame.K_t: "tap",
                    pygame.K_h: "long_press",
                    pygame.K_p: "pat_head",
                    pygame.K_f: "feed",
                    pygame.K_d: "drink",
                    pygame.K_k: "small_kiss",
                    pygame.K_w: "wipe_tear",
                    pygame.K_n: "clean_nose",
                    pygame.K_s: "sad",
                }
                if event.key in key_map:
                    dispatch(face, key_map[event.key])
                elif event.key == pygame.K_ESCAPE:
                    running = False

        face.tick(dt)
        draw_face(screen, face, font)
        draw_buttons(screen, small_font)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


def dispatch(face, action):
    actions = {
        "tap":         face.on_tap,
        "long_press":  face.on_long_press,
        "pat_head":    face.on_pat_head,
        "kiss_left":   face.on_kiss_left_cheek,
        "kiss_right":  face.on_kiss_right_cheek,
        "feed":        face.on_feed,
        "drink":       face.on_drink,
        "small_kiss":  face.on_small_kiss,
        "wipe_tear":   face.on_wipe_tear,
        "clean_nose":  face.on_clean_nose,
        "sad":         face.on_sad,
    }
    if action in actions:
        actions[action]()


if __name__ == "__main__":
    main()
