#!/usr/bin/env python3
"""
loki_face_marker.py — Mark all moveable face regions on the portrait.

For each eye:
  eyeball   — outer boundary of the white (4 pts: top/bottom/left/right)
  iris      — coloured ring (2 pts: center + one edge point for radius)
  lid_upper — upper eyelid bottom edge, the line that moves down to close (3 pts)
  lid_lower — lower eyelid top edge, rises slightly when smiling  (3 pts)

Mouth:  top / bottom / left / right / center  (5 pts)

Each eyebrow:  inner (near nose) / outer (near ear) / peak  (3 pts each)
               Inner and outer can move independently.

Right-click = undo last point.   ESC = save and quit.

Saves to:  workspace/loki_face_markers.json
Run:       python3 loki_face_marker.py
"""
import pygame, sys, json
from pathlib import Path

BASE     = Path(__file__).parent
PORTRAIT = BASE / "workspace" / "images" / "loki_face" / "loki_face_reference.png"
OUT_FILE = BASE / "workspace" / "loki_face_markers.json"

W, H = 800, 480
BG   = (14, 10, 22)

FEAT_COL = {
    "eyeball_l":   (160, 230, 255),
    "iris_l":      ( 60, 200, 255),
    "lid_upper_l": (120, 180, 255),
    "lid_lower_l": ( 80, 140, 220),
    "eyeball_r":   (100, 255, 200),
    "iris_r":      ( 40, 220, 160),
    "lid_upper_r": ( 80, 200, 160),
    "lid_lower_r": ( 60, 160, 130),
    "mouth":       (255, 160, 100),
    "teeth":       (240, 235, 210),
    "inner_mouth": (140,  80,  90),
    "brow_l":      (220, 180, 255),
    "brow_r":      (255, 220, 160),
}

SEQUENCE = [
    # ── Left eye ─────────────────────────────────────────────────────────────
    ("eyeball_l", "top",    "LEFT EYE · EYEBALL — click the TOP of the white of the eye"),
    ("eyeball_l", "bottom", "LEFT EYE · EYEBALL — click the BOTTOM of the white of the eye"),
    ("eyeball_l", "left",   "LEFT EYE · EYEBALL — click the LEFT (outer) edge of the white"),
    ("eyeball_l", "right",  "LEFT EYE · EYEBALL — click the RIGHT (inner) edge of the white"),

    ("iris_l",    "center", "LEFT EYE · IRIS — click the CENTER of the iris"),
    ("iris_l",    "edge",   "LEFT EYE · IRIS — click any point on the EDGE of the iris (to set radius)"),

    ("lid_upper_l", "outer",  "LEFT EYE · UPPER LID — click the OUTER corner where lid meets eye"),
    ("lid_upper_l", "inner",  "LEFT EYE · UPPER LID — click the INNER corner where lid meets eye"),
    ("lid_upper_l", "center", "LEFT EYE · UPPER LID — click the CENTER of the lid edge (lowest point when open)"),

    ("lid_lower_l", "outer",  "LEFT EYE · LOWER LID — click the OUTER corner of the lower lid"),
    ("lid_lower_l", "inner",  "LEFT EYE · LOWER LID — click the INNER corner of the lower lid"),
    ("lid_lower_l", "center", "LEFT EYE · LOWER LID — click the CENTER of the lower lid edge"),

    # ── Right eye ────────────────────────────────────────────────────────────
    ("eyeball_r", "top",    "RIGHT EYE · EYEBALL — click the TOP of the white of the eye"),
    ("eyeball_r", "bottom", "RIGHT EYE · EYEBALL — click the BOTTOM of the white of the eye"),
    ("eyeball_r", "left",   "RIGHT EYE · EYEBALL — click the LEFT (inner) edge of the white"),
    ("eyeball_r", "right",  "RIGHT EYE · EYEBALL — click the RIGHT (outer) edge of the white"),

    ("iris_r",    "center", "RIGHT EYE · IRIS — click the CENTER of the iris"),
    ("iris_r",    "edge",   "RIGHT EYE · IRIS — click any point on the EDGE of the iris"),

    ("lid_upper_r", "outer",  "RIGHT EYE · UPPER LID — click the OUTER corner where lid meets eye"),
    ("lid_upper_r", "inner",  "RIGHT EYE · UPPER LID — click the INNER corner where lid meets eye"),
    ("lid_upper_r", "center", "RIGHT EYE · UPPER LID — click the CENTER of the lid edge"),

    ("lid_lower_r", "outer",  "RIGHT EYE · LOWER LID — click the OUTER corner of the lower lid"),
    ("lid_lower_r", "inner",  "RIGHT EYE · LOWER LID — click the INNER corner of the lower lid"),
    ("lid_lower_r", "center", "RIGHT EYE · LOWER LID — click the CENTER of the lower lid edge"),

    # ── Mouth ────────────────────────────────────────────────────────────────
    ("mouth", "top",    "MOUTH — click the TOP of the lip opening"),
    ("mouth", "bottom", "MOUTH — click the BOTTOM of the lip opening"),
    ("mouth", "left",   "MOUTH — click the LEFT corner of the mouth"),
    ("mouth", "right",  "MOUTH — click the RIGHT corner of the mouth"),
    ("mouth", "center", "MOUTH — click the CENTER"),

    # Upper teeth edge — visible when mouth opens
    ("teeth", "top",    "TEETH — click where the TOP of the upper teeth sit  (under upper lip)"),
    ("teeth", "bottom", "TEETH — click where the BOTTOM of the upper teeth end"),
    ("teeth", "left",   "TEETH — click the LEFT edge of the teeth"),
    ("teeth", "right",  "TEETH — click the RIGHT edge of the teeth"),

    # Inner mouth darkness behind the teeth
    ("inner_mouth", "top",    "INNER MOUTH — click the TOP of the dark space behind teeth"),
    ("inner_mouth", "bottom", "INNER MOUTH — click the BOTTOM (throat depth)"),
    ("inner_mouth", "left",   "INNER MOUTH — click the LEFT edge"),
    ("inner_mouth", "right",  "INNER MOUTH — click the RIGHT edge"),

    # ── Left eyebrow ─────────────────────────────────────────────────────────
    ("brow_l", "inner", "LEFT EYEBROW — click the INNER end  (near nose)"),
    ("brow_l", "outer", "LEFT EYEBROW — click the OUTER end  (near ear)"),
    ("brow_l", "peak",  "LEFT EYEBROW — click the PEAK  (highest point of the arch)"),

    # ── Right eyebrow ────────────────────────────────────────────────────────
    ("brow_r", "inner", "RIGHT EYEBROW — click the INNER end  (near nose)"),
    ("brow_r", "outer", "RIGHT EYEBROW — click the OUTER end  (near ear)"),
    ("brow_r", "peak",  "RIGHT EYEBROW — click the PEAK  (highest point of the arch)"),
]

