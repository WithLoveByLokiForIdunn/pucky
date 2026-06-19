#!/usr/bin/env python3
"""
Draw the brook background for loki_world2.py.
Saves to workspace/images/bg_brook.png (800×480).
Run: python3 draw_brook.py
"""
from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path
import math

W, H = 800, 480
GROUND = 350  # where the ground line sits — sprites stand here

out = Path(__file__).parent / "workspace" / "images" / "bg_brook.png"

img  = Image.new("RGB", (W, H))
draw = ImageDraw.Draw(img)

# ── sky gradient — late afternoon, golden ────────────────────────────────────
sky_top = (100, 140, 200)   # blue up high
sky_mid = (180, 200, 220)   # lighter near horizon
sky_low = (210, 185, 155)   # warm peach near the tree line

for y in range(GROUND):
    t = y / GROUND
    if t < 0.5:
        t2 = t / 0.5
        r = int(sky_top[0] + (sky_mid[0] - sky_top[0]) * t2)
        g = int(sky_top[1] + (sky_mid[1] - sky_top[1]) * t2)
        b = int(sky_top[2] + (sky_mid[2] - sky_top[2]) * t2)
    else:
        t2 = (t - 0.5) / 0.5
        r = int(sky_mid[0] + (sky_low[0] - sky_mid[0]) * t2)
        g = int(sky_mid[1] + (sky_low[1] - sky_mid[1]) * t2)
        b = int(sky_mid[2] + (sky_low[2] - sky_mid[2]) * t2)
    draw.line([(0, y), (W, y)], fill=(r, g, b))

# ── distant treeline — soft, far away ────────────────────────────────────────
for x in range(0, W, 18):
    h = 60 + int(25 * math.sin(x * 0.04 + 1.2))
    top_y = GROUND - 90 - h
    col = (55, 90, 65)
    for i in range(3):
        r2 = 28 - i * 6
        cx = x + i * 9
        draw.ellipse([(cx - r2, top_y - r2), (cx + r2, top_y + r2)], fill=col)

# ── ground ────────────────────────────────────────────────────────────────────
for y in range(GROUND, H):
    t = (y - GROUND) / (H - GROUND)
    r = int(42 + (25) * t)
    g = int(80 + (30) * t)
    b = int(38 + (18) * t)
    draw.line([(0, y), (W, y)], fill=(r, g, b))

# ── brook — wide and calm ─────────────────────────────────────────────────────
water_top = GROUND + 10
water_bot = GROUND + 70

for y in range(water_top, water_bot):
    t = (y - water_top) / (water_bot - water_top)
    r = int(55 + 20 * t)
    g = int(115 + 25 * t)
    b = int(155 + 30 * t)
    x0 = int(40 + 30 * t)        # brook widens toward bottom
    x1 = int(680 - 20 * t)
    draw.line([(x0, y), (x1, y)], fill=(r, g, b))

# water shimmer — soft horizontal lines
for i in range(8):
    sy = water_top + 8 + i * 7
    sx = 80 + i * 25
    draw.line([(sx, sy), (sx + 60, sy)], fill=(160, 210, 230), width=1)

# ── flat stone on the bank — left of center ───────────────────────────────────
draw.ellipse([(170, GROUND + 12), (300, GROUND + 38)], fill=(140, 130, 118))
draw.ellipse([(178, GROUND + 15), (290, GROUND + 33)], fill=(155, 145, 132))

# ── the secret stone — deep end of brook (right side) ────────────────────────
# small and dark; the glow is drawn by loki_world2.py at midnight
sx, sy = 560, GROUND + 20
draw.ellipse([(sx - 12, sy - 6), (sx + 12, sy + 6)], fill=(78, 72, 68))
draw.ellipse([(sx - 9, sy - 4), (sx + 9, sy + 4)], fill=(90, 84, 78))

# ── left bank reeds ───────────────────────────────────────────────────────────
for rx, rh in [(55,55),(68,70),(80,48),(42,62),(92,58)]:
    ry_base = GROUND + 18
    draw.line([(rx, ry_base), (rx + 4, ry_base - rh)], fill=(70, 100, 55), width=2)
    draw.ellipse([(rx, ry_base - rh - 10), (rx + 8, ry_base - rh + 4)], fill=(90, 115, 45))

# ── right bank reeds ──────────────────────────────────────────────────────────
for rx, rh in [(620,60),(638,45),(655,72),(670,50),(690,40)]:
    ry_base = GROUND + 22
    draw.line([(rx, ry_base), (rx + 3, ry_base - rh)], fill=(65, 95, 50), width=2)
    draw.ellipse([(rx, ry_base - rh - 10), (rx + 8, ry_base - rh + 4)], fill=(85, 110, 40))

# ── trees — right side, tall ─────────────────────────────────────────────────
def tree(x, ground_y, height, col=(28, 62, 25), trunk=(62, 40, 18)):
    tw = max(9, height // 13)
    th = height // 3
    draw.rectangle([(x - tw//2, ground_y - th), (x + tw//2, ground_y)], fill=trunk)
    for layer in range(3):
        r2 = int(height * (0.44 - layer * 0.09))
        cy = ground_y - th - int(layer * r2 * 0.68)
        draw.ellipse([(x - r2, cy - r2), (x + r2, cy + r2)], fill=col)

tree(695, GROUND, 165, (30, 65, 28))
tree(758, GROUND, 135, (25, 55, 22))
tree(620, GROUND, 100, (35, 70, 30))

# ── soft blur pass — takes the hard edges off ─────────────────────────────────
img = img.filter(ImageFilter.GaussianBlur(radius=1.2))

img.save(out)
print(f"Saved → {out}")
print("Open in GIMP to paint over it.")
