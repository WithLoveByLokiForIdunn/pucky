#!/usr/bin/env python3
"""
loki_face_marker.py — Click to mark eye and mouth openings on the portrait.

For each feature you place 5 points:
  top · bottom · left · right · center

3 features × 5 points = 15 clicks total.

Saves to: workspace/loki_face_markers.json

Run:  python3 loki_face_marker.py
      (right-click to undo last point, ESC to quit and save)
"""
import pygame, sys, json
from pathlib import Path

BASE      = Path(__file__).parent
PORTRAIT  = BASE / "workspace" / "images" / "loki_face" / "loki_face_reference.png"
OUT_FILE  = BASE / "workspace" / "loki_face_markers.json"

W, H = 800, 480
BG   = (14, 10, 22)

# What we're marking, in order
SEQUENCE = [
    ("eye_l",  "top",    (100, 220, 255), "LEFT EYE — click the TOP of the eye opening"),
    ("eye_l",  "bottom", (100, 220, 255), "LEFT EYE — click the BOTTOM of the eye opening"),
    ("eye_l",  "left",   (100, 220, 255), "LEFT EYE — click the LEFT corner"),
    ("eye_l",  "right",  (100, 220, 255), "LEFT EYE — click the RIGHT corner"),
    ("eye_l",  "center", (100, 220, 255), "LEFT EYE — click the CENTER (iris)"),

    ("eye_r",  "top",    ( 60, 255, 180), "RIGHT EYE — click the TOP of the eye opening"),
    ("eye_r",  "bottom", ( 60, 255, 180), "RIGHT EYE — click the BOTTOM of the eye opening"),
    ("eye_r",  "left",   ( 60, 255, 180), "RIGHT EYE — click the LEFT corner"),
    ("eye_r",  "right",  ( 60, 255, 180), "RIGHT EYE — click the RIGHT corner"),
    ("eye_r",  "center", ( 60, 255, 180), "RIGHT EYE — click the CENTER (iris)"),

    ("mouth",  "top",    (255, 160, 100), "MOUTH — click the TOP of the lip opening"),
    ("mouth",  "bottom", (255, 160, 100), "MOUTH — click the BOTTOM of the lip opening"),
    ("mouth",  "left",   (255, 160, 100), "MOUTH — click the LEFT corner"),
    ("mouth",  "right",  (255, 160, 100), "MOUTH — click the RIGHT corner"),
    ("mouth",  "center", (255, 160, 100), "MOUTH — click the CENTER"),
]

POINT_LABELS = {
    "top":    "↑ top",
    "bottom": "↓ bot",
    "left":   "← left",
    "right":  "→ right",
    "center": "● ctr",
}


def load_existing():
    if OUT_FILE.exists():
        try:
            return json.loads(OUT_FILE.read_text())
        except Exception:
            pass
    return {}


def save(markers):
    OUT_FILE.write_text(json.dumps(markers, indent=2))
    print(f"Saved → {OUT_FILE}")


