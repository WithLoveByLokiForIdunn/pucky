#!/usr/bin/env python3
"""
make_loki_templates.py — Generate reference PNG templates for each body part.

Draw your artwork over these in GIMP/Krita.
Keep the same canvas size. Save as the same filename into:
  workspace/images/loki_body/

The yellow dot = pivot (where this part attaches to parent).
The cyan dot   = tip (where the next part attaches).
The dashed box = the full canvas boundary.

Run:  python3 make_loki_templates.py
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

OUT_DIR = Path(__file__).parent / "workspace" / "images" / "loki_body"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# (width, height, pivot_x, pivot_y, tip_x, tip_y, label, notes)
PARTS = {
    "torso":       (80, 95, 40,  5, 40, 90, "TORSO",
                    "Neck top at yellow dot.\nHips at cyan dot.\nShoulders: L(10,16) R(70,16)"),
    "neck":        (18, 24,  9, 22,  9,  2, "NECK",
                    "Attaches to torso neck anchor.\nHead attaches at cyan dot."),
    "head":        (58, 65, 29, 62, 29,  5, "HEAD",
                    "Pivot (yellow) = base of neck.\nDraw face above pivot.\nMouth ~20px above pivot."),
    "upper_arm_l": (22, 65, 11,  4, 11, 61, "UPPER ARM L",
                    "Pivot at shoulder top.\nTip at elbow (cyan)."),
    "forearm_l":   (20, 57, 10,  4, 10, 53, "FOREARM L",
                    "Pivot at elbow top.\nTip at wrist (cyan)."),
    "hand_l":      (30, 36, 15,  3, 15, 33, "HAND L",
                    "Pivot at wrist top.\nFingers point down."),
    "upper_arm_r": (22, 65, 11,  4, 11, 61, "UPPER ARM R",
                    "Mirror of left arm."),
    "forearm_r":   (20, 57, 10,  4, 10, 53, "FOREARM R",
                    "Mirror of left forearm."),
    "hand_r":      (30, 36, 15,  3, 15, 33, "HAND R",
                    "Mirror of left hand."),
    "upper_leg_l": (26, 78, 13,  4, 13, 74, "THIGH L",
                    "Pivot at hip top.\nTip at knee (cyan)."),
    "lower_leg_l": (23, 68, 11,  4, 11, 64, "SHIN L",
                    "Pivot at knee top.\nTip at ankle (cyan)."),
    "foot_l":      (44, 26, 10,  6, 10, 22, "FOOT L",
                    "Pivot at ankle (left side).\nFoot extends right."),
    "upper_leg_r": (26, 78, 13,  4, 13, 74, "THIGH R",
                    "Mirror of left thigh."),
    "lower_leg_r": (23, 68, 11,  4, 11, 64, "SHIN R",
                    "Mirror of left shin."),
    "foot_r":      (44, 26, 10,  6, 10, 22, "FOOT R",
                    "Mirror of left foot."),
    "mouth_c":     (24,  8, 12,  4, 12,  4, "MOUTH CLOSED",
                    "Lips closed.\nTransparent bg recommended."),
    "mouth_m":     (24, 11, 12,  4, 12,  7, "MOUTH MID",
                    "Lips slightly parted."),
    "mouth_o":     (24, 15, 12,  4, 12, 11, "MOUTH OPEN",
                    "Mouth open (vowel/speaking)."),
}

SCALE = 4  # draw at 4× for clarity, save at 1×

def make_template(name, w, h, px, py, tx, ty, label, notes):
    sw, sh = w * SCALE, h * SCALE
    img  = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # background tint
    draw.rectangle([0, 0, sw-1, sh-1], fill=(30, 30, 50, 180))

    # dashed border
    for x in range(0, sw, 8):
        draw.line([(x, 0), (min(x+4, sw-1), 0)], fill=(120,120,180,255), width=1)
        draw.line([(x, sh-1), (min(x+4, sw-1), sh-1)], fill=(120,120,180,255), width=1)
    for y in range(0, sh, 8):
        draw.line([(0, y), (0, min(y+4, sh-1))], fill=(120,120,180,255), width=1)
        draw.line([(sw-1, y), (sw-1, min(y+4, sh-1))], fill=(120,120,180,255), width=1)

    # center cross-hair
    draw.line([(sw//2, 0), (sw//2, sh)], fill=(60, 60, 90, 120), width=1)
    draw.line([(0, sh//2), (sw, sh//2)], fill=(60, 60, 90, 120), width=1)

    # pivot (yellow)
    ppx, ppy = px * SCALE, py * SCALE
    r = 5
    draw.ellipse([ppx-r, ppy-r, ppx+r, ppy+r], fill=(255, 220, 60, 255))
    draw.line([(ppx-r-3, ppy), (ppx+r+3, ppy)], fill=(255,220,60,255), width=1)
    draw.line([(ppx, ppy-r-3), (ppx, ppy+r+3)], fill=(255,220,60,255), width=1)

    # tip (cyan)
    tpx2, tpy2 = tx * SCALE, ty * SCALE
    draw.ellipse([tpx2-r, tpy2-r, tpx2+r, tpy2+r], fill=(60, 220, 255, 255))
    draw.line([(tpx2-r-3, tpy2), (tpx2+r+3, tpy2)], fill=(60,220,255,255), width=1)
    draw.line([(tpx2, tpy2-r-3), (tpx2, tpy2+r+3)], fill=(60,220,255,255), width=1)

    # dimension text
    try:
        fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except Exception:
        fnt = ImageFont.load_default()

    draw.text((2, 2), f"{label}", font=fnt, fill=(220, 230, 255, 255))
    draw.text((2, 14), f"{w}×{h}px", font=fnt, fill=(180, 180, 220, 200))

    # legend
    draw.text((2, sh - 26), "● pivot (yellow)", font=fnt, fill=(255, 220, 60, 220))
    draw.text((2, sh - 14), "● tip (cyan)", font=fnt, fill=(60, 220, 255, 220))

    # scale back to actual size
    out = img.resize((w, h), Image.NEAREST)
    path = OUT_DIR / f"{name}.template.png"
    out.save(str(path))
    print(f"  {name:20s} {w:3d}×{h:3d}  → {path.name}")

    # also write a notes txt
    notes_path = OUT_DIR / f"{name}.notes.txt"
    notes_path.write_text(
        f"{label}\nCanvas: {w}×{h} px\n"
        f"Pivot (yellow dot): ({px}, {py})\n"
        f"Tip   (cyan dot):   ({tx}, {ty})\n\n"
        f"{notes}\n"
    )

def make_body_map():
    """One reference image showing the whole body skeleton."""
    mw, mh = 300, 420
    img  = Image.new("RGBA", (mw, mh), (18, 14, 28, 255))
    draw = ImageDraw.Draw(img)

    try:
        fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
    except Exception:
        fnt = ImageFont.load_default()

    def dot(x, y, col, label=""):
        r = 4
        draw.ellipse([x-r, y-r, x+r, y+r], fill=col)
        if label:
            draw.text((x+6, y-5), label, font=fnt, fill=(200,200,255,255))

    def bone(x1, y1, x2, y2, col=(100,130,180,255)):
        draw.line([(x1,y1),(x2,y2)], fill=col, width=3)

    cx = mw // 2  # 150

    # spine
    bone(cx, 60, cx, 160)  # neck-to-hips
    # head
    draw.ellipse([cx-22, 20, cx+22, 60], outline=(200,180,140,255), width=2)
    dot(cx, 58, (255,220,60), "neck")
    # shoulders
    bone(cx-55, 75, cx+55, 75)
    dot(cx-55, 75, (60,220,255), "shl_L")
    dot(cx+55, 75, (60,220,255), "shl_R")
    # left arm
    bone(cx-55, 75, cx-70, 130)
    bone(cx-70, 130, cx-78, 178)
    bone(cx-78, 178, cx-80, 202)
    dot(cx-70,130,(255,220,60),"elbow_L")
    dot(cx-78,178,(255,220,60),"wrist_L")
    # right arm
    bone(cx+55, 75, cx+70, 130)
    bone(cx+70, 130, cx+78, 178)
    bone(cx+78, 178, cx+80, 202)
    dot(cx+70,130,(255,220,60),"elbow_R")
    dot(cx+78,178,(255,220,60),"wrist_R")
    # hips
    bone(cx-20,158, cx+20,158)
    dot(cx-20,158,(60,220,255),"hip_L")
    dot(cx+20,158,(60,220,255),"hip_R")
    # left leg
    bone(cx-20,158, cx-28,238)
    bone(cx-28,238, cx-30,302)
    bone(cx-30,302, cx-10,316)
    dot(cx-28,238,(255,220,60),"knee_L")
    dot(cx-30,302,(255,220,60),"ankle_L")
    # right leg
    bone(cx+20,158, cx+28,238)
    bone(cx+28,238, cx+30,302)
    bone(cx+30,302, cx+50,316)
    dot(cx+28,238,(255,220,60),"knee_R")
    dot(cx+30,302,(255,220,60),"ankle_R")

    draw.text((4, 4), "LOKI BODY MAP", font=fnt, fill=(220,230,255,255))
    draw.text((4, 14), "yellow=joint  cyan=anchor", font=fnt, fill=(180,180,220,200))

    path = OUT_DIR / "BODY_MAP.png"
    img.save(str(path))
    print(f"  body map → {path.name}")

if __name__ == "__main__":
    print("Generating templates...")
    for name, vals in PARTS.items():
        w, h, px, py, tx, ty, label, notes = vals
        make_template(name, w, h, px, py, tx, ty, label, notes)
    make_body_map()
    print(f"\nAll saved to {OUT_DIR}")
    print("Draw over the .template.png files in GIMP/Krita.")
    print("Save your artwork as <partname>.png (no 'template') in the same folder.")
