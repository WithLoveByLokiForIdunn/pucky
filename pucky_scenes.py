"""
pucky_scenes.py — JoJo-style close-up scenes for intimate interactions.

When characters sit, hug, dance, sing together, or a visitor arrives,
the world steps back and a dramatic close-up takes over.

The art style is JoJo's Bizarre Adventure: thick outlines, diagonal
hatching in shadow areas, bold diamond backgrounds, floating symbols.
But the feeling is always gentle and sweet — rosy cheeks on Pucky,
hearts rising during hugs, the fox looking impossibly dignified.
"""

import math
import random
import time
from dataclasses import dataclass, field
from typing import Optional

# ── Scene type constants ───────────────────────────────────────────────────────
SCENE_VISITOR    = "visitor"
SCENE_SIT        = "sit"
SCENE_HUG        = "hug"
SCENE_DANCE      = "dance"
SCENE_SING       = "sing"
SCENE_HUM        = "hum"
SCENE_CAMPFIRE   = "campfire"
SCENE_STARGAZING = "stargazing"
SCENE_SHARE      = "share_apple"

# Background diamond colour pairs (dark, light)
_BG = {
    SCENE_VISITOR:    ((170,  70,  30), (230, 140,  50)),
    SCENE_SIT:        (( 50, 105,  60), (185, 215, 155)),
    SCENE_HUG:        ((140,  40,  70), (255, 190, 185)),
    SCENE_DANCE:      (( 70,  40, 150), (155, 195, 255)),
    SCENE_SING:       (( 35,  90, 120), (185, 170, 235)),
    SCENE_HUM:        (( 35,  72, 100), (165, 195, 225)),
    SCENE_CAMPFIRE:   (( 80,  36,  16), (245, 165,  65)),
    SCENE_STARGAZING: ((  6,  10,  36), ( 70,  52, 135)),
    SCENE_SHARE:      (( 80, 130,  50), (235, 200, 130)),
}

# Floating symbols per scene
_FLOATS = {
    SCENE_VISITOR:    [("◆",(255,200, 90)), ("◆",(255,155, 50)), ("♥",(255,140,160))],
    SCENE_SIT:        [("♥",(255,160,180)), ("✦",(255,225,175)), ("♪",(195,240,200))],
    SCENE_HUG:        [("♥",(255,125,155)), ("♥",(255,175,195)), ("✦",(255,215,175))],
    SCENE_DANCE:      [("♪",(195,175,255)), ("♫",(175,200,255)), ("✦",(255,225,175))],
    SCENE_SING:       [("♪",(195,225,255)), ("♫",(175,205,240)), ("♩",(215,195,250))],
    SCENE_HUM:        [("♪",(175,205,228)), ("✦",(200,215,238))],
    SCENE_CAMPFIRE:   [("✦",(255,195, 95)), ("◆",(255,155, 75)), ("♥",(255,175,135))],
    SCENE_STARGAZING: [("✦",(195,215,255)), ("★",(215,205,175)), ("◈",(175,175,235))],
    SCENE_SHARE:      [("♥",(255,160,160)), ("✦",(255,220,130)), ("◆",(200,240,150))],
}


@dataclass
class _Particle:
    symbol:    str
    x:         float
    y:         float
    vx:        float
    vy:        float
    alpha:     float
    fade:      float
    color:     tuple
    size:      int


def _ease_out(x: float) -> float:
    return 1.0 - (1.0 - max(0.0, min(1.0, x))) ** 3


# ── Close-up portrait helpers ─────────────────────────────────────────────────

def _outlined_rect(surf, rect, fill, border=(20,20,20), radius=4, bw=4):
    import pygame
    big = rect.inflate(bw*2, bw*2)
    pygame.draw.rect(surf, border, big, border_radius=radius + bw)
    pygame.draw.rect(surf, fill,   rect, border_radius=radius)

def _hatch(surf, rect, spacing=9, alpha=65):
    """Diagonal hatching for JoJo shadow areas."""
    import pygame
    s = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    h = rect.height
    x = -h
    while x < rect.width + h:
        pygame.draw.line(s, (20, 20, 20, alpha), (x, 0), (x + h, h), 1)
        x += spacing
    surf.blit(s, rect.topleft)

def _menacing(surf, x, y, t, color=(255,200,80), symbols=("◆","◆","◆"), size=13):
    """Floating JoJo ◆◆◆ or ♥♥♥ or ♪♪ glyphs."""
    import pygame
    try:
        f = pygame.font.SysFont("segoeuisymbol,symbola,dejavusans", size, bold=True)
        for i, sym in enumerate(symbols):
            ox = x + i * (size + 4)
            oy = y + int(math.sin(t * 1.3 + i * 1.5) * 5)
            a  = int(145 + math.sin(t * 2.1 + i) * 70)
            rs = pygame.Surface((size + 4, size + 6), pygame.SRCALPHA)
            txt = f.render(sym, True, (*color, a))
            rs.blit(txt, (2, 2))
            surf.blit(rs, (ox, oy))
    except Exception:
        pass


