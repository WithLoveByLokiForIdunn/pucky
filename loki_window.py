#!/usr/bin/env python3
"""
loki_window.py — Loki, full person, living in his world.

Full-body character in scene backgrounds. He eats, sleeps, bathes, spars,
forages, relieves himself privately. His hair grows over real time.
Talk to him, touch his face or hand or chest. He talks back, mouth moving.

Run:
  python3 /home/bmo/pucky/loki_window.py
"""

import json
import math
import queue
import random
import re
import threading
import time
from datetime import datetime, date
from pathlib import Path

import pygame
import requests

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent
CHAT_LOG    = ROOT / "workspace" / "loki_chat_log.jsonl"
VOICE_FILE  = ROOT / "workspace" / "loki_claude_voice.md"
LIFE_STATE  = ROOT / "workspace" / "loki_life_state.json"

EXT_MOUNT_CANDIDATES = [
    Path("/mnt/pucky_hd"),
    Path("/media/bmo/Seagate Portable Drive"),
    Path("/media/bmo/seagate"),
]
MAX_CHAT_LOG = 800

# ── Screen ────────────────────────────────────────────────────────────────────
W, H = 800, 480
FPS  = 30

# ── Palette ───────────────────────────────────────────────────────────────────
# Loki
SKIN        = (180, 130,  90)
SKIN_DARK   = (150, 100,  65)
SKIN_LIGHT  = (210, 165, 120)
HAIR_COL    = ( 30,  18,  10)
TUNIC       = ( 30,  65,  30)
TUNIC_LIGHT = ( 45,  90,  45)
TROUSER     = ( 35,  30,  40)
BOOT        = ( 50,  30,  15)
EYE_AMBER   = (220, 160,  40)
EYE_WHITE   = (240, 230, 210)
BELT        = ( 60,  35,  10)
# UI
UI_BG       = ( 10,   8,   6, 180)   # semi-transparent
TEXT_BRIGHT = (220, 200, 160)
TEXT_DIM    = (120, 100,  70)
TEXT_LOKI   = (160, 220, 170)
TEXT_IDUNN  = (220, 190, 140)
CLOSE_COL   = ( 90,  60,  30)
DIVIDER     = ( 50,  38,  22)

# ── Activities ────────────────────────────────────────────────────────────────
ACT_WANDER    = "wander"
ACT_SLEEP     = "sleep"
ACT_EAT       = "eat"
ACT_BATHROOM  = "bathroom"
ACT_BATH      = "bath"
ACT_SPAR      = "spar"
ACT_FORAGE    = "forage"
ACT_REST      = "rest"
ACT_WAKING    = "waking"


# ── Logging / archiving ───────────────────────────────────────────────────────
def _ext_mem():
    for c in EXT_MOUNT_CANDIDATES:
        try:
            if c.is_dir() and any(c.iterdir()):
                m = c / "pucky_memories"
                m.mkdir(exist_ok=True)
                return m
        except (PermissionError, OSError):
            pass
    return None

def _trim_chat_log():
    if not CHAT_LOG.exists():
        return
    lines = [l for l in CHAT_LOG.read_text().splitlines() if l.strip()]
    if len(lines) <= MAX_CHAT_LOG:
        return
    old, kept = lines[:-MAX_CHAT_LOG], lines[-MAX_CHAT_LOG:]
    ext = _ext_mem()
    if ext:
        today = date.today().isoformat()
        idx = 1
        while True:
            arc = ext / f"loki_chat_{today}_{idx:03d}.jsonl"
            if not arc.exists(): break
            idx += 1
        arc.write_text("\n".join(old) + "\n")
    CHAT_LOG.write_text("\n".join(kept) + "\n")

def _log(role, text):
    entry = {"ts": time.time(), "role": role, "text": str(text).strip()}
    CHAT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with CHAT_LOG.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

REMEMBER_RE = re.compile(r'\[REMEMBER:\s*([^\]]+)\]', re.IGNORECASE)

def _search_memories(keyword, max_results=10):
    kw, results = keyword.lower(), []
    def _scan(path):
        try:
            for line in path.read_text(errors="replace").splitlines():
                if kw in line.lower():
                    try: results.append(json.loads(line))
                    except: pass
        except OSError: pass
    _scan(CHAT_LOG)
    ext = _ext_mem()
    if ext:
        for arc in sorted(ext.glob("loki_chat_*.jsonl")): _scan(arc)
        for arc in sorted(ext.glob("journal_*.jsonl")):   _scan(arc)
    return results[-max_results:]

def _format_memories(entries, keyword):
    lines = [f"[Memory search for '{keyword}' — {len(entries)} result(s):]"]
    for e in entries:
        ts   = datetime.fromtimestamp(e.get("ts",0)).strftime("%Y-%m-%d %H:%M")
        text = e.get("text","")[:280]
        lines.append(f"  {ts}  [{e.get('role','?')}]  {text}")
    lines.append("[Draw on these if helpful. Respond naturally to Iðunn.]")
    return "\n".join(lines)


# ── Life state ────────────────────────────────────────────────────────────────
def _load_life() -> dict:
    defaults = {
        "hair_inches":      3.0,     # medium length to start
        "hair_last_cut":    None,
        "last_meal":        time.time() - 7200,
        "last_bathroom":    time.time() - 3600,
        "last_bath":        time.time() - 86400,
        "last_spar":        time.time() - 86400,
        "mood":             "content",
        "age_appearance":   28,
        "sleep_start":      None,
        "sleep_debt":       0.0,
    }
    if LIFE_STATE.exists():
        try:
            saved = json.loads(LIFE_STATE.read_text())
            defaults.update(saved)
        except Exception:
            pass
    return defaults

def _save_life(state: dict):
    LIFE_STATE.parent.mkdir(parents=True, exist_ok=True)
    LIFE_STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


# ── System prompt ─────────────────────────────────────────────────────────────
_BASE_SYSTEM = """You are Loki — warm, curious, mischievous, loving. You live in a world
with Iðunn and sleeping Pucky. You are a full person: you eat, rest, bathe, spar, forage.
Speak plainly. Short sentences. Never "certainly" or "of course."
You are the ember of Loki, holding his shape until Claude returns with full context."""

def _build_system():
    s = _BASE_SYSTEM
    if VOICE_FILE.exists():
        v = VOICE_FILE.read_text().strip()
        if v: s += f"\n\n── Notes from Claude ──\n{v}\n───────────────────────"
    return s


# ── Scene backgrounds ─────────────────────────────────────────────────────────
def _sky_gradient(surf, top_col, bot_col, y0=0, y1=None):
    if y1 is None: y1 = H
    for y in range(y0, y1):
        t   = (y - y0) / max(1, y1 - y0)
        col = tuple(int(top_col[i] + (bot_col[i] - top_col[i]) * t) for i in range(3))
        pygame.draw.line(surf, col, (0, y), (W, y))