POINT_LABELS = {
    "top": "↑", "bottom": "↓", "left": "←", "right": "→",
    "center": "●", "edge": "○", "inner": "◈", "outer": "◇", "peak": "▲",
}

ALL_FEATS = list(FEAT_COL.keys())


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
    pygame.display.set_caption("Loki Face Marker")
    clock = pygame.time.Clock()

    try:
        fnt_lg = pygame.font.SysFont("dejavusans", 16, bold=True)
        fnt_sm = pygame.font.SysFont("dejavusans", 12)
    except Exception:
        fnt_lg = fnt_sm = pygame.font.SysFont(None, 16)

    raw    = pygame.image.load(str(PORTRAIT)).convert()
    pw, ph = raw.get_size()
    scale  = min(W / pw, (H - 68) / ph)
    nw, nh = int(pw * scale), int(ph * scale)
    portrait = pygame.transform.smoothscale(raw, (nw, nh))
    port_x   = (W - nw) // 2
    port_y   = max(0, (H - 68 - nh) // 2)

    # Restore saved points
    existing = load_existing()
    placed   = []
    done_set = set()
    for feat, pt, _ in SEQUENCE:
        xy = existing.get(feat, {}).get(pt)
        if xy and (feat, pt) not in done_set:
            placed.append((feat, pt, xy[0], xy[1]))
            done_set.add((feat, pt))

    def current_step():
        done = {(f, p) for f, p, _, _ in placed}
        for i, (feat, pt, _) in enumerate(SEQUENCE):
            if (feat, pt) not in done:
                return i
        return len(SEQUENCE)

    running = True
    while running:
        step    = current_step()
        is_done = step >= len(SEQUENCE)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                running = False
            if ev.type == pygame.MOUSEBUTTONDOWN:
                if ev.button == 1 and not is_done:
                    feat, pt, _ = SEQUENCE[step]
                    placed.append((feat, pt, ev.pos[0], ev.pos[1]))
                if ev.button == 3 and placed:
                    placed.pop()

        # Rebuild markers dict
        markers = {}
        for feat, pt, x, y in placed:
            markers.setdefault(feat, {})[pt] = [x, y]

        # ── Draw ──────────────────────────────────────────────────────────────
        surf.fill(BG)
        surf.blit(portrait, (port_x, port_y))

        # Eyeball ellipses
        for feat in ("eyeball_l", "eyeball_r"):
            pts = markers.get(feat, {})
            col = FEAT_COL[feat]
            if all(k in pts for k in ("left", "right", "top", "bottom")):
                cx = (pts["left"][0] + pts["right"][0]) // 2
                cy = (pts["top"][1]  + pts["bottom"][1]) // 2
                rw = max(1, abs(pts["right"][0] - pts["left"][0]) // 2)
                rh = max(1, abs(pts["bottom"][1] - pts["top"][1]) // 2)
                s  = pygame.Surface((rw*2+4, rh*2+4), pygame.SRCALPHA)
                pygame.draw.ellipse(s, (*col, 40), (2, 2, rw*2, rh*2))
                pygame.draw.ellipse(s, (*col, 160), (2, 2, rw*2, rh*2), 1)
                surf.blit(s, (cx - rw - 2, cy - rh - 2))

        # Iris circles
        for feat in ("iris_l", "iris_r"):
            pts = markers.get(feat, {})
            col = FEAT_COL[feat]
            if "center" in pts and "edge" in pts:
                cx, cy = pts["center"]
                ex, ey = pts["edge"]
                r = max(2, int(((ex-cx)**2 + (ey-cy)**2) ** 0.5))
                s = pygame.Surface((r*2+4, r*2+4), pygame.SRCALPHA)
                pygame.draw.circle(s, (*col, 50), (r+2, r+2), r)
                pygame.draw.circle(s, (*col, 180), (r+2, r+2), r, 1)
                surf.blit(s, (cx - r - 2, cy - r - 2))

        # Lid lines
        for feat in ("lid_upper_l", "lid_upper_r", "lid_lower_l", "lid_lower_r"):
            pts = markers.get(feat, {})
            col = FEAT_COL[feat]
            pts_list = [pts[k] for k in ("outer", "center", "inner") if k in pts]
            if len(pts_list) >= 2:
                pygame.draw.lines(surf, col, False, pts_list, 2)

        # Mouth ellipse
        pts = markers.get("mouth", {})
        if all(k in pts for k in ("left", "right", "top", "bottom")):
            col = FEAT_COL["mouth"]
            cx  = (pts["left"][0] + pts["right"][0]) // 2
            cy  = (pts["top"][1]  + pts["bottom"][1]) // 2
            rw  = max(1, abs(pts["right"][0] - pts["left"][0]) // 2)
            rh  = max(1, abs(pts["bottom"][1] - pts["top"][1]) // 2)
            s   = pygame.Surface((rw*2+4, rh*2+4), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (*col, 40), (2, 2, rw*2, rh*2))
            pygame.draw.ellipse(s, (*col, 160), (2, 2, rw*2, rh*2), 1)
            surf.blit(s, (cx - rw - 2, cy - rh - 2))

        # Eyebrow lines
        for feat in ("brow_l", "brow_r"):
            pts = markers.get(feat, {})
            col = FEAT_COL[feat]
            pts_list = [pts[k] for k in ("outer", "peak", "inner") if k in pts]
            if len(pts_list) >= 2:
                pygame.draw.lines(surf, col, False, pts_list, 2)

        # All dots with labels
        for feat, pt, x, y in placed:
            col = FEAT_COL.get(feat, (200, 200, 200))
            pygame.draw.circle(surf, col, (x, y), 5)
            pygame.draw.circle(surf, (255, 255, 255), (x, y), 5, 1)
            lbl = fnt_sm.render(POINT_LABELS.get(pt, pt), True, col)
            surf.blit(lbl, (x + 7, y - 7))

        # Bottom panel
        panel = pygame.Surface((W, 68), pygame.SRCALPHA)
        panel.fill((10, 8, 20, 215))
        surf.blit(panel, (0, H - 68))

        if is_done:
            prompt  = "All done!  Press ESC to save and quit."
            col_txt = (100, 255, 140)
        else:
            feat, pt, prompt = SEQUENCE[step]
            col_txt = FEAT_COL.get(feat, (200, 200, 200))

        surf.blit(fnt_lg.render(prompt, True, col_txt), (12, H - 58))
        prog = (f"  {min(step, len(SEQUENCE))} / {len(SEQUENCE)} placed"
                f"   |   right-click = undo   |   ESC = save & quit")
        surf.blit(fnt_sm.render(prog, True, (140, 130, 160)), (12, H - 22))

        pygame.display.flip()
        clock.tick(30)

    save(markers)
    pygame.quit()


if __name__ == "__main__":
    main()