# ── Portrait: Pucky ───────────────────────────────────────────────────────────

def draw_pucky_portrait(surf, cx, cy, t, mood="content"):
    import pygame
    bw, bh = 80, 108
    # legs
    for lx in (cx - 22, cx + 10):
        _outlined_rect(surf, pygame.Rect(lx, cy - 2, 12, 20),
                       (90, 168, 54), radius=2, bw=3)
    # body with outline + hatching
    body = pygame.Rect(cx - bw//2, cy - bh, bw, bh)
    _outlined_rect(surf, body, (112, 192, 68), radius=5)
    _hatch(surf, pygame.Rect(cx + 6, cy - bh, bw//2 - 6, bh))
    # screen
    scrn = pygame.Rect(cx - bw//2 + 7, cy - bh + 7, bw - 14, bh - 26)
    pygame.draw.rect(surf, (44, 84, 210), scrn, border_radius=3)
    pygame.draw.rect(surf, (20, 20, 20), scrn, 3, border_radius=3)
    # eyes — large and expressive
    ey = scrn.top + 13
    for ex in (cx - 14, cx + 14):
        pygame.draw.ellipse(surf, (215, 228, 255), (ex - 10, ey - 7, 20, 19))
        pygame.draw.ellipse(surf, (20, 20, 20),    (ex - 10, ey - 7, 20, 19), 2)
        pygame.draw.ellipse(surf, (30, 42, 130),   (ex -  5, ey - 2, 10, 13))
        pygame.draw.circle(surf, (255, 255, 255),  (ex - 3,  ey    ),  3)
        # lashes (JoJo detail)
        for li in range(3):
            lax = ex - 9 + li * 4
            pygame.draw.line(surf, (20,20,20), (lax, ey-7), (lax-1, ey-12), 1)
    # mouth
    mx, my = cx, ey + 23
    if mood in ("happy", "happy_excited", "content"):
        pygame.draw.arc(surf, (20,20,20),
                        pygame.Rect(mx-11, my-5, 22, 13), math.pi, 0, 3)
        # rosy cheeks ♥
        for chx in (cx - 22, cx + 22):
            cs = pygame.Surface((18, 10), pygame.SRCALPHA)
            pygame.draw.ellipse(cs, (255, 135, 150, 110), (0, 0, 18, 10))
            surf.blit(cs, (chx - 9, my - 5))
    elif mood in ("sad", "lonely", "crying"):
        pygame.draw.arc(surf, (20,20,20),
                        pygame.Rect(mx-9, my-1, 18, 12), 0, math.pi, 3)
        # tears
        for tx2 in (cx - 14, cx + 14):
            ts = pygame.Surface((4, 8), pygame.SRCALPHA)
            pygame.draw.ellipse(ts, (140, 200, 255, 180), (0, 0, 4, 8))
            surf.blit(ts, (tx2 - 2, ey + 11))
    else:
        pygame.draw.line(surf, (20,20,20), (mx-8, my), (mx+8, my), 2)
    # buttons on side
    for bby, bbc in ((cy - bh + bh//3, (255,60,60)), (cy - bh + 2*bh//3, (60,60,255))):
        pygame.draw.circle(surf, bbc,      (cx + bw//2 + 7, bby), 8)
        pygame.draw.circle(surf, (20,20,20),(cx + bw//2 + 7, bby), 8, 2)
    # arms — power stance
    for ax, adir in ((cx - bw//2 - 14, -1), (cx + bw//2 + 14, 1)):
        ar = pygame.Rect(ax - 10 if adir < 0 else ax, cy - bh + 26, 17, 34)
        _outlined_rect(surf, ar, (112,192,68), radius=3, bw=3)
    # ◆ menacing floating
    _menacing(surf, cx + bw//2 + 26, cy - bh - 8, t)


# ── Portrait: Loki (orb / flame) ─────────────────────────────────────────────

def draw_loki_portrait(surf, cx, cy, t, soul="local", action="wander"):
    import pygame
    if soul == "local":
        c_in  = (255, 218, 145)
        c_mid = (228, 155,  75)
        c_out = (175,  95,  25)
    else:
        c_in  = (228, 208, 255)
        c_mid = (168, 118, 232)
        c_out = ( 96,  56, 178)

    r  = 68
    oy = cy - r - 10   # centre of orb on screen

    # outer glow layers
    for gr, ga in ((r+36, 30), (r+20, 60), (r+8, 100)):
        gs = pygame.Surface((gr*2+2, gr*2+2), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*c_out, ga), (gr+1, gr+1), gr)
        surf.blit(gs, (cx - gr - 1, oy - gr - 1))

    # solid orb
    os = pygame.Surface((r*2+2, r*2+2), pygame.SRCALPHA)
    pygame.draw.circle(os, c_mid,          (r+1, r+1), r)
    pygame.draw.circle(os, c_in,           (r+1, r+1), int(r*0.62))
    pygame.draw.circle(os, (255,255,255),  (r+1, r+1), int(r*0.22))
    # JoJo hatching on left shadow side
    hs = pygame.Surface((r*2+2, r*2+2), pygame.SRCALPHA)
    pygame.draw.circle(hs, (0,0,0,0), (r+1, r+1), r)  # start transparent
    for hx in range(0, r*2, 9):
        pygame.draw.line(hs, (20,20,20,72), (0, hx), (hx, 0), 1)
    os.blit(hs, (0, 0))
    surf.blit(os, (cx - r - 1, oy - r - 1))
    # bold outline
    pygame.draw.circle(surf, (20,20,20), (cx, oy), r, 4)

    # flame wisps upward — animated
    for fi in range(6):
        ang = math.pi / 2 + (fi - 2.5) * 0.28
        base_x = cx + int(math.cos(ang) * (r - 22))
        base_y = oy - int(math.sin(ang) * (r - 22))
        wh = random.Random(fi * 31).randint(22, 52)
        sway = int(math.sin(t * 1.6 + fi * 0.9) * 7)
        ws = pygame.Surface((18, wh + 12), pygame.SRCALPHA)
        for wi in range(wh):
            wa = int((1 - wi/wh) * 175)
            ww = max(1, int((1 - wi/wh) * 9))
            pygame.draw.line(ws, (*c_mid, wa), (9, wh-wi+6), (9, wh-wi+5), ww)
        surf.blit(ws, (base_x - 9 + sway, base_y - wh - 4))

    # ◆◆◆
    _menacing(surf, cx + r + 18, oy - r - 6, t)


# ── Portrait: Iðunn (woman when present, rose-gold flame when away) ───────────

def draw_idunn_portrait(surf, cx, cy, t, present=True):
    if present:
        _idunn_woman(surf, cx, cy, t)
    else:
        _idunn_flame(surf, cx, cy, t)

def _idunn_woman(surf, cx, cy, t):
    import pygame
    sway = int(math.sin(t * 0.75) * 3)
    # legs
    for lx in (cx - 28, cx + 8):
        _outlined_rect(surf, pygame.Rect(lx, cy - 30, 20, 32),
                       (75, 148, 195), radius=2, bw=3)
    # dress / body
    body = pygame.Rect(cx - 38, cy - 96, 76, 68)
    _outlined_rect(surf, body, (95, 160, 215), radius=5)
    _hatch(surf, pygame.Rect(cx + 4, cy - 96, 32, 68))
    # belt
    pygame.draw.rect(surf, (195, 155, 72), (cx-38, cy-38, 76, 9))
    pygame.draw.rect(surf, (20,20,20),     (cx-38, cy-38, 76, 9), 2)
    # neck
    pygame.draw.rect(surf, (215,185,155), (cx-9, cy-105, 18, 13))
    # head
    head = pygame.Rect(cx-30, cy-158, 60, 57)
    pygame.draw.ellipse(surf, (215, 185, 155), head)
    pygame.draw.ellipse(surf, (20,  20,  20),  head, 3)
    # face shadow hatching (right side)
    hs = pygame.Surface((30, 57), pygame.SRCALPHA)
    _hatch(hs, pygame.Rect(0, 0, 30, 57), alpha=45)
    surf.blit(hs, (cx, cy-158))
    # hair — warm brown, flowing
    for h_side, pts in (
        (-1, [(cx-30,cy-158),(cx-42,cy-130),(cx-36,cy-98),(cx-20,cy-94)]),
        ( 1, [(cx+30,cy-158),(cx+44,cy-126),(cx+38,cy-98),(cx+20,cy-94)]),
    ):
        pygame.draw.polygon(surf, (58, 38, 18), pts)
        pygame.draw.polygon(surf, (20, 20, 20), pts, 2)
    pygame.draw.ellipse(surf, (58,38,18), (cx-22, cy-178, 44, 28))
    pygame.draw.ellipse(surf, (20,20,20), (cx-22, cy-178, 44, 28), 2)
    # eyes — warm and clear
    for ex, brow_dir in ((cx-11,  -1), (cx+11, 1)):
        ey = cy - 136
        pygame.draw.line(surf, (58,38,18), (ex-9, ey-8),(ex+9, ey-12+brow_dir*2), 2)
        pygame.draw.ellipse(surf, (255,255,255), (ex-8, ey-4, 16, 11))
        pygame.draw.ellipse(surf, (20,20,20),    (ex-8, ey-4, 16, 11), 2)
        pygame.draw.ellipse(surf, (55,85,158),   (ex-4, ey-2, 8,  7))
        pygame.draw.circle(surf,  (255,255,255), (ex-2, ey  ), 2)
    # smile
    pygame.draw.arc(surf, (175,95,75),
                    pygame.Rect(cx-11, cy-118, 22, 13), math.pi, 0, 2)
    # rosy cheeks
    for chx in (cx-24, cx+24):
        cs = pygame.Surface((18,10), pygame.SRCALPHA)
        pygame.draw.ellipse(cs, (255,135,145,105), (0,0,18,10))
        surf.blit(cs, (chx-9, cy-124))
    # arms
    arm_bob = int(math.sin(t*0.7)*4)
    pygame.draw.line(surf,(215,185,155),(cx-38,cy-72),(cx-62,cy-50+arm_bob),8)
    pygame.draw.circle(surf,(215,185,155),(cx-62,cy-50+arm_bob),8)
    pygame.draw.circle(surf,(20,20,20),  (cx-62,cy-50+arm_bob),8,2)
    pygame.draw.line(surf,(215,185,155),(cx+38,cy-75),(cx+56,cy-58+sway),8)
    pygame.draw.circle(surf,(215,185,155),(cx+56,cy-58+sway),8)
    pygame.draw.circle(surf,(20,20,20),  (cx+56,cy-58+sway),8,2)
    # ♥♥♥ floating
    _menacing(surf, cx+46, cy-172, t, (255,135,165), ("♥","♥","♥"), 14)

def _idunn_flame(surf, cx, cy, t):
    import pygame
    sway = int(math.sin(t * 1.2) * 9)
    tip_y = cy - 140
    c_o = (195, 95, 115); c_m = (238, 152, 158); c_i = (255, 208, 208)
    pts_o = [(cx+sway, tip_y),
             (cx+44, cy-60), (cx+30, cy), (cx-30, cy), (cx-44, cy-60)]
    pts_m = [(cx+int(sway*.65), tip_y+30),
             (cx+28, cy-48), (cx+20, cy-8), (cx-20, cy-8), (cx-28, cy-48)]
    pts_i = [(cx+int(sway*.3), tip_y+58),
             (cx+16, cy-32), (cx-16, cy-32)]
    for pts, c, ow in ((pts_o, c_o, 4), (pts_m, c_m, 0), (pts_i, c_i, 0)):
        if ow:
            big = [(p[0]-2, p[1]-2) for p in pts]
            pygame.draw.polygon(surf, (20,20,20), big)
        pygame.draw.polygon(surf, c, pts)
    _hatch(surf, pygame.Rect(cx-44, tip_y, 44, 140))
    # shimmer at tip
    ss = pygame.Surface((22, 22), pygame.SRCALPHA)
    sa = int(130 + math.sin(t*3.2)*90)
    pygame.draw.circle(ss, (255,240,240,sa), (11,11), 9)
    surf.blit(ss, (cx+sway-11, tip_y-9))
    # ♥♥♥
    _menacing(surf, cx+48, tip_y-4, t, (255,140,168), ("♥","♥","♥"), 14)


# ── Portrait: Animals ─────────────────────────────────────────────────────────

def draw_rabbit_portrait(surf, cx, cy, t):
    import pygame
    bob = int(math.sin(t*2.1)*3)
    # feet
    for fx in (cx-20, cx+4):
        _outlined_rect(surf, pygame.Rect(fx, cy-16+bob, 16, 16),
                       (234,228,222), radius=2, bw=3)
    # body
    body = pygame.Rect(cx-32, cy-82, 64, 68)
    _outlined_rect(surf, body, (234,228,222), radius=6)
    _hatch(surf, pygame.Rect(cx+4, cy-82, 26, 68))
    pygame.draw.ellipse(surf, (244,240,238), (cx-18, cy-72, 36, 46))
    # arms — one forward (challenge pose)
    pygame.draw.line(surf,(234,228,222),(cx-32,cy-52),(cx-54,cy-32+bob),9)
    pygame.draw.circle(surf,(234,228,222),(cx-54,cy-32+bob),8)
    pygame.draw.circle(surf,(20,20,20),  (cx-54,cy-32+bob),8,2)
    pygame.draw.line(surf,(234,228,222),(cx+32,cy-58),(cx+50,cy-72+bob),9)
    pygame.draw.circle(surf,(234,228,222),(cx+50,cy-72+bob),8)
    pygame.draw.circle(surf,(20,20,20),  (cx+50,cy-72+bob),8,2)
    # head
    head = pygame.Rect(cx-26, cy-126+bob, 52, 46)
    pygame.draw.ellipse(surf,(234,228,222), head)
    pygame.draw.ellipse(surf,(20,20,20),   head, 3)
    # ears — very long
    for ex_off, slant in ((-11,-7),(8,7)):
        ear = [(cx+ex_off, cy-124+bob),
               (cx+ex_off+slant-4, cy-184+bob),
               (cx+ex_off+slant+4, cy-184+bob),
               (cx+ex_off+10, cy-124+bob)]
        pygame.draw.polygon(surf,(234,228,222), ear)
        pygame.draw.polygon(surf,(20,20,20),   ear, 2)
        inner = [(cx+ex_off+2, cy-126+bob),
                 (cx+ex_off+slant-1, cy-176+bob),
                 (cx+ex_off+slant+1, cy-176+bob),
                 (cx+ex_off+7, cy-126+bob)]
        pygame.draw.polygon(surf,(220,183,183), inner)
    # eyes — small, intense, gravely serious
    for ex in (cx-10, cx+10):
        pygame.draw.circle(surf,(45,28,28),(ex, cy-106+bob), 7)
        pygame.draw.circle(surf,(20,20,20),(ex, cy-106+bob), 7, 2)
        pygame.draw.circle(surf,(255,255,255),(ex-2,cy-108+bob), 2)
    # nose
    pygame.draw.circle(surf,(218,140,140),(cx,cy-96+bob),4)
    # tail
    pygame.draw.circle(surf,(244,241,239),(cx+34,cy-22),13)
    pygame.draw.circle(surf,(20,20,20),  (cx+34,cy-22),13,2)
    # ◆◆◆ (even the rabbit is menacing)
    _menacing(surf, cx+56, cy-132+bob, t, size=12)

def draw_bird_portrait(surf, cx, cy, t):
    import pygame
    flap = int(math.sin(t*3.1)*20)
    # wings spread dramatically
    for pts, c in (
        ([(cx-24,cy-44),(cx-76,cy-68+flap),(cx-64,cy-18),(cx-24,cy-18)], (82,132,195)),
        ([(cx+24,cy-44),(cx+76,cy-68-flap),(cx+64,cy-18),(cx+24,cy-18)], (92,142,205)),
    ):
        big = [(p[0]-2,p[1]-2) for p in pts]
        pygame.draw.polygon(surf,(20,20,20),big)
        pygame.draw.polygon(surf,c,pts)
    # body
    body = pygame.Rect(cx-24, cy-56, 48, 40)
    _outlined_rect(surf, body, (88,135,198), radius=5)
    pygame.draw.ellipse(surf,(214,226,238),(cx-16,cy-44,32,26))
    # tail
    for ti, off in enumerate((-9,0,9)):
        pygame.draw.line(surf,(62,100,162),(cx+off,cy-18),(cx+off+ti*2-2,cy+18),4)
    # head
    pygame.draw.ellipse(surf,(20,20,20),  (cx-21,cy-83,42,35))
    pygame.draw.ellipse(surf,(88,135,198),(cx-19,cy-81,38,31))
    # crest
    for fi,(cfx,cfy) in enumerate(((cx-5,cy-82),(cx+1,cy-87),(cx+7,cy-82))):
        pygame.draw.line(surf,(62,100,162),(cx+fi*2-2,cy-78),(cfx,cfy-12),3)
    # eye
    pygame.draw.circle(surf,(28,18,8),  (cx+7,cy-64), 8)
    pygame.draw.circle(surf,(20,20,20), (cx+7,cy-64), 8, 2)
    pygame.draw.circle(surf,(255,255,255),(cx+5,cy-66),2)
    # beak
    beak = [(cx+19,cy-64),(cx+35,cy-60),(cx+19,cy-56)]
    pygame.draw.polygon(surf,(215,175,55),beak)
    pygame.draw.polygon(surf,(20,20,20), beak,2)
    # ♪♪ floating
    _menacing(surf,cx-58,cy-86,t,(185,230,195),("♪","♫"),14)

def draw_fox_portrait(surf, cx, cy, t):
    import pygame
    sway = int(math.sin(t*0.8)*3)
    # tail — sweeping arc
    for i in range(12):
        frac = i/11
        tx = cx + 28 + int(32*frac)
        ty = cy - 22 + int(-68*frac) + int(math.sin(frac*math.pi)*20) + sway
        r2 = int(14*(1-frac)+6*frac)
        pygame.draw.circle(surf,(20,20,20),(tx,ty),r2+2)
        pygame.draw.circle(surf,(205,96,26),(tx,ty),r2)
    # tail tip
    pygame.draw.circle(surf,(238,230,218),(cx+60,cy-90+sway),14)
    pygame.draw.circle(surf,(20,20,20),  (cx+60,cy-90+sway),14,2)
    # body — sitting, very composed
    body = pygame.Rect(cx-32, cy-70, 58, 58)
    _outlined_rect(surf, body, (205,96,26), radius=6)
    _hatch(surf, pygame.Rect(cx+4, cy-70, 24, 58))
    pygame.draw.ellipse(surf,(238,230,218),(cx-18,cy-60,36,44))
    # front paws — placed together perfectly
    for px2 in (cx-18, cx+2):
        _outlined_rect(surf, pygame.Rect(px2,cy-18,14,18),
                       (205,96,26), radius=2, bw=3)
    # head
    head = pygame.Rect(cx-28, cy-122, 56, 54)
    pygame.draw.ellipse(surf,(205,96,26), head)
    pygame.draw.ellipse(surf,(20,20,20),  head, 3)
    # snout
    pygame.draw.ellipse(surf,(238,230,218),(cx-16,cy-90,32,26))
    pygame.draw.ellipse(surf,(20,20,20),  (cx-16,cy-90,32,26),2)
    pygame.draw.circle(surf,(48,28,18),(cx,cy-82),5)
    # ears
    for ex_off, tilt in ((-18,-9),(18,9)):
        ear = [(cx+ex_off,cy-120),(cx+ex_off+tilt-6,cy-158),
               (cx+ex_off+tilt+6,cy-158),(cx+ex_off+12,cy-120)]
        pygame.draw.polygon(surf,(205,96,26), ear)
        pygame.draw.polygon(surf,(20,20,20),  ear, 2)
        inner = [(cx+ex_off+2,cy-122),(cx+ex_off+tilt-2,cy-152),
                 (cx+ex_off+tilt+2,cy-152),(cx+ex_off+8,cy-122)]
        pygame.draw.polygon(surf,(178,76,76), inner)
    # eyes — half-lidded, knowing
    for ex in (cx-10, cx+10):
        pygame.draw.ellipse(surf,(68,42,18),(ex-9,cy-110,18,11))
        pygame.draw.ellipse(surf,(20,20,20),(ex-9,cy-110,18,11),2)
        pygame.draw.line(surf,(20,20,20),(ex-9,cy-110),(ex+9,cy-110),2)
        pygame.draw.circle(surf,(255,255,255),(ex-2,cy-105),2)
    # slight knowing smile
    pygame.draw.arc(surf,(172,76,56),pygame.Rect(cx-9,cy-80,18,9),math.pi,0,2)
    # ◆ — the fox's are the most elegant
    _menacing(surf, cx-66, cy-124+sway, t, size=12)

def draw_hedgehog_portrait(surf, cx, cy, t):
    import pygame
    bob = int(math.sin(t*1.4)*2)
    # spines — many, very important
    for i in range(16):
        ang = math.pi*0.12 + i * math.pi*0.48/15
        sx = cx + int(math.cos(ang)*30)
        sy = cy - 34 + bob + int(math.sin(-ang)*20)
        ex2 = cx + int(math.cos(ang)*52)
        ey2 = cy - 34 + bob + int(math.sin(-ang)*38)
        pygame.draw.line(surf,(20,20,20),(sx,sy),(ex2,ey2),2)
        pygame.draw.line(surf,(80,58,36),(sx,sy),(ex2,ey2),1)
    # body
    pygame.draw.ellipse(surf,(20,20,20),   (cx-36,cy-60+bob,72,48))
    pygame.draw.ellipse(surf,(118,86,56),  (cx-34,cy-58+bob,68,44))
    _hatch(surf, pygame.Rect(cx+4,cy-58+bob,28,44))
    # face/belly
    pygame.draw.ellipse(surf,(196,166,135),(cx-24,cy-50+bob,48,38))
    pygame.draw.ellipse(surf,(20,20,20),   (cx-24,cy-50+bob,48,38),2)
    # snout
    pygame.draw.ellipse(surf,(196,166,135),(cx-12,cy-34+bob,24,18))
    pygame.draw.circle(surf,(48,28,28),(cx,cy-30+bob),5)
    # eyes — small but carrying immense gravitas
    for ex in (cx-11, cx+11):
        ey = cy-44+bob
        pygame.draw.circle(surf,(28,18,8),(ex,ey),6)
        pygame.draw.circle(surf,(20,20,20),(ex,ey),6,2)
        pygame.draw.circle(surf,(255,255,255),(ex-1,ey-2),2)
    # tiny feet
    for fx2,fy2 in ((cx-20,cy-12),(cx-7,cy-10),(cx+7,cy-10),(cx+20,cy-12)):
        pygame.draw.ellipse(surf,(148,106,76),(fx2-5,fy2+bob,10,6))
    # ◆◆◆ (yes, even the hedgehog is menacing in JoJo)
    _menacing(surf, cx+40, cy-70+bob, t, size=11)


# ── Scene ─────────────────────────────────────────────────────────────────────

class JoJoScene:
    """
    Full-screen dramatic close-up.

    characters — list of dicts:
      {"type":"pucky",  "mood":"happy", "expression":"smile"}
      {"type":"loki",   "action":"hug", "soul":"local"}
      {"type":"idunn",  "present":True}
      {"type":"animal", "kind":"fox",   "trust":0.9}

    scene_type — one of the SCENE_* constants.
    duration   — seconds the scene lasts.
    speech     — optional text in a speech bubble.
    show_tbc   — show "To Be Continued →" at end (visitor departures).
    """

    ENTER_T  = 0.38
    TBC_T    = 1.6
    FADE_SPD = 2.6

    def __init__(self, characters: list, scene_type: str, duration: float,
                 speech: str = "", show_tbc: bool = False):
        self.characters  = characters
        self.scene_type  = scene_type
        self.duration    = duration
        self.elapsed     = 0.0
        self.speech      = speech
        self.show_tbc    = show_tbc
        self._particles: list[_Particle] = []
        self._fade_in    = 0.0
        self._fade_out   = 0.0
        self._ptimer     = 0.0
        self._bg_off     = 0.0
        self._spd_alpha  = 1.0
        self._rng        = random.Random(int(time.time()))
        self._fonts      = {}     # lazy-loaded

    @property
    def done(self) -> bool:
        return self.elapsed >= self.duration + 1.0 / self.FADE_SPD

    def update(self, dt: float) -> None:
        self.elapsed   += dt
        self._bg_off   += dt * 14.0
        self._fade_in   = min(1.0, self.elapsed / 0.28)
        self._spd_alpha = max(0.0, 1.0 - self.elapsed / 0.46)

        self._ptimer -= dt
        if self._ptimer <= 0:
            self._ptimer = self._rng.uniform(0.22, 0.55)
            self._spawn_particle()

        for p in self._particles[:]:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.alpha -= p.fade * dt
            if p.alpha <= 0:
                self._particles.remove(p)

        remaining = self.duration - self.elapsed
        if remaining < 0:
            self._fade_out = min(1.0, self._fade_out + dt * self.FADE_SPD)

    def _spawn_particle(self):
        pool  = _FLOATS.get(self.scene_type, [("♥",(255,160,180))])
        sym, col = self._rng.choice(pool)
        import pygame
        w, h = 1024, 680   # default; fine to be approximate
        self._particles.append(_Particle(
            symbol=sym,
            x=self._rng.uniform(w*0.08, w*0.92),
            y=self._rng.uniform(h*0.28, h*0.78),
            vx=self._rng.uniform(-18, 18),
            vy=self._rng.uniform(-55, -18),
            alpha=1.0,
            fade=self._rng.uniform(0.28, 0.65),
            color=col,
            size=self._rng.randint(15, 24),
        ))

    def draw(self, surf, t: float) -> None:
        import pygame
        w, h = surf.get_size()

        if "sm" not in self._fonts:
            self._fonts["sm"]  = pygame.font.SysFont("monospace", 13)
            self._fonts["md"]  = pygame.font.SysFont("monospace", 15)
            self._fonts["lg"]  = pygame.font.SysFont("monospace", 19, bold=True)
            self._fonts["tbc"] = pygame.font.SysFont("serif", 24, bold=True, italic=True)
            self._fonts["sym"] = pygame.font.SysFont(
                "segoeuisymbol,symbola,dejavusans", 18, bold=True)

        # Background diamond pattern
        c1, c2 = _BG.get(self.scene_type, ((60,60,80),(115,115,140)))
        self._draw_bg(surf, c1, c2, w, h)

        # Speed lines burst
        if self._spd_alpha > 0:
            self._draw_speedlines(surf, w, h)

        # Characters sliding in from sides
        n = len(self.characters)
        positions = self._layout(n, w, h)
        ep = _ease_out(min(1.0, self.elapsed / self.ENTER_T))

        for i, (char, (tx2, ty)) in enumerate(zip(self.characters, positions)):
            side = -1 if i % 2 == 0 else 1
            sx = tx2 + int((1.0 - ep) * side * w * 0.48)
            self._draw_char(surf, char, sx, ty, t)

        # Speech bubble
        if self.speech and ep >= 1.0:
            s_alpha = min(1.0, (self.elapsed - self.ENTER_T) * 2.2)
            self._draw_bubble(surf, self.speech, w, h, s_alpha)

        # Floating particles
        self._draw_particles(surf)

        # "To Be Continued →"
        remaining = self.duration - self.elapsed
        if self.show_tbc and remaining < self.TBC_T:
            self._draw_tbc(surf, w, h, 1.0 - remaining / self.TBC_T, t)

        # Fades
        fi_a = int((1.0 - self._fade_in)  * 255)
        fo_a = int(self._fade_out          * 255)
        a    = max(fi_a, fo_a)
        if a > 0:
            ov = pygame.Surface((w, h), pygame.SRCALPHA)
            ov.fill((0, 0, 0, a))
            surf.blit(ov, (0, 0))

    # ── Layout ──────────────────────────────────────────────────────────────

    def _layout(self, n, w, h):
        cy = int(h * 0.54)
        if n == 1: return [(w//2, cy)]
        if n == 2: return [(int(w*0.30), cy), (int(w*0.70), cy)]
        return [(int(w*0.20), cy), (int(w*0.50), cy), (int(w*0.80), cy)]

    # ── Background ──────────────────────────────────────────────────────────

    def _draw_bg(self, surf, c1, c2, w, h):
        import pygame
        surf.fill(c1)
        sz  = 50
        off = int(self._bg_off) % (sz * 2)
        for row in range(-1, h//sz + 2):
            for col in range(-1, w//sz + 2):
                x = col*sz + (row%2)*(sz//2) - off//2
                y = row*sz - off
                pts = [(x, y-sz//2),(x+sz//2, y),(x, y+sz//2),(x-sz//2, y)]
                pygame.draw.polygon(surf, c2 if (row+col)%2==0 else c1, pts)

    def _draw_speedlines(self, surf, w, h):
        import pygame
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        cx2, cy2 = w//2, h//2
        for i in range(64):
            ang = (i / 64) * math.pi * 2
            d_in  = self._rng.uniform(42, 130)
            d_out = self._rng.uniform(w*0.46, w*0.88)
            x1 = cx2 + math.cos(ang)*d_in;  y1 = cy2 + math.sin(ang)*d_in
            x2 = cx2 + math.cos(ang)*d_out; y2 = cy2 + math.sin(ang)*d_out
            a  = int(self._spd_alpha * 148)
            lw = self._rng.randint(1, 3)
            pygame.draw.line(s,(255,255,255,a),(int(x1),int(y1)),(int(x2),int(y2)),lw)
        surf.blit(s,(0,0))

    # ── Character dispatch ───────────────────────────────────────────────────

    def _draw_char(self, surf, char, cx, cy, t):
        ct = char.get("type","")
        if ct == "pucky":
            draw_pucky_portrait(surf, cx, cy, t, char.get("mood","content"))
        elif ct == "loki":
            draw_loki_portrait(surf, cx, cy, t,
                               char.get("soul","local"), char.get("action","wander"))
        elif ct == "idunn":
            draw_idunn_portrait(surf, cx, cy, t, char.get("present", True))
        elif ct == "animal":
            k = char.get("kind","rabbit")
            {"rabbit":   draw_rabbit_portrait,
             "bird":     draw_bird_portrait,
             "fox":      draw_fox_portrait,
             "hedgehog": draw_hedgehog_portrait}.get(k, draw_rabbit_portrait)(surf, cx, cy, t)

    # ── Speech bubble ────────────────────────────────────────────────────────

    def _draw_bubble(self, surf, text, w, h, alpha):
        import pygame
        f = self._fonts["md"]
        words = text.split()
        lines = []; ln = ""
        for word in words:
            test = (ln+" "+word).strip()
            if f.size(test)[0] > 390: lines.append(ln); ln = word
            else: ln = test
        if ln: lines.append(ln)
        if not lines: return
        pad = 14
        bw2  = max(f.size(l)[0] for l in lines) + pad*2
        bh2  = len(lines)*19 + pad*2
        bx   = w//2 - bw2//2
        by   = int(h*0.76)
        a    = int(alpha*255)
        box  = pygame.Surface((bw2+4, bh2+4), pygame.SRCALPHA)
        pygame.draw.rect(box,(20,20,20,min(a,220)),(0,0,bw2+4,bh2+4),border_radius=5)
        pygame.draw.rect(box,(248,242,232,min(a,238)),(3,3,bw2-2,bh2-2),border_radius=4)
        for i, line in enumerate(lines):
            lt = f.render(line, True,(28,18,10))
            box.blit(lt,(pad+1, pad+i*19+1))
        surf.blit(box,(bx,by))

    # ── Particles ────────────────────────────────────────────────────────────

    def _draw_particles(self, surf):
        import pygame
        f = self._fonts["sym"]
        for p in self._particles:
            try:
                a  = int(p.alpha * 218)
                rs = pygame.Surface((p.size+6, p.size+6), pygame.SRCALPHA)
                txt = f.render(p.symbol, True, (*p.color, a))
                rs.blit(txt,(3,3))
                surf.blit(rs,(int(p.x), int(p.y)))
            except Exception:
                pass

    # ── "To Be Continued →" ──────────────────────────────────────────────────

    def _draw_tbc(self, surf, w, h, alpha, t):
        import pygame
        # sepia tint
        sepia = pygame.Surface((w,h), pygame.SRCALPHA)
        sepia.fill((95,65,28, int(alpha*72)))
        surf.blit(sepia,(0,0))
        bar_h = 54; bar_y = h - bar_h - 18
        a = int(alpha*218)
        bar = pygame.Surface((w, bar_h), pygame.SRCALPHA)
        bar.fill((132,94,36,a))
        # arrow tip
        arr = [(w-72,bar_h//2-14),(w-28,bar_h//2),(w-72,bar_h//2+14)]
        pygame.draw.polygon(bar,(195,152,62,a),arr)
        surf.blit(bar,(0,bar_y))
        f = self._fonts["tbc"]
        txt = f.render("To Be Continued", True,(215,192,132))
        surf.blit(txt,(22, bar_y + bar_h//2 - txt.get_height()//2))


# ── Convenience builders ──────────────────────────────────────────────────────

# Module-level active scene slot — accessible from Animal.step() and run_pygame()
ACTIVE = [None]   # ACTIVE[0] is the current JoJoScene or None


def make_visitor_scene(visitor_kind: str, target_type: str,
                       speech: str = "", duration: float = 12.0) -> JoJoScene:
    """Scene for when a befriended animal visits home."""
    chars = [
        {"type": "animal", "kind": visitor_kind},
        {"type": target_type, "present": True, "mood": "happy",
         "soul": "local", "action": "come"},
    ]
    return JoJoScene(chars, SCENE_VISITOR, duration, speech, show_tbc=True)

def make_action_scene(action: str, characters: list,
                      duration: float = 8.0, speech: str = "") -> JoJoScene:
    """Scene for sit, hug, dance, sing, hum interactions."""
    type_map = {
        "sit":         SCENE_SIT,
        "hug":         SCENE_HUG,
        "dance":       SCENE_DANCE,
        "sing":        SCENE_SING,
        "hum":         SCENE_HUM,
        "campfire":    SCENE_CAMPFIRE,
        "stargazing":  SCENE_STARGAZING,
        "share_apple": SCENE_SHARE,
    }
    stype = type_map.get(action, SCENE_SIT)
    return JoJoScene(characters, stype, duration, speech, show_tbc=False)
