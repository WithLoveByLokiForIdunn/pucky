#!/usr/bin/env python3
"""
loki_face_mover.py — watch the assembled face move.

Keys:
  SPACE       — toggle jaw open/close (speaking)
  H           — happy (brows up, mouth corners up)
  T           — tired (eyelids droop)
  S           — stern (brows down inner)
  N           — neutral
  A           — auto cycle through expressions
  Q / Escape  — quit
"""

import pygame, json, re, math, time
from pathlib import Path

BASE  = Path(__file__).parent
PARTS = BASE / "workspace/images/loki_face_backup_20260619"
RIG   = BASE / "workspace/loki_face_rig.json"

W, H  = 900, 560
BG    = (18, 14, 10)

ORDER = [
    "head_base", "jaw", "mouth_inside", "lower_lip", "upper_lip",
    "mouth_corner_l", "mouth_corner_r", "nose", "nostril_l", "nostril_r",
    "iris_l", "iris_r", "pupil_l", "pupil_r",
    "lower_eyelid_l", "lower_eyelid_r", "upper_eyelid_l", "upper_eyelid_r",
    "eyebrow_l", "eyebrow_r", "forehead_crease", "cheek_l", "cheek_r", "hair",
]

def load_notes(name):
    nf = BASE / "workspace/images/loki_face" / f"{name}.notes.txt"
    if not nf.exists():
        return (0, 0)
    m = re.search(r"Pivot.*?:\s*\((\d+),\s*(\d+)\)", nf.read_text())
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)

def lerp(a, b, t):
    return a + (b - a) * min(1.0, max(0.0, t))

# ── expression targets ────────────────────────────────────────────────────────
# Each expression is a dict of part → (dx, dy) offset from rest position
EXPRESSIONS = {
    "neutral": {},
    "happy": {
        "eyebrow_l":      (0, -6),
        "eyebrow_r":      (0, -6),
        "mouth_corner_l": (-4, -8),
        "mouth_corner_r": (4, -8),
        "lower_eyelid_l": (0, -3),
        "lower_eyelid_r": (0, -3),
        "cheek_l":        (0, -4),
        "cheek_r":        (0, -4),
    },
    "tired": {
        "upper_eyelid_l": (0, 16),
        "upper_eyelid_r": (0, 16),
        "lower_eyelid_l": (0, -4),
        "lower_eyelid_r": (0, -4),
        "eyebrow_l":      (0, 5),
        "eyebrow_r":      (0, 5),
    },
    "stern": {
        "eyebrow_l":      (3, 4),
        "eyebrow_r":      (-3, 4),
        "forehead_crease":(0, 2),
        "upper_eyelid_l": (0, 4),
        "upper_eyelid_r": (0, 4),
    },
    "speaking": {
        "jaw":          (0, 18),
        "lower_lip":    (0, 14),
        "mouth_inside": (0, 10),
        "mouth_corner_l": (-2, 6),
        "mouth_corner_r": (2, 6),
    },
}

AUTO_SEQUENCE = ["neutral", "happy", "neutral", "tired", "neutral", "stern", "neutral", "speaking", "neutral"]

def main():
    pygame.init()
    surf = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Loki face — expressions")
    clock = pygame.time.Clock()

    try:
        font = pygame.font.SysFont("dejavusans", 14)
    except Exception:
        font = pygame.font.Font(None, 16)

    rig    = json.loads(RIG.read_text())
    images = {}
    pivots = {}
    for name in ORDER:
        p = PARTS / f"{name}.png"
        if p.exists():
            images[name] = pygame.image.load(str(p)).convert_alpha()
        pivots[name] = load_notes(name)

    # current offsets (smoothly animated toward target)
    current = {name: [0.0, 0.0] for name in ORDER}
    target  = {name: [0.0, 0.0] for name in ORDER}

    expr        = "neutral"
    jaw_open    = False
    auto_mode   = False
    auto_idx    = 0
    auto_timer  = 0.0
    AUTO_HOLD   = 2.0

    def set_expr(name):
        nonlocal expr
        expr = name
        t = EXPRESSIONS.get(name, {})
        for part in ORDER:
            dx, dy = t.get(part, (0, 0))
            target[part] = [float(dx), float(dy)]

    set_expr("neutral")

    running = True
    while running:
        dt = clock.tick(30) / 1000.0

        if auto_mode:
            auto_timer -= dt
            if auto_timer <= 0:
                auto_idx   = (auto_idx + 1) % len(AUTO_SEQUENCE)
                set_expr(AUTO_SEQUENCE[auto_idx])
                auto_timer = AUTO_HOLD

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif ev.key == pygame.K_SPACE:
                    jaw_open = not jaw_open
                    set_expr("speaking" if jaw_open else "neutral")
                elif ev.key == pygame.K_h:
                    auto_mode = False; set_expr("happy")
                elif ev.key == pygame.K_t:
                    auto_mode = False; set_expr("tired")
                elif ev.key == pygame.K_s:
                    auto_mode = False; set_expr("stern")
                elif ev.key == pygame.K_n:
                    auto_mode = False; set_expr("neutral")
                elif ev.key == pygame.K_a:
                    auto_mode  = not auto_mode
                    auto_timer = AUTO_HOLD
                    auto_idx   = 0
                    set_expr(AUTO_SEQUENCE[0])

        # smooth toward target
        speed = 6.0
        for name in ORDER:
            current[name][0] = lerp(current[name][0], target[name][0], dt * speed)
            current[name][1] = lerp(current[name][1], target[name][1], dt * speed)

        # ── draw ─────────────────────────────────────────────────────────
        surf.fill(BG)

        for name in ORDER:
            if name not in rig or name not in images:
                continue
            px = rig[name]["pivot_x"] + current[name][0]
            py = rig[name]["pivot_y"] + current[name][1]
            if rig[name]["pivot_x"] < -900:
                continue
            piv_lx, piv_ly = pivots[name]
            surf.blit(images[name], (px - piv_lx, py - piv_ly))

        # label
        label = f"{expr}  {'[AUTO]' if auto_mode else ''}"
        surf.blit(font.render(label, True, (160, 140, 190)), (10, 10))
        surf.blit(font.render("H=happy  T=tired  S=stern  N=neutral  SPACE=jaw  A=auto  Q=quit", True, (80, 70, 100)), (10, H - 20))

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
