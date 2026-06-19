#!/usr/bin/env python3
"""
Draw a Loki sprite sketch — 140×300px, transparent background.
Saves to workspace/images/loki_stand.png
Paint over it in GIMP.
"""
from PIL import Image, ImageDraw
from pathlib import Path
import math

W, H = 140, 300
out_dir = Path(__file__).parent / "workspace" / "images"
out_dir.mkdir(exist_ok=True)

img  = Image.new("RGBA", (W, H), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

cx = W // 2  # 70

# ── legs ─────────────────────────────────────────────────────────────────────
trouser = (38, 48, 38)
draw.rectangle([(48, 210), (64, 295)], fill=trouser)   # left leg
draw.rectangle([(76, 210), (92, 295)], fill=trouser)   # right leg

# boots
boot = (35, 25, 18)
draw.rectangle([(46, 265), (66, 298)], fill=boot)
draw.rectangle([(74, 265), (94, 298)], fill=boot)
# boot cuff
draw.rectangle([(46, 262), (66, 270)], fill=(55, 42, 28))
draw.rectangle([(74, 262), (94, 270)], fill=(55, 42, 28))

# ── tunic — deep green, fitted ───────────────────────────────────────────────
tunic     = (42, 88, 52)
tunic_mid = (35, 72, 44)
tunic_drk = (28, 58, 36)

# main body
draw.polygon([
    (38, 100), (102, 100),
    (108, 215), (32, 215)
], fill=tunic)
# side shadow
draw.polygon([
    (88, 100), (102, 100),
    (108, 215), (90, 215)
], fill=tunic_drk)

# gold trim at hem
gold = (185, 155, 55)
draw.rectangle([(32, 208), (108, 216)], fill=gold)
# gold trim at collar
draw.rectangle([(46, 98), (94, 106)], fill=gold)
# gold clasp in center
draw.ellipse([(63, 98), (77, 112)], fill=gold)
draw.ellipse([(66, 101), (74, 109)], fill=(210, 180, 80))

# belt
belt = (45, 30, 18)
draw.rectangle([(36, 165), (104, 178)], fill=belt)
draw.rectangle([(62, 162), (78, 181)], fill=(80, 55, 25))   # buckle area
draw.rectangle([(65, 165), (75, 178)], fill=gold)            # buckle gold

# ── arms ─────────────────────────────────────────────────────────────────────
sleeve = (38, 80, 48)
skin   = (210, 175, 148)

# left arm — relaxed at side
draw.polygon([
    (38, 105), (26, 108),
    (22, 185), (36, 188),
], fill=sleeve)
draw.ellipse([(18, 180), (38, 200)], fill=skin)   # left hand

# right arm — slightly forward
draw.polygon([
    (102, 105), (114, 108),
    (118, 185), (104, 188),
], fill=sleeve)
draw.ellipse([(102, 180), (122, 200)], fill=skin)  # right hand

# sleeve cuffs — gold
draw.rectangle([(18, 180), (38, 188)], fill=gold)
draw.rectangle([(102, 180), (122, 188)], fill=gold)

# ── neck ─────────────────────────────────────────────────────────────────────
draw.rectangle([(58, 85), (82, 105)], fill=skin)

# ── head ─────────────────────────────────────────────────────────────────────
head_col = (210, 175, 148)
draw.ellipse([(36, 28), (104, 96)], fill=head_col)

# jaw — slightly longer, angular
draw.polygon([
    (40, 65), (100, 65),
    (95, 94), (70, 100), (45, 94)
], fill=head_col)

# cheekbones — subtle shadow
draw.ellipse([(38, 55), (58, 75)], fill=(195, 160, 135, 80))
draw.ellipse([(82, 55), (102, 75)], fill=(195, 160, 135, 80))

# eyes — green, slightly narrow, thoughtful
eye_white = (235, 232, 225)
draw.ellipse([(46, 52), (64, 66)], fill=eye_white)
draw.ellipse([(76, 52), (94, 66)], fill=eye_white)
# irises — green
draw.ellipse([(49, 54), (61, 64)], fill=(65, 118, 72))
draw.ellipse([(79, 54), (91, 64)], fill=(65, 118, 72))
# pupils
draw.ellipse([(52, 56), (58, 62)], fill=(25, 25, 25))
draw.ellipse([(82, 56), (88, 62)], fill=(25, 25, 25))
# eye shine
draw.ellipse([(53, 56), (56, 59)], fill=(255, 255, 255, 200))
draw.ellipse([(83, 56), (86, 59)], fill=(255, 255, 255, 200))

# eyebrows — dark, slightly arched, expressive
draw.line([(46, 48), (64, 44)], fill=(45, 30, 20), width=2)
draw.line([(76, 44), (94, 48)], fill=(45, 30, 20), width=2)

# nose — straight, fine
draw.line([(68, 64), (66, 78)], fill=(180, 145, 122), width=2)
draw.ellipse([(62, 76), (78, 84)], fill=(195, 158, 134))

# mouth — closed, a little wry
draw.line([(56, 88), (84, 88)], fill=(165, 118, 105), width=2)
draw.arc([(58, 84), (82, 94)], start=5, end=50, fill=(185, 135, 115), width=1)

# ── hair — dark, long, loose ──────────────────────────────────────────────────
hair = (32, 22, 18)
hair_hi = (55, 40, 30)

# top of head
draw.ellipse([(36, 18), (104, 62)], fill=hair)
# left fall — past shoulder
draw.polygon([
    (38, 38), (26, 50),
    (18, 95), (22, 130),
    (32, 135), (38, 120),
    (38, 80)
], fill=hair)
# right fall
draw.polygon([
    (102, 38), (114, 50),
    (122, 95), (118, 130),
    (108, 135), (102, 120),
    (102, 80)
], fill=hair)
# hair highlight — catches light on left
draw.polygon([
    (44, 20), (64, 18), (60, 34), (42, 38)
], fill=hair_hi)
# a few loose strands
draw.line([(38, 60), (28, 85)], fill=hair, width=2)
draw.line([(102, 60), (112, 85)], fill=hair, width=2)
draw.line([(70, 18), (68, 28)], fill=hair_hi, width=1)

img.save(out_dir / "loki_stand.png")

# copy to other poses — paint them separately later
for pose in ("loki_sit.png", "loki_sleep.png", "loki_crouch.png",
             "loki_spar.png", "loki_bath.png"):
    img.save(out_dir / pose)

print("Saved → workspace/images/loki_stand.png")
print("Open in GIMP and paint over him.")
