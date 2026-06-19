#!/usr/bin/env python3
"""
loki_face_placer.py — placement tool for the articulated Loki face.

Shows head_base on screen. One by one, each face part appears following
your mouse. Click to drop it where its pivot (yellow dot) should land.
All placed parts stay visible so you can see the face build up.

Controls:
  Left-click      — place current part
  Right-click     — skip this part (place it off-screen)
  Backspace       — go back one part
  S               — save progress
  Escape / Q      — save and quit

Saves to: workspace/loki_face_rig.json
Run:  python3 loki_face_placer.py
"""

import pygame
import json
import re
import sys
from pathlib import Path

BASE    = Path(__file__).parent
PARTS   = BASE / "workspace" / "images" / "loki_face_backup_20260619"
OUT     = BASE / "workspace" / "loki_face_rig.json"

W, H    = 900, 560
BG      = (18, 14, 10)
PLACED_ALPHA = 90   # opacity of already-placed parts in the background

# Order to place parts — bottom layers first, hair last
PART_ORDER = [
    "head_base",
    "jaw",
    "mouth_inside",
    "lower_lip",
    "upper_lip",
    "mouth_corner_l",
    "mouth_corner_r",
    "nose",
    "nostril_l",
    "nostril_r",
    "iris_l",
    "iris_r",
    "pupil_l",
    "pupil_r",
    "lower_eyelid_l",
    "lower_eyelid_r",
    "upper_eyelid_l",
    "upper_eyelid_r",
    "eyebrow_l",
    "eyebrow_r",
    "forehead_crease",
    "cheek_l",
    "cheek_r",
    "hair",
]

def load_notes(name):
    """Parse pivot point from the notes file."""
    nf = BASE / "workspace" / "images" / "loki_face" / f"{name}.notes.txt"
    if not nf.exists():
        return (0, 0)
    txt = nf.read_text()
    m = re.search(r"Pivot.*?:\s*\((\d+),\s*(\d+)\)", txt)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return (0, 0)

def load_image(name):
    path = PARTS / f"{name}.png"
    if not path.exists():
        return None
    img = pygame.image.load(str(path)).convert_alpha()
    return img

def load_rig():
    if OUT.exists():
        try:
            return json.loads(OUT.read_text())
        except Exception:
            pass
    return {}

def save_rig(rig):
    OUT.write_text(json.dumps(rig, indent=2))

def main():
    pygame.init()
    surf = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Loki face placement")
    clock = pygame.time.Clock()

    try:
        font = pygame.font.SysFont("dejavusans", 14)
        font_lg = pygame.font.SysFont("dejavusans", 18)
    except Exception:
        font = font_lg = pygame.font.Font(None, 16)

    # Load all images and their pivot offsets
    images  = {}
    pivots  = {}
    for name in PART_ORDER:
        img = load_image(name)
        if img:
            images[name] = img
        pivots[name] = load_notes(name)

    rig = load_rig()

    # head_base starts centered
    if "head_base" not in rig and "head_base" in images:
        hb = images["head_base"]
        rig["head_base"] = {
            "pivot_x": W // 2,
            "pivot_y": H // 2 - 30,
        }

    idx = 0
    # skip to first unplaced part
    for i, name in enumerate(PART_ORDER):
        if name not in rig:
            idx = i
            break
    else:
        idx = len(PART_ORDER)  # all done

    running = True
    mx, my  = W // 2, H // 2

    while running:
        clock.tick(30)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                save_rig(rig)
                running = False

            elif ev.type == pygame.MOUSEMOTION:
                mx, my = ev.pos

            elif ev.type == pygame.MOUSEBUTTONDOWN:
                if idx >= len(PART_ORDER):
                    continue
                name = PART_ORDER[idx]
                if ev.button == 1:
                    rig[name] = {"pivot_x": mx, "pivot_y": my}
                    save_rig(rig)
                    idx += 1
                elif ev.button == 3:
                    # skip — place off-screen
                    rig[name] = {"pivot_x": -999, "pivot_y": -999}
                    save_rig(rig)
                    idx += 1

            elif ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE, pygame.K_q):
                    save_rig(rig)
                    running = False
                elif ev.key == pygame.K_s:
                    save_rig(rig)
                elif ev.key == pygame.K_BACKSPACE:
                    if idx > 0:
                        idx -= 1
                        name = PART_ORDER[idx]
                        rig.pop(name, None)
                        save_rig(rig)

        # ── draw ─────────────────────────────────────────────────────────
        surf.fill(BG)

        # draw all placed parts (dim)
        for name in PART_ORDER:
            if name not in rig or name not in images:
                continue
            px = rig[name]["pivot_x"]
            py = rig[name]["pivot_y"]
            if px < -900:
                continue
            piv_lx, piv_ly = pivots[name]
            img = images[name].copy()
            img.set_alpha(PLACED_ALPHA)
            surf.blit(img, (px - piv_lx, py - piv_ly))

        # draw current part following mouse
        if idx < len(PART_ORDER):
            name = PART_ORDER[idx]
            if name in images:
                piv_lx, piv_ly = pivots[name]
                img = images[name].copy()
                img.set_alpha(220)
                surf.blit(img, (mx - piv_lx, my - piv_ly))
                pygame.draw.circle(surf, (255, 220, 0), (mx, my), 5)

                # ── zoom panel — bottom-right corner ─────────────────────
                raw = images[name]
                iw, ih = raw.get_size()
                # scale up to at most 260×260, keeping aspect
                scale = min(260 / max(iw, 1), 260 / max(ih, 1), 6.0)
                zw, zh = max(1, int(iw * scale)), max(1, int(ih * scale))
                zoomed = pygame.transform.scale(raw, (zw, zh))
                pad = 10
                zx = W - zw - pad
                zy = H - zh - pad
                # dark backing
                backing = pygame.Surface((zw + 4, zh + 4), pygame.SRCALPHA)
                backing.fill((10, 8, 20, 200))
                surf.blit(backing, (zx - 2, zy - 2))
                surf.blit(zoomed, (zx, zy))
                # yellow dot on zoomed image
                zdx = int(piv_lx * scale)
                zdy = int(piv_ly * scale)
                pygame.draw.circle(surf, (255, 220, 0), (zx + zdx, zy + zdy), max(3, int(4 * scale)), 2)
                surf.blit(font.render("pivot", True, (255, 220, 0)), (zx, zy - 16))

            # instructions
            part_label = name.replace("_", " ").upper()
            surf.blit(font_lg.render(f"Place:  {part_label}  ({idx+1} / {len(PART_ORDER)})", True, (220, 210, 245)), (12, 12))
            surf.blit(font.render("Left-click = place  ·  Right-click = skip  ·  Backspace = undo  ·  S = save  ·  Q = done", True, (120, 110, 140)), (12, 36))

            pygame.draw.circle(surf, (255, 220, 0), (mx, my), 8, 2)

        else:
            surf.blit(font_lg.render("All parts placed! Press Q to save and quit.", True, (160, 230, 160)), (12, 12))

        pygame.display.flip()

    pygame.quit()
    print(f"Saved to {OUT}")

if __name__ == "__main__":
    main()
