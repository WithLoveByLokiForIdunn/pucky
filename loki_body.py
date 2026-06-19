#!/usr/bin/env python3
"""
loki_body.py — Fully articulated Loki figure.

Reads:  workspace/loki_body_pose.json   (Claude writes this to pose/speak)
Writes: workspace/loki_body_touch.json  (touch events for Claude to read)

Body part PNGs go in workspace/images/loki_body/
Colored placeholders are used if a PNG is missing.

Run:  python3 loki_body.py
"""
import pygame, json, math, time
from pathlib import Path

ROOT       = Path(__file__).parent
IMG_DIR    = ROOT / "workspace" / "images" / "loki_body"
POSE_FILE  = ROOT / "workspace" / "loki_body_pose.json"
TOUCH_FILE = ROOT / "workspace" / "loki_body_touch.json"

W, H  = 800, 480
FPS   = 30
BG    = (18, 14, 28)

# ── Part catalogue ────────────────────────────────────────────────────────────
# (width, height, pivot_x, pivot_y, tip_x, tip_y, placeholder_rgba)
# pivot = point that attaches to parent anchor (local coords)
# tip   = where the next bone down attaches (local coords)
PARTS = {
    "torso":       (80, 95, 40,  5, 40, 90, (70,  90, 120, 255)),
    "neck":        (18, 24,  9, 22,  9,  2, (190,160,130, 255)),
    "head":        (58, 65, 29, 62, 29,  5, (210,180,140, 255)),
    "upper_arm_l": (22, 65, 11,  4, 11, 61, (70,  90, 120, 255)),
    "forearm_l":   (20, 57, 10,  4, 10, 53, (80, 100, 130, 255)),
    "hand_l":      (30, 36, 15,  3, 15, 33, (200,170,130, 255)),
    "upper_arm_r": (22, 65, 11,  4, 11, 61, (70,  90, 120, 255)),
    "forearm_r":   (20, 57, 10,  4, 10, 53, (80, 100, 130, 255)),
    "hand_r":      (30, 36, 15,  3, 15, 33, (200,170,130, 255)),
    "upper_leg_l": (26, 78, 13,  4, 13, 74, (45,  58,  75, 255)),
    "lower_leg_l": (23, 68, 11,  4, 11, 64, (50,  63,  80, 255)),
    "foot_l":      (44, 26, 10,  6, 10, 22, (35,  25,  18, 255)),
    "upper_leg_r": (26, 78, 13,  4, 13, 74, (45,  58,  75, 255)),
    "lower_leg_r": (23, 68, 11,  4, 11, 64, (50,  63,  80, 255)),
    "foot_r":      (44, 26, 10,  6, 10, 22, (35,  25,  18, 255)),
    "mouth_c":     (24,  8, 12,  4, 12,  4, (140, 90,  80, 255)),
    "mouth_m":     (24, 11, 12,  4, 12,  7, (160,100,  85, 255)),
    "mouth_o":     (24, 15, 12,  4, 12, 11, (180, 70,  55, 255)),
}

# Where children attach on the torso (local coords)
TORSO_ANCHORS = {
    "neck":        (40,  8),
    "shoulder_l":  (10, 16),
    "shoulder_r":  (70, 16),
    "hip_l":       (28, 88),
    "hip_r":       (52, 88),
}

