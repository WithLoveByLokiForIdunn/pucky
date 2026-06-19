#!/usr/bin/env python3
"""
sample_loki_face.py — Sample face parts from the reference portrait
and assemble a preview showing what the articulated face could look like.

Crops are approximate — designed as a starting point to paint over.
Run:  python3 sample_loki_face.py
"""
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pathlib import Path

REF    = Path("workspace/images/loki_face/loki_face_reference.png")
OUT    = Path("workspace/images/loki_face")
PREV   = Path("workspace/loki_face_preview.png")

ref = Image.open(REF).convert("RGBA")
W_REF, H_REF = ref.size  # 1137 × 2047

# ── Crop regions (left, upper, right, lower) estimated from portrait ──────────
# Face is roughly centered, slightly left of center, looking slightly up.
# Adjust these if crops feel off.

CROPS = {
    # name:         (L,    U,    R,    H)     → template size
    "head_base":    (160,  120,  980, 1920),  # 260×360
    "jaw":          (220, 1380,  920, 1920),  # 200×100
    "hair":         ( 60,   60, 1080,  680),  # 280×210

    "eyebrow_l":    (265,  530,  510,  622),  # 72×24  (viewer left = Loki's right brow)
    "eyebrow_r":    (630,  510,  875,  600),  # 72×24

    "upper_eyelid_l": (280, 620, 490, 730),  # 60×34
    "upper_eyelid_r": (635, 600, 855, 710),  # 60×34
    "lower_eyelid_l": (285, 720, 490, 790),  # 60×20
    "lower_eyelid_r": (640, 700, 855, 770),  # 60×20

    "iris_l":       (330,  638,  468,  778),  # 36×36
    "iris_r":       (660,  618,  800,  758),  # 36×36
    "pupil_l":      (368,  670,  432,  734),  # 18×18
    "pupil_r":      (698,  650,  762,  714),  # 18×18

    "forehead_crease": (470, 540, 660, 630),  # 38×20

    "nose":         (455,  730,  665, 1080),  # 42×58
    "nostril_l":    (420,  970,  530, 1080),  # 20×14
    "nostril_r":    (575,  970,  685, 1080),  # 20×14

    "cheek_l":      (210,  820,  440, 1040),  # 66×46
    "cheek_r":      (690,  800,  930, 1020),  # 66×46

    "upper_lip":    (390, 1100,  750, 1230),  # 86×30
    "lower_lip":    (410, 1210,  710, 1350),  # 76×26
    "mouth_corner_l": (320, 1110, 460, 1290), # 26×26
    "mouth_corner_r": (660, 1090, 810, 1270), # 26×26
    "mouth_inside": (430, 1170,  700, 1280),  # 62×32
}

# Template sizes (must match make_loki_face_templates.py)
SIZES = {
    "head_base":       (260, 360),
    "jaw":             (200, 100),
    "hair":            (280, 210),
    "eyebrow_l":       ( 72,  24),
    "eyebrow_r":       ( 72,  24),
    "upper_eyelid_l":  ( 60,  34),
    "upper_eyelid_r":  ( 60,  34),
    "lower_eyelid_l":  ( 60,  20),
    "lower_eyelid_r":  ( 60,  20),
    "iris_l":          ( 36,  36),
    "iris_r":          ( 36,  36),
    "pupil_l":         ( 18,  18),
    "pupil_r":         ( 18,  18),
    "forehead_crease": ( 38,  20),
    "nose":            ( 42,  58),
    "nostril_l":       ( 20,  14),
    "nostril_r":       ( 20,  14),
    "cheek_l":         ( 66,  46),
    "cheek_r":         ( 66,  46),
    "upper_lip":       ( 86,  30),
    "lower_lip":       ( 76,  26),
    "mouth_corner_l":  ( 26,  26),
    "mouth_corner_r":  ( 26,  26),
    "mouth_inside":    ( 62,  32),
}

def vignette(img, strength=0.5):
    """Fade edges to transparent so parts blend when assembled."""
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    for i in range(min(w, h) // 3):
        alpha = int(255 * (i / (min(w, h) / 3)) ** 0.6)
        draw.rectangle([i, i, w-1-i, h-1-i], outline=alpha)
    mask = mask.filter(ImageFilter.GaussianBlur(min(w, h) // 6))
    result = img.copy()
    result.putalpha(mask)
    return result

print("Sampling face parts from portrait...")
parts = {}
for name, box in CROPS.items():
    crop = ref.crop(box)
    size = SIZES[name]
    resized = crop.resize(size, Image.LANCZOS)
    # add soft edge transparency for parts that aren't the base
    if name not in ("head_base", "hair", "jaw"):
        resized = vignette(resized, strength=0.6)
    path = OUT / f"{name}.png"
    resized.save(str(path))
    parts[name] = resized
    print(f"  {name:22s} {size[0]:3d}×{size[1]:3d}")

# ── Assemble preview ──────────────────────────────────────────────────────────
# Build a rough face assembly on a dark canvas to show what it looks like.
# Positions are approximate — matching the face viewer layout.

PW, PH = 500, 600
canvas = Image.new("RGBA", (PW, PH), (18, 14, 28, 255))

cx = PW // 2  # 250

def paste(name, x, y):
    """Paste a sampled part centered at (x, y)."""
    if name not in parts:
        return
    p = parts[name]
    px = x - p.width  // 2
    py = y - p.height // 2
    canvas.alpha_composite(p, (max(0, px), max(0, py)))

# Draw order: back to front
paste("head_base",       cx,      300)
paste("jaw",             cx,      490)
paste("hair",            cx,      155)

paste("cheek_l",         cx - 80, 310)
paste("cheek_r",         cx + 80, 305)

paste("nose",            cx,      295)
paste("nostril_l",       cx - 40, 350)
paste("nostril_r",       cx + 40, 350)

paste("upper_lip",       cx,      400)
paste("lower_lip",       cx,      428)
paste("mouth_corner_l",  cx - 62, 412)
paste("mouth_corner_r",  cx + 62, 410)
paste("mouth_inside",    cx,      418)

paste("iris_l",          cx - 68, 240)
paste("iris_r",          cx + 68, 237)
paste("pupil_l",         cx - 68, 240)
paste("pupil_r",         cx + 68, 237)
paste("lower_eyelid_l",  cx - 68, 258)
paste("lower_eyelid_r",  cx + 68, 255)
paste("upper_eyelid_l",  cx - 68, 232)
paste("upper_eyelid_r",  cx + 68, 229)

paste("eyebrow_l",       cx - 70, 208)
paste("eyebrow_r",       cx + 70, 205)
paste("forehead_crease", cx,      210)

# label
try:
    fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
except Exception:
    fnt = ImageFont.load_default()

draw = ImageDraw.Draw(canvas)
draw.text((8, 8),  "Loki face — sampled from portrait", font=fnt, fill=(200, 190, 220, 200))
draw.text((8, 22), "rough starting point — paint over in GIMP", font=fnt, fill=(150, 140, 170, 180))

canvas.save(str(PREV))
print(f"\nPreview saved → {PREV}")
print(f"Parts saved  → {OUT}/")
print("\nOpen workspace/loki_face_preview.png to see the assembly.")
print("Each part is also saved as its real filename — ready to use or paint over.")