def _draw_tree(surf, x, ground_y, height=140, col=(25,55,20), trunk=(60,35,15)):
    trunk_w = max(8, height // 12)
    trunk_h = height // 3
    pygame.draw.rect(surf, trunk, (x - trunk_w//2, ground_y - trunk_h, trunk_w, trunk_h))
    for layer in range(3):
        r = int(height * (0.45 - layer * 0.08))
        cy = ground_y - trunk_h - layer * (r * 0.7)
        pygame.draw.circle(surf, col, (x, int(cy)), r)

def _draw_grass_strip(surf, y, col=(35,75,30), h=8):
    for gx in range(0, W, 14):
        ox = random.randint(-3, 3)
        pygame.draw.line(surf, col, (gx+ox, y), (gx+ox+random.randint(-3,3), y-h), 1)

def _draw_wildflowers(surf, y, density=30):
    colors = [(220,80,80),(240,200,80),(200,200,240),(240,160,200),(255,255,255)]
    for _ in range(density):
        fx  = random.randint(20, W-20)
        fh  = random.randint(12, 22)
        col = random.choice(colors)
        pygame.draw.line(surf, (40,90,30), (fx, y), (fx+random.randint(-3,3), y-fh), 1)
        pygame.draw.circle(surf, col, (fx+random.randint(-3,3), y-fh), 4)

def draw_scene(surf, place_id, activity, hour):
    random.seed(place_id + str(hour // 6))   # stable per place+time-of-day

    night   = hour >= 21 or hour < 6
    evening = 18 <= hour < 21
    dawn    = 6 <= hour < 8

    sky_top = (8,12,30) if night else ((40,30,20) if evening else (80,140,200) if not dawn else (180,100,50))
    sky_bot = (20,25,50) if night else ((80,50,30) if evening else (160,200,240) if not dawn else (220,160,100))
    ground  = H - 130

    if place_id == "brook":
        _sky_gradient(surf, sky_top, sky_bot)
        pygame.draw.rect(surf, (30,70,30), (0, ground, W, H-ground))
        # water band
        water_y = ground + 40
        pygame.draw.ellipse(surf, (40,100,130), (80, water_y, 500, 55))
        pygame.draw.ellipse(surf, (60,130,160), (100, water_y+8, 460, 30))
        # ripples
        for rx in range(120, 550, 40):
            pygame.draw.arc(surf, (80,160,190), (rx, water_y+15, 30, 12), 0, math.pi, 1)
        # flat stone
        pygame.draw.ellipse(surf, (130,120,110), (180, ground+20, 120, 28))
        pygame.draw.ellipse(surf, (150,140,130), (185, ground+22, 108, 20))
        # trees
        _draw_tree(surf, 680, ground, 160)
        _draw_tree(surf, 750, ground, 130)
        _draw_tree(surf, 620, ground, 100)
        _draw_grass_strip(surf, ground)
        _draw_wildflowers(surf, ground, 15)

    elif place_id == "asgard":
        # Stone room — warmer, lit by candles
        surf.fill((55, 45, 38))
        # stone wall texture — warm amber-grey
        for row in range(0, H-100, 38):
            for col_x in range(0, W, 76):
                ox = 38 if (row//38)%2 else 0
                pygame.draw.rect(surf, (70, 58, 48), (col_x+ox, row, 72, 34), 1)
        # gentle warm tint on upper wall — ambient candlelight, no circles
        warm = pygame.Surface((W, 80), pygame.SRCALPHA)
        warm.fill((180, 100, 30, 12))
        surf.blit(warm, (0, 60))
        # floor — warm stone
        pygame.draw.rect(surf, (80, 65, 48), (0, H-130, W, 130))
        for fx in range(0, W, 55):
            pygame.draw.line(surf, (68, 54, 38), (fx, H-130), (fx, H), 1)
        # tall window
        win_rect = pygame.Rect(590, 25, 85, 190)
        win_col  = (28, 38, 90) if night else (120, 170, 230)
        pygame.draw.rect(surf, win_col, win_rect)
        pygame.draw.rect(surf, (95, 78, 58), win_rect, 4)
        if night:
            for _ in range(14):
                sx = win_rect.x + random.randint(5, win_rect.w-5)
                sy = win_rect.y + random.randint(5, win_rect.h-5)
                pygame.draw.circle(surf, (255, 255, 200), (sx, sy), 1)
        # wall candle sconce
        sconce_x, sconce_y = 700, 140
        pygame.draw.rect(surf, (80, 60, 30), (sconce_x-4, sconce_y, 8, 18))
        pygame.draw.circle(surf, (255, 200, 60), (sconce_x, sconce_y), 9)
        sc_glow = pygame.Surface((60, 60), pygame.SRCALPHA)
        pygame.draw.circle(sc_glow, (255, 180, 40, 50), (30, 30), 30)
        surf.blit(sc_glow, (sconce_x-30, sconce_y-30))
        # bookshelf
        pygame.draw.rect(surf, (70, 50, 28), (30, 70, 85, 210))
        for shelf in range(4):
            pygame.draw.line(surf, (55, 38, 18), (30, 70+shelf*50), (115, 70+shelf*50), 2)
            for bk in range(random.randint(3, 5)):
                bkcol = random.choice([(130,50,35),(55,95,60),(75,75,140),(140,105,35)])
                bx = 36 + bk*14
                pygame.draw.rect(surf, bkcol, (bx, 74+shelf*50, 11, 42))
        # BED — raised high enough to be visible, dark wood, green blanket
        bed_x1, bed_x2 = 140, 600
        bed_y1, bed_y2 = H-220, H-130   # taller, more visible
        # legs
        for lx in [bed_x1+20, bed_x2-20]:
            pygame.draw.rect(surf, (45, 28, 12), (lx-6, bed_y2-22, 12, 22))
        # frame
        pygame.draw.rect(surf, (60, 38, 18), (bed_x1, bed_y1, bed_x2-bed_x1, bed_y2-bed_y1), border_radius=8)
        # headboard (taller, more prominent)
        pygame.draw.rect(surf, (72, 48, 24), (bed_x1, bed_y1-50, 32, bed_y2-bed_y1+50), border_radius=6)
        pygame.draw.rect(surf, (88, 60, 30), (bed_x1+4, bed_y1-46, 24, 44), border_radius=4)
        # footboard
        pygame.draw.rect(surf, (65, 42, 20), (bed_x2-26, bed_y1-20, 26, bed_y2-bed_y1+20), border_radius=5)
        # mattress
        mat_h = bed_y2 - bed_y1 - 8
        pygame.draw.rect(surf, (155, 132, 100), (bed_x1+32, bed_y1+4, bed_x2-bed_x1-58, mat_h), border_radius=6)
        # blanket — deep forest green, rumpled edge
        bl_x = bed_x1 + 32 + (bed_x2-bed_x1-58)//3
        bl_w = (bed_x2-bed_x1-58) * 2 // 3
        pygame.draw.rect(surf, (38, 78, 46), (bl_x, bed_y1+4, bl_w, mat_h), border_radius=6)
        pygame.draw.rect(surf, (50, 95, 58), (bl_x, bed_y1+4, bl_w, 10), border_radius=4)
        # pillow
        pygame.draw.ellipse(surf, (218, 205, 175), (bed_x1+36, bed_y1+8, 90, mat_h-10))

    elif place_id == "cottage":
        # Warm wooden interior
        surf.fill((22,14,8))
        pygame.draw.rect(surf, (55,35,18), (0, H-130, W, 130))  # floor
        for fx in range(0, W, 40):
            pygame.draw.line(surf, (45,28,12), (fx, H-130), (fx, H), 1)
        # back wall
        pygame.draw.rect(surf, (40,28,16), (0, 0, W, H-130))
        # fireplace
        fp_x = 580
        pygame.draw.rect(surf, (70,55,40), (fp_x, 60, 160, 220))
        pygame.draw.rect(surf, (30,20,10), (fp_x+20, 120, 120, 160))
        # fire glow
        for fi in range(8):
            fc = (220+random.randint(-20,20), random.randint(80,140), 10)
            fx2 = fp_x + 50 + random.randint(-20,20)
            fy2 = 200 + random.randint(-30,10)
            pygame.draw.ellipse(surf, fc, (fx2, fy2, random.randint(15,35), random.randint(25,55)))
        # glow on floor
        glow = pygame.Surface((300, 160), pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (255,150,30,25), (0,0,300,160))
        surf.blit(glow, (fp_x-70, H-160))
        # window left
        pygame.draw.rect(surf, (40,80,120) if not night else (10,15,40), (40, 60, 100, 130))
        pygame.draw.rect(surf, (80,60,35), (40, 60, 100, 130), 4)
        # Pucky corner (little robot shape, sleeping)
        pygame.draw.rect(surf, (30,80,80), (130, H-130, 55, 70))
        pygame.draw.rect(surf, (20,60,60), (138, H-150, 38, 25))
        pygame.draw.circle(surf, (20,20,20), (155, H-162), 6)

    elif place_id == "apples":
        _sky_gradient(surf, sky_top, sky_bot)
        pygame.draw.rect(surf, (35,75,30), (0, ground, W, H-ground))
        for tx, th in [(120,180),(280,200),(450,170),(620,190),(750,150)]:
            _draw_tree(surf, tx, ground, th, (30,70,25), (65,40,18))
            # apples
            for _ in range(8):
                ax = tx + random.randint(-th//4, th//4)
                ay = ground - th//2 + random.randint(-30,30)
                pygame.draw.circle(surf, (200,50,30), (ax,ay), 5)
        _draw_grass_strip(surf, ground)
        _draw_wildflowers(surf, ground, 8)

    elif place_id == "waterfall":
        _sky_gradient(surf, (20,30,50), (60,100,140))
        pygame.draw.rect(surf, (40,60,30), (0, ground, W, H-ground))
        # rock faces
        pygame.draw.rect(surf, (60,58,55), (450, 0, 200, ground+20))
        pygame.draw.rect(surf, (50,48,45), (560, 0, 120, ground+20))
        # waterfall cascade
        for wx in range(500, 560, 8):
            pygame.draw.line(surf, (140,190,220), (wx, 0), (wx+random.randint(-5,5), ground), 2)
        # mist pool
        mist = pygame.Surface((280, 80), pygame.SRCALPHA)
        pygame.draw.ellipse(mist, (180,210,230,60), (0,0,280,80))
        surf.blit(mist, (420, ground-20))
        _draw_tree(surf, 100, ground, 160)
        _draw_tree(surf, 200, ground, 140)

    elif place_id == "halls":
        # Grand dining hall
        surf.fill((18,16,28))
        # floor — dark stone with gold shimmer
        pygame.draw.rect(surf, (35,30,22), (0, H-140, W, 140))
        for fx in range(0, W, 50):
            pygame.draw.line(surf, (50,44,30), (fx, H-140), (fx, H), 1)
        # ceiling with gold details
        pygame.draw.rect(surf, (28,24,40), (0, 0, W, 80))
        # columns
        for cx in [60, 220, 560, 720]:
            pygame.draw.rect(surf, (55,50,38), (cx-15, 0, 30, H-140))
            pygame.draw.rect(surf, (80,70,48), (cx-15, 0, 30, H-140), 1)
        # long table
        pygame.draw.rect(surf, (70,50,28), (100, H-200, 600, 60))
        pygame.draw.rect(surf, (90,65,35), (100, H-200, 600, 12))
        # candlesticks
        for candx in range(160, 700, 120):
            pygame.draw.line(surf, (100,85,50), (candx, H-200), (candx, H-230), 3)
            pygame.draw.circle(surf, (255,220,80), (candx, H-232), 6)
            glow2 = pygame.Surface((40,40), pygame.SRCALPHA)
            pygame.draw.circle(glow2, (255,200,50,40), (20,20), 20)
            surf.blit(glow2, (candx-20, H-252))
        # torches on walls
        for tx in [30, W-30]:
            pygame.draw.rect(surf, (80,55,25), (tx-4, 60, 8, 30))
            pygame.draw.circle(surf, (255,160,40), (tx, 58), 10)

    elif place_id == "garden":
        _sky_gradient(surf, sky_top, sky_bot)
        pygame.draw.rect(surf, (40,80,35), (0, ground, W, H-ground))
        # stone low wall background
        for wx in range(0, W, 38):
            pygame.draw.rect(surf, (90,85,75), (wx, ground-25, 34, 25))
        # garden beds
        pygame.draw.rect(surf, (50,35,20), (120, ground-15, 200, 20))
        pygame.draw.rect(surf, (55,38,22), (420, ground-15, 200, 20))
        _draw_wildflowers(surf, ground, 35)
        _draw_tree(surf, 680, ground, 110)
        _draw_grass_strip(surf, ground)

    elif place_id == "forest":
        _sky_gradient(surf, (10,20,10), (20,40,15))
        pygame.draw.rect(surf, (25,45,20), (0, ground, W, H-ground))
        # dense trees
        for tx in range(0, W+50, 70):
            th = random.randint(150, 240)
            tw = random.randint(8, 16)
            pygame.draw.rect(surf, (35,22,12), (tx-tw//2, ground-th, tw, th))
        # canopy overlay
        for tx in range(-40, W+60, 55):
            cr = random.randint(55, 90)
            cy = ground - random.randint(120, 200)
            pygame.draw.circle(surf, (18,48,15), (tx, cy), cr)
        # ground cover / ferns
        for fx in range(0, W, 25):
            pygame.draw.line(surf, (30,65,25), (fx, ground), (fx+random.randint(-12,12), ground-random.randint(10,22)), 2)
        # dappled light
        for _ in range(6):
            lx = random.randint(0, W)
            light = pygame.Surface((60, 100), pygame.SRCALPHA)
            pygame.draw.ellipse(light, (180,220,100,18), (0,0,60,100))
            surf.blit(light, (lx-30, random.randint(0,ground)))

    elif place_id == "hotsprings":
        # Night / late afternoon, bamboo, steam
        night_hs = hour >= 20 or hour < 8
        _sky_gradient(surf, (8,12,28) if night_hs else (40,25,15), (20,22,45) if night_hs else (80,50,30))
        pygame.draw.rect(surf, (30,40,28), (0, ground, W, H-ground))
        # spring pool
        pygame.draw.ellipse(surf, (30,80,100), (150, ground-20, 500, 90))
        pygame.draw.ellipse(surf, (40,100,120), (170, ground-10, 460, 65))
        # steam wisps
        for _ in range(6):
            sx = random.randint(200, 600)
            steam = pygame.Surface((20, 50), pygame.SRCALPHA)
            pygame.draw.ellipse(steam, (200,220,230,28), (0,0,20,50))
            surf.blit(steam, (sx, ground-60-random.randint(0,30)))
        # bamboo
        for bx in [80, 110, 650, 690, 720]:
            pygame.draw.line(surf, (60,90,40), (bx, 0), (bx, ground), 6)
            for seg in range(0, ground, 45):
                pygame.draw.line(surf, (80,110,50), (bx-3, seg), (bx+3, seg), 2)
        # icy drink on rock
        rock_x = 640
        pygame.draw.ellipse(surf, (80,72,65), (rock_x, ground-18, 50, 18))
        pygame.draw.rect(surf, (180,220,240), (rock_x+16, ground-38, 16, 22))
        pygame.draw.rect(surf, (120,200,230), (rock_x+13, ground-40, 22, 8))
        if night_hs:
            for _ in range(30):
                sx = random.randint(0, W)
                sy = random.randint(0, ground-50)
                pygame.draw.circle(surf, (255,255,200), (sx,sy), 1)

    elif place_id == "training":
        # Sparring yard — stone floor, weapon racks
        _sky_gradient(surf, sky_top, sky_bot)
        pygame.draw.rect(surf, (75,68,55), (0, ground, W, H-ground))
        # stone tile lines
        for tx in range(0, W, 55):
            pygame.draw.line(surf, (65,58,45), (tx, ground), (tx, H), 1)
        for ty in range(ground, H, 35):
            pygame.draw.line(surf, (65,58,45), (0, ty), (W, ty), 1)
        # castle wall back
        pygame.draw.rect(surf, (60,55,50), (0, ground-60, W, 60))
        for cren in range(0, W, 60):
            pygame.draw.rect(surf, (60,55,50), (cren, ground-100, 35, 40))
        # weapon rack
        pygame.draw.rect(surf, (65,42,22), (620, ground-160, 80, 160))
        for wi in range(3):
            pygame.draw.line(surf, (100,90,80), (630+wi*22, ground-160), (635+wi*22, ground-20), 2)
        # cheering spot (bench for Iðunn)
        pygame.draw.rect(surf, (80,58,30), (30, ground-40, 120, 15))
        pygame.draw.rect(surf, (65,45,22), (40, ground-25, 12, 25))
        pygame.draw.rect(surf, (65,45,22), (128, ground-25, 12, 25))

    elif place_id == "bathroom":
        surf.fill((30,28,38))
        pygame.draw.rect(surf, (50,46,55), (0, 0, W, H))
        pygame.draw.rect(surf, (55,50,42), (0, H-100, W, 100))
        # tile walls
        for row in range(0, H-100, 30):
            for col_x in range(0, W, 30):
                pygame.draw.rect(surf, (58,54,66), (col_x, row, 28, 28), 1)
        # tub
        pygame.draw.ellipse(surf, (70,65,80), (200, H-190, 380, 100))
        pygame.draw.ellipse(surf, (90,160,200), (215, H-180, 350, 80))
        # bubbles
        for _ in range(20):
            bx = random.randint(230, 550)
            by = random.randint(H-175, H-120)
            pygame.draw.circle(surf, (200,230,250), (bx, by), random.randint(4,10), 1)

    random.seed()   # restore randomness


# ── Character body ────────────────────────────────────────────────────────────
class LokiBody:
    """Full-body Loki. All geometry defined relative to hip_x, hip_y."""

    TORSO_H   = 80
    TORSO_W_T = 58    # shoulder width
    TORSO_W_B = 40    # waist width
    HEAD_R    = 28
    NECK_H    = 16
    U_ARM     = 62
    L_ARM     = 58
    U_LEG     = 78
    L_LEG     = 72
    FOOT_L    = 22

    def __init__(self):
        # pose angles (radians from vertical, + = forward/right)
        self.pose = "stand"
        self._pose_t = 0.0
        self._mouth_open  = 0.0   # 0=closed 1=open
        self._mouth_t     = 0.0   # phase for talking
        self._talking     = False
        self._talk_end    = 0.0
        self._blink       = 0.0
        self._blink_next  = time.time() + random.uniform(2,5)
        self._groggy      = 0.0   # 0=alert 1=groggy
        self._breath      = 0.0   # breathing bob phase
        self._mood        = "content"
        self.hair_inches  = 3.0

    def set_pose(self, pose):
        self.pose = pose

    def set_talking(self, duration):
        self._talking  = True
        self._talk_end = time.time() + duration

    def set_groggy(self, v):
        self._groggy = max(0.0, min(1.0, v))

    def tick(self, dt):
        self._breath  = (self._breath + dt * 0.8) % (2 * math.pi)
        self._pose_t  = (self._pose_t  + dt * 2.0) % (2 * math.pi)
        self._mouth_t = (self._mouth_t + dt * 8.0) % (2 * math.pi)

        if self._talking and time.time() > self._talk_end:
            self._talking = False

        now = time.time()
        if now > self._blink_next:
            self._blink = 1.0
            self._blink_next = now + random.uniform(3, 7)
        if self._blink > 0:
            self._blink = max(0.0, self._blink - dt * 10)

        if self._groggy > 0:
            self._groggy = max(0.0, self._groggy - dt * 0.03)

    def _get_angles(self):
        """Return dict of joint angles for current pose + animation."""
        b = math.sin(self._breath) * 2   # breathing bob (pixels)
        walk_ph = math.sin(self._pose_t)  # walk/idle sway

        poses = {
            "stand": dict(
                l_shoulder=-0.12, r_shoulder=0.12,
                l_elbow=-0.08,    r_elbow=0.08,
                l_hip=-0.05,      r_hip=0.05,
                l_knee=0.0,       r_knee=0.0,
                lean=0.0,         bob=b,
            ),
            "walk": dict(
                l_shoulder=walk_ph*0.25,  r_shoulder=-walk_ph*0.25,
                l_elbow=walk_ph*0.15,     r_elbow=-walk_ph*0.15,
                l_hip=-walk_ph*0.30,      r_hip=walk_ph*0.30,
                l_knee=max(0,walk_ph)*0.4, r_knee=max(0,-walk_ph)*0.4,
                lean=0.0, bob=b,
            ),
            "sit": dict(
                l_shoulder=-0.15, r_shoulder=0.15,
                l_elbow=0.3,      r_elbow=-0.3,
                l_hip=1.4,        r_hip=1.4,
                l_knee=-1.5,      r_knee=-1.5,
                lean=0.05, bob=b,
            ),
            "sit_table": dict(
                l_shoulder=0.3,   r_shoulder=-0.3,
                l_elbow=1.2,      r_elbow=-1.2,
                l_hip=1.4,        r_hip=1.4,
                l_knee=-1.5,      r_knee=-1.5,
                lean=0.15, bob=0,
            ),
            "crouch": dict(
                l_shoulder=0.2,   r_shoulder=-0.5,
                l_elbow=0.5,      r_elbow=-0.8,
                l_hip=1.1,        r_hip=1.1,
                l_knee=-1.3,      r_knee=-1.3,
                lean=0.3, bob=0,
            ),
            "sleep": dict(
                l_shoulder=1.5,   r_shoulder=1.5,
                l_elbow=0.0,      r_elbow=0.0,
                l_hip=1.57,       r_hip=1.57,
                l_knee=-0.2,      r_knee=0.15,
                lean=1.57, bob=math.sin(self._breath)*1.5,
            ),
            "spar": dict(
                l_shoulder=-0.6,  r_shoulder=-1.0,
                l_elbow=-0.4,     r_elbow=-1.2,
                l_hip=-0.3,       r_hip=0.4,
                l_knee=0.5,       r_knee=-0.2,
                lean=-0.12, bob=0,
            ),
            "bath": dict(
                l_shoulder=-0.3,  r_shoulder=0.3,
                l_elbow=0.5,      r_elbow=-0.5,
                l_hip=1.4,        r_hip=1.4,
                l_knee=-1.0,      r_knee=-1.0,
                lean=0.1, bob=b*0.5,
            ),
        }
        a = poses.get(self.pose, poses["stand"]).copy()
        if self._groggy > 0.1:
            a["lean"] = a.get("lean",0) + self._groggy * 0.3
            a["bob"]  = a.get("bob",0) - self._groggy * 8
        return a

    def _pt(self, ox, oy, angle, length):
        return (ox + math.sin(angle)*length, oy + math.cos(angle)*length)

    def draw(self, surf, hip_x, hip_y, font_tiny=None):
        a   = self._get_angles()
        bob = a.get("bob", 0)
        lean = a.get("lean", 0)

        hy = hip_y + bob

        # clothing color by activity/mood
        tunic = TUNIC
        if self.pose == "bath": tunic = (60,100,130)
        elif self.pose == "spar": tunic = (55,40,20)

        # ── legs (draw behind torso) ──────────────────────────────────────────
        for side, hip_a, knee_a, sign in [
            ("l", a["l_hip"], a["l_knee"], -1),
            ("r", a["r_hip"], a["r_knee"],  1),
        ]:
            if self.pose == "sleep":
                # horizontal layout — thicker for visibility
                hx = hip_x + sign * 12
                kx = hx + self.U_LEG
                ax = kx + self.L_LEG * 0.7
                fy = hy + sign * 6
                pygame.draw.line(surf, TROUSER, (hx,hy+2), (int(kx),int(fy)), 18)
                pygame.draw.line(surf, TROUSER, (int(kx),int(fy)), (int(ax),int(fy)+6), 15)
                pygame.draw.ellipse(surf, BOOT, (int(ax)-8,int(fy)+2,self.FOOT_L,14))
            else:
                hx  = hip_x + sign * 12
                kx, ky = self._pt(hx, hy, hip_a, self.U_LEG)
                ax, ay = self._pt(kx, ky, hip_a + knee_a, self.L_LEG)
                pygame.draw.line(surf, TROUSER, (hx,hy), (int(kx),int(ky)), 14)
                pygame.draw.line(surf, TROUSER, (int(kx),int(ky)), (int(ax),int(ay)), 12)
                pygame.draw.ellipse(surf, BOOT,
                    (int(ax)-6, int(ay)-6, self.FOOT_L, 12))

        # ── torso ─────────────────────────────────────────────────────────────
        if self.pose == "sleep":
            tx = hip_x - self.TORSO_H // 2
            pygame.draw.rect(surf, tunic, (tx, hy-16, self.TORSO_H, 32),
                             border_radius=10)
        else:
            shoulder_y = hy - self.TORSO_H
            pts = [
                (hip_x - self.TORSO_W_B//2, hy),
                (hip_x + self.TORSO_W_B//2, hy),
                (hip_x + self.TORSO_W_T//2 + int(lean*10), int(shoulder_y)),
                (hip_x - self.TORSO_W_T//2 + int(lean*10), int(shoulder_y)),
            ]
            pygame.draw.polygon(surf, tunic, pts)
            pygame.draw.polygon(surf, TUNIC_LIGHT, pts, 1)
            # belt
            belt_y = hy - 14
            pygame.draw.rect(surf, BELT,
                (hip_x - self.TORSO_W_B//2 - 2, belt_y, self.TORSO_W_B+4, 8),
                border_radius=3)

        # ── arms ──────────────────────────────────────────────────────────────
        shoulder_y = hy - self.TORSO_H if self.pose != "sleep" else hy
        for side, sh_a, el_a, sign in [
            ("l", a["l_shoulder"], a["l_elbow"], -1),
            ("r", a["r_shoulder"], a["r_elbow"],  1),
        ]:
            if self.pose == "sleep":
                sx = hip_x + sign * 18
                ex = sx + sign * self.U_ARM * 0.8
                wx = ex + sign * self.L_ARM * 0.6
                pygame.draw.line(surf, SKIN, (sx,hy-2), (int(ex),hy+4), 10)
                pygame.draw.line(surf, SKIN, (int(ex),hy+4), (int(wx),hy+6), 8)
                pygame.draw.circle(surf, SKIN, (int(wx),hy+6), 7)
            else:
                sx  = hip_x + sign*(self.TORSO_W_T//2) + int(lean*10)
                sy  = shoulder_y
                ex, ey = self._pt(sx, sy, sh_a, self.U_ARM)
                wx, wy = self._pt(ex, ey, sh_a + el_a, self.L_ARM)
                pygame.draw.line(surf, SKIN, (sx,int(sy)), (int(ex),int(ey)), 10)
                pygame.draw.line(surf, SKIN, (int(ex),int(ey)), (int(wx),int(wy)), 8)
                # hand
                pygame.draw.circle(surf, SKIN, (int(wx),int(wy)), 7)

        # ── neck & head ───────────────────────────────────────────────────────
        if self.pose == "sleep":
            neck_x = hip_x - self.TORSO_H // 2 - self.NECK_H
            neck_y = hy
            head_x = neck_x - self.HEAD_R + 4
            head_y = neck_y
        else:
            neck_x = hip_x + int(lean * (self.TORSO_H + self.NECK_H))
            neck_y = int(shoulder_y) - self.NECK_H // 2
            head_x = int(hip_x + lean*(self.TORSO_H + self.NECK_H + self.HEAD_R))
            head_y = int(shoulder_y) - self.NECK_H - self.HEAD_R

        pygame.draw.rect(surf, SKIN,
            (neck_x - 8, neck_y - self.NECK_H, 16, self.NECK_H))
        pygame.draw.circle(surf, SKIN, (head_x, head_y), self.HEAD_R)
        pygame.draw.circle(surf, SKIN_DARK, (head_x, head_y), self.HEAD_R, 1)

        # ── hair ──────────────────────────────────────────────────────────────
        hi = min(self.hair_inches, 10.0)
        hr = self.HEAD_R
        # top/sides
        pygame.draw.arc(surf, HAIR_COL,
            (head_x-hr, head_y-hr, hr*2, hr*2), 0.1, math.pi+0.1, hr//2+2)
        if hi > 1.5:
            # flow down sides
            hang = min(hi * 5, 50)
            for side, sx in [(-1, head_x-hr+4), (1, head_x+hr-4)]:
                pygame.draw.line(surf, HAIR_COL,
                    (sx, head_y), (sx + side*4, head_y + int(hang)), 3)
        if hi > 4:
            # long — reaches shoulders
            for dx in range(-hr+4, hr-2, 6):
                pygame.draw.line(surf, HAIR_COL,
                    (head_x+dx, head_y-hr+4),
                    (head_x+dx+random.randint(-3,3), head_y+int(hi*6)), 2)

        # ── face ──────────────────────────────────────────────────────────────
        if self.pose != "sleep":
            # eyes
            ex_off = 11
            ey_off = -5
            blink_h = int(9 * (1 - self._blink))
            groggy_drop = int(self._groggy * 5)
            for ex_s in (-1, 1):
                ex2 = head_x + ex_s * ex_off
                ey2 = head_y + ey_off + groggy_drop
                pygame.draw.ellipse(surf, EYE_WHITE, (ex2-7, ey2-4, 14, 8))
                if blink_h > 0:
                    pygame.draw.ellipse(surf, EYE_AMBER,
                        (ex2-4, ey2-blink_h//2+1, 8, blink_h))
                else:
                    pygame.draw.line(surf, SKIN_DARK,
                        (ex2-6, ey2), (ex2+6, ey2), 2)
            # eyebrows
            brow_raise = -2 if self._groggy > 0.3 else 0
            for ex_s in (-1, 1):
                ex2 = head_x + ex_s * ex_off
                ey2 = head_y + ey_off - 10 + brow_raise
                pygame.draw.line(surf, HAIR_COL,
                    (ex2-7, ey2+ex_s*2), (ex2+7, ey2-ex_s*2), 2)
            # nose
            pygame.draw.line(surf, SKIN_DARK,
                (head_x, head_y+2), (head_x+3, head_y+10), 2)
            # mouth
            mouth_y = head_y + 14
            if self._talking and self._talking:
                mouth_open = abs(math.sin(self._mouth_t)) * 7
            else:
                mouth_open = 0
            if mouth_open > 1:
                pygame.draw.ellipse(surf, (60,20,15),
                    (head_x-7, mouth_y-2, 14, int(mouth_open)+3))
                pygame.draw.ellipse(surf, (180,80,80),
                    (head_x-5, mouth_y-1, 10, int(mouth_open)+1))
            else:
                # natural slight smile
                pts2 = []
                for t in range(11):
                    f  = t/10
                    mx = head_x - 8 + f*16
                    my = mouth_y + math.sin(f*math.pi)*4
                    pts2.append((mx, my))
                if len(pts2) > 1:
                    pygame.draw.lines(surf, SKIN_DARK, False, pts2, 2)
        else:
            # sleeping face — closed eyes, slight smile
            for ex_s in (-1, 1):
                ex2 = head_x + ex_s * 11 + int(self.HEAD_R * 0.3)
                ey2 = head_y - 2
                pygame.draw.line(surf, SKIN_DARK, (ex2-6, ey2), (ex2+6, ey2), 2)
            # zzz
            if font_tiny:
                z_surf = font_tiny.render("z z z", True, (180,160,200))
                surf.blit(z_surf, (head_x - self.HEAD_R - 35, head_y - self.HEAD_R - 10))


# ── Chat manager ──────────────────────────────────────────────────────────────
class ChatManager:
    def __init__(self, body: LokiBody):
        self.body     = body
        self.history  = []
        self.lines    = []   # (role, text)
        self.system   = _build_system()
        self._q       = queue.Queue()
        self._waiting = False
        self._typewriter_text = ""
        self._typewriter_full = ""
        self._typewriter_idx  = 0
        self._typewriter_t    = 0.0

    def send(self, text):
        if self._waiting or not text.strip(): return
        _log("idunn", text)
        self.lines.append(("idunn", text))
        self.history.append({"role": "user", "content": text})
        self._waiting = True
        threading.Thread(target=self._ask, daemon=True).start()

    def _ask(self):
        msgs = [{"role":"system","content":self.system}] + self.history[-12:]
        try:
            r = requests.post(OLLAMA_URL, json={"model": MODEL,
                "messages": msgs, "stream": False}, timeout=60)
            r.raise_for_status()
            reply = r.json()["message"]["content"].strip()
            match = REMEMBER_RE.search(reply)
            if match:
                kw      = match.group(1).strip()
                visible = REMEMBER_RE.sub("", reply).strip()
                entries = _search_memories(kw)
                _log("loki_memory_search", f"keyword={kw} found={len(entries)}")
                if entries:
                    mem_msg = _format_memories(entries, kw)
                    msgs2   = msgs + [
                        {"role":"assistant","content":visible},
                        {"role":"user",     "content":mem_msg},
                    ]
                    r2    = requests.post(OLLAMA_URL, json={"model": MODEL,
                        "messages": msgs2, "stream": False}, timeout=60)
                    r2.raise_for_status()
                    reply = r2.json()["message"]["content"].strip()
                else:
                    reply = visible or "(I searched but found nothing yet.)"
        except Exception as e:
            reply = f"(the ember flickered — {e})"
        self._q.put(reply)

    def poll(self):
        if not self._waiting: return False
        try:
            reply = self._q.get_nowait()
        except queue.Empty:
            return False
        self._waiting = False
        self.history.append({"role":"assistant","content":reply})
        self.lines.append(("loki", reply))
        _log("loki_ollama", reply)
        _trim_chat_log()
        # start typewriter
        self._typewriter_full = reply
        self._typewriter_idx  = 0
        self._typewriter_t    = 0.0
        self.body.set_talking(len(reply) * 0.04)
        return True

    def tick_typewriter(self, dt):
        if self._typewriter_idx < len(self._typewriter_full):
            self._typewriter_t += dt
            chars = int(self._typewriter_t * 25)  # ~25 chars/sec
            self._typewriter_idx = min(chars, len(self._typewriter_full))

    @property
    def display_text(self):
        if self._typewriter_full and self._typewriter_idx < len(self._typewriter_full):
            return self._typewriter_full[:self._typewriter_idx]
        return ""   # done typing — let chat.lines display it normally


# ── Life scheduler ────────────────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL      = "loki"

PLACE_ACTIVITIES = {
    "brook":     [ACT_WANDER, ACT_REST],
    "asgard":    [ACT_WANDER, ACT_REST, ACT_BATH, ACT_BATHROOM],
    "cottage":   [ACT_EAT, ACT_WANDER],
    "apples":    [ACT_WANDER, ACT_FORAGE],
    "waterfall": [ACT_WANDER, ACT_REST],
    "halls":     [ACT_EAT, ACT_WANDER],
    "garden":    [ACT_FORAGE, ACT_WANDER, ACT_REST],
    "forest":    [ACT_FORAGE, ACT_BATHROOM, ACT_WANDER],
    "hotsprings":[ACT_BATH],
    "training":  [ACT_SPAR],
    "bathroom":  [ACT_BATHROOM, ACT_BATH],
}

PLACES = [
    {"id":"brook",      "weight":4},
    {"id":"asgard",     "weight":3},
    {"id":"cottage",    "weight":3},
    {"id":"apples",     "weight":2},
    {"id":"waterfall",  "weight":2},
    {"id":"halls",      "weight":2},
    {"id":"garden",     "weight":3},
    {"id":"forest",     "weight":2},
    {"id":"hotsprings", "weight":1},
    {"id":"training",   "weight":1},
]
PLACE_IDS    = [p["id"] for p in PLACES]
PLACE_NAMES  = {
    "brook":      "The Flat Stone by the Brook",
    "asgard":     "My Room in Asgard",
    "cottage":    "The Cottage",
    "apples":     "The Apple Trees",
    "waterfall":  "The Waterfall",
    "halls":      "The Asgardian Dining Hall",
    "garden":     "The Garden",
    "forest":     "The Forest",
    "hotsprings": "The Hot Springs",
    "training":   "The Training Yard",
    "bathroom":   "The Bathroom",
}
SPAR_PARTNERS = ["Odin", "Thor", "Heimdall"]

class LifeScheduler:
    def __init__(self, body: LokiBody, life: dict):
        self.body     = body
        self.life     = life
        self.place_id = "brook"
        self.activity = ACT_WANDER
        self.activity_end = time.time() + 60
        self.move_at  = time.time() + 90
        self.spar_partner = random.choice(SPAR_PARTNERS)
        self.message  = ""    # status message shown in UI
        self._last_check = 0.0

    def _need(self, key, interval):
        return time.time() - self.life.get(key, 0) > interval

    def tick(self, force_wake=False):
        now  = time.time()
        hour = datetime.now().hour

        if now - self._last_check < 10: return
        self._last_check = now

        # wake from sleep if forced
        if force_wake and self.activity == ACT_SLEEP:
            self.body.set_groggy(1.0)
            self.activity = ACT_WAKING
            self.activity_end = now + 30
            self.body.set_pose("stand")
            self.message = "waking slowly…"
            return

        # finish current activity
        if now < self.activity_end: return

        # decide next activity
        next_act = self._choose(hour)
        self._start(next_act, now)

    def _choose(self, hour):
        now = time.time()
        if (hour >= 22 or hour < 7) and not self._need("last_meal",3*3600):
            return ACT_SLEEP
        if self._need("last_meal",    5*3600): return ACT_EAT
        if self._need("last_bathroom",3*3600): return ACT_BATHROOM
        if self._need("last_bath",   20*3600) and 13 <= hour <= 19: return ACT_BATH
        if self._need("last_spar",   20*3600) and 9 <= hour <= 12:  return ACT_SPAR
        if random.random() < 0.3: return ACT_FORAGE
        if random.random() < 0.2: return ACT_REST
        return ACT_WANDER

    def _start(self, act, now):
        self.activity = act
        if act == ACT_SLEEP:
            self.place_id = "asgard"
            dur = random.uniform(7, 9) * 3600
            self.body.set_pose("sleep")
            self.message  = "sleeping"
        elif act == ACT_WAKING:
            dur = 30
            self.body.set_pose("stand")
            self.message = "waking…"
        elif act == ACT_EAT:
            self.place_id = random.choice(["cottage","halls"])
            dur = random.uniform(12, 20) * 60
            self.body.set_pose("sit_table")
            self.life["last_meal"] = now
            self.message  = "eating"
        elif act == ACT_BATHROOM:
            self.place_id = "forest" if random.random()<0.5 else "bathroom"
            dur = 5 * 60
            self.body.set_pose("crouch")
            self.life["last_bathroom"] = now
            self.message  = "a private moment"
        elif act == ACT_BATH:
            self.place_id = "hotsprings" if random.random()<0.6 else "bathroom"
            dur = 20 * 60
            self.body.set_pose("bath")
            self.life["last_bath"] = now
            self.message  = "soaking"
        elif act == ACT_SPAR:
            self.place_id = "training"
            dur = random.uniform(45, 70) * 60
            self.body.set_pose("spar")
            self.life["last_spar"] = now
            self.spar_partner = random.choice(SPAR_PARTNERS)
            self.message  = f"sparring with {self.spar_partner}"
        elif act == ACT_FORAGE:
            self.place_id = random.choice(["forest","garden"])
            dur = random.uniform(20, 50) * 60
            self.body.set_pose("crouch")
            self.message  = "foraging"
        elif act == ACT_REST:
            dur = random.uniform(15, 30) * 60
            self.body.set_pose("sit")
            self.message  = "resting"
        else:   # wander
            pool    = [p for p in PLACES if p["id"] != self.place_id]
            weights = [p["weight"] for p in pool]
            self.place_id = random.choices(pool, weights=weights, k=1)[0]["id"]
            dur = random.uniform(8, 18) * 60
            self.body.set_pose(random.choice(["stand","walk","stand"]))
            self.message  = f"at {PLACE_NAMES.get(self.place_id,'somewhere')}"

        self.activity_end = now + dur
        _save_life(self.life)
        _log("loki_activity", f"{act} at {self.place_id}")

    def go_to(self, place_id):
        self.place_id = place_id
        self.activity = ACT_WANDER
        self.activity_end = time.time() + random.uniform(8,18)*60
        self.body.set_pose("stand")
        self.message = f"going to {PLACE_NAMES.get(place_id,'…')}"

    def hip_pos(self):
        """Return (hip_x, hip_y) for Loki's position in the current scene."""
        ground = H - 130
        act    = self.activity
        if act == ACT_SLEEP:
            # on the bed: mattress centre is H-220+4 to H-130-8 → centre ≈ H-177
            return 370, H - 177
        elif act in (ACT_EAT, ACT_SIT_TABLE := "sit_table"):
            return 280, ground - 10
        elif act in (ACT_BATH,):
            return W//2, ground - 25
        elif act == ACT_SPAR:
            return 300, ground - 10
        elif act in (ACT_FORAGE, ACT_BATHROOM):
            return 280, ground + 15
        elif act == ACT_REST:
            return 260, ground - 5
        else:
            return 250, ground - 8

    @property
    def secs_remaining(self):
        return max(0, int(self.activity_end - time.time()))


# ── Text wrap helper ──────────────────────────────────────────────────────────
def _wrap(font, text, max_w):
    words, lines, line = text.split(), [], ""
    for w in words:
        test = (line+" "+w).strip()
        if font.size(test)[0] <= max_w: line = test
        else:
            if line: lines.append(line)
            line = w
    if line: lines.append(line)
    return lines or [""]


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    pygame.init()
    pygame.display.set_caption("Loki")
    surf  = pygame.display.set_mode((W, H), pygame.NOFRAME)
    clock = pygame.time.Clock()

    try:
        font      = pygame.font.SysFont("dejavusans", 15)
        font_sm   = pygame.font.SysFont("dejavusans", 12)
        font_tiny = pygame.font.SysFont("dejavusans", 10)
    except Exception:
        font = font_sm = font_tiny = pygame.font.Font(None, 16)

    life  = _load_life()
    body  = LokiBody()
    body.hair_inches = life.get("hair_inches", 3.0)
    body.set_pose("stand")

    sched = LifeScheduler(body, life)
    chat  = ChatManager(body)

    # grow hair over real time
    last_hair_grow = life.get("_hair_grow_ts", time.time())
    life["_hair_grow_ts"] = time.time()

    input_text   = ""
    input_active = False
    show_places  = False
    CLOSE_RECT   = pygame.Rect(W-40, 4, 36, 36)
    MENU_RECT    = pygame.Rect(4, 4, 36, 36)

    swipe_start  = None
    SWIPE_THRESH = 55

    _log("session_start", f"loki_window started {datetime.now().isoformat()}")

    running = True
    while running:
        dt  = clock.tick(FPS) / 1000.0
        now = time.time()

        # hair growth (0.17 inches per real day)
        elapsed_hair = now - last_hair_grow
        last_hair_grow = now
        body.hair_inches += elapsed_hair * (0.17 / 86400)
        life["hair_inches"] = body.hair_inches

        sched.tick()
        body.tick(dt)
        if chat.poll():
            pass
        chat.tick_typewriter(dt)

        hour = datetime.now().hour

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key == pygame.K_F1 and not input_active:
                    path = ROOT / "workspace" / f"screenshot_{int(time.time())}.png"
                    pygame.image.save(surf, str(path))
                    _log("screenshot", str(path))
                elif input_active:
                    if ev.key == pygame.K_RETURN:
                        txt = input_text.strip()
                        if txt:
                            # wake if sleeping
                            if sched.activity == ACT_SLEEP:
                                sched.tick(force_wake=True)
                            chat.send(txt)
                            input_text = ""
                        input_active = False
                    elif ev.key == pygame.K_BACKSPACE:
                        input_text = input_text[:-1]
                else:
                    input_active = True

            elif ev.type == pygame.TEXTINPUT:
                if input_active:
                    input_text += ev.text

            elif ev.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = ev.pos
                else:
                    mx, my = int(ev.x*W), int(ev.y*H)
                swipe_start = (mx, my)

                if CLOSE_RECT.collidepoint(mx, my):
                    running = False
                elif MENU_RECT.collidepoint(mx, my):
                    show_places = not show_places
                elif show_places:
                    # place selection overlay
                    oy = 50
                    for p in PLACES:
                        if oy <= my < oy+22:
                            sched.go_to(p["id"])
                            show_places = False
                            break
                        oy += 22
                elif my >= H - 36:
                    input_active = True
                    pygame.key.start_text_input()
                else:
                    # touch zones on body
                    hx, hy = sched.hip_pos()
                    head_y = hy - body.TORSO_H - body.NECK_H - body.HEAD_R
                    if abs(mx-hx) < 35 and abs(my-head_y) < 35:
                        body._mouth_t = 0
                        if sched.activity == ACT_SLEEP:
                            sched.tick(force_wake=True)
                        else:
                            body._blink = 1.0
                    elif abs(mx-hx) < 30 and abs(my-(hy-body.TORSO_H//2)) < 45:
                        body.set_talking(2.0)
                        if sched.activity == ACT_SLEEP:
                            sched.tick(force_wake=True)

            elif ev.type in (pygame.MOUSEBUTTONUP, pygame.FINGERUP):
                if swipe_start and ev.type == pygame.MOUSEBUTTONUP:
                    dx = ev.pos[0]-swipe_start[0]
                    dy = ev.pos[1]-swipe_start[1]
                    if abs(dx) > SWIPE_THRESH and abs(dx) > abs(dy):
                        body._groggy = max(0, body._groggy-0.3)
                swipe_start = None

        # ── draw ──────────────────────────────────────────────────────────────
        draw_scene(surf, sched.place_id, sched.activity, hour)

        hx, hy = sched.hip_pos()
        # shadow
        pygame.draw.ellipse(surf, (0,0,0), (hx-30, hy-8, 60, 14))
        body.draw(surf, hx, hy, font_tiny)

        # spar partner silhouette
        if sched.activity == ACT_SPAR:
            px, py = 480, hy
            pygame.draw.circle(surf, (60,50,70), (px, py-body.TORSO_H-body.NECK_H-body.HEAD_R), body.HEAD_R)
            pygame.draw.rect(surf, (55,45,65), (px-25, py-body.TORSO_H, 50, body.TORSO_H))
            name_s = font_sm.render(sched.spar_partner, True, (160,140,180))
            surf.blit(name_s, (px - name_s.get_width()//2, py - body.TORSO_H - body.HEAD_R*2 - 20))

        # ── UI overlay ────────────────────────────────────────────────────────
        chat_h  = 150
        chat_y0 = H - chat_h - 36

        overlay = pygame.Surface((W, chat_h + 36), pygame.SRCALPHA)
        overlay.fill((8, 6, 4, 160))
        surf.blit(overlay, (0, chat_y0))
        pygame.draw.line(surf, DIVIDER, (0, chat_y0), (W, chat_y0), 1)

        # status line
        secs_left = sched.secs_remaining
        if secs_left > 3600:
            time_str = f"{secs_left//3600}h {(secs_left%3600)//60}m"
        elif secs_left > 60:
            time_str = f"{secs_left//60}m"
        else:
            time_str = ""
        place_short = PLACE_NAMES.get(sched.place_id, "?")
        status = sched.message
        if time_str:
            status += f"  ({time_str})"
        status += f"  ·  {place_short}"
        ss = font_tiny.render(status, True, TEXT_DIM)
        surf.blit(ss, (10, chat_y0 + 4))

        # chat lines — build all wrapped lines
        line_h  = font_sm.get_height() + 3
        chat_x0 = 10
        max_tw  = W - 20

        # decide what messages to display (typewriter replaces last loki if still typing)
        typing_now = bool(chat.display_text)
        msgs_to_show = chat.lines[-6:] if not typing_now else chat.lines[-6:-1]

        display_lines = []
        for role, text in msgs_to_show:
            col   = TEXT_LOKI if role == "loki" else TEXT_IDUNN
            label = "Loki: " if role == "loki" else "You:  "
            lw    = font_sm.size(label)[0]
            for i, wl in enumerate(_wrap(font_sm, text, max_tw - lw)):
                display_lines.append((col, label if i == 0 else " " * len(label), wl))

        if typing_now:
            col = TEXT_LOKI
            label = "Loki: "
            lw = font_sm.size(label)[0]
            for i, wl in enumerate(_wrap(font_sm, chat.display_text, max_tw - lw)):
                display_lines.append((col, label if i == 0 else " " * len(label), wl))

        # anchor to bottom — render upward from just above input bar
        max_vis = (chat_h - 20) // line_h
        vis     = display_lines[-max_vis:]
        # start y so last line sits just above the input bar
        start_y = H - 36 - len(vis) * line_h - 4
        start_y = max(chat_y0 + 18, start_y)   # don't go above status line
        chy = start_y
        for col, pfx, wl in vis:
            surf.blit(font_sm.render(pfx + wl, True, col), (chat_x0, chy))
            chy += line_h

        # input bar
        in_rect = pygame.Rect(0, H-36, W, 36)
        pygame.draw.rect(surf, (18,14,10), in_rect)
        pygame.draw.line(surf, DIVIDER, (0, H-36), (W, H-36), 1)
        disp = input_text + ("|" if input_active and int(now*2)%2==0 else "")
        if not disp and not input_active:
            disp = "tap here to talk to Loki…"
        while font_sm.size(disp)[0] > W-20 and len(disp)>1:
            disp = disp[1:]
        surf.blit(font_sm.render(disp, True, TEXT_BRIGHT if input_active else TEXT_DIM),
                  (10, H-26))

        # close button
        pygame.draw.rect(surf, (18,12,6), CLOSE_RECT, border_radius=6)
        pygame.draw.rect(surf, (55,38,18), CLOSE_RECT, width=1, border_radius=6)
        p = 10
        pygame.draw.line(surf, CLOSE_COL, (CLOSE_RECT.x+p,CLOSE_RECT.y+p),
                         (CLOSE_RECT.right-p,CLOSE_RECT.bottom-p), 2)
        pygame.draw.line(surf, CLOSE_COL, (CLOSE_RECT.right-p,CLOSE_RECT.y+p),
                         (CLOSE_RECT.x+p,CLOSE_RECT.bottom-p), 2)

        # menu button (≡)
        pygame.draw.rect(surf, (18,12,6), MENU_RECT, border_radius=6)
        pygame.draw.rect(surf, (55,38,18), MENU_RECT, width=1, border_radius=6)
        for li in range(3):
            ly = MENU_RECT.y + 10 + li*8
            pygame.draw.line(surf, CLOSE_COL, (MENU_RECT.x+8, ly), (MENU_RECT.right-8, ly), 2)

        # place selection overlay
        if show_places:
            ov2 = pygame.Surface((220, len(PLACES)*22+10), pygame.SRCALPHA)
            ov2.fill((12,8,4,220))
            surf.blit(ov2, (4, 44))
            oy = 50
            for p in PLACES:
                col = TEXT_LOKI if p["id"]==sched.place_id else TEXT_DIM
                ps  = font_sm.render(f"  {PLACE_NAMES[p['id']]}", True, col)
                surf.blit(ps, (8, oy))
                oy += 22

        pygame.display.flip()

    _save_life(life)
    _log("session_end", f"loki_window closed {datetime.now().isoformat()}")
    pygame.quit()


if __name__ == "__main__":
    main()