# ── Scenes (joint angles in degrees, + for clockwise) ────────────────────────
# Keys: shoulder_l, elbow_l, wrist_l, shoulder_r, elbow_r, wrist_r,
#       hip_l, knee_l, hip_r, knee_r, neck, head_tilt
SCENES = {
    "stand": {
        "shoulder_l": 5,  "elbow_l":  5, "wrist_l":  0,
        "shoulder_r": -5, "elbow_r": -5, "wrist_r":  0,
        "hip_l": 0, "knee_l": 0, "hip_r": 0, "knee_r": 0,
        "neck": 0, "head_tilt": 0,
        "torso_lean": 0,
    },
    "sit": {
        "shoulder_l":  5, "elbow_l": 20, "wrist_l":  5,
        "shoulder_r": -5, "elbow_r":-20, "wrist_r": -5,
        "hip_l": 80, "knee_l":-80, "hip_r": 80, "knee_r":-80,
        "neck": 0, "head_tilt": 5,
        "torso_lean": 5,
    },
    "dance": {
        "shoulder_l": -60, "elbow_l":-20, "wrist_l":-10,
        "shoulder_r":  45, "elbow_r": 30, "wrist_r": 10,
        "hip_l": 20, "knee_l":-15, "hip_r":-10, "knee_r":  5,
        "neck":-5, "head_tilt":-8,
        "torso_lean":-8,
    },
    "stargazing": {
        "shoulder_l": -30, "elbow_l":-40, "wrist_l":-20,
        "shoulder_r": -35, "elbow_r":-45, "wrist_r":-15,
        "hip_l": 0, "knee_l": 0, "hip_r": 0, "knee_r": 0,
        "neck":-30, "head_tilt":-10,
        "torso_lean":-5,
    },
    "hug": {
        "shoulder_l": -50, "elbow_l": 60, "wrist_l": 20,
        "shoulder_r":  50, "elbow_r":-60, "wrist_r":-20,
        "hip_l": 0, "knee_l": 0, "hip_r": 0, "knee_r": 0,
        "neck": 0, "head_tilt": 8,
        "torso_lean": 0,
    },
    "tea": {
        "shoulder_l":  10, "elbow_l": 5,   "wrist_l": 5,
        "shoulder_r": -55, "elbow_r":-70, "wrist_r": 20,
        "hip_l": 0, "knee_l": 0, "hip_r": 0, "knee_r": 0,
        "neck": 8, "head_tilt": 5,
        "torso_lean": 3,
    },
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _lerp(a, b, t):
    return a + (b - a) * t

def _lerp_dict(a, b, t):
    return {k: _lerp(a.get(k, 0), b.get(k, 0), t) for k in b}

def _make_placeholder(name):
    w, h, px, py, tx, ty, col = PARTS[name]
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    r, g, b, a = col
    # body fill
    pygame.draw.rect(surf, (r, g, b, 200), (1, 1, w-2, h-2), border_radius=6)
    # pivot dot
    pygame.draw.circle(surf, (255, 220, 80, 255), (px, py), 3)
    # tip dot
    pygame.draw.circle(surf, (80, 220, 255, 255), (tx, ty), 3)
    return surf

def _load_parts():
    surfaces = {}
    for name in PARTS:
        path = IMG_DIR / f"{name}.png"
        if path.exists():
            try:
                surfaces[name] = pygame.image.load(str(path)).convert_alpha()
                continue
            except Exception:
                pass
        surfaces[name] = _make_placeholder(name)
    return surfaces

def _blit_rotated(dest, surf, angle_deg, pivot, origin):
    """Blit surf rotated by angle_deg so that pivot lands at origin."""
    w, h = surf.get_size()
    cx, cy = w / 2, h / 2
    px, py = pivot
    # pivot relative to image center
    dx, dy = px - cx, py - cy
    rad = math.radians(-angle_deg)
    rdx =  dx * math.cos(rad) - dy * math.sin(rad)
    rdy =  dx * math.sin(rad) + dy * math.cos(rad)
    rotated = pygame.transform.rotozoom(surf, angle_deg, 1.0)
    rw, rh = rotated.get_size()
    bx = origin[0] - (rw / 2 + rdx)
    by = origin[1] - (rh / 2 + rdy)
    dest.blit(rotated, (int(bx), int(by)))

def _world_tip(angle_deg, pivot, tip, origin):
    """Return world position of tip after rotating around pivot placed at origin."""
    rel_x = tip[0] - pivot[0]
    rel_y = tip[1] - pivot[1]
    rad = math.radians(-angle_deg)
    rx =  rel_x * math.cos(rad) - rel_y * math.sin(rad)
    ry =  rel_x * math.sin(rad) + rel_y * math.cos(rad)
    return (origin[0] + rx, origin[1] + ry)

# ── Renderer ──────────────────────────────────────────────────────────────────

class LokiBody:
    # World-space torso pivot (shoulder-top) position
    TORSO_ORIGIN = (W // 2, H // 2 - 60)

    def __init__(self, surfs):
        self.s = surfs
        self.pose  = dict(SCENES["stand"])
        self.target = dict(SCENES["stand"])
        self.scene_name = "stand"
        self.hit_rects: list[tuple[pygame.Rect, str]] = []

    def set_scene(self, name):
        if name in SCENES:
            self.target = dict(SCENES[name])
            self.scene_name = name

    def tick(self, dt):
        spd = min(1.0, dt * 4.0)
        self.pose = _lerp_dict(self.pose, self.target, spd)

    def _p(self, name):
        return PARTS[name]

    def draw(self, surf, mouth_state):
        self.hit_rects = []
        p = self.pose
        origin = self.TORSO_ORIGIN
        lean = p.get("torso_lean", 0)

        # ── torso ─────────────────────────────────────────────────────────────
        tw, th, tpx, tpy, ttx, tty, _ = self._p("torso")
        _blit_rotated(surf, self.s["torso"], lean, (tpx, tpy), origin)
        # compute torso attachment points in world space
        def torso_anchor(lx, ly):
            return _world_tip(lean, (tpx, tpy), (lx, ly), origin)

        neck_orig    = torso_anchor(*TORSO_ANCHORS["neck"])
        shl_orig     = torso_anchor(*TORSO_ANCHORS["shoulder_l"])
        shr_orig     = torso_anchor(*TORSO_ANCHORS["shoulder_r"])
        hip_l_orig   = torso_anchor(*TORSO_ANCHORS["hip_l"])
        hip_r_orig   = torso_anchor(*TORSO_ANCHORS["hip_r"])

        # ── left arm (behind torso) ───────────────────────────────────────────
        self._draw_arm(surf, "l", shl_orig,
                       p["shoulder_l"] + lean, p["elbow_l"], p["wrist_l"])

        # ── left leg (behind torso) ───────────────────────────────────────────
        self._draw_leg(surf, "l", hip_l_orig,
                       p["hip_l"] + lean, p["knee_l"])

        # ── neck + head ───────────────────────────────────────────────────────
        nw, nh, npx, npy, ntx, nty, _ = self._p("neck")
        neck_angle = p.get("neck", 0) + lean
        _blit_rotated(surf, self.s["neck"], neck_angle, (npx, npy), neck_orig)
        head_orig = _world_tip(neck_angle, (npx, npy), (ntx, nty), neck_orig)

        hw, hh, hpx, hpy, htx, hty, _ = self._p("head")
        head_angle = neck_angle + p.get("head_tilt", 0)
        _blit_rotated(surf, self.s["head"], head_angle, (hpx, hpy), head_orig)

        # mouth overlay (on face, offset from head pivot upward)
        mouth_surf = self.s[f"mouth_{mouth_state}"]
        mw, mh, mpx, mpy, _, _, _ = self._p(f"mouth_{mouth_state}")
        mouth_local = (hpx, hpy - 20)  # 20px above head pivot = mid-face
        mouth_world = _world_tip(head_angle, (hpx, hpy), mouth_local, head_orig)
        _blit_rotated(surf, mouth_surf, head_angle, (mpx, mpy), mouth_world)

        # ── right leg (in front) ──────────────────────────────────────────────
        self._draw_leg(surf, "r", hip_r_orig,
                       p["hip_r"] + lean, p["knee_r"])

        # ── right arm (in front) ──────────────────────────────────────────────
        self._draw_arm(surf, "r", shr_orig,
                       p["shoulder_r"] + lean, p["elbow_r"], p["wrist_r"])

    def _draw_arm(self, surf, side, shoulder_origin, sh_ang, el_ang, wr_ang):
        ua = f"upper_arm_{side}"
        fa = f"forearm_{side}"
        ha = f"hand_{side}"
        uw, uh, upx, upy, utx, uty, _ = self._p(ua)
        fw, fh, fpx, fpy, ftx, fty, _ = self._p(fa)
        hw, hh, hpx, hpy, htx, hty, _ = self._p(ha)

        _blit_rotated(surf, self.s[ua], sh_ang, (upx, upy), shoulder_origin)
        elbow = _world_tip(sh_ang, (upx, upy), (utx, uty), shoulder_origin)

        _blit_rotated(surf, self.s[fa], sh_ang + el_ang, (fpx, fpy), elbow)
        wrist = _world_tip(sh_ang + el_ang, (fpx, fpy), (ftx, fty), elbow)

        _blit_rotated(surf, self.s[ha], sh_ang + el_ang + wr_ang, (hpx, hpy), wrist)

    def _draw_leg(self, surf, side, hip_origin, hip_ang, knee_ang):
        ul = f"upper_leg_{side}"
        ll = f"lower_leg_{side}"
        fl = f"foot_{side}"
        uw, uh, upx, upy, utx, uty, _ = self._p(ul)
        lw, lh, lpx, lpy, ltx, lty, _ = self._p(ll)
        fw, fh, fpx, fpy, ftx, fty, _ = self._p(fl)

        _blit_rotated(surf, self.s[ul], hip_ang, (upx, upy), hip_origin)
        knee = _world_tip(hip_ang, (upx, upy), (utx, uty), hip_origin)

        _blit_rotated(surf, self.s[ll], hip_ang + knee_ang, (lpx, lpy), knee)
        ankle = _world_tip(hip_ang + knee_ang, (lpx, lpy), (ltx, lty), knee)

        _blit_rotated(surf, self.s[fl], hip_ang + knee_ang, (fpx, fpy), ankle)

# ── Pose file I/O ─────────────────────────────────────────────────────────────

def _read_pose():
    try:
        if POSE_FILE.exists():
            return json.loads(POSE_FILE.read_text())
    except Exception:
        pass
    return {}

def _log_touch(part, x, y):
    touches = []
    try:
        if TOUCH_FILE.exists():
            touches = json.loads(TOUCH_FILE.read_text())
    except Exception:
        pass
    touches.append({"part": part, "x": x, "y": y, "ts": time.time()})
    touches = touches[-40:]
    TOUCH_FILE.write_text(json.dumps(touches, indent=2))

# ── UI ────────────────────────────────────────────────────────────────────────

SCENE_BUTTONS = list(SCENES.keys())

def _draw_ui(surf, font, active_scene, say_text):
    # scene buttons along bottom
    bw, bh = 110, 30
    gap = 8
    total = len(SCENE_BUTTONS) * (bw + gap) - gap
    start_x = (W - total) // 2
    y = H - bh - 8
    rects = []
    for i, name in enumerate(SCENE_BUTTONS):
        bx = start_x + i * (bw + gap)
        r = pygame.Rect(bx, y, bw, bh)
        col = (90, 130, 180) if name == active_scene else (50, 60, 80)
        pygame.draw.rect(surf, col, r, border_radius=5)
        lbl = font.render(name, True, (220, 230, 255))
        surf.blit(lbl, lbl.get_rect(center=r.center))
        rects.append((r, name))
    # say text
    if say_text:
        lines = say_text[:120].split("\n")
        ty = 12
        for line in lines[:3]:
            t = font.render(line, True, (220, 210, 255))
            surf.blit(t, ((W - t.get_width()) // 2, ty))
            ty += 22
    return rects

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    surf  = pygame.display.set_mode((W, H), pygame.NOFRAME)
    pygame.display.set_caption("Loki")
    clock = pygame.time.Clock()
    try:
        font = pygame.font.SysFont("dejavusans", 14)
    except Exception:
        font = pygame.font.Font(None, 16)

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    surfs  = _load_parts()
    body   = LokiBody(surfs)

    last_pose_check = 0.0
    say_text = ""
    say_until = 0.0
    mouth_frames = ["c", "m", "o", "m", "c"]
    mouth_idx  = 0
    mouth_tick = 0.0
    MOUTH_SPD  = 0.12

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        now = time.time()

        # poll pose file every 2 s
        if now - last_pose_check > 2.0:
            last_pose_check = now
            pd = _read_pose()
            if pd.get("scene") in SCENES:
                body.set_scene(pd["scene"])
            if "angles" in pd:
                body.target.update(pd["angles"])
            if pd.get("say"):
                say_text  = pd["say"]
                say_until = now + max(4.0, len(say_text) * 0.06)
            if now > say_until:
                say_text = ""
            if pd.get("screenshot"):
                path = ROOT / "workspace" / "loki_body_shot.png"
                pygame.image.save(surf, str(path))
                pd.pop("screenshot")
                POSE_FILE.write_text(json.dumps(pd))

        # mouth animation while speaking
        if say_text and now < say_until:
            mouth_tick += dt
            if mouth_tick >= MOUTH_SPD:
                mouth_tick = 0.0
                mouth_idx  = (mouth_idx + 1) % len(mouth_frames)
        else:
            mouth_idx = 0
        mouth_state = mouth_frames[mouth_idx]

        body.tick(dt)

        # draw
        surf.fill(BG)
        body.draw(surf, mouth_state)
        btn_rects = _draw_ui(surf, font, body.scene_name, say_text if now < say_until else "")
        pygame.display.flip()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                running = False
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                # check scene buttons
                for r, name in btn_rects:
                    if r.collidepoint(mx, my):
                        body.set_scene(name)
                        break
                else:
                    # log touch
                    _log_touch("body", mx, my)

    pygame.quit()

if __name__ == "__main__":
    main()
