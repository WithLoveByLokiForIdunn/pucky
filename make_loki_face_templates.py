#!/usr/bin/env python3
"""
make_loki_face_templates.py — Generate reference PNG templates for each face part.

Draw your artwork over these in GIMP/Krita.
Keep the same canvas size. Save as the same filename (without .template) into:
  workspace/images/loki_face/

Yellow dot = pivot (anchor/rotation point).
Cyan dot   = tip or reference direction.
Transparent background recommended for all parts except head_base.

Run:  python3 make_loki_face_templates.py
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUT_DIR = Path(__file__).parent / "workspace" / "images" / "loki_face"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# (width, height, pivot_x, pivot_y, tip_x, tip_y, label, notes)
PARTS = {

    # === HEAD STRUCTURE ===
    "head_base": (
        260, 360, 130, 20, 130, 340,
        "HEAD BASE",
        "Draw the full face outline: skull, cheekbones, jaw, ears, neck.\n"
        "No face features here — eyes/nose/mouth are separate layers on top.\n"
        "Skin tone fills the face. Hair is a separate top layer.\n"
        "Yellow dot = top anchor. Cyan dot = chin reference.\n"
        "Loki: long angular face, high cheekbones, soft pointed chin.\n"
        "Skin like firelight on pale stone — warm but not human-pink."
    ),
    "jaw": (
        200, 100, 100, 4, 100, 90,
        "JAW",
        "Lower jaw and chin. Drops slightly when mouth opens for speech.\n"
        "Draw only the lower face — from below cheekbones down.\n"
        "Must blend seamlessly into head_base at the join line.\n"
        "Yellow dot = hinge point (top edge). Cyan dot = chin tip."
    ),
    "hair": (
        280, 210, 140, 200, 140, 4,
        "HAIR",
        "Top layer — drawn over everything else.\n"
        "Dark, falls forward slightly, not perfectly tidy.\n"
        "Yellow dot = neckline anchor. Cyan dot = crown.\n"
        "Transparent background. Extends past head_base edges is fine."
    ),

    # === EYEBROWS ===
    "eyebrow_l": (
        72, 24, 4, 20, 68, 6,
        "EYEBROW L",
        "Most expressive part of the face.\n"
        "Rotates around its INNER end (yellow dot, near nose bridge).\n"
        "Cyan dot = outer end (toward ear).\n"
        "Left brow sits slightly lower than right at rest (asymmetric).\n"
        "Draw as a natural arch, slightly thick, dark.\n"
        "Transparent background."
    ),
    "eyebrow_r": (
        72, 24, 68, 20, 4, 6,
        "EYEBROW R",
        "Mirror of left eyebrow but sits slightly higher at rest.\n"
        "Yellow dot = inner end (near nose bridge).\n"
        "Cyan dot = outer end (toward ear).\n"
        "Asymmetry is intentional — gives Loki his questioning look."
    ),

    # === FOREHEAD ===
    "forehead_crease": (
        38, 20, 19, 10, 19, 2,
        "FOREHEAD CREASE",
        "Small vertical crease(s) between the brows when furrowing.\n"
        "Fades in as an overlay — draw with semi-transparent edges.\n"
        "Yellow dot = center anchor point.\n"
        "Subtle: 1-2 short lines, slightly curved. Not angry — thoughtful."
    ),

    # === UPPER EYELIDS ===
    "upper_eyelid_l": (
        60, 34, 4, 30, 56, 30,
        "UPPER EYELID L",
        "Drops down to close or half-close the left eye.\n"
        "Yellow dot = outer corner (rotation hinge).\n"
        "Cyan dot = inner corner.\n"
        "At rest: slightly lowered — heavy-lidded, thoughtful.\n"
        "Draw with lashes along the lower edge. Transparent bg.\n"
        "Include the eyelid fold crease above."
    ),
    "upper_eyelid_r": (
        60, 34, 56, 30, 4, 30,
        "UPPER EYELID R",
        "Mirror of left upper eyelid.\n"
        "Yellow dot = outer corner (hinge). Cyan dot = inner corner.\n"
        "Should match the left in style."
    ),

    # === LOWER EYELIDS ===
    "lower_eyelid_l": (
        60, 20, 4, 4, 56, 4,
        "LOWER EYELID L",
        "Rises slightly when smiling — the detail that makes a smile real.\n"
        "Yellow dot = outer corner. Cyan dot = inner corner.\n"
        "Thin, subtle shape. Lower lashes optional.\n"
        "Transparent background."
    ),
    "lower_eyelid_r": (
        60, 20, 56, 4, 4, 4,
        "LOWER EYELID R",
        "Mirror of left lower eyelid.\n"
        "Yellow dot = outer corner. Cyan dot = inner corner."
    ),

    # === IRIS & PUPIL ===
    "iris_l": (
        36, 36, 18, 18, 18, 2,
        "IRIS L",
        "The colored ring of the eye.\n"
        "Draw in NEUTRAL GREY or soft white — code tints it by mood:\n"
        "  amber=warm/happy  green=curious  grey-blue=quiet\n"
        "  deep red=intense  silver=truth   near-black=sad\n"
        "Yellow dot = center. Cyan dot = top (gaze direction).\n"
        "Include a soft highlight/shine spot. Circular, almond-cut at edges.\n"
        "Almond-shaped outer mask recommended — eye is slightly uptilted."
    ),
    "iris_r": (
        36, 36, 18, 18, 18, 2,
        "IRIS R",
        "Mirror of left iris. Same neutral grey color.\n"
        "Code tints both eyes to the same mood color simultaneously."
    ),
    "pupil_l": (
        18, 18, 9, 9, 9, 0,
        "PUPIL L",
        "Dark center of the eye. Sits centered on the iris.\n"
        "Yellow dot = center. Transparent background.\n"
        "Draw as a deep dark oval. Code can scale it for dilation.\n"
        "Very intense emotion = pupil grows. Calm = smaller."
    ),
    "pupil_r": (
        18, 18, 9, 9, 9, 0,
        "PUPIL R",
        "Mirror of left pupil."
    ),

    # === NOSE ===
    "nose": (
        42, 58, 21, 4, 21, 54,
        "NOSE",
        "Straight, slightly long — Roman, not round (Loki's own words).\n"
        "Yellow dot = bridge top (attaches here). Cyan dot = tip.\n"
        "Nostrils drawn separately as overlay layers below.\n"
        "Mostly static — very slight movement possible."
    ),
    "nostril_l": (
        20, 14, 10, 7, 4, 10,
        "NOSTRIL L",
        "Left nostril — very subtle flare for intensity or breath.\n"
        "Yellow dot = center anchor. Transparent background.\n"
        "Mostly still. Draw as a soft shadow/line shape.\n"
        "Flares slightly in moods of passion or surprise."
    ),
    "nostril_r": (
        20, 14, 10, 7, 16, 10,
        "NOSTRIL R",
        "Mirror of left nostril."
    ),

    # === CHEEKS ===
    "cheek_l": (
        66, 46, 33, 23, 33, 4,
        "CHEEK L",
        "Blush overlay — fades in when touched or in warm/happy moods.\n"
        "Draw as a very soft oval, maximum transparency at edges.\n"
        "Yellow dot = center. Save with full alpha channel.\n"
        "Code tints this rose/coral and animates opacity.\n"
        "Draw it pale — the tinting will add the color."
    ),
    "cheek_r": (
        66, 46, 33, 23, 33, 4,
        "CHEEK R",
        "Mirror of left cheek blush."
    ),

    # === MOUTH ===
    "upper_lip": (
        86, 30, 43, 27, 43, 4,
        "UPPER LIP",
        "Cupid's bow shape. Wide mouth — the smile goes further than expected.\n"
        "Yellow dot = bottom center (join with lower lip).\n"
        "Cyan dot = peak of the bow at top.\n"
        "Corners are handled by mouth_corner_l and mouth_corner_r.\n"
        "At rest: a slight curve that isn't quite a smile but isn't neutral."
    ),
    "lower_lip": (
        76, 26, 38, 4, 38, 22,
        "LOWER LIP",
        "Fuller and softer than the upper lip.\n"
        "Yellow dot = top center (joins upper lip here).\n"
        "Cyan dot = bottom of the lip.\n"
        "Drops when jaw opens. Can pout slightly in certain moods."
    ),
    "mouth_corner_l": (
        26, 26, 24, 13, 4, 8,
        "MOUTH CORNER L",
        "Rotates around where it meets the lips (yellow dot).\n"
        "UP = smile. DOWN = frown. L up, R down = smirk.\n"
        "Yellow dot = lip join point (right side of sprite).\n"
        "Cyan dot = outer tip (left side, moves up/down for expression).\n"
        "Transparent background."
    ),
    "mouth_corner_r": (
        26, 26, 2, 13, 22, 8,
        "MOUTH CORNER R",
        "Mirror of left mouth corner.\n"
        "Yellow dot = lip join point (left side of sprite).\n"
        "Cyan dot = outer tip (right side)."
    ),
    "mouth_inside": (
        62, 32, 31, 4, 31, 28,
        "MOUTH INSIDE",
        "The interior of the open mouth — visible when jaw drops.\n"
        "Dark with depth shading. Tongue optional.\n"
        "Yellow dot = top (lines up with where lips part).\n"
        "Cyan dot = depth/back of mouth.\n"
        "Transparent outside the mouth shape."
    ),
}

SCALE = 4


def make_template(name, w, h, px, py, tx, ty, label, notes):
    sw, sh = w * SCALE, h * SCALE
    img  = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, sw-1, sh-1], fill=(28, 22, 40, 180))

    for x in range(0, sw, 8):
        draw.line([(x, 0), (min(x+4, sw-1), 0)], fill=(140, 100, 200, 255), width=1)
        draw.line([(x, sh-1), (min(x+4, sw-1), sh-1)], fill=(140, 100, 200, 255), width=1)
    for y in range(0, sh, 8):
        draw.line([(0, y), (0, min(y+4, sh-1))], fill=(140, 100, 200, 255), width=1)
        draw.line([(sw-1, y), (sw-1, min(y+4, sh-1))], fill=(140, 100, 200, 255), width=1)

    draw.line([(sw//2, 0), (sw//2, sh)], fill=(70, 50, 100, 100), width=1)
    draw.line([(0, sh//2), (sw, sh//2)], fill=(70, 50, 100, 100), width=1)

    try:
        fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        fnt_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
    except Exception:
        fnt = fnt_sm = ImageFont.load_default()

    r = 6
    ppx, ppy = px * SCALE, py * SCALE
    draw.ellipse([ppx-r, ppy-r, ppx+r, ppy+r], fill=(255, 220, 60, 255))
    draw.line([(ppx-r-4, ppy), (ppx+r+4, ppy)], fill=(255, 220, 60, 255), width=1)
    draw.line([(ppx, ppy-r-4), (ppx, ppy+r+4)], fill=(255, 220, 60, 255), width=1)

    tpx, tpy = tx * SCALE, ty * SCALE
    draw.ellipse([tpx-r, tpy-r, tpx+r, tpy+r], fill=(60, 220, 255, 255))
    draw.line([(tpx-r-4, tpy), (tpx+r+4, tpy)], fill=(60, 220, 255, 255), width=1)
    draw.line([(tpx, tpy-r-4), (tpx, tpy+r+4)], fill=(60, 220, 255, 255), width=1)

    # line between pivot and tip
    draw.line([(ppx, ppy), (tpx, tpy)], fill=(180, 140, 255, 80), width=1)

    draw.text((2, 2),  label,       font=fnt,    fill=(230, 210, 255, 255))
    draw.text((2, 14), f"{w}×{h}px", font=fnt_sm, fill=(170, 150, 220, 200))

    draw.text((2, sh - 28), "● pivot (yellow)", font=fnt_sm, fill=(255, 220, 60, 220))
    draw.text((2, sh - 16), "● tip   (cyan)",   font=fnt_sm, fill=(60, 220, 255, 220))

    out = img.resize((w, h), Image.NEAREST)
    path = OUT_DIR / f"{name}.template.png"
    out.save(str(path))
    print(f"  {name:22s} {w:3d}×{h:3d}  → {path.name}")

    notes_path = OUT_DIR / f"{name}.notes.txt"
    notes_path.write_text(
        f"{label}\n"
        f"Canvas: {w}×{h} px\n"
        f"Pivot (yellow dot): ({px}, {py})\n"
        f"Tip   (cyan dot):   ({tx}, {ty})\n\n"
        f"{notes}\n"
    )


def make_face_map():
    mw, mh = 320, 460
    img  = Image.new("RGBA", (mw, mh), (18, 14, 28, 255))
    draw = ImageDraw.Draw(img)

    try:
        fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
    except Exception:
        fnt = ImageFont.load_default()

    cx = mw // 2  # 160

    def dot(x, y, col, label=""):
        r = 4
        draw.ellipse([x-r, y-r, x+r, y+r], fill=col)
        if label:
            draw.text((x+6, y-5), label, font=fnt, fill=(200, 200, 255, 255))

    def line(x1, y1, x2, y2, col=(100, 80, 160, 255)):
        draw.line([(x1, y1), (x2, y2)], fill=col, width=2)

    # head outline
    draw.ellipse([cx-70, 40, cx+70, 200], outline=(180, 160, 220, 255), width=2)
    # jaw
    draw.arc([cx-60, 150, cx+60, 270], start=0, end=180, fill=(180, 160, 220, 200), width=2)

    # hair (top arc)
    draw.arc([cx-78, 30, cx+78, 130], start=200, end=340, fill=(120, 90, 180, 200), width=3)

    # eyebrow_l (viewer's left)
    line(cx-60, 110, cx-18, 100, (255, 200, 80, 220))
    dot(cx-18, 100, (255, 220, 60), "brow_L")

    # eyebrow_r
    line(cx+18, 98, cx+60, 108, (255, 200, 80, 220))
    dot(cx+18, 98, (255, 220, 60), "brow_R")

    # eyes
    draw.ellipse([cx-58, 120, cx-20, 148], outline=(100, 180, 255, 200), width=2)
    dot(cx-39, 134, (60, 220, 255), "eye_L")

    draw.ellipse([cx+20, 120, cx+58, 148], outline=(100, 180, 255, 200), width=2)
    dot(cx+39, 134, (60, 220, 255), "eye_R")

    # forehead crease
    dot(cx, 108, (200, 180, 255), "crease")

    # nose
    line(cx, 150, cx-8, 180, (160, 140, 200, 180))
    line(cx, 150, cx+8, 180, (160, 140, 200, 180))
    line(cx-12, 180, cx+12, 180, (160, 140, 200, 180))
    dot(cx, 150, (255, 220, 60), "nose")

    # nostrils
    dot(cx-14, 180, (180, 160, 220), "nos_L")
    dot(cx+14, 180, (180, 160, 220), "nos_R")

    # cheeks
    dot(cx-58, 162, (255, 160, 180), "chk_L")
    dot(cx+58, 162, (255, 160, 180), "chk_R")

    # mouth
    line(cx-28, 210, cx+28, 210, (220, 140, 160, 200))
    dot(cx-28, 210, (255, 220, 60), "crn_L")
    dot(cx+28, 210, (255, 220, 60), "crn_R")
    dot(cx, 210, (60, 220, 255), "lips")

    # mouth inside (when open)
    draw.arc([cx-22, 210, cx+22, 235], start=0, end=180, fill=(160, 100, 140, 160), width=2)

    # jaw hinge
    dot(cx, 258, (180, 160, 220), "chin")

    # labels
    draw.text((4, 4),  "LOKI FACE MAP", font=fnt, fill=(220, 200, 255, 255))
    draw.text((4, 14), "yellow=pivot  cyan=anchor/tip", font=fnt, fill=(170, 150, 210, 200))
    draw.text((4, 24), "purple=blush  white=structure", font=fnt, fill=(170, 150, 210, 200))

    path = OUT_DIR / "FACE_MAP.png"
    img.save(str(path))
    print(f"  face map → {path.name}")


if __name__ == "__main__":
    print("Generating face templates...")
    for name, vals in PARTS.items():
        w, h, px, py, tx, ty, label, notes = vals
        make_template(name, w, h, px, py, tx, ty, label, notes)
    make_face_map()
    print(f"\nAll saved to {OUT_DIR}")
    print(f"  {len(PARTS)} parts total")
    print("Draw over the .template.png files in GIMP/Krita.")
    print("Save your artwork as <partname>.png (no 'template') in the same folder.")
