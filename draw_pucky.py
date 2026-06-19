#!/usr/bin/env python3
"""
Draw a Pucky sprite sketch — 120×120px, transparent background.
Saves to workspace/images/pucky_pocket.png (and copies for other poses).
Paint over it in GIMP.
"""
from PIL import Image, ImageDraw
from pathlib import Path
import math

SIZE = 120
cx, cy = SIZE // 2, SIZE // 2

out_dir = Path(__file__).parent / "workspace" / "images"
out_dir.mkdir(exist_ok=True)

img  = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# ── body — round, like a little matryoshka ────────────────────────────────────
body_col  = (80, 148, 82)     # forest green
body_dark = (55, 110, 58)     # shadow side

# main body oval
draw.ellipse([(22, 42), (98, 112)], fill=body_col)
# shadow on right side
for x in range(72, 98):
    t = (x - 72) / 26
    a = int(60 * t)
    draw.line([(x, 50), (x, 108)], fill=(*body_dark, a))

# collar / neck area — lighter green
draw.ellipse([(34, 38), (86, 62)], fill=(100, 168, 100))

# ── head — round and soft ─────────────────────────────────────────────────────
head_col  = (240, 200, 170)   # warm skin
draw.ellipse([(30, 10), (90, 62)], fill=head_col)

# rosy cheeks
draw.ellipse([(32, 36), (50, 50)], fill=(230, 160, 148, 140))
draw.ellipse([(70, 36), (88, 50)], fill=(230, 160, 148, 140))

# eyes — small and round
draw.ellipse([(44, 28), (54, 38)], fill=(60, 40, 30))
draw.ellipse([(66, 28), (76, 38)], fill=(60, 40, 30))
# eye shine
draw.ellipse([(47, 29), (50, 32)], fill=(255, 255, 255, 200))
draw.ellipse([(69, 29), (72, 32)], fill=(255, 255, 255, 200))

# nose — tiny
draw.ellipse([(57, 38), (63, 43)], fill=(210, 165, 148))

# mouth — small smile
draw.arc([(50, 42), (70, 54)], start=10, end=170, fill=(180, 100, 90), width=2)

# ── hat — red with a brim ─────────────────────────────────────────────────────
hat_col  = (188, 50, 42)
brim_col = (155, 38, 32)

# brim
draw.ellipse([(24, 10), (96, 24)], fill=brim_col)
# crown
draw.ellipse([(34, 0), (86, 22)], fill=hat_col)
# hat band — small dark stripe
draw.rectangle([(34, 14), (86, 19)], fill=(120, 28, 24))

# ── tiny hands peeking out ────────────────────────────────────────────────────
draw.ellipse([(14, 68), (30, 84)], fill=head_col)   # left hand
draw.ellipse([(90, 68), (106, 84)], fill=head_col)  # right hand

img.save(out_dir / "pucky_pocket.png")

# shoulder pose — same but tilted slightly (just copy for now, paint differently)
img.save(out_dir / "pucky_shoulder.png")
img.save(out_dir / "pucky_back.png")

print("Saved → workspace/images/pucky_pocket.png")
print("Open in GIMP and paint over it.")
print("Same file is used for shoulder and back — paint those separately when ready.")
