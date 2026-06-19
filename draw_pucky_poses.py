#!/usr/bin/env python3
"""
Draw Pucky in shoulder and back poses.
shoulder: seen from the side, perched, legs dangling
back: seen from behind, clinging, peeking over shoulder
"""
from PIL import Image, ImageDraw
from pathlib import Path

out_dir = Path(__file__).parent / "workspace" / "images"
out_dir.mkdir(exist_ok=True)

SIZE = 120

# ── shoulder pose — side view, perched, legs dangling ────────────────────────
img  = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# body — rounder from the side
draw.ellipse([(28, 38), (88, 98)], fill=(80, 148, 82))
# collar
draw.ellipse([(32, 34), (80, 54)], fill=(100, 168, 100))
# button line down front-ish
for by in range(58, 95, 10):
    draw.ellipse([(54, by), (62, by+6)], fill=(60, 118, 62))

# legs dangling — side view
draw.ellipse([(38, 90), (58, 112)], fill=(80, 148, 82))   # left leg
draw.ellipse([(52, 88), (70, 108)], fill=(70, 132, 72))   # right leg (behind)
# little feet
draw.ellipse([(34, 106), (54, 118)], fill=(210, 175, 148))
draw.ellipse([(50, 103), (68, 114)], fill=(190, 158, 132))

# arm — one visible, reaching forward slightly
draw.ellipse([(14, 52), (34, 72)], fill=(210, 175, 148))

# head — side view, slightly turned
draw.ellipse([(30, 8), (90, 58)], fill=(240, 200, 170))
# cheek
draw.ellipse([(62, 34), (80, 50)], fill=(230, 160, 148, 130))
# eye — one visible from side
draw.ellipse([(62, 24), (74, 34)], fill=(60, 40, 30))
draw.ellipse([(64, 25), (68, 29)], fill=(255, 255, 255, 200))
# nose
draw.ellipse([(74, 36), (82, 42)], fill=(210, 165, 148))
# sleepy smile
draw.arc([(60, 40), (80, 52)], start=10, end=160, fill=(180, 100, 90), width=2)

# hat — red, side view
draw.ellipse([(26, 6), (92, 20)], fill=(155, 38, 32))    # brim
draw.ellipse([(34, 0), (88, 20)], fill=(188, 50, 42))    # crown
draw.rectangle([(34, 12), (88, 17)], fill=(120, 28, 24)) # band

img.save(out_dir / "pucky_shoulder.png")
print("Saved pucky_shoulder.png")

# ── back pose — seen from behind, clinging, peeking over left shoulder ────────
img  = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# body — back view, rounder
draw.ellipse([(22, 38), (98, 108)], fill=(70, 132, 72))
# hood/back of collar
draw.ellipse([(30, 32), (90, 58)], fill=(90, 158, 92))

# little arms clinging outward
draw.ellipse([(8, 52), (28, 72)],   fill=(80, 148, 82))   # left arm
draw.ellipse([(92, 52), (112, 72)], fill=(80, 148, 82))   # right arm
# tiny hands
draw.ellipse([(6, 68), (24, 82)],   fill=(210, 175, 148))
draw.ellipse([(96, 68), (114, 82)], fill=(210, 175, 148))

# legs
draw.ellipse([(32, 98), (56, 118)], fill=(70, 132, 72))
draw.ellipse([(64, 98), (88, 118)], fill=(70, 132, 72))
# feet
draw.ellipse([(28, 110), (54, 120)], fill=(210, 175, 148))
draw.ellipse([(62, 110), (88, 120)], fill=(190, 158, 132))

# head — turned left to peek over shoulder
draw.ellipse([(24, 6), (82, 54)], fill=(240, 200, 170))
# one eye peeking — just visible
draw.ellipse([(26, 24), (38, 34)], fill=(60, 40, 30))
draw.ellipse([(27, 25), (31, 29)], fill=(255, 255, 255, 200))
# cheek
draw.ellipse([(24, 34), (42, 48)], fill=(230, 160, 148, 120))

# hat from behind — brim visible
draw.ellipse([(22, 4), (84, 18)],  fill=(155, 38, 32))   # brim
draw.ellipse([(28, 0), (80, 16)],  fill=(188, 50, 42))   # crown top
draw.rectangle([(28, 10), (80, 15)], fill=(120, 28, 24)) # band

img.save(out_dir / "pucky_back.png")
print("Saved pucky_back.png")