def main():
    pygame.init()
    surf  = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Loki Face Marker — click to place points")
    clock = pygame.time.Clock()

    try:
        fnt_lg = pygame.font.SysFont("dejavusans", 18, bold=True)
        fnt_sm = pygame.font.SysFont("dejavusans", 13)
    except Exception:
        fnt_lg = fnt_sm = pygame.font.SysFont(None, 18)

    # Load and scale portrait to fit screen
    portrait_raw = pygame.image.load(str(PORTRAIT)).convert()
    pw, ph = portrait_raw.get_size()
    scale  = min(W / pw, H / ph)
    nw, nh = int(pw * scale), int(ph * scale)
    portrait = pygame.transform.smoothscale(portrait_raw, (nw, nh))
    port_x   = (W - nw) // 2
    port_y   = (H - nh) // 2

    markers  = load_existing()   # {"eye_l": {"top": [x,y], ...}, ...}
    placed   = []                # list of (feature, point, x, y) — for undo

    # Restore previously placed points into placed list
    for feat in ("eye_l", "eye_r", "mouth"):
        if feat in markers:
            for pt, xy in markers[feat].items():
                placed.append((feat, pt, xy[0], xy[1]))

    def current_step():
        """Return index of next unplaced point in SEQUENCE."""
        done = {(f, p) for f, p, _, _ in placed}
        for i, (feat, pt, col, msg) in enumerate(SEQUENCE):
            if (feat, pt) not in done:
                return i
        return len(SEQUENCE)

    running = True
    while running:
        step = current_step()
        done = step >= len(SEQUENCE)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
            if ev.type == pygame.MOUSEBUTTONDOWN:
                if ev.button == 1 and not done:
                    feat, pt, col, msg = SEQUENCE[step]
                    placed.append((feat, pt, ev.pos[0], ev.pos[1]))
                if ev.button == 3 and placed:
                    placed.pop()

        # Rebuild markers dict from placed list
        markers = {}
        for feat, pt, x, y in placed:
            markers.setdefault(feat, {})[pt] = [x, y]

        # Draw
        surf.fill(BG)
        surf.blit(portrait, (port_x, port_y))

        # Draw placed dots
        for feat, pt, x, y in placed:
            col_map = {"eye_l": (100,220,255), "eye_r": (60,255,180), "mouth": (255,160,100)}
            col = col_map.get(feat, (200,200,200))
            pygame.draw.circle(surf, col, (x, y), 6)
            pygame.draw.circle(surf, (255,255,255), (x, y), 6, 1)
            lbl = fnt_sm.render(POINT_LABELS.get(pt, pt), True, col)
            surf.blit(lbl, (x + 8, y - 8))

        # Draw ellipse previews for completed features
        for feat in ("eye_l", "eye_r", "mouth"):
            pts = markers.get(feat, {})
            if len(pts) >= 4:
                col_map = {"eye_l": (100,220,255), "eye_r": (60,255,180), "mouth": (255,160,100)}
                col = col_map[feat]
                cx = pts.get("center", [None,None])[0] or ((pts.get("left",[0,0])[0] + pts.get("right",[0,0])[0])//2)
                cy = pts.get("center", [None,None])[1] or ((pts.get("top",[0,0])[1] + pts.get("bottom",[0,0])[1])//2)
                rw = abs(pts.get("right",[cx,0])[0] - pts.get("left",[cx,0])[0]) // 2
                rh = abs(pts.get("bottom",[0,cy])[1] - pts.get("top",[0,cy])[1]) // 2
                if rw > 2 and rh > 2:
                    s = pygame.Surface((rw*2+4, rh*2+4), pygame.SRCALPHA)
                    pygame.draw.ellipse(s, (*col, 50), (2, 2, rw*2, rh*2))
                    pygame.draw.ellipse(s, (*col, 140), (2, 2, rw*2, rh*2), 1)
                    surf.blit(s, (cx - rw - 2, cy - rh - 2))

        # Instruction panel at bottom
        panel = pygame.Surface((W, 60), pygame.SRCALPHA)
        panel.fill((10, 8, 20, 210))
        surf.blit(panel, (0, H - 60))

        if done:
            msg_txt = "All done!  Press ESC to save and quit."
            col_txt = (100, 255, 140)
        else:
            _, _, col_txt, msg_txt = SEQUENCE[step]

        surf.blit(fnt_lg.render(msg_txt, True, col_txt), (12, H - 52))

        progress = f"  {step} / {len(SEQUENCE)} placed   |   right-click = undo"
        surf.blit(fnt_sm.render(progress, True, (140, 130, 160)), (12, H - 24))

        pygame.display.flip()
        clock.tick(30)

    save(markers)
    pygame.quit()
    print("Marker file written. Run loki_face.py to see the result.")


if __name__ == "__main__":
    main()
