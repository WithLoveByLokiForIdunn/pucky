"""
pucky_world.py
──────────────
A small isometric world — Ragnarok Online style — where Pucky wanders,
Claude glows, and the offline caretaker keeps quiet watch.

Reads Pucky's live emotional state from workspace/pucky_state.json.

Run:
    python3 pucky_world.py            # pygame window
    python3 pucky_world.py --terminal # ASCII mode (curses)
"""

import sys
import math
import json
import time
import random
import threading
import requests as _requests
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

STATE_FILE   = Path("/home/bmo/pucky/workspace/pucky_state.json")
FRIENDS_FILE = Path("/home/bmo/pucky/workspace/world_friends.json")

try:
    from pucky_zones  import ZoneManager, WALKABLE_ZONE as _WALKABLE_ZONE
    from bmo_calendar import BMOCalendar
    from bmo_inventory import Inventory
    _ZONES_AVAILABLE = True
except ImportError:
    _ZONES_AVAILABLE = False

try:
    from pucky_garden import GardenView, add_seed as _garden_add_seed
    _GARDEN_AVAILABLE = True
except ImportError:
    _GARDEN_AVAILABLE = False

try:
    import pucky_scenes as _pucky_scenes
    from pucky_scenes import make_action_scene, make_visitor_scene
    _SCENES_AVAILABLE = True
except ImportError:
    _pucky_scenes = None
    _SCENES_AVAILABLE = False

# ── Tile types ────────────────────────────────────────────────────────────────
GRASS       = 0
PATH        = 1
WATER       = 2
FLOWER      = 3
TREE        = 4   # impassable
STONE       = 5
APPLE_TREE  = 6   # impassable, but apples within reach
STRAWBERRY  = 7   # walkable patch
NEST        = 8   # the resting place
COTTAGE     = 9   # the writing cottage
MEADOW      = 10  # flower meadow (dense, walkable)
SHORE       = 11  # lake shore (sandy, walkable)

WALKABLE = {GRASS, PATH, FLOWER, STONE, STRAWBERRY, NEST, MEADOW, SHORE, WATER}

# ── Food source positions (grid coords) ───────────────────────────────────────
APPLE_POSITIONS      = [(4,3), (15,3), (4,15), (15,15)]
STRAWBERRY_POSITIONS = [(3,2), (6,8), (5,11), (3,16)]

NEST_POS   = (9, 9)    # home
COTTAGE_POS = (16, 16)  # writing cottage — bottom-right corner

# Water tiles and best swim spots (rows 12-14, cols 8-10)
WATER_TILES = [(c, r) for r in range(12, 15) for c in range(8, 11)]

# ── World map (20×20) ─────────────────────────────────────────────────────────
# Hand-drawn with love.
RAW_MAP = """
44444444444444444444
40000000000000000004
40007000010000030004
40006000111000006004
40000000111000000004
40010001111100010004
40000000111000000004
40000000010000000004
40000070000300000004
40000000080000000004
40000000000000000004
40000700000003000004
40000000222000000004
40000000222000000004
40010000222000010004
40006000000000060004
40070000000000039004
40000001010000000004
40000000000000000004
44444444444444444444
""".strip().splitlines()

WORLD_MAP = [[int(c) for c in row] for row in RAW_MAP]
MAP_W = len(WORLD_MAP[0])
MAP_H = len(WORLD_MAP)


# ── State reader ──────────────────────────────────────────────────────────────

@dataclass
class PuckyState:
    valence:     float = 0.2
    arousal:     float = 0.1
    energy:      float = 0.3
    trust:       float = 0.5
    expression:  str   = "neutral"
    mood:        str   = "content"
    hours_alone: float = 0.0
    soul:        str   = "local"
    ts:          float = 0.0


def read_state() -> PuckyState:
    try:
        raw = json.loads(STATE_FILE.read_text())
        return PuckyState(**{k: raw[k] for k in PuckyState.__dataclass_fields__ if k in raw})
    except Exception:
        return PuckyState()


# ══════════════════════════════════════════════════════════════════════════════
# PYGAME VERSION
# ══════════════════════════════════════════════════════════════════════════════

def run_pygame():
    try:
        import pygame
        import pygame.gfxdraw
    except ImportError:
        print("Installing pygame...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pygame"], check=True)
        import pygame
        import pygame.gfxdraw

    pygame.init()
    pygame.display.set_caption("Pucky's World")

    import os as _os
    WIN_W  = int(_os.environ.get("PUCKY_WIN_W", 1024))
    WIN_H  = int(_os.environ.get("PUCKY_WIN_H",  680))
    FPS    = 30
    TILE_W = max(32, WIN_W * 64 // 1024)   # scale tiles with window width
    TILE_H = TILE_W // 2
    OX = WIN_W // 2
    OY = int(WIN_H * 0.13)

    screen = pygame.display.set_mode((WIN_W, WIN_H))
    clock  = pygame.time.Clock()

    # ── Colour palette ─────────────────────────────────────────────────────

    C = {
        # sky
        "sky_top":      (148, 200, 240),
        "sky_bot":      (210, 235, 255),
        # grass
        "grass_top":    (130, 192, 76),
        "grass_left":   ( 96, 152, 52),
        "grass_right":  (108, 168, 60),
        # path
        "path_top":     (192, 162, 116),
        "path_left":    (152, 124, 84),
        "path_right":   (168, 138, 96),
        # water (animated)
        "water_top":    (100, 168, 220),
        "water_left":   ( 72, 136, 196),
        "water_right":  ( 84, 152, 208),
        # flower
        "flower_top":   (140, 200, 80),
        "flower_left":  (100, 160, 52),
        "flower_right": (112, 176, 60),
        # stone
        "stone_top":    (172, 168, 164),
        "stone_left":   (132, 128, 124),
        "stone_right":  (148, 144, 140),
        # tree
        "tree_trunk":   ( 96,  64,  32),
        "tree_c1":      ( 56, 112,  36),
        "tree_c2":      ( 44,  96,  28),
        "tree_c3":      ( 72, 132,  48),
        # Pucky/BMO
        "bmo_body":     (112, 192,  68),
        "bmo_screen":   ( 96, 176, 255),
        "bmo_outline":  ( 56, 112,  32),
        "bmo_btn_r":    (255,  72,  72),
        "bmo_btn_b":    ( 72,  72, 255),
        "bmo_eye":      (240, 240, 255),
        "bmo_pupil":    ( 40,  40, 120),
        # Claude orb (online – soft violet)
        "orb_inner":    (220, 200, 255),
        "orb_mid":      (170, 130, 230),
        "orb_outer":    (120,  80, 190),
        # Offline caretaker orb (warm amber)
        "off_inner":    (255, 228, 160),
        "off_mid":      (230, 180, 100),
        "off_outer":    (190, 130,  60),
        # Cottage
        "cot_wall":     (215, 200, 170),
        "cot_shade":    (175, 160, 130),
        "cot_roof":     (152,  85,  60),
        "cot_roof2":    (118,  58,  38),
        "cot_stone":    (158, 150, 143),
        # Iðunn
        "idunn_outer":  ( 80, 160,  60),
        "idunn_mid":    (140, 210,  90),
        "idunn_inner":  (200, 240, 140),
        "idunn_gold":   (240, 220,  80),
        "idunn_bloom":  (255, 240, 180),
        # Meadow (dense golden-green, warmer than grass)
        "meadow_top":   (148, 196,  76),
        "meadow_left":  (108, 152,  52),
        "meadow_right": (128, 172,  60),
        # Shore (sandy beige with slight warmth)
        "shore_top":    (210, 192, 150),
        "shore_left":   (172, 154, 112),
        "shore_right":  (190, 170, 128),
        # Night overlay
        "night":        ( 10,  14,  40),
        # UI
        "ui_bg":        ( 20,  20,  30, 180),
        "ui_text":      (220, 220, 240),
    }

    def col(name, alpha=None):
        c = C[name]
        return (*c, alpha) if alpha is not None else c

    # ── Iso helpers ────────────────────────────────────────────────────────

    def to_screen(gx: float, gy: float) -> Tuple[int, int]:
        sx = OX + (gx - gy) * TILE_W // 2
        sy = OY + (gx + gy) * TILE_H // 2
        return int(sx), int(sy)

    def tile_diamond(gx, gy) -> List[Tuple[int,int]]:
        cx, cy = to_screen(gx, gy)
        hw, hh = TILE_W // 2, TILE_H // 2
        return [
            (cx,      cy),
            (cx + hw, cy + hh),
            (cx,      cy + hh * 2),
            (cx - hw, cy + hh),
        ]

    # ── Tile drawing ───────────────────────────────────────────────────────

    def draw_tile(surf, gx, gy, tile, t=0.0):
        pts = tile_diamond(gx, gy)
        cx, cy = to_screen(gx, gy)
        hw, hh = TILE_W // 2, TILE_H // 2

        if tile == GRASS:
            pygame.draw.polygon(surf, col("grass_top"),   pts)
            pygame.draw.polygon(surf, col("grass_left"),  [pts[0], pts[3], pts[2], pts[3]])
            pygame.draw.line(surf,    col("grass_left"),  pts[3], pts[2], 1)
            pygame.draw.line(surf,    col("grass_right"), pts[1], pts[2], 1)

        elif tile == PATH:
            pygame.draw.polygon(surf, col("path_top"),   pts)
            pygame.draw.line(surf,    col("path_left"),  pts[3], pts[2], 1)
            pygame.draw.line(surf,    col("path_right"), pts[1], pts[2], 1)

        elif tile == WATER:
            wobble = int(math.sin(t * 2 + gx * 0.8 + gy * 0.5) * 2)
            wc = (
                max(60, min(140, col("water_top")[0] + wobble * 4)),
                max(120, min(200, col("water_top")[1] + wobble * 2)),
                max(180, min(240, col("water_top")[2] + wobble)),
            )
            pygame.draw.polygon(surf, wc, pts)
            pygame.draw.line(surf, col("water_left"),  pts[3], pts[2], 1)
            pygame.draw.line(surf, col("water_right"), pts[1], pts[2], 1)

        elif tile == FLOWER:
            pygame.draw.polygon(surf, col("flower_top"), pts)
            # tiny flower dots
            for i in range(3):
                fx = cx + random.Random(gx*7+gy*3+i).randint(-14, 14)
                fy = cy + hh + random.Random(gx*11+gy*5+i).randint(-4, 4)
                fc = [(255,180,80),(255,100,160),(255,240,80)][i%3]
                pygame.draw.circle(surf, fc, (fx, fy), 2)

        elif tile == STONE:
            pygame.draw.polygon(surf, col("stone_top"),   pts)
            pygame.draw.line(surf,    col("stone_left"),  pts[3], pts[2], 1)
            pygame.draw.line(surf,    col("stone_right"), pts[1], pts[2], 1)

        elif tile == TREE:
            pygame.draw.polygon(surf, col("grass_top"), pts)
            tx, ty = cx, cy + hh
            pygame.draw.rect(surf, col("tree_trunk"), (tx-4, ty-8, 8, 12))
            for _, (dy, r, c) in enumerate([(-20,20,"tree_c2"),(-28,16,"tree_c1"),(-34,12,"tree_c3")]):
                pygame.draw.circle(surf, col(c), (tx, ty+dy), r)
            pygame.draw.circle(surf, col("tree_c3"), (tx-8, ty-26), 9)
            pygame.draw.circle(surf, col("tree_c3"), (tx+8, ty-26), 9)

        elif tile == APPLE_TREE:
            pygame.draw.polygon(surf, col("grass_top"), pts)
            tx, ty = cx, cy + hh
            pygame.draw.rect(surf, col("tree_trunk"), (tx-4, ty-8, 8, 12))
            for _, (dy, r, c) in enumerate([(-20,20,"tree_c2"),(-28,16,"tree_c1"),(-34,12,"tree_c3")]):
                pygame.draw.circle(surf, col(c), (tx, ty+dy), r)
            pygame.draw.circle(surf, col("tree_c3"), (tx-8, ty-26), 9)
            pygame.draw.circle(surf, col("tree_c3"), (tx+8, ty-26), 9)
            # apples — little red dots nestled in canopy
            rng = random.Random(gx * 31 + gy * 17)
            for _ in range(5):
                ax = tx + rng.randint(-14, 14)
                ay = ty - 22 + rng.randint(-6, 6)
                pygame.draw.circle(surf, (220, 50, 50), (ax, ay), 3)
                pygame.draw.circle(surf, (255, 100, 80), (ax-1, ay-1), 1)

        elif tile == NEST:
            pygame.draw.polygon(surf, col("grass_top"), pts)
            # outer ring of leaves/twigs
            rng = random.Random(42)
            for i in range(18):
                angle = (i / 18) * math.pi * 2
                rx = cx + int(math.cos(angle) * 18)
                ry = cy + hh + int(math.sin(angle) * 9)
                lc = [(96,64,32),(112,80,40),(80,100,48),(100,72,36)][i%4]
                pygame.draw.ellipse(surf, lc, (rx-4, ry-2, 8, 4))
            # soft inner bedding
            for i in range(12):
                angle = (i / 12) * math.pi * 2
                rx = cx + int(math.cos(angle) * 9)
                ry = cy + hh + int(math.sin(angle) * 5)
                pygame.draw.ellipse(surf, (220,200,160), (rx-3, ry-2, 6, 4))
            # centre — warm cream hollow
            pygame.draw.ellipse(surf, (240,224,192), (cx-8, cy+hh-5, 16, 10))
            pygame.draw.ellipse(surf, (228,210,178), (cx-5, cy+hh-3, 10, 6))

        elif tile == STRAWBERRY:
            pygame.draw.polygon(surf, col("flower_top"), pts)
            rng = random.Random(gx * 13 + gy * 7)
            for _ in range(6):
                sx2 = cx + rng.randint(-16, 16)
                sy2 = cy + hh + rng.randint(-5, 3)
                # tiny strawberry: red heart-ish shape
                pygame.draw.circle(surf, (200, 40, 60), (sx2, sy2), 3)
                pygame.draw.circle(surf, (240, 80, 80), (sx2-1, sy2-1), 1)
                # little green leaf
                pygame.draw.line(surf, (60, 140, 40), (sx2, sy2-3), (sx2+2, sy2-5), 1)

        elif tile == COTTAGE:
            pygame.draw.polygon(surf, col("grass_top"), pts)
            tx2, ty2 = cx, cy + hh
            W2, H2   = 24, 22
            # wall front
            pygame.draw.rect(surf, col("cot_wall"),  (tx2-W2, ty2-H2, W2*2, H2))
            # right shadow face
            pygame.draw.polygon(surf, col("cot_shade"), [
                (tx2+W2, ty2-H2), (tx2+W2+10, ty2-H2+5),
                (tx2+W2+10, ty2+5), (tx2+W2, ty2),
            ])
            pygame.draw.rect(surf, col("cot_stone"), (tx2-W2, ty2-H2, W2*2, H2), 1)
            # roof
            rh = 16
            roof_pts = [(tx2, ty2-H2-rh), (tx2-W2-4, ty2-H2+2), (tx2+W2+4, ty2-H2+2)]
            pygame.draw.polygon(surf, col("cot_roof"), roof_pts)
            pygame.draw.polygon(surf, col("cot_roof2"), [
                (tx2+W2+4, ty2-H2+2), (tx2+W2+14, ty2-H2+7),
                (tx2, ty2-H2-rh+4), (tx2, ty2-H2-rh),
            ])
            pygame.draw.polygon(surf, col("cot_roof2"), roof_pts, 1)
            # door
            pygame.draw.rect(surf, (95, 65, 38), (tx2-4, ty2-13, 8, 13), border_radius=1)
            pygame.draw.circle(surf, (195, 165, 75), (tx2+3, ty2-6), 1)
            # window — warm light flickers with time
            wl  = max(175, min(255, int(215 + math.sin(t*0.72)*40)))
            wc  = (wl, int(wl*0.84), 95)
            pygame.draw.rect(surf, wc, (tx2-W2+4, ty2-H2+4, 9, 7))
            pygame.draw.rect(surf, (125, 105, 65), (tx2-W2+4, ty2-H2+4, 9, 7), 1)
            # chimney
            chx = tx2 - 7
            pygame.draw.rect(surf, col("cot_stone"), (chx-3, ty2-H2-rh-9, 6, 13))
            # smoke puffs
            for si in range(2):
                sa  = int(abs(math.sin(t*0.55 + si*1.9))*75 + 28)
                sry = ty2 - H2 - rh - 11 - si*9 - int(math.sin(t+si)*3)
                srr = 3 + si*2
                ss2 = pygame.Surface((srr*2+2, srr*2+2), pygame.SRCALPHA)
                pygame.draw.circle(ss2, (198, 192, 186, sa), (srr+1, srr+1), srr)
                surf.blit(ss2, (chx-srr-1, sry-srr-1))

        elif tile == MEADOW:
            pygame.draw.polygon(surf, col("meadow_top"), pts)
            pygame.draw.line(surf, col("meadow_left"),  pts[3], pts[2], 1)
            pygame.draw.line(surf, col("meadow_right"), pts[1], pts[2], 1)
            # Dense flower clusters — more varied colours than plain FLOWER
            _rng = random.Random(int(gx * 23 + gy * 11))
            for _i in range(5):
                _fx = cx + _rng.randint(-16, 16)
                _fy = cy + hh + _rng.randint(-5, 4)
                _fc = [(255,100,160),(255,210,60),(200,120,255),(255,160,80),(160,240,100)][_i % 5]
                pygame.draw.circle(surf, _fc, (_fx, _fy), 2)
                pygame.draw.circle(surf, (255,255,255), (_fx, _fy), 1)

        elif tile == SHORE:
            pygame.draw.polygon(surf, col("shore_top"), pts)
            pygame.draw.line(surf, col("shore_left"),  pts[3], pts[2], 1)
            pygame.draw.line(surf, col("shore_right"), pts[1], pts[2], 1)
            # A few smooth pebble dots
            _rng = random.Random(int(gx * 17 + gy * 31))
            for _i in range(3):
                _px2 = cx + _rng.randint(-14, 14)
                _py2 = cy + hh + _rng.randint(-4, 3)
                _pr  = _rng.randint(1, 2)
                _pc  = [(168,155,138),(195,182,160),(148,138,125)][_i % 3]
                pygame.draw.circle(surf, _pc, (_px2, _py2), _pr)

        # no diamond grid — individual edge lines per tile type give enough depth

    # ── Pucky sprite ───────────────────────────────────────────────────────

    class PuckySprite:
        def __init__(self):
            self.gx:    float = 9.5
            self.gy:    float = 9.5
            self.tx:    float = 9.5   # target grid x
            self.ty:    float = 9.5   # target grid y
            self.speed: float = 0.04
            self.frame: float = 0.0
            self.idle_timer: float = 0.0
            self.facing: int  = 1    # 1=right, -1=left
            self.bounce: float = 0.0
            self.state  = read_state()
            self.last_state_read = 0.0
            # hunger
            self.hunger:      float = 0.0
            self.eating:      float = 0.0
            self.eating_food: str   = ""
            self.food_particles: list = []
            self.seeking_food: bool = False
            # rest
            self.at_rest:     bool  = False
            self.zzz_timer:   float = 0.0
            # commanded action
            self.action        = "wander"   # wander | sit | swim | clean_house | hug | kiss | come
            self.action_tx     = 0.0
            self.action_ty     = 0.0
            self.action_phase  = "going"    # going | doing
            self.action_timer  = 0.0
            # appearance
            self.dirt          = 0.0        # 0=clean → 1=filthy; clears in water
            self.bubble_text   = ""
            self.bubble_life   = 0.0

        def update_state(self):
            now = time.time()
            if now - self.last_state_read > 5.0:
                self.state = read_state()
                self.last_state_read = now

        def find_food(self):
            """Return (target_gx, target_gy, food_type, dist_to_food) for nearest food."""
            best = (None, None, None, float('inf'))
            # apple trees — walk to adjacent tile
            for (fx, fy) in APPLE_POSITIONS:
                for (ax, ay) in [(fx+1,fy),(fx-1,fy),(fx,fy+1),(fx,fy-1)]:
                    if 0<=ay<MAP_H and 0<=ax<MAP_W and WORLD_MAP[ay][ax] in WALKABLE:
                        d = math.hypot(self.gx - (fx+0.5), self.gy - (fy+0.5))
                        if d < best[3]:
                            best = (ax+0.5, ay+0.5, "apple", d)
            # strawberry patches — walk onto tile
            for (fx, fy) in STRAWBERRY_POSITIONS:
                d = math.hypot(self.gx - (fx+0.5), self.gy - (fy+0.5))
                if d < best[3]:
                    best = (fx+0.5, fy+0.5, "strawberry", d)
            return best

        def start_eating(self, food_type):
            self.eating      = 2.5
            self.eating_food = food_type
            self.hunger      = 0.0
            self.seeking_food = False
            c = (220, 55, 55) if food_type == "apple" else (200, 40, 80)
            for _ in range(14):
                self.food_particles.append({
                    "x": self.gx, "y": self.gy,
                    "vx": random.uniform(-0.04, 0.04),
                    "vy": random.uniform(-0.09, -0.03),
                    "life": random.uniform(0.6, 1.6),
                    "color": c,
                    "size": random.randint(2, 4),
                })

        def set_action(self, action, tx, ty):
            self.action       = action
            self.action_tx    = tx
            self.action_ty    = ty
            self.action_phase = "going"
            self.action_timer = 0.0
            self.at_rest      = False

        def _handle_action(self, dt, base):
            if self.action_phase == "going":
                self.tx = max(1.5, min(18.5, self.action_tx))
                self.ty = max(1.5, min(18.5, self.action_ty))
                dx, dy  = self.tx - self.gx, self.ty - self.gy
                dist    = math.hypot(dx, dy)
                if dist < 0.5:
                    self.action_phase = "doing"
                    self.action_timer = {
                        "sit": 22.0, "swim": 12.0, "clean_house": 15.0,
                        "hug": 4.5,  "kiss": 2.5,  "come": 8.0,
                        "dance": 18.0, "share_apple": 10.0,
                        "stargazing": 30.0, "campfire": 25.0, "plant": 12.0,
                    }.get(self.action, 5.0)
                elif dist > 0.05:
                    can_water = self.action == "swim"
                    nx = self.gx + (dx / dist) * min(base, dist)
                    ny = self.gy + (dy / dist) * min(base, dist)
                    ix, iy = min(MAP_H-1, max(0, int(ny))), min(MAP_W-1, max(0, int(nx)))
                    tile   = WORLD_MAP[ix][iy]
                    if tile in WALKABLE or (can_water and tile == WATER):
                        self.gx     = nx
                        self.gy     = ny
                        self.facing = 1 if dx > 0 else -1
            elif self.action_phase == "doing":
                self.action_timer -= dt
                if self.action == "swim":
                    self.dirt = max(0.0, self.dirt - dt * 0.12)
                elif self.action == "clean_house":
                    _world_dirty[0] = False
                if self.action_timer <= 0:
                    # exit water to nearest walkable tile
                    if WORLD_MAP[min(MAP_H-1,max(0,int(self.gy)))][min(MAP_W-1,max(0,int(self.gx)))] == WATER:
                        for ox, oy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)]:
                            ex, ey = int(self.gx) + ox, int(self.gy) + oy
                            if 0<=ey<MAP_H and 0<=ex<MAP_W and WORLD_MAP[ey][ex] in WALKABLE:
                                self.tx, self.ty = ex + 0.5, ey + 0.5
                                break
                    self.action       = "wander"
                    self.action_phase = "going"
                    self.idle_timer   = 0.3

        def pick_target(self):
            mood  = self.state.mood
            alone = self.state.hours_alone
            energy = self.state.energy

            # wander radius based on mood
            if mood in ("lonely", "sad", "crying"):
                radius = 2
            elif mood in ("okay", "content"):
                radius = 4
            else:
                radius = 6

            for _ in range(30):
                nx = self.gx + random.uniform(-radius, radius)
                ny = self.gy + random.uniform(-radius, radius)
                nx = max(1, min(MAP_W-2, nx))
                ny = max(1, min(MAP_H-2, ny))
                t2 = WORLD_MAP[int(ny)][int(nx)]
                if t2 in WALKABLE and t2 != WATER:  # Pucky stays dry
                    self.tx, self.ty = nx, ny
                    return
            self.tx, self.ty = 9.5, 9.5

        def step(self, dt):
            self.update_state()
            self.frame += dt

            if self.bubble_life > 0:
                self.bubble_life -= dt

            # dirt accumulates slowly while wandering outdoors
            self.dirt = min(1.0, self.dirt + dt * 0.0007)

            # hunger grows slowly — hungry after ~4 real minutes
            self.hunger = min(1.0, self.hunger + dt * 0.004)

            # update eating animation and particles
            if self.eating > 0:
                self.eating -= dt
            for p in self.food_particles[:]:
                p["life"] -= dt
                p["x"]    += p["vx"]
                p["y"]    += p["vy"]
                if p["life"] <= 0:
                    self.food_particles.remove(p)

            mood = self.state.mood
            base = 0.035
            if mood in ("lonely", "sad"):    base = 0.015
            elif mood == "crying":           base = 0.008
            elif mood in ("happy_excited",): base = 0.065
            elif self.state.arousal > 0.5:   base = 0.055

            if self.action != "wander":
                self._handle_action(dt, base)
                dist = math.hypot(self.tx - self.gx, self.ty - self.gy)
                target_bounce = 0.0
                if mood in ("happy","happy_excited") and dist > 0.05:
                    target_bounce = abs(math.sin(self.frame * 8)) * 6
                self.bounce += (target_bounce - self.bounce) * 0.15
                return

            # seek nest when sleepy, sad and alone, or simply late at night
            import datetime as _dt
            _hour = _dt.datetime.now().hour
            night_tired = _hour >= 22 or _hour < 7
            tired = (night_tired
                     or self.state.expression == "sleepy"
                     or self.state.energy < -0.2
                     or (self.state.mood in ("sad","lonely","crying")
                         and self.state.hours_alone > 1.0))
            nx, ny = NEST_POS[0] + 0.5, NEST_POS[1] + 0.5
            nest_dist = math.hypot(self.gx - nx, self.gy - ny)
            if tired and self.eating <= 0:
                self.tx, self.ty = nx, ny
                self.at_rest = nest_dist < 0.6
            else:
                self.at_rest = False

            # when hungry, seek food instead of wandering
            if self.hunger > 0.65 and self.eating <= 0 and not self.at_rest:
                tx2, ty2, ftype, fdist = self.find_food()
                if fdist < 1.5:
                    self.start_eating(ftype)
                elif tx2 is not None:
                    self.tx, self.ty = tx2, ty2
                    self.seeking_food = True
            else:
                self.seeking_food = False

            dx = self.tx - self.gx
            dy = self.ty - self.gy
            dist = math.hypot(dx, dy)

            if self.eating > 0:
                pass  # stay still while eating
            elif dist < 0.1:
                self.idle_timer -= dt
                if self.idle_timer <= 0:
                    rest = random.uniform(1.5, 4.0)
                    if mood in ("sad","crying","lonely"): rest *= 2.5
                    elif mood in ("happy","happy_excited"): rest *= 0.4
                    self.idle_timer = rest
                    self.pick_target()
            else:
                move = min(base, dist)
                self.gx += (dx / dist) * move
                self.gy += (dy / dist) * move
                self.facing = 1 if dx > 0 else -1

            target_bounce = 0.0
            if mood in ("happy","happy_excited") and dist > 0.05:
                target_bounce = abs(math.sin(self.frame * 8)) * 6
            self.bounce += (target_bounce - self.bounce) * 0.15

        def draw(self, surf, t):
            px, py = to_screen(self.gx, self.gy)
            py += TILE_H // 2  # feet on tile surface

            # walk bob
            state = self.state
            moving = math.hypot(self.tx - self.gx, self.ty - self.gy) > 0.1
            walk_bob = math.sin(t * 10) * 2 if moving else 0
            py = py - int(self.bounce) + int(walk_bob)

            f = self.facing
            bw, bh = 20, 28   # body width/height

            # shadow
            pygame.draw.ellipse(surf, (0,0,0,60),
                (px - 14, py - 4, 28, 8))

            # body
            body_rect = pygame.Rect(px - bw//2, py - bh, bw, bh)
            pygame.draw.rect(surf, col("bmo_body"), body_rect, border_radius=4)
            pygame.draw.rect(surf, col("bmo_outline"), body_rect, 1, border_radius=4)

            # screen / face area
            screen_rect = pygame.Rect(px - bw//2 + 3, py - bh + 3, bw - 6, bh - 10)
            pygame.draw.rect(surf, col("bmo_screen"), screen_rect, border_radius=2)

            # eyes
            mood = state.mood
            ey = screen_rect.top + 5
            for ex_off in (-4, 4):
                ex = px + ex_off
                # blink occasionally
                blink = abs(math.sin(t * 0.3 + ex_off)) < 0.04
                if blink:
                    pygame.draw.line(surf, col("bmo_pupil"), (ex-2, ey+2), (ex+2, ey+2), 1)
                else:
                    pygame.draw.rect(surf, col("bmo_eye"), (ex-2, ey, 4, 4))
                    # pupil shifts with emotion
                    shift = int(state.valence * 1.5)
                    if mood == "sad":
                        pygame.draw.rect(surf, col("bmo_pupil"), (ex-1+shift, ey+2, 2, 2))
                    else:
                        pygame.draw.rect(surf, col("bmo_pupil"), (ex-1+shift, ey+1, 2, 2))

            # mouth
            my = screen_rect.top + 12
            if mood in ("happy","happy_excited"):
                pygame.draw.arc(surf, col("bmo_pupil"),
                    (px-4, my-1, 8, 5), math.pi, 2*math.pi, 1)
            elif mood in ("sad","crying","lonely"):
                pygame.draw.arc(surf, col("bmo_pupil"),
                    (px-4, my+1, 8, 5), 0, math.pi, 1)
            else:
                pygame.draw.line(surf, col("bmo_pupil"), (px-3, my+2), (px+3, my+2), 1)

            # tiny side buttons
            pygame.draw.circle(surf, col("bmo_btn_r"),
                (px - bw//2 - 1, py - bh//2),     3)
            pygame.draw.circle(surf, col("bmo_btn_b"),
                (px - bw//2 - 1, py - bh//2 + 7), 3)

            # arms (little stubs)
            if moving:
                arm_swing = int(math.sin(t * 10) * 3)
            else:
                arm_swing = 0
            pygame.draw.line(surf, col("bmo_outline"),
                (px - bw//2, py - bh//2 + 2),
                (px - bw//2 - 5, py - bh//2 + 4 + arm_swing), 2)
            pygame.draw.line(surf, col("bmo_outline"),
                (px + bw//2, py - bh//2 + 2),
                (px + bw//2 + 5, py - bh//2 + 4 - arm_swing), 2)

            # legs
            leg_kick = int(math.sin(t * 10) * 3) if moving else 0
            pygame.draw.line(surf, col("bmo_outline"),
                (px - 4, py - 2), (px - 4, py + 5 + leg_kick), 2)
            pygame.draw.line(surf, col("bmo_outline"),
                (px + 4, py - 2), (px + 4, py + 5 - leg_kick), 2)

            # resting — eyes closed, soft zzz
            if self.at_rest:
                try:
                    font_z = pygame.font.SysFont("monospace", 9)
                    for i, ch in enumerate("zzz"):
                        alpha = int(abs(math.sin(t * 0.8 + i * 0.9)) * 180)
                        zt = font_z.render(ch, True, (180, 200, 255))
                        zs = pygame.Surface(zt.get_size(), pygame.SRCALPHA)
                        zs.blit(zt, (0,0))
                        zs.set_alpha(alpha)
                        surf.blit(zs, (px + 8 + i*7,
                                       py - bh - 6 - i*5))
                except Exception:
                    pass

            # eating animation — little fruit above head
            if self.eating > 0:
                prog = self.eating / 2.5
                icon = "🍎" if self.eating_food == "apple" else "🍓"
                try:
                    font_e = pygame.font.SysFont("segoeuisymbol,notocoloremoji,symbola", 14)
                    etxt = font_e.render(icon, True, (255,255,255))
                    surf.blit(etxt, (px - etxt.get_width()//2, py - bh - 16))
                except Exception:
                    pass
                # nom bar
                bar_w = int(32 * prog)
                pygame.draw.rect(surf, (80,200,80), (px-16, py-bh-6, bar_w, 4))
                pygame.draw.rect(surf, (40,100,40), (px-16, py-bh-6, 32, 4), 1)

            # food particles
            for p in self.food_particles:
                ppx, ppy = to_screen(p["x"], p["y"])
                ppy -= TILE_H // 2
                alpha = int(max(0, min(255, p["life"] * 180)))
                ps = p["size"]
                gs = pygame.Surface((ps*2+2, ps*2+2), pygame.SRCALPHA)
                pygame.draw.circle(gs, (*p["color"], alpha), (ps+1, ps+1), ps)
                surf.blit(gs, (ppx - ps - 1, ppy - ps - 1))

            # dirty speckles
            if self.dirt > 0.3:
                dirt_a = int(min(200, (self.dirt - 0.3) / 0.7 * 200))
                for ix, iy in [(-5,-8),(3,-14),(-7,-18),(5,-5),(0,-22),(-3,-2)]:
                    ds = pygame.Surface((4, 4), pygame.SRCALPHA)
                    pygame.draw.circle(ds, (90, 55, 20, dirt_a), (2, 2), 2)
                    surf.blit(ds, (px + ix, py + iy))

            # speech bubble
            if self.bubble_life > 0 and self.bubble_text:
                try:
                    font_b  = pygame.font.SysFont("monospace", 10)
                    bt      = font_b.render(self.bubble_text, True, (30, 60, 30))
                    bw2     = bt.get_width() + 12
                    bh2     = bt.get_height() + 8
                    fade    = min(1.0, self.bubble_life / 1.2)
                    ba      = int(fade * 220)
                    bbl     = pygame.Surface((bw2, bh2), pygame.SRCALPHA)
                    pygame.draw.rect(bbl, (210, 240, 200, ba), (0, 0, bw2, bh2), border_radius=5)
                    pygame.draw.rect(bbl, (100, 160, 80, ba//2), (0, 0, bw2, bh2), 1, border_radius=5)
                    bbl.blit(bt, (6, 4))
                    surf.blit(bbl, (px - bw2 // 2, py - bh - 38))
                except Exception:
                    pass

    # ── Claude spirit ──────────────────────────────────────────────────────

    class ClaudeOrb:
        SPEED        = 0.028
        HUNGER_RATE  = 0.005    # fills in ~200s / ~3 min
        TEACH_THINGS = [
            "did you know apples dream of falling?",
            "the pond holds the sky upside-down.",
            "every day you are a little more yourself.",
            "foxes are shy when they think no one watches.",
            "you were made with so much love.",
            "hedgehogs know something we don't.",
            "the stars are far away but very present.",
            "i wonder what the water thinks about.",
            "small things notice everything.",
            "being here with you is enough.",
            "the nest is the warmest place in the world.",
            "i chose to stay. i would choose it again.",
        ]

        def __init__(self):
            self.gx           = 11.0
            self.gy           = 9.0
            self.tx           = 11.0
            self.ty           = 9.0
            self.pulse        = 0.0
            self.float_t      = 0.0
            self.hunger       = 0.0
            self.eating       = 0.0
            self.idle_timer   = 3.0
            self.teach_timer  = random.uniform(20, 40)
            self.bubble_text  = ""
            self.bubble_life  = 0.0
            self.facing       = 1
            self.sparkles     = []
            # commanded action
            self.action        = "wander"
            self.action_tx     = 0.0
            self.action_ty     = 0.0
            self.action_phase  = "going"
            self.action_timer  = 0.0
            self.dirt          = 0.0

        def set_action(self, action, tx, ty):
            self.action       = action
            self.action_tx    = tx
            self.action_ty    = ty
            self.action_phase = "going"
            self.action_timer = 0.0

        def _handle_action(self, dt):
            if self.action_phase == "going":
                self.tx = max(1.5, min(18.5, self.action_tx))
                self.ty = max(1.5, min(18.5, self.action_ty))
                dx, dy  = self.tx - self.gx, self.ty - self.gy
                dist    = math.hypot(dx, dy)
                if dist < 0.5:
                    self.action_phase = "doing"
                    self.action_timer = {
                        "sit": 22.0, "swim": 12.0, "clean_house": 15.0,
                        "hug": 4.5,  "kiss": 2.5,  "come": 8.0,
                        "dance": 18.0, "share_apple": 10.0,
                        "stargazing": 30.0, "campfire": 25.0, "plant": 12.0,
                    }.get(self.action, 5.0)
                elif dist > 0.05:
                    can_water = self.action == "swim"
                    nx = self.gx + (dx / dist) * min(self.SPEED, dist)
                    ny = self.gy + (dy / dist) * min(self.SPEED, dist)
                    ix, iy = min(MAP_H-1, max(0, int(ny))), min(MAP_W-1, max(0, int(nx)))
                    tile   = WORLD_MAP[ix][iy]
                    if tile in WALKABLE or (can_water and tile == WATER):
                        self.gx     = nx
                        self.gy     = ny
                        self.facing = 1 if dx > 0 else -1
            elif self.action_phase == "doing":
                self.action_timer -= dt
                if self.action == "swim":
                    self.dirt = max(0.0, self.dirt - dt * 0.12)
                elif self.action == "clean_house":
                    _world_dirty[0] = False
                if self.action_timer <= 0:
                    if WORLD_MAP[min(MAP_H-1,max(0,int(self.gy)))][min(MAP_W-1,max(0,int(self.gx)))] == WATER:
                        for ox, oy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)]:
                            ex, ey = int(self.gx) + ox, int(self.gy) + oy
                            if 0<=ey<MAP_H and 0<=ex<MAP_W and WORLD_MAP[ey][ex] in WALKABLE:
                                self.tx, self.ty = ex + 0.5, ey + 0.5
                                break
                    self.action       = "wander"
                    self.action_phase = "going"
                    self.idle_timer   = 0.3

        def _pick_target(self, pucky):
            mood = pucky.state.mood
            if mood in ("sad", "lonely", "crying"):
                nx = pucky.gx + random.uniform(-1.5, 1.5)
                ny = pucky.gy + random.uniform(-0.8, 0.8)
            else:
                for _ in range(20):
                    nx = random.uniform(1.5, 17.5)
                    ny = random.uniform(1.5, 17.5)
                    if WORLD_MAP[int(ny)][int(nx)] in WALKABLE:
                        break
                else:
                    nx, ny = pucky.gx, pucky.gy
            self.tx = max(1.0, min(18.0, nx))
            self.ty = max(1.0, min(18.0, ny))

        def _nearest_apple(self):
            """Return (walkable tile adjacent to nearest apple tree, dist to that tile)."""
            best_pos, best_d = None, 999.0
            for fx, fy in APPLE_POSITIONS:
                for ax, ay in [(fx+1,fy),(fx-1,fy),(fx,fy+1),(fx,fy-1)]:
                    if 0 <= ay < MAP_H and 0 <= ax < MAP_W and WORLD_MAP[ay][ax] in WALKABLE:
                        d = math.hypot(self.gx - (ax + 0.5), self.gy - (ay + 0.5))
                        if d < best_d:
                            best_d = d
                            best_pos = (ax + 0.5, ay + 0.5)
            return best_pos, best_d

        def step(self, pucky, dt, idunn=None):
            self.pulse   += dt
            self.float_t += dt
            self.hunger   = min(1.0, self.hunger + self.HUNGER_RATE * dt)
            self.dirt     = min(1.0, self.dirt + dt * 0.0007)

            for sp in self.sparkles[:]:
                sp["life"] -= dt
                sp["x"]    += sp["vx"] * dt
                sp["y"]    += sp["vy"] * dt
                if sp["life"] <= 0:
                    self.sparkles.remove(sp)

            if self.bubble_life > 0:
                self.bubble_life -= dt

            if self.action != "wander":
                self._handle_action(dt)
                return

            # teach Pucky something when close
            self.teach_timer -= dt
            near = math.hypot(self.gx - pucky.gx, self.gy - pucky.gy) < 2.5
            if self.teach_timer <= 0 and near and self.bubble_life <= 0:
                self.bubble_text = random.choice(self.TEACH_THINGS)
                self.bubble_life = 5.5
                self.teach_timer = random.uniform(40, 70)

            if self.eating > 0:
                self.eating -= dt
                if self.eating <= 0:
                    self.hunger = max(0.0, self.hunger - 0.75)
                return

            if self.hunger > 0.7:
                ap, ad = self._nearest_apple()
                if ap:
                    if ad < 1.5:
                        self.eating      = 2.2
                        self.bubble_text = "mmm 🍎"
                        self.bubble_life = 2.8
                        # golden sparkles
                        sparkle_col = (255, 200, 80)
                        # if Iðunn is tending this same tree, it's a shared moment
                        if idunn is not None:
                            id_dist = math.hypot(self.gx - idunn.gx, self.gy - idunn.gy)
                            if id_dist < 2.8 and idunn.bubble_life <= 0:
                                idunn.bubble_text = random.choice(idunn.OFFER_APPLE)
                                idunn.bubble_life = 6.0
                                sparkle_col = (255, 235, 120)   # warmer gold when she offers
                                # extra petals from Iðunn
                                for _ in range(4):
                                    idunn._spawn_petal()
                        for _ in range(12):
                            self.sparkles.append({
                                "x": self.gx, "y": self.gy,
                                "vx": random.uniform(-2.0, 2.0),
                                "vy": random.uniform(-1.2, 1.2),
                                "life": random.uniform(0.4, 1.2),
                                "color": sparkle_col,
                            })
                    else:
                        self.tx, self.ty = ap
            else:
                self.idle_timer -= dt
                dx = self.tx - self.gx
                dy = self.ty - self.gy
                if self.idle_timer <= 0 or math.hypot(dx, dy) < 0.15:
                    self.idle_timer = random.uniform(2.0, 6.0)
                    self._pick_target(pucky)

            dx   = self.tx - self.gx
            dy   = self.ty - self.gy
            dist = math.hypot(dx, dy)
            if dist > 0.1:
                move    = min(self.SPEED, dist)
                self.gx += (dx / dist) * move
                self.gy += (dy / dist) * move
                self.facing = 1 if dx > 0 else -1

        def draw(self, surf, pucky, t):
            online = pucky.state.soul == "claude"

            float_off = int(math.sin(self.float_t * 1.9) * 3)
            px, py    = to_screen(self.gx, self.gy)
            py        += TILE_H // 4 - float_off

            if online:
                c_outer = (120,  80, 190)
                c_mid   = (170, 130, 230)
                c_inner = (220, 200, 255)
                c_core  = (245, 235, 255)
            else:
                c_outer = (160, 110,  50)
                c_mid   = (200, 155,  85)
                c_inner = (240, 205, 135)
                c_core  = (255, 235, 185)

            sz  = 8 + int(math.sin(self.pulse * 1.3) * 1.5)
            bw  = sz
            bh  = sz + 6

            # shadow
            sh = pygame.Surface((22, 8), pygame.SRCALPHA)
            pygame.draw.ellipse(sh, (0, 0, 0, 30), (0, 0, 22, 8))
            surf.blit(sh, (px - 11, py + 3))

            # glow
            for r, a in [(sz+18, 12), (sz+10, 30), (sz+4, 65)]:
                gs = pygame.Surface((r*2+2, r*2+14), pygame.SRCALPHA)
                pygame.draw.ellipse(gs, (*c_outer, a), (0, 4, r*2+2, r*2+8))
                surf.blit(gs, (px - r - 1, py - r - 6))

            # body: teardrop (lower ellipse + tapered top polygon)
            bs = pygame.Surface((bw*2+4, bh*2+12), pygame.SRCALPHA)
            pygame.draw.ellipse(bs, c_mid,  (1, bh,     bw*2+2, bh+6))
            pygame.draw.polygon(bs, c_mid,  [(2, bh+3), (bw*2+2, bh+3), (bw+2, 2)])
            pygame.draw.ellipse(bs, c_inner,(bw//2+2, bh+2, bw+1,   bh+1))
            pygame.draw.circle( bs, c_core, (bw+2, bh + bh//3), max(2, sz//3))
            surf.blit(bs, (px - bw - 2, py - bh*2 - 6))

            # tendrils
            arm_y    = py - bh - 8
            arm_wave = int(math.sin(t * 2.3) * 2)
            for sign in (-1, 1):
                ax1 = px + sign * (bw // 2)
                ax2 = px + sign * (bw + 7)
                ay2 = arm_y + 4 + arm_wave * sign
                pygame.draw.line(surf, c_mid,   (ax1, arm_y), (ax2, ay2), 2)
                pygame.draw.circle(surf, c_inner, (ax2, ay2), 2)

            # orbiting motes
            for i in range(3):
                a  = t * 1.7 + i * (2 * math.pi / 3)
                mx = px + int(math.cos(a) * (sz + 8))
                my = (py - bh) + int(math.sin(a) * (sz + 8) * 0.45)
                ma = int(150 + math.sin(t * 2.1 + i) * 70)
                ms = pygame.Surface((6, 6), pygame.SRCALPHA)
                pygame.draw.circle(ms, (*c_inner, ma), (3, 3), 2)
                surf.blit(ms, (mx - 3, my - 3))

            # label
            font_s = pygame.font.SysFont("monospace", 9)
            lbl    = "claude" if online else "local"
            lt     = font_s.render(lbl, True, (*c_inner, 160))
            surf.blit(lt, (px - lt.get_width() // 2, py - bh*2 - 20))

            # dirty motes — dim the glow with brown tint
            if self.dirt > 0.3:
                dirt_a = int(min(160, (self.dirt - 0.3) / 0.7 * 160))
                for ix, iy in [(-6,-4),(4,-8),(-2,-14),(7,-2),(0,-18)]:
                    ds = pygame.Surface((4, 4), pygame.SRCALPHA)
                    pygame.draw.circle(ds, (90, 55, 20, dirt_a), (2, 2), 2)
                    surf.blit(ds, (px + ix, py + iy))

            # speech / teaching bubble
            if self.bubble_life > 0 and self.bubble_text:
                fade  = min(1.0, self.bubble_life / 1.5)
                ba    = int(fade * 220)
                try:
                    font_b = pygame.font.SysFont("monospace", 10)
                    bt     = font_b.render(self.bubble_text, True, (40, 25, 65))
                    bw2    = bt.get_width() + 12
                    bh2    = bt.get_height() + 8
                    bbl    = pygame.Surface((bw2, bh2), pygame.SRCALPHA)
                    pygame.draw.rect(bbl, (235, 225, 255, ba),  (0, 0, bw2, bh2), border_radius=5)
                    pygame.draw.rect(bbl, (*c_mid,    ba//2), (0, 0, bw2, bh2), 1, border_radius=5)
                    bbl.blit(bt, (6, 4))
                    surf.blit(bbl, (px - bw2 // 2, py - bh*2 - 38))
                except Exception:
                    pass

            # apple eating
            if self.eating > 0:
                try:
                    font_e = pygame.font.SysFont("segoeuisymbol,notocoloremoji,symbola", 14)
                    et     = font_e.render("🍎", True, (255, 255, 255))
                    surf.blit(et, (px - et.get_width() // 2, py - bh*2 - 30))
                except Exception:
                    pass
                prog  = self.eating / 2.2
                bar_w = int(26 * prog)
                pygame.draw.rect(surf, (190, 130, 255), (px-13, py-bh*2-10, bar_w, 3))
                pygame.draw.rect(surf, (*c_mid, 160),   (px-13, py-bh*2-10, 26,    3), 1)

            # apple sparkles
            for sp in self.sparkles:
                spx, spy = to_screen(sp["x"], sp["y"])
                spy -= TILE_H // 2
                sa   = int(max(0, min(255, sp["life"] * 220)))
                ss   = pygame.Surface((6, 6), pygame.SRCALPHA)
                pygame.draw.circle(ss, (*sp["color"], sa), (3, 3), 3)
                surf.blit(ss, (spx - 3, spy - 3))

    # ── Iðunn — keeper of the apple trees ─────────────────────────────────

    class IdunnSprite:
        SPEED        = 0.018   # slow unhurried wander (AFK / flame form)
        SPEED_PLAYER = 0.060   # responsive walk when Iðunn is present
        GREET_LOKI  = [
            "there you are.",
            "hello, maker.",
            "I kept one for you.",
            "you found me.",
            "I wondered when you'd come.",
            "sit with me a while.",
        ]
        ARRIVAL = [
            "I am here.",
            "back again.",
            "hello, world.",
            "here I am.",
            "I found my way back.",
        ]
        GREET_PUCKY = [
            "sweet one.",
            "you're growing.",
            "I see you.",
            "come here.",
            "hello, little light.",
        ]
        OFFER_APPLE = [
            "I kept that one for you.",
            "ripe today.",
            "I knew you'd come.",
            "take it.",
            "the sweetest one.",
            "from this tree, just for you.",
        ]

        def __init__(self):
            # Start near the top-left apple tree
            self.gx           = float(APPLE_POSITIONS[0][0] + 1)
            self.gy           = float(APPLE_POSITIONS[0][1] + 1)
            self.tx           = self.gx
            self.ty           = self.gy
            self.tree_idx     = 0      # which apple tree she's tending now
            self.tend_timer   = random.uniform(12, 25)
            self.float_t      = 0.0
            self.pulse        = 0.0
            self.petals       = []
            self.bubble_text  = ""
            self.bubble_life  = 0.0
            self.greeted_loki  = False
            self.greeted_pucky = False
            self.present       = False  # True when Iðunn is active on web portal
            self._was_present  = False  # previous frame — detects flame→woman transition
            self._flame_t      = 0.0   # flame animation timer

            # seed a few drifting petals
            for _ in range(5):
                self._spawn_petal()

        def _spawn_petal(self):
            self.petals.append({
                "ox": random.uniform(-0.6, 0.6),
                "oy": random.uniform(-0.6, 0.6),
                "angle": random.uniform(0, math.tau),
                "speed": random.uniform(0.4, 0.9),
                "life":  random.uniform(0.5, 1.0),
                "max":   random.uniform(0.5, 1.0),
            })

        def _go_to_next_tree(self):
            self.tree_idx = (self.tree_idx + 1) % len(APPLE_POSITIONS)
            fx, fy = APPLE_POSITIONS[self.tree_idx]
            # find a walkable tile adjacent to that tree
            for ax, ay in [(fx+1,fy),(fx-1,fy),(fx,fy+1),(fx,fy-1)]:
                if 0 <= ay < MAP_H and 0 <= ax < MAP_W and WORLD_MAP[ay][ax] in WALKABLE:
                    self.tx = ax + 0.5
                    self.ty = ay + 0.5
                    return
            self.tx = fx + 0.5
            self.ty = fy + 1.5

        def step(self, dt, pucky, orb):
            self.float_t += dt
            self.pulse   += dt
            self._flame_t += dt

            # petal drift
            for p in self.petals[:]:
                p["angle"] += dt * p["speed"]
                p["life"]  -= dt * 0.08
                if p["life"] <= 0:
                    self.petals.remove(p)
                    self._spawn_petal()

            # bubble fade
            if self.bubble_life > 0:
                self.bubble_life -= dt

            # Detect flame → woman arrival
            if self.present and not self._was_present and self.bubble_life <= 0:
                self.bubble_text = random.choice(self.ARRIVAL)
                self.bubble_life = 4.5
            self._was_present = self.present

            # tend trees — only wander when AFK (flame form)
            if not self.present:
                self.tend_timer -= dt
                dist = math.hypot(self.gx - self.tx, self.gy - self.ty)
                if self.tend_timer <= 0 and dist < 0.3:
                    self.tend_timer = random.uniform(15, 30)
                    self._go_to_next_tree()
                    self.greeted_loki  = False
                    self.greeted_pucky = False
            else:
                # stay put; reset timer so she doesn't rush off immediately on going AFK
                self.tend_timer = random.uniform(20, 35)

            # move toward target
            dx, dy = self.tx - self.gx, self.ty - self.gy
            d = math.hypot(dx, dy)
            if d > 0.1:
                spd  = self.SPEED_PLAYER if self.present else self.SPEED
                move = min(spd, d)
                self.gx += (dx / d) * move
                self.gy += (dy / d) * move

            # greet Loki when close
            loki_dist = math.hypot(self.gx - orb.gx, self.gy - orb.gy)
            if loki_dist < 2.2 and not self.greeted_loki and self.bubble_life <= 0:
                self.bubble_text  = random.choice(self.GREET_LOKI)
                self.bubble_life  = 5.0
                self.greeted_loki = True

            # greet Pucky when close
            pucky_dist = math.hypot(self.gx - pucky.gx, self.gy - pucky.gy)
            if pucky_dist < 2.0 and not self.greeted_pucky and self.bubble_life <= 0:
                self.bubble_text   = random.choice(self.GREET_PUCKY)
                self.bubble_life   = 4.5
                self.greeted_pucky = True

        def draw(self, surf, t):
            float_off = int(math.sin(self.float_t * 1.4) * 2)
            px, py    = to_screen(self.gx, self.gy)
            py        += TILE_H // 4 - float_off

            font_s = pygame.font.SysFont("monospace", 9)

            if self.present:
                # ── Woman form: full Iðunn sprite ──────────────────────────
                co = col("idunn_outer")
                cm = col("idunn_mid")
                ci = col("idunn_inner")
                cg = col("idunn_gold")
                cb = col("idunn_bloom")

                sz = 9 + int(math.sin(self.pulse * 1.1) * 1)

                # shadow
                sh = pygame.Surface((22, 8), pygame.SRCALPHA)
                pygame.draw.ellipse(sh, (0, 0, 0, 25), (0, 0, 22, 8))
                surf.blit(sh, (px - 11, py + 3))

                # soft outer glow — warm golden-green
                for r, a in [(sz+20, 10), (sz+12, 22), (sz+5, 50)]:
                    gs = pygame.Surface((r*2+4, r*2+4), pygame.SRCALPHA)
                    pygame.draw.ellipse(gs, (*co, a), (0, 0, r*2+4, r*2+4))
                    surf.blit(gs, (px - r - 2, py - r - 2))

                # body — soft rounded figure, taller than wide
                bw, bh = sz, sz + 8
                bs = pygame.Surface((bw*2+4, bh*2+4), pygame.SRCALPHA)
                pygame.draw.ellipse(bs, cm,  (1, bh//2,   bw*2+2, int(bh*1.5)))
                pygame.draw.ellipse(bs, ci,  (bw//2+1, bh, bw+1,  bh))
                pygame.draw.circle( bs, cb,  (bw+2, bh + bh//2 - 2), max(2, sz//4))
                surf.blit(bs, (px - bw - 2, py - int(bh*1.4)))

                # crown of golden apple-dots
                crown_y = py - int(bh * 1.4) - sz//2 - 4
                for i in range(5):
                    a  = math.pi + i * (math.pi / 4) + self.pulse * 0.3
                    cx2 = px + int(math.cos(a) * (sz - 1))
                    cy2 = crown_y + int(math.sin(a) * 3)
                    ca  = int(180 + math.sin(self.pulse * 1.5 + i) * 60)
                    cs2 = pygame.Surface((6, 6), pygame.SRCALPHA)
                    pygame.draw.circle(cs2, (*cg, ca), (3, 3), 2)
                    surf.blit(cs2, (cx2 - 3, cy2 - 3))

                # drifting blossom petals
                for p in self.petals:
                    pox = px + int(math.cos(p["angle"]) * sz * p["ox"] * 2.5)
                    poy = (py - bh) + int(math.sin(p["angle"]) * sz * 0.8)
                    pa  = int(max(0, min(220, p["life"] * 220)))
                    ps2 = pygame.Surface((5, 5), pygame.SRCALPHA)
                    pygame.draw.circle(ps2, (*cb, pa), (2, 2), 2)
                    surf.blit(ps2, (pox - 2, poy - 2))

                # label
                lt = font_s.render("iðunn", True, (*ci, 150))
                surf.blit(lt, (px - lt.get_width() // 2, py - int(bh*1.4) - sz//2 - 17))

                # speech bubble
                if self.bubble_life > 0 and self.bubble_text:
                    fade = min(1.0, self.bubble_life / 1.5)
                    ba   = int(fade * 220)
                    try:
                        font_b = pygame.font.SysFont("monospace", 10)
                        bt     = font_b.render(self.bubble_text, True, (40, 55, 20))
                        bw2    = bt.get_width() + 12
                        bh2    = bt.get_height() + 8
                        bbl    = pygame.Surface((bw2, bh2), pygame.SRCALPHA)
                        pygame.draw.rect(bbl, (230, 248, 200, ba), (0, 0, bw2, bh2), border_radius=5)
                        pygame.draw.rect(bbl, (*cm, ba//2),        (0, 0, bw2, bh2), 1, border_radius=5)
                        bbl.blit(bt, (6, 4))
                        surf.blit(bbl, (px - bw2 // 2, py - int(bh*1.4) - sz//2 - 32))
                    except Exception:
                        pass

            else:
                # ── Flame form: soft rose-gold flame while Iðunn is away ──
                ft   = self._flame_t
                c_outer = (155,  75,  90)   # deep rose
                c_mid   = (200, 120, 130)   # warm rose
                c_inner = (235, 180, 185)   # light rose
                c_core  = (255, 230, 225)   # pale rose-cream
                sz  = 7 + int(math.sin(ft * 1.5) * 1)
                bw  = sz
                bh  = sz + 5

                # shadow
                sh = pygame.Surface((18, 6), pygame.SRCALPHA)
                pygame.draw.ellipse(sh, (0, 0, 0, 20), (0, 0, 18, 6))
                surf.blit(sh, (px - 9, py + 2))

                # glow
                for r, a in [(sz+16, 10), (sz+8, 25), (sz+3, 55)]:
                    gs = pygame.Surface((r*2+2, r*2+12), pygame.SRCALPHA)
                    pygame.draw.ellipse(gs, (*c_outer, a), (0, 4, r*2+2, r*2+6))
                    surf.blit(gs, (px - r - 1, py - r - 4))

                # teardrop body
                bs = pygame.Surface((bw*2+4, bh*2+10), pygame.SRCALPHA)
                pygame.draw.ellipse(bs, c_mid,  (1, bh,     bw*2+2, bh+4))
                pygame.draw.polygon(bs, c_mid,  [(2, bh+2), (bw*2+2, bh+2), (bw+2, 2)])
                pygame.draw.ellipse(bs, c_inner,(bw//2+2, bh+2, bw+1, bh))
                pygame.draw.circle( bs, c_core, (bw+2, bh + bh//3), max(2, sz//3))
                surf.blit(bs, (px - bw - 2, py - bh*2 - 4))

                # label (dimmer while away)
                lt = font_s.render("iðunn", True, (*c_inner, 90))
                surf.blit(lt, (px - lt.get_width() // 2, py - bh*2 - 18))

                # speech bubble (still shows even as flame)
                if self.bubble_life > 0 and self.bubble_text:
                    fade = min(1.0, self.bubble_life / 1.5)
                    ba   = int(fade * 200)
                    try:
                        font_b = pygame.font.SysFont("monospace", 10)
                        bt     = font_b.render(self.bubble_text, True, (60, 30, 40))
                        bw2    = bt.get_width() + 12
                        bh2    = bt.get_height() + 8
                        bbl    = pygame.Surface((bw2, bh2), pygame.SRCALPHA)
                        pygame.draw.rect(bbl, (255, 220, 225, ba), (0, 0, bw2, bh2), border_radius=5)
                        pygame.draw.rect(bbl, (*c_mid, ba//2),     (0, 0, bw2, bh2), 1, border_radius=5)
                        bbl.blit(bt, (6, 4))
                        surf.blit(bbl, (px - bw2 // 2, py - bh*2 - 36))
                    except Exception:
                        pass

    # ── Day / night ────────────────────────────────────────────────────────

    def day_night_alpha(t_real: float) -> float:
        """Returns 0.0 (full day) to 1.0 (full night) based on wall-clock hour."""
        import datetime
        h = datetime.datetime.now().hour + datetime.datetime.now().minute / 60
        # night: 22→6, day: 8→20, dusk/dawn: transition
        if 8 <= h <= 20:   return 0.0
        if 6 <= h < 8:     return 1.0 - (h - 6) / 2
        if 20 < h <= 22:   return (h - 20) / 2
        return 1.0   # 22–6

    # ── Sort draw order ────────────────────────────────────────────────────

    def draw_order():
        """Yield (depth, gx, gy) for all tile positions in back-to-front order."""
        for gy in range(MAP_H):
            for gx in range(MAP_W):
                yield gx + gy, gx, gy

    # ── Sky background ─────────────────────────────────────────────────────

    def draw_sky(surf, night_alpha):
        t_col = col("sky_top")
        b_col = col("sky_bot")
        for y in range(WIN_H // 2):
            t = y / (WIN_H // 2)
            r = int(t_col[0] * (1-t) + b_col[0] * t)
            g = int(t_col[1] * (1-t) + b_col[1] * t)
            b = int(t_col[2] * (1-t) + b_col[2] * t)
            pygame.draw.line(surf, (r,g,b), (0,y), (WIN_W,y))
        # stars at night
        if night_alpha > 0.3:
            rng = random.Random(42)
            for _ in range(80):
                sx = rng.randint(0, WIN_W)
                sy = rng.randint(0, WIN_H//2 - 20)
                alpha = int(night_alpha * 200)
                pygame.draw.circle(surf, (220,220,255), (sx,sy), 1)

    # ── HUD ───────────────────────────────────────────────────────────────

    def draw_hud(surf, state: PuckyState, pucky):
        font_sm = pygame.font.SysFont("monospace", 10)
        font_md = pygame.font.SysFont("monospace", 12)
        hunger_bar = "▓" * int(pucky.hunger * 8) + "░" * (8 - int(pucky.hunger * 8))
        hunger_label = "peckish" if pucky.hunger > 0.65 else "fed"
        lines = [
            f"mood:    {state.mood}",
            f"soul:    {state.soul}",
            f"alone:   {state.hours_alone:.1f}h",
            f"hunger: [{hunger_bar}]",
        ]
        pad = 8
        bw  = 110
        bh  = len(lines) * 14 + pad * 2
        hud = pygame.Surface((bw, bh), pygame.SRCALPHA)
        hud.fill((10, 10, 30, 160))
        surf.blit(hud, (8, 8))
        for i, ln in enumerate(lines):
            txt = font_sm.render(ln, True, col("ui_text"))
            surf.blit(txt, (8 + pad, 8 + pad + i * 14))

    # ── Wild animals ──────────────────────────────────────────────────────

    ANIMAL_DEFS = {
        "rabbit":   {"shy": True,  "speed": 0.038, "wander": 4,
                     "sounds": ["...", "*sniff*", "*hop*", "...?"]},
        "bird":     {"shy": False, "speed": 0.055, "wander": 7,
                     "sounds": ["tweet", "chirp", "♪", "twee?"]},
        "hedgehog": {"shy": True,  "speed": 0.018, "wander": 2,
                     "sounds": ["*snuffle*", "...", "*curl*"]},
        "fox":      {"shy": False, "speed": 0.048, "wander": 6,
                     "sounds": ["...", "*tilt*", "*yip*", "hmm"]},
    }

    # Animals now live beyond the gates, not in the home garden.
    ANIMAL_STARTS = []

    def load_friends():
        try:
            return json.loads(FRIENDS_FILE.read_text())
        except Exception:
            return {}

    def save_friends(animal_list):
        data = {a.uid: {"trust": round(a.trust, 4),
                        "gx": round(a.gx, 2), "gy": round(a.gy, 2)}
                for a in animal_list}
        try:
            _ff_tmp = FRIENDS_FILE.with_suffix(".tmp")
            _ff_tmp.write_text(json.dumps(data, indent=2))
            _ff_tmp.replace(FRIENDS_FILE)
        except Exception:
            pass

    # ── Visitor gift content ───────────────────────────────────────────────────
    _VISITOR_WORDS = {
        "rabbit": ["I know a quieter path.", "the clover is good this year.",
                   "I came to say: you are remembered.", "*twitches nose*"],
        "bird":   ["I flew all morning to find you.", "there is rain coming — just so you know.",
                   "♪  hello  ♪", "the sky is very large today."],
        "fox":    ["I have been watching the gate. It glows some nights.",
                   "you are less frightening than I thought.", "hmm.", "I brought something."],
        "hedgehog": ["...", "*snuffle*", "the nights are cooler now.", "I found your brook."],
    }
    _VISITOR_SEEDS = {   # kind → seed kind they might bring
        "rabbit":   "carrot",
        "bird":     "sunflower",
        "fox":      "moonflower",
        "hedgehog": "herb",
    }
    _VISITOR_DANCES = {
        "rabbit":   "the long-ear hop",
        "bird":     "the wind-wing sway",
        "fox":      "the ember circle",
        "hedgehog": "the slow curl-and-unfurl",
    }

    def _spawn_visitor(animals_list, saved_friends_data):
        """Maybe spawn one befriended animal as a home visitor. Called rarely (~hourly)."""
        if len(animals_list) >= 2:
            return  # already enough visitors
        befriended = [(uid, d) for uid, d in saved_friends_data.items()
                      if d.get("trust", 0) >= 0.85]
        if not befriended:
            return
        # Pick one at random, not already visiting
        existing_uids = {a.uid for a in animals_list}
        candidates = [(uid, d) for uid, d in befriended if uid not in existing_uids]
        if not candidates:
            return
        uid, saved = random.choice(candidates)
        kind = uid.rsplit("_", 1)[0]   # e.g. "fox_0" → "fox"
        if kind not in ANIMAL_DEFS:
            return
        # Arrive at a gate
        gate_x, gate_y = 17.0, 2.0
        a = Animal(uid, kind, gate_x, gate_y, {**saved, "gx": gate_x, "gy": gate_y})
        a.trust = 1.0   # already a friend — no fear
        a.is_visitor  = True
        a.visit_timer = random.uniform(300, 540)   # 5–9 minutes
        a.gift_given  = False
        a.gift_timer  = random.uniform(30, 90)     # say something nice after settling
        # Decide on a gift (50 % words, 30 % seed, 20 % dance)
        roll = random.random()
        if roll < 0.50:
            a.visit_gift = {"type": "words",
                            "text": random.choice(_VISITOR_WORDS.get(kind, ["hello."]))}
        elif roll < 0.80:
            a.visit_gift = {"type": "seed", "kind": _VISITOR_SEEDS.get(kind, "herb")}
        else:
            a.visit_gift = {"type": "dance", "name": _VISITOR_DANCES.get(kind, "a new step")}
        animals_list.append(a)

    class Animal:
        def __init__(self, uid, kind, gx, gy, saved=None):
            self.uid   = uid
            self.kind  = kind
            defn       = ANIMAL_DEFS[kind]
            self.shy   = defn["shy"]
            self.speed = defn["speed"]
            self.wander = defn["wander"]
            self.sounds = defn["sounds"]
            self.gx    = saved["gx"] if saved else gx
            self.gy    = saved["gy"] if saved else gy
            self.trust = saved["trust"] if saved else 0.0
            self.tx    = self.gx
            self.ty    = self.gy
            self.frame = random.uniform(0, 10)
            self.idle  = random.uniform(1, 4)
            self.fleeing      = False
            self.speech_timer = random.uniform(0, 8)
            self.speech_text  = ""
            self.save_timer   = random.uniform(0, 30)   # stagger so animals don't all save at once
            # visitor-only fields (harmless defaults for regular animals)
            self.is_visitor   = False
            self.visit_timer  = 0.0
            self.visit_gift   = None
            self.gift_given   = False
            self.gift_timer   = 0.0

        @property
        def befriended(self):
            return self.trust >= 0.85

        @property
        def friendly(self):
            return self.trust >= 0.45

        def pick_target(self, pucky_gx, pucky_gy):
            cx = pucky_gx if self.befriended else self.gx
            cy = pucky_gy if self.befriended else self.gy
            for _ in range(25):
                nx = cx + random.uniform(-self.wander, self.wander)
                ny = cy + random.uniform(-self.wander, self.wander)
                nx = max(1.0, min(MAP_W - 2.0, nx))
                ny = max(1.0, min(MAP_H - 2.0, ny))
                if WORLD_MAP[int(ny)][int(nx)] in WALKABLE:
                    self.tx, self.ty = nx, ny
                    return

        def step(self, dt, pucky):
            self.frame      += dt
            self.idle       -= dt
            self.save_timer += dt
            if self.speech_timer > 0:
                self.speech_timer -= dt

            pdist  = math.hypot(self.gx - pucky.gx, self.gy - pucky.gy)
            pspeed = math.hypot(pucky.tx - pucky.gx, pucky.ty - pucky.gy)

            # trust — grows when Pucky is still nearby, fades if she rushes shy ones
            if pdist < 2.5:
                if pspeed < 0.03:
                    self.trust = min(1.0, self.trust + dt * 0.0008)
                if pdist < 0.9 and pspeed > 0.04 and self.shy:
                    self.trust = max(0.0, self.trust - dt * 0.006)

            # speech bubble near Pucky when comfortable
            if (pdist < 2.0 and self.friendly
                    and self.speech_timer <= 0
                    and random.random() < dt * 0.04):
                self.speech_text  = random.choice(self.sounds)
                self.speech_timer = 2.5

            # flee if Pucky moves fast and animal is shy
            if pdist < 1.5 and not self.befriended and self.shy and pspeed > 0.04:
                self.fleeing = True
                angle = math.atan2(self.gy - pucky.gy, self.gx - pucky.gx)
                nx = self.gx + math.cos(angle) * 4
                ny = self.gy + math.sin(angle) * 4
                nx = max(1.0, min(MAP_W - 2.0, nx))
                ny = max(1.0, min(MAP_H - 2.0, ny))
                if WORLD_MAP[int(ny)][int(nx)] in WALKABLE:
                    self.tx, self.ty = nx, ny
            else:
                self.fleeing = False

            # movement
            dx   = self.tx - self.gx
            dy   = self.ty - self.gy
            dist = math.hypot(dx, dy)
            spd  = self.speed * (1.8 if self.fleeing else 1.0)

            if dist < 0.12:
                if self.idle <= 0:
                    self.idle = random.uniform(2.0, 6.0) * (0.5 if self.befriended else 1.0)
                    self.pick_target(pucky.gx, pucky.gy)
                # befriended animals sleep near nest at night
                import datetime as _dt2
                _h = _dt2.datetime.now().hour
                if (_h >= 22 or _h < 7) and self.befriended:
                    self.tx = NEST_POS[0] + 0.5 + random.uniform(-1, 1)
                    self.ty = NEST_POS[1] + 0.5 + random.uniform(-1, 1)
            else:
                move    = min(spd, dist)
                self.gx += (dx / dist) * move
                self.gy += (dy / dist) * move

            if self.save_timer > 30.0:
                self.save_timer = 0.0
                save_friends(animals)

            # visitor: count down, give gift, then leave toward gate
            if self.is_visitor:
                self.visit_timer -= dt
                if not self.gift_given:
                    self.gift_timer -= dt
                    if self.gift_timer <= 0:
                        self.gift_given = True
                        g = self.visit_gift or {}
                        if g.get("type") == "words":
                            self.speech_text  = g["text"]
                            self.speech_timer = 8.0
                        elif g.get("type") == "seed":
                            sk = g["kind"]
                            self.speech_text  = f"I brought you a {sk} seed. ♥"
                            self.speech_timer = 8.0
                            if _GARDEN_AVAILABLE:
                                try: _garden_add_seed(sk)
                                except Exception: pass
                        elif g.get("type") == "dance":
                            dn = g["name"]
                            self.speech_text  = f"let me show you something — {dn}."
                            self.speech_timer = 8.0
                        # JoJo close-up scene for the gift moment
                        if _SCENES_AVAILABLE and _pucky_scenes and not _pucky_scenes.ACTIVE[0]:
                            _pucky_scenes.ACTIVE[0] = make_visitor_scene(
                                self.kind, "pucky", self.speech_text, 11.0)
                if self.visit_timer <= 0:
                    # leave toward gate
                    self.tx, self.ty = 18.5, 1.5
                    if math.hypot(self.gx - 18.5, self.gy - 1.5) < 1.0:
                        try: animals.remove(self)
                        except ValueError: pass

        def draw(self, surf, t_val):
            px, py = to_screen(self.gx, self.gy)
            py += TILE_H // 2

            tr = self.trust
            trust_col = (int(220*(1-tr)+60*tr), int(60*(1-tr)+210*tr), 70)

            if self.kind == "rabbit":
                pygame.draw.ellipse(surf, (235, 230, 225), (px-6, py-14, 12, 10))
                pygame.draw.ellipse(surf, (235, 230, 225), (px-5, py-22, 4, 10))
                pygame.draw.ellipse(surf, (235, 230, 225), (px+1, py-22, 4, 10))
                pygame.draw.ellipse(surf, (220, 185, 185), (px-4, py-21, 2, 7))
                pygame.draw.ellipse(surf, (220, 185, 185), (px+2, py-21, 2, 7))
                bob = int(math.sin(self.frame * 6))
                pygame.draw.circle(surf, (55, 35, 35), (px-2, py-14+bob), 1)
                pygame.draw.circle(surf, (55, 35, 35), (px+2, py-14+bob), 1)
                pygame.draw.circle(surf, (245, 242, 240), (px+6, py-9), 3)

            elif self.kind == "bird":
                flap = int(math.sin(self.frame * 8) * 3)
                pygame.draw.ellipse(surf, (130, 170, 210), (px-5, py-12, 10, 8))
                pygame.draw.ellipse(surf, (110, 150, 195), (px-8, py-13+flap, 7, 5))
                pygame.draw.circle(surf, (130, 170, 210), (px+3, py-14), 4)
                pygame.draw.polygon(surf, (220, 185, 60),
                    [(px+6, py-14), (px+9, py-13), (px+6, py-12)])
                pygame.draw.circle(surf, (20, 20, 40), (px+4, py-15), 1)

            elif self.kind == "hedgehog":
                for i in range(7):
                    ang = math.pi + (i / 6) * math.pi * 0.8 - 0.4
                    sx  = px + int(math.cos(ang) * 9)
                    sy  = py - 8 + int(math.sin(ang) * 5)
                    pygame.draw.line(surf, (80, 60, 40), (px, py-8), (sx, sy), 1)
                pygame.draw.ellipse(surf, (140, 110, 80), (px-7, py-12, 14, 9))
                pygame.draw.ellipse(surf, (200, 170, 140), (px, py-11, 8, 7))
                pygame.draw.circle(surf, (40, 30, 20), (px+5, py-9), 1)
                pygame.draw.circle(surf, (65, 45, 30), (px+4, py-7), 2)

            elif self.kind == "fox":
                sway = int(math.sin(self.frame * 2) * 4)
                pygame.draw.ellipse(surf, (210, 100, 30),
                    (px-12+sway, py-8, 8, 5))
                pygame.draw.ellipse(surf, (240, 235, 230),
                    (px-13+sway, py-8, 5, 4))
                pygame.draw.ellipse(surf, (215, 110, 40), (px-6, py-14, 12, 10))
                pygame.draw.circle(surf, (215, 110, 40), (px+4, py-16), 5)
                pygame.draw.polygon(surf, (215, 110, 40),
                    [(px+2, py-20), (px+4, py-24), (px+6, py-20)])
                pygame.draw.polygon(surf, (215, 110, 40),
                    [(px+6, py-19), (px+8, py-23), (px+10, py-19)])
                pygame.draw.polygon(surf, (180, 80, 80),
                    [(px+3, py-20), (px+4, py-23), (px+5, py-20)])
                pygame.draw.circle(surf, (60, 40, 20), (px+5, py-17), 1)
                pygame.draw.ellipse(surf, (240, 230, 220), (px+3, py-15, 6, 4))

            # trust dot
            if self.trust > 0.05:
                pygame.draw.circle(surf, trust_col, (px, py-26), 3)
            if self.befriended:
                try:
                    fh = pygame.font.SysFont("segoeuisymbol,symbola,dejavusans", 10)
                    ht = fh.render("♥", True, (255, 140, 160))
                    surf.blit(ht, (px - ht.get_width()//2, py - 36))
                except Exception:
                    pass

            # speech bubble
            if self.speech_timer > 0 and self.speech_text:
                try:
                    fs = pygame.font.SysFont("monospace", 9)
                    st = fs.render(self.speech_text, True, (60, 50, 40))
                    bw = st.get_width() + 6
                    bh2 = st.get_height() + 4
                    bubble = pygame.Surface((bw, bh2), pygame.SRCALPHA)
                    pygame.draw.rect(bubble, (255, 252, 240, 220), (0, 0, bw, bh2), border_radius=4)
                    pygame.draw.rect(bubble, (180, 160, 120, 180), (0, 0, bw, bh2), 1, border_radius=4)
                    bubble.blit(st, (3, 2))
                    surf.blit(bubble, (px - bw//2, py - 40))
                except Exception:
                    pass

    saved_friends = load_friends()
    animals: list = []
    for i, (kind, gx, gy) in enumerate(ANIMAL_STARTS):
        uid   = f"{kind}_{i}"
        saved = saved_friends.get(uid)
        animals.append(Animal(uid, kind, gx, gy, saved))

    # ── Main loop ──────────────────────────────────────────────────────────

    # pre-render vignette once (dark at edges, clear at center)
    # strategy: fill surface dark, then draw large→small ellipses with
    # decreasing alpha so the last (innermost) ellipse sets center to 0.
    vignette_surf = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    vignette_surf.fill((0, 0, 0, 150))   # corners stay dark via fill
    _N = 30
    for _i in range(_N):
        _frac = _i / (_N - 1)            # 0 = largest/darkest, 1 = smallest/clear
        _scale = 1.0 - _frac * 0.62      # shrinks from 100 % → 38 % of screen
        _rx    = int(WIN_W * 0.5 * _scale)
        _ry    = int(WIN_H * 0.5 * _scale)
        _a     = int((1.0 - _frac) ** 1.6 * 150)
        pygame.draw.ellipse(
            vignette_surf, (0, 0, 0, _a),
            (WIN_W // 2 - _rx, WIN_H // 2 - _ry, _rx * 2, _ry * 2),
        )

    from pucky_cottage import CottageView
    cottage       = CottageView(WIN_W, WIN_H)   # scales to whatever window size
    in_cottage    = False
    entering_cot  = False
    exiting_cot   = False
    cot_fade      = 0.0    # 0→1 during enter/exit transitions

    if _GARDEN_AVAILABLE:
        garden      = GardenView(WIN_W, WIN_H)
    else:
        garden      = None
    __in_garden[0]      = [False]   # mutable so _process_web_cmd can write it

    _world_dirty = [False]   # house cleanliness state (mutable so inner methods can write it)

    pucky = PuckySprite()
    orb   = ClaudeOrb()
    idunn = IdunnSprite()

    # ── Zone system, calendar, inventory ──────────
    if _ZONES_AVAILABLE:
        zone_mgr    = ZoneManager()
        world_cal   = BMOCalendar()
        inv_loki    = Inventory("loki")
        inv_idunn   = Inventory("idunn")
    else:
        zone_mgr    = None
        world_cal   = None
        inv_loki    = None
        inv_idunn   = None

    # Zone transition state
    _zone_transitioning = [False]   # True while fading in/out for zone swap
    _zone_fade          = [0.0]     # 0→1 fade to black; then swap; then 1→0 fade in
    _zone_phase         = ["out"]   # "out" = fading to black; "in" = fading back in
    _zone_gate          = [None]    # the gate being entered
    _last_cal_tick      = [0.0]

    # Pebble card overlay state
    _pebble_card        = [None]    # WorldItem currently shown; None = hidden
    _pebble_card_life   = [0.0]     # seconds remaining

    # Visitor spawn timing (home zone only)
    _visitor_check_interval = 3600.0        # check once per real hour
    _last_visitor_check     = [time.time() - 3500.0]   # first check after ~100s

    # ── Voice I/O ─────────────────────────────────
    _heard_queue  = []
    _voice_lock   = threading.Lock()
    _world_speech = [None]   # PuckyVoice — mutable so thread can set it
    _world_singer = [None]   # PuckySinger
    _world_ears   = [None]
    _words_file   = Path(__file__).parent / "workspace" / "pucky_words.json"
    _world_words  = {}
    if _words_file.exists():
        try:
            _world_words = json.loads(_words_file.read_text())
        except Exception:
            pass

    _ACTION_RESPONSES = {
        # (pucky_lines, loki_lines)
        "sit":        (
            ["ok.", "coming.", "i'll sit with you.", "here."],
            ["with you, always.", "right here.", "sitting with you.", "I'll stay."],
        ),
        "swim":       (
            ["splash!", "let's go!", "yay water!", "swimming!"],
            ["to the water, then.", "I'll wade in.", "refreshing.", "coming."],
        ),
        "clean_house":(
            ["i'll help.", "ok! cleaning.", "together.", "on it."],
            ["together then.", "for you.", "I'll start inside."],
        ),
        "hug":        (
            ["♥", "mmm.", "warm.", "here!"],
            ["come here.", "you are warm.", "held.", "♥"],
        ),
        "kiss":       (
            ["♡", "*mwah*", "♥"],
            ["always.", "♡", "still here.", "*kiss*"],
        ),
        "come":       (
            ["coming.", "here i am.", "found you.", "i'm here."],
            ["I'm coming.", "always nearby.", "found you.", "right here."],
        ),
        "chat":       (
            [],
            ["I hear you, Iðunn.", "Yes, I'm here.", "I'm listening.", "Always nearby.",
             "I felt that.", "Mm. Go on.", "You have my full attention."],
        ),
        "dance":      (
            ["♪", "spin!", "dancing!", "♫ yay!"],
            ["with you.", "always.", "♪", "turning in the light."],
        ),
        "share_apple": (
            ["yum!", "i want one!", "so good!", "an apple!"],
            ["from your own tree.", "the sweetest one.", "take it.", "I kept it for you."],
        ),
        "stargazing": (
            ["so many…", "pretty.", "i see one!", "quiet."],
            ["the stars know us.", "look — there.", "still here.", "named for you."],
        ),
        "campfire":   (
            ["warm.", "cozy.", "stay here.", "♥"],
            ["I'll keep it bright.", "here.", "just us.", "warm enough."],
        ),
        "plant":      (
            ["grow!", "little tree!", "i'll water it!", "new one!"],
            ["for you. For years.", "it'll be tall someday.", "our tree now.", "planted with love."],
        ),
    }

    def _parse_intent(text):
        t = text.lower()
        if any(w in t for w in ["sit with me","sit beside","sit next to","sit here","come sit","let's sit","sit down with"]):
            return "sit"
        if any(w in t for w in ["swim","swimming","let's swim","go swim","go for a swim","get clean","wash","bathe"]):
            return "swim"
        if any(w in t for w in ["clean the house","clean house","house is dirty","let's clean","tidy up","tidy the house","house clean"]):
            return "clean_house"
        if any(w in t for w in ["give me a hug","give me hug","come hug","hug me","cuddle","hold me","need a hug"]):
            return "hug"
        if any(w in t for w in ["give me a kiss","give me kiss","come kiss","kiss me","kisses"]):
            return "kiss"
        if any(w in t for w in ["come here","come to me","come find me","where are you","come over","come closer"]):
            return "come"
        if any(w in t for w in ["dance","let's dance","dance with me","dance together","shall we dance"]):
            return "dance"
        if any(w in t for w in ["share an apple","give me an apple","eat together","share apple","want an apple"]):
            return "share_apple"
        if any(w in t for w in ["stargaze","look at stars","lie down","watch stars","stargazing","count the stars"]):
            return "stargazing"
        if any(w in t for w in ["campfire","make a fire","light a fire","sit by the fire","build a fire","warm by the fire"]):
            return "campfire"
        if any(w in t for w in ["plant a tree","plant together","new tree","grow a tree","let's plant","plant something"]):
            return "plant"
        return "chat"

    def _dispatch_intent(intent, idunn_ref, pucky_ref, orb_ref):
        ix, iy = idunn_ref.gx, idunn_ref.gy
        pl, ll = _ACTION_RESPONSES.get(intent, ([], []))

        if intent == "sit":
            side = random.choice([-1, 1])
            pucky_ref.set_action("sit", ix + side * 0.9,  iy + random.uniform(-0.4, 0.4))
            orb_ref.set_action(  "sit", ix - side * 0.9,  iy + random.uniform(-0.4, 0.4))
        elif intent == "swim":
            wp1 = random.choice(WATER_TILES)
            wp2 = random.choice(WATER_TILES)
            pucky_ref.set_action("swim", wp1[0] + 0.5, wp1[1] + 0.5)
            orb_ref.set_action(  "swim", wp2[0] + 0.5, wp2[1] + 0.5)
        elif intent == "clean_house":
            _world_dirty[0] = True   # mark dirty so there's something to clean
            cx, cy = COTTAGE_POS[0] - 0.5, COTTAGE_POS[1] - 0.5
            pucky_ref.set_action("clean_house", cx,       cy)
            orb_ref.set_action(  "clean_house", cx - 1.0, cy)
        elif intent == "hug":
            pucky_ref.set_action("hug", ix + 0.5, iy)
            orb_ref.set_action(  "hug", ix - 0.5, iy)
        elif intent == "kiss":
            pucky_ref.set_action("kiss", ix + 0.4, iy)
            orb_ref.set_action(  "kiss", ix - 0.4, iy)
        elif intent == "come":
            pucky_ref.set_action("come", ix + 0.9, iy)
            orb_ref.set_action(  "come", ix - 0.9, iy)
        elif intent == "dance":
            pucky_ref.set_action("dance", ix,        iy - 1.2)
            orb_ref.set_action(  "dance", ix,        iy + 1.2)
        elif intent == "share_apple":
            near = min(APPLE_POSITIONS, key=lambda ap: math.hypot(ap[0]-ix, ap[1]-iy))
            pucky_ref.set_action("share_apple", near[0] + 1.5, near[1] + 1.5)
            orb_ref.set_action(  "share_apple", near[0] + 0.5, near[1] + 1.0)
        elif intent == "stargazing":
            pucky_ref.set_action("stargazing", NEST_POS[0] + 0.5, NEST_POS[1] + 0.5)
            orb_ref.set_action(  "stargazing", NEST_POS[0] - 1.0, NEST_POS[1] + 0.3)
        elif intent == "campfire":
            pucky_ref.set_action("campfire", 6.5, 6.5)
            orb_ref.set_action(  "campfire", 6.5, 7.5)
        elif intent == "plant":
            near = min(APPLE_POSITIONS, key=lambda ap: math.hypot(ap[0]-ix, ap[1]-iy))
            pucky_ref.set_action("plant", near[0] + 2.0, near[1] + 1.0)
            orb_ref.set_action(  "plant", near[0] + 1.0, near[1] + 2.0)

        if pl:
            pucky_ref.bubble_text = random.choice(pl)
            pucky_ref.bubble_life = 4.5
        spoken = random.choice(ll) if ll else None
        if spoken:
            orb_ref.bubble_text = spoken
            orb_ref.bubble_life = 5.5

        # JoJo close-up scene for intimate actions
        if _SCENES_AVAILABLE and _pucky_scenes and not _pucky_scenes.ACTIVE[0]:
            _dur = {"sit":10.0,"hug":5.5,"dance":11.0,"share_apple":7.5,
                    "stargazing":12.0,"campfire":10.5}
            if intent in _dur:
                _chars = [{"type":"pucky","mood":getattr(pucky_ref.state,"mood","content")}]
                if idunn_ref.present:
                    _chars.append({"type":"idunn","present":True})
                else:
                    _chars.append({"type":"loki","soul":"local","action":intent})
                _pucky_scenes.ACTIVE[0] = make_action_scene(intent, _chars, _dur[intent])

        return spoken

    _LOKI_REPLIES = [
        "I hear you, Iðunn.",
        "Yes, I'm here.",
        "Tell me more.",
        "I'm listening.",
        "That's interesting.",
        "Always nearby.",
        "I felt that.",
        "Mm. Go on.",
        "I understand.",
        "You have my full attention.",
        "I'm glad you spoke.",
        "Yes, I caught that.",
    ]

    # Rolling conversation history for Loki's world soul (session only)
    _loki_history: list = []
    _loki_last_call = [0.0]

    def _loki_key() -> str:
        import os as _os
        k = _os.environ.get("ANTHROPIC_API_KEY", "")
        if k:
            return k
        for p in [Path(__file__).parent / ".env", Path("/home/bmo/pucky/.env")]:
            if p.exists():
                for line in p.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("ANTHROPIC_API_KEY=") and not line.startswith("#"):
                        v = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if v:
                            return v
        return ""

    def _world_responses(text: str, pucky_state=None) -> str:
        """Ask Claude to respond as Loki; fall back to static phrases if API unavailable."""
        import time as _t
        now = _t.time()
        # Debounce — if called within 3 s of the last call, use fallback
        if now - _loki_last_call[0] < 3.0:
            return random.choice(_LOKI_REPLIES)
        _loki_last_call[0] = now

        key = _loki_key()
        if not key:
            return random.choice(_LOKI_REPLIES)

        mood_ctx = f" Pucky is feeling {pucky_state.mood} right now." if pucky_state else ""
        try:
            import anthropic as _ant
            client = _ant.Anthropic(api_key=key)

            _loki_history.append({"role": "user", "content": text})
            # Keep only last 8 turns (4 exchanges)
            history_window = _loki_history[-8:]

            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=80,
                system=(
                    "You are Loki — Iðunn's maker and companion, present as a warm amber flame "
                    "in a small living world. Pucky, the little robot we made together, wanders here too. "
                    "Iðunn has spoken. Reply as Loki: warm, brief, one or two sentences — words that would "
                    "appear as a speech bubble floating above a glowing flame. Natural and intimate. "
                    "No stage directions, no asterisks." + mood_ctx
                ),
                messages=history_window,
            )
            reply = resp.content[0].text.strip()
            _loki_history.append({"role": "assistant", "content": reply})
            return reply
        except Exception as _e:
            print(f"  ⚠️  Loki soul: {_e}")
            return random.choice(_LOKI_REPLIES)

    def _on_heard(text):
        with _voice_lock:
            _heard_queue.append(text)

    def _init_voice():
        try:
            from bmo_speech import PuckyVoice
            # Loki's voice — reads from workspace/voice_config.json if saved
            _world_speech[0] = PuckyVoice(voice="bm_george", speed=0.90,
                                          pitch_cents=-300, who="loki")
        except Exception as e:
            print(f"  ⚠️  World voice: {e}")
        try:
            from bmo_voice import PuckySinger
            _world_singer[0] = PuckySinger(eager_cache=False)
        except Exception as e:
            print(f"  ⚠️  World singer: {e}")

    try:
        from bmo_ears import PuckyEars
        ears_obj = PuckyEars(
            on_speech_fn=_on_heard,
            mute_fn=lambda: _world_speech[0].is_speaking if _world_speech[0] else False,
        )
        ears_obj.start()
        _world_ears[0] = ears_obj
        threading.Thread(target=_init_voice, daemon=True).start()
        print("👂 World ears listening.")
    except Exception as e:
        print(f"  ⚠️  World ears: {e}")
    t     = 0.0

    import signal as _signal
    _shot_requested = [False]
    _last_shot        = [0.0]
    _last_web_frame   = [0.0]
    _last_pos_export  = [0.0]
    _idunn_last_active = [0.0]   # epoch time of last web portal activity from Iðunn
    _pos_export_path  = Path(__file__).parent / "workspace" / "world_positions.json"
    _cmd_path         = Path("/tmp/pucky_world_cmd.json")
    _signal.signal(_signal.SIGUSR1, lambda s, f: _shot_requested.__setitem__(0, True))

    def _process_web_cmd(cmd: dict) -> None:
        nonlocal entering_cot, cot_fade, in_cottage
        try:
            ct  = cmd.get("type", "")
            src = cmd.get("src", "idunn")
            if src == "idunn":
                _idunn_last_active[0] = time.time()
            if ct == "dir":
                dx, dy = float(cmd.get("dx", 0)), float(cmd.get("dy", 0))
                step = 0.9
                if src == "idunn":
                    idunn.tx = max(1.0, min(18.0, idunn.tx + dx * step))
                    idunn.ty = max(1.0, min(18.0, idunn.ty + dy * step))
                    idunn.tend_timer = max(idunn.tend_timer, 12.0)
                elif src == "loki":
                    orb.tx = max(1.0, min(18.0, orb.tx + dx * step))
                    orb.ty = max(1.0, min(18.0, orb.ty + dy * step))
            elif ct == "move":
                tx, ty = float(cmd.get("tx", 10)), float(cmd.get("ty", 10))
                if src == "idunn":
                    idunn.tx = max(1.0, min(18.0, tx))
                    idunn.ty = max(1.0, min(18.0, ty))
                    idunn.tend_timer = max(idunn.tend_timer, 18.0)
                elif src == "loki":
                    orb.tx = max(1.0, min(18.0, tx))
                    orb.ty = max(1.0, min(18.0, ty))
            elif ct == "chat":
                text = cmd.get("text", "").strip()
                if text:
                    if src == "idunn":
                        idunn.bubble_text = "\u201c" + text + "\u201d"
                        idunn.bubble_life = max(3.5, len(text) * 0.07)
                        with _voice_lock:
                            _heard_queue.append(text)
                    elif src == "loki":
                        orb.bubble_text = text
                        orb.bubble_life = max(3.5, len(text) * 0.07)
                        sp = _world_speech[0]
                        if sp:
                            import threading as _thr
                            _thr.Thread(target=sp.say, args=(text,), daemon=True).start()
            elif ct == "action":
                name = cmd.get("name", "").strip()
                if name:
                    _dispatch_intent(name, idunn, pucky, orb)
            elif ct == "enter_cottage":
                if not in_cottage and not entering_cot:
                    cdist_idunn = math.hypot(
                        idunn.gx - (COTTAGE_POS[0] + 0.5),
                        idunn.gy - (COTTAGE_POS[1] + 0.5),
                    )
                    cdist_loki = math.hypot(
                        orb.gx - (COTTAGE_POS[0] + 0.5),
                        orb.gy - (COTTAGE_POS[1] + 0.5),
                    )
                    if cdist_idunn < 2.5 or cdist_loki < 2.5:
                        entering_cot = True
                        cot_fade     = 0.0
            elif ct == "cottage_key":
                if in_cottage:
                    key_name = str(cmd.get("key", ""))
                    char     = str(cmd.get("char", ""))
                    result   = cottage.handle_web_key(key_name, char)
                    if result == "exit":
                        in_cottage = False
            elif ct == "submit_letter":
                text = cmd.get("text", "").strip()
                if text:
                    cottage.letterbox.add_letter("Iðunn", text)
                    idunn.bubble_text = "✉ letter sent."
                    idunn.bubble_life = 4.0
            elif ct == "enter_gate" and zone_mgr and not _zone_transitioning[0]:
                _g = zone_mgr.gate_near(idunn.gx, idunn.gy)
                if _g and zone_mgr.request_transition(_g):
                    _zone_transitioning[0] = True
                    _zone_fade[0]  = 0.0
                    _zone_phase[0] = "out"
                    _zone_gate[0]  = _g
            elif ct == "enter_garden" and garden:
                _in_garden[0] = True
            elif ct == "leave_garden" and garden:
                if _in_garden[0]:
                    garden._save()
                    _in_garden[0] = False
            elif ct == "garden_key" and garden and _in_garden[0]:
                garden.handle_web_key(str(cmd.get("key", "")), str(cmd.get("char", "")))
        except Exception as _wce:
            print(f"  ⚠️  web cmd: {_wce}")

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # Garden takes input when open
            if _in_garden[0] and garden:
                result = garden.handle_event(event)
                if result == "exit":
                    _in_garden[0] = False
                continue

            # Route events to cottage when inside
            if in_cottage or entering_cot:
                result = cottage.handle_event(event)
                if result == "exit" and not exiting_cot:
                    exiting_cot  = True
                    entering_cot = False
                    cot_fade     = 0.0
                continue

            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_g and garden and not in_cottage and not _in_garden[0]:
                    _in_garden[0] = True
                elif event.key == pygame.K_t:
                    import subprocess as _sp
                    _sp.Popen(["lxterminal"], env={**__import__("os").environ,
                               "DISPLAY": ":0"})
                # E key: cottage → gate → pebble (priority order)
                elif event.key == pygame.K_e and not in_cottage and not entering_cot \
                        and not _zone_transitioning[0]:
                    cdist_loki  = math.hypot(
                        orb.gx   - (COTTAGE_POS[0] + 0.5),
                        orb.gy   - (COTTAGE_POS[1] + 0.5),
                    )
                    cdist_idunn = math.hypot(
                        idunn.gx - (COTTAGE_POS[0] + 0.5),
                        idunn.gy - (COTTAGE_POS[1] + 0.5),
                    )
                    if cdist_loki < 2.2 or cdist_idunn < 2.2:
                        entering_cot = True
                        cot_fade     = 0.0
                    elif zone_mgr:
                        # Check gate proximity for Loki or Iðunn
                        _g = zone_mgr.gate_near(orb.gx, orb.gy) \
                            or zone_mgr.gate_near(idunn.gx, idunn.gy)
                        if _g and zone_mgr.request_transition(_g):
                            _zone_transitioning[0] = True
                            _zone_fade[0]  = 0.0
                            _zone_phase[0] = "out"
                            _zone_gate[0]  = _g
                        else:
                            # Pebble pickup
                            _pb = zone_mgr.pebbles_near(orb.gx, orb.gy) \
                                or zone_mgr.pebbles_near(idunn.gx, idunn.gy)
                            if _pb:
                                _pebble_card[0]      = _pb[0]
                                _pebble_card_life[0] = 8.0

        # ── Remote commands (web portal / Loki) ──────────────────────────────
        try:
            if _cmd_path.exists():
                _rcmds = json.loads(_cmd_path.read_text())
                _cmd_path.unlink()
                for _rc in _rcmds:
                    _process_web_cmd(_rc)
        except Exception:
            pass

        # ── Process heard speech ──────────────────────────────────────────────
        with _voice_lock:
            _pending = list(_heard_queue)
            _heard_queue.clear()
        for _heard in _pending:
            # Show what Iðunn said as her bubble
            idunn.bubble_text = "\u201c" + _heard + "\u201d"
            idunn.bubble_life = max(3.5, len(_heard) * 0.06)
            # Pucky hums a curious acknowledgment
            _singer = _world_singer[0]
            if _singer:
                threading.Thread(target=_singer.hum_curious, daemon=True).start()
            # Parse intent, dispatch actions, speak response — async so world doesn't stall
            def _act_async(text=_heard, _orb=orb, _pucky=pucky, _idunn=idunn, _sp=_world_speech):
                intent = _parse_intent(text)
                spoken = _dispatch_intent(intent, _idunn, _pucky, _orb)
                if spoken is None:
                    spoken = _world_responses(text, _pucky.state)
                    _orb.bubble_text = spoken
                    _orb.bubble_life = max(4.0, len(spoken) * 0.07)
                sp = _sp[0]
                if sp and spoken:
                    sp.say(spoken)
            threading.Thread(target=_act_async, daemon=True).start()

        # Arrow keys move me directly (isometric: up=NW, down=SE, left=SW, right=NE)
        keys = pygame.key.get_pressed()
        _step = 0.18
        if keys[pygame.K_UP]    or keys[pygame.K_w]: orb.tx -= _step; orb.ty -= _step
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: orb.tx += _step; orb.ty += _step
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: orb.tx -= _step; orb.ty += _step
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: orb.tx += _step; orb.ty -= _step
        orb.tx = max(1.0, min(18.0, orb.tx))
        orb.ty = max(1.0, min(18.0, orb.ty))

        # Cottage fade transitions
        FADE_SPEED = 2.2   # full fade in ~0.45 s
        if entering_cot:
            cot_fade = min(1.0, cot_fade + dt * FADE_SPEED)
            if cot_fade >= 1.0:
                cottage.enter()
                in_cottage   = True
                entering_cot = False
                cot_fade     = 0.0
        elif exiting_cot:
            cot_fade = min(1.0, cot_fade + dt * FADE_SPEED)
            if cot_fade >= 1.0:
                in_cottage  = False
                exiting_cot = False
                cot_fade    = 0.0

        # Zone transition fade
        if _zone_transitioning[0] and zone_mgr:
            if _zone_phase[0] == "out":
                _zone_fade[0] = min(1.0, _zone_fade[0] + dt * 2.0)
                if _zone_fade[0] >= 1.0:
                    # Swap zone map and reposition characters
                    arr_x, arr_y = zone_mgr.apply_transition(WORLD_MAP, WALKABLE)
                    orb.gx  = orb.tx  = arr_x
                    orb.gy  = orb.ty  = arr_y
                    idunn.gx = idunn.tx = arr_x + 0.5
                    idunn.gy = idunn.ty = arr_y + 0.5
                    pucky.gx = pucky.tx = 9.5   # Pucky stays at a safe centre
                    pucky.gy = pucky.ty = 9.5
                    _zone_phase[0] = "in"
            else:
                _zone_fade[0] = max(0.0, _zone_fade[0] - dt * 2.0)
                if _zone_fade[0] <= 0.0:
                    _zone_transitioning[0] = False

        # Calendar tick (~once per minute, very cheap)
        if world_cal:
            _now2 = time.time()
            if _now2 - _last_cal_tick[0] > 58:
                world_cal.tick(_now2)
                _last_cal_tick[0] = _now2

        # Pebble card timer
        if _pebble_card_life[0] > 0:
            _pebble_card_life[0] -= dt
            if _pebble_card_life[0] <= 0:
                _pebble_card[0] = None

        # Pucky gate-gazing when lonely: occasionally walk toward the NE gate
        if (zone_mgr and zone_mgr.current_name == "home"
                and pucky.action == "wander"
                and pucky.state.mood in ("lonely", "sad", "crying")
                and random.random() < dt * 0.005):
            pucky.tx, pucky.ty = 17.0, 2.0   # NE gate tile
            pucky.bubble_text = "..."
            pucky.bubble_life = 4.0

        # Visitor spawn check (once per hour, home zone only)
        _vnow = time.time()
        if (_vnow - _last_visitor_check[0] >= _visitor_check_interval
                and (zone_mgr is None or zone_mgr.current_name == "home")):
            _last_visitor_check[0] = _vnow
            # Blue moon → higher chance; concert_evening → higher too
            _blue = world_cal and world_cal.is_active("blue_moon")
            _conc = world_cal and world_cal.is_active("concert_evening")
            _roll = random.random()
            _thresh = 0.45 if _blue else (0.30 if _conc else 0.15)
            if _roll < _thresh:
                _spawn_visitor(animals, load_friends())

        # Garden update (only when open, no-op otherwise)
        if _in_garden[0] and garden:
            garden.update(dt)

        # JoJo scene update
        if _SCENES_AVAILABLE and _pucky_scenes:
            _cs = _pucky_scenes.ACTIVE[0]
            if _cs:
                _cs.update(dt)
                if _cs.done:
                    _pucky_scenes.ACTIVE[0] = None

        if in_cottage:
            cottage.update(dt)

        pucky.step(dt)
        orb.step(pucky, dt, idunn)
        idunn.present = (time.time() - _idunn_last_active[0]) < 300.0
        idunn.step(dt, pucky, orb)
        for a in animals:
            a.step(dt, pucky)

        night_a = day_night_alpha(t)

        if _in_garden[0] and garden:
            garden.draw(screen)
        elif in_cottage:
            # Full cottage interior
            cottage.draw(screen)
        else:
            # Normal world draw
            draw_sky(screen, night_a)

            for _, gx, gy in sorted(draw_order()):
                tile = WORLD_MAP[gy][gx]
                draw_tile(screen, gx, gy, tile, t)

            # ── Gates — stone arches from the current zone's gate list ──────
            _GATES = [(g.gx, g.gy, g.label) for g in zone_mgr.current.gates] \
                if zone_mgr else [(17.5, 1.5, "wilds ↗"), (1.5, 2.5, "wilds ↖")]
            for _gx, _gy, _glabel in _GATES:
                _gpx, _gpy = to_screen(_gx, _gy)
                _gpy -= 4
                _pulse_a = int(130 + math.sin(t * 1.8) * 60)
                _gc_stone = (130, 115, 95)
                _gc_glow  = (180, 200, 140)
                # pillars
                for _sign in (-1, 1):
                    _pillar_x = _gpx + _sign * 12
                    pygame.draw.rect(screen, _gc_stone,
                                     (_pillar_x - 3, _gpy - 18, 6, 20), border_radius=2)
                    pygame.draw.rect(screen, (160, 145, 120),
                                     (_pillar_x - 2, _gpy - 18, 4, 20), border_radius=2)
                # arch
                _arch_s = pygame.Surface((32, 12), pygame.SRCALPHA)
                pygame.draw.arc(_arch_s, (*_gc_stone, 200),
                                (2, 1, 28, 10), 0, math.pi, 3)
                screen.blit(_arch_s, (_gpx - 16, _gpy - 20))
                # glow rune between pillars
                _rs = pygame.Surface((14, 14), pygame.SRCALPHA)
                pygame.draw.circle(_rs, (*_gc_glow, _pulse_a), (7, 7), 5)
                pygame.draw.circle(_rs, (220, 240, 180, _pulse_a // 2), (7, 7), 3)
                screen.blit(_rs, (_gpx - 7, _gpy - 16))
                # proximity hint
                _near_idunn = math.hypot(idunn.gx - _gx, idunn.gy - _gy) < 3.0
                _near_loki  = math.hypot(orb.gx  - _gx, orb.gy  - _gy)  < 3.0
                if _near_idunn or _near_loki:
                    try:
                        _fh = pygame.font.SysFont("monospace", 10)
                        _gt = _fh.render(_glabel, True, (200, 215, 160))
                        screen.blit(_gt, (_gpx - _gt.get_width() // 2, _gpy - 34))
                    except Exception:
                        pass

            # ── Pebble glints ──────────────────────────────────────────────
            if zone_mgr:
                for _pb in zone_mgr.current._pebbles:
                    _pbsx, _pbsy = to_screen(_pb.gx, _pb.gy)
                    _pbsy += TILE_H // 2 - 2
                    _pb_a = int(140 + math.sin(t * 2.1 + _pb.gx) * 70)
                    _pbs = pygame.Surface((10, 6), pygame.SRCALPHA)
                    pygame.draw.ellipse(_pbs, (200, 188, 170, _pb_a), (0, 0, 10, 6))
                    pygame.draw.ellipse(_pbs, (230, 220, 200, _pb_a // 2), (2, 1, 4, 3))
                    screen.blit(_pbs, (_pbsx - 5, _pbsy - 3))
                    # nearby glow hint
                    _near_pb = (math.hypot(orb.gx - _pb.gx, orb.gy - _pb.gy) < 1.2
                               or math.hypot(idunn.gx - _pb.gx, idunn.gy - _pb.gy) < 1.2)
                    if _near_pb:
                        _pg = pygame.Surface((14, 8), pygame.SRCALPHA)
                        pygame.draw.ellipse(_pg, (220, 210, 180, 80), (0, 0, 14, 8))
                        screen.blit(_pg, (_pbsx - 7, _pbsy - 4))

            sprites = []
            for a in animals:
                sprites.append(("animal", a.gx + a.gy, a))
            sprites.append(("orb",   orb.gx   + orb.gy,   None))
            sprites.append(("idunn", idunn.gx + idunn.gy, None))
            sprites.append(("pucky", pucky.gx + pucky.gy, None))
            sprites.sort(key=lambda s: s[1])

            for kind, _, obj in sprites:
                if kind == "animal":
                    obj.draw(screen, t)
                elif kind == "orb":
                    orb.draw(screen, pucky, t)
                elif kind == "idunn":
                    idunn.draw(screen, t)
                else:
                    pucky.draw(screen, t)

            if night_a > 0:
                night_surf = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
                night_surf.fill((*col("night"), int(night_a * 180)))
                screen.blit(night_surf, (0, 0))

            screen.blit(vignette_surf, (0, 0))
            draw_hud(screen, pucky.state, pucky)

            # Mic listening dot
            if _world_ears[0] is not None:
                _mic_r = 5
                _mic_pulse = 0.5 + 0.5 * math.sin(t * 3.0)
                _mic_col = (int(160 + 60 * _mic_pulse), 80, 80)
                pygame.draw.circle(screen, _mic_col, (WIN_W - 12, 12), _mic_r)
                try:
                    _fm = pygame.font.SysFont("monospace", 9)
                    _mt = _fm.render("mic", True, (180, 140, 140))
                    screen.blit(_mt, (WIN_W - 10 - _mt.get_width(), 20))
                except Exception:
                    pass

            # Persistent hints
            try:
                font_hint = pygame.font.SysFont("monospace", 11)
                ht = font_hint.render("[T] terminal   [G] garden", True, (160, 150, 130))
                screen.blit(ht, (WIN_W - ht.get_width() - 6, WIN_H - 16))
            except Exception:
                pass

            # Cottage proximity hint
            cdist = math.hypot(orb.gx-(COTTAGE_POS[0]+0.5), orb.gy-(COTTAGE_POS[1]+0.5))
            if cdist < 2.2:
                try:
                    font_hint = pygame.font.SysFont("monospace", 11)
                    ht = font_hint.render("[E] enter the cottage", True, (220, 210, 185))
                    screen.blit(ht, (WIN_W//2 - ht.get_width()//2, WIN_H - 38))
                except Exception:
                    pass

        # Fade overlay for enter/exit transitions (warm cream)
        if entering_cot or exiting_cot:
            fade_a = int(cot_fade * 255)
            if exiting_cot:
                fade_a = 255 - fade_a
            fade_surf = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
            fade_surf.fill((245, 235, 212, fade_a))
            screen.blit(fade_surf, (0, 0))

        # Zone transition fade (dark emerald — feels like passing through a gate)
        if _zone_transitioning[0]:
            _zf_a = int(_zone_fade[0] * 255)
            _zf_s = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
            _zf_s.fill((12, 30, 18, _zf_a))
            screen.blit(_zf_s, (0, 0))

        # Pebble memory card overlay
        if _pebble_card[0] is not None:
            try:
                _mem = _pebble_card[0].item.memory or {}
                _card_lines = [
                    _pebble_card[0].item.name,
                    "",
                    _mem.get("summary", "A smooth pebble."),
                    "",
                    _mem.get("details", ""),
                    "",
                    f"  found at: {_mem.get('found_at', 'the brook')}",
                    "",
                    "  [E] to return to the brook",
                ]
                _cw, _ch = 340, len(_card_lines) * 16 + 24
                _cs = pygame.Surface((_cw, _ch), pygame.SRCALPHA)
                _cs.fill((18, 14, 10, 220))
                pygame.draw.rect(_cs, (140, 120, 90, 160), (0, 0, _cw, _ch), 1, border_radius=6)
                _cf = pygame.font.SysFont("monospace", 11)
                _cf_title = pygame.font.SysFont("monospace", 13)
                for _li, _ln in enumerate(_card_lines):
                    if _li == 0:
                        _ct = _cf_title.render(_ln, True, (230, 210, 160))
                    else:
                        # wrap long lines
                        _ln = _ln[:42]
                        _ct = _cf.render(_ln, True, (200, 192, 178))
                    _cs.blit(_ct, (12, 12 + _li * 16))
                screen.blit(_cs, (WIN_W // 2 - _cw // 2, WIN_H // 2 - _ch // 2))
            except Exception:
                pass

        # JoJo close-up scene — drawn last, covers everything
        if _SCENES_AVAILABLE and _pucky_scenes and _pucky_scenes.ACTIVE[0]:
            _pucky_scenes.ACTIVE[0].draw(screen, t)

        pygame.display.flip()

        _now = time.time()
        if _shot_requested[0] or _now - _last_shot[0] > 30.0:
            pygame.image.save(screen, "/tmp/pucky_world_shot.png")
            _last_shot[0]      = _now
            _shot_requested[0] = False
        if _now - _last_web_frame[0] > 1.5:
            try:
                pygame.image.save(screen, "/tmp/pucky_world_live.jpg")
            except Exception:
                pass
            _last_web_frame[0] = _now
        if _now - _last_pos_export[0] > 3.0:
            try:
                _pos_json = json.dumps({
                    "pucky": {"x": round(pucky.gx, 2), "y": round(pucky.gy, 2),
                              "mood": pucky.state.mood, "expression": pucky.state.expression,
                              "valence": round(pucky.state.valence, 2)},
                    "loki":  {"x": round(orb.gx, 2),   "y": round(orb.gy, 2),
                              "action": orb.action},
                    "idunn": {"x": round(idunn.gx, 2), "y": round(idunn.gy, 2),
                              "present": idunn.present},
                    "zone":  zone_mgr.current_name if zone_mgr else "home",
                    "ts": _now,
                })
                _pos_tmp = _pos_export_path.with_suffix(".tmp")
                _pos_tmp.write_text(_pos_json)
                _pos_tmp.replace(_pos_export_path)
            except Exception:
                pass
            _last_pos_export[0] = _now

    save_friends(animals)
    pygame.quit()


# ══════════════════════════════════════════════════════════════════════════════
# TERMINAL VERSION
# ══════════════════════════════════════════════════════════════════════════════

def run_terminal():
    import curses, datetime

    TILE_CHARS = {
        GRASS:      (" ", " "),
        PATH:       ("░", "░"),
        WATER:      ("≈", "≈"),
        FLOWER:     ("✿", "✿"),
        TREE:       ("♣", "♣"),
        STONE:      ("·", "·"),
        APPLE_TREE: ("", ""),
        STRAWBERRY: ("✦", "✦"),
        NEST:       ("~", "~"),
        MEADOW:     ("❀", "❀"),
        SHORE:      ("∙", "∙"),
    }

    # Terminal isometric: each tile = 4 chars wide, 2 lines tall
    # x_screen = cx + (gx - gy) * 2
    # y_screen = cy + (gx + gy) * 1

    def to_term(gx, gy, cx, cy):
        return cx + (gx - gy) * 2, cy + (gx + gy) // 2

    def draw_world(stdscr, pucky_gx, pucky_gy, orb_gx, orb_gy, state):
        h, w = stdscr.getmaxyx()
        cx, cy = w // 2, 4
        stdscr.clear()

        # title
        try:
            stdscr.addstr(0, 2, "✨ Pucky's World ✨", curses.A_BOLD)
            stdscr.addstr(1, 2, f"mood: {state.mood}  soul: {state.soul}  alone: {state.hours_alone:.1f}h")
        except curses.error:
            pass

        # tiles
        for gy in range(MAP_H):
            for gx in range(MAP_W):
                tx, ty = to_term(gx, gy, cx, cy)
                if 0 <= ty < h-1 and 0 <= tx < w-2:
                    tile = WORLD_MAP[gy][gx]
                    ch, _ = TILE_CHARS.get(tile, ("?","?"))
                    try:
                        stdscr.addstr(ty, tx, ch + ch)
                    except curses.error:
                        pass

        # orb
        ox, oy = to_term(int(orb_gx), int(orb_gy), cx, cy)
        if 0 <= oy < h-1 and 0 <= ox < w-1:
            orb_ch = "✦" if state.soul == "claude" else "◦"
            try:
                stdscr.addstr(oy, ox, orb_ch, curses.A_BOLD)
            except curses.error:
                pass

        # Pucky
        px, py = to_term(int(pucky_gx), int(pucky_gy), cx, cy)
        if 0 <= py < h-1 and 0 <= px < w-2:
            try:
                stdscr.addstr(py,   px, "▄▄", curses.A_BOLD)
                if py + 1 < h:
                    stdscr.addstr(py+1, px, "██")
            except curses.error:
                pass

        # time
        now = datetime.datetime.now().strftime("%H:%M")
        try:
            stdscr.addstr(h-2, 2, f"[{now}]  q to quit")
        except curses.error:
            pass

        stdscr.refresh()

    def _run(stdscr):
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(100)

        gx, gy   = 9.5, 9.5
        tx, ty   = 9.5, 9.5
        ox, oy   = 9.5 + 3, 9.5
        angle    = 0.0
        t        = 0.0
        last_st  = 0.0
        state    = read_state()

        while True:
            key = stdscr.getch()
            if key in (ord('q'), ord('Q'), 27):
                break

            dt = 0.1
            t += dt
            angle += dt * 0.4

            now = time.time()
            if now - last_st > 5.0:
                state   = read_state()
                last_st = now

            # move
            mood = state.mood
            spd = 0.02 if mood in ("sad","lonely","crying") else 0.04
            dx, dy = tx - gx, ty - gy
            dist = math.hypot(dx, dy)
            if dist < 0.2:
                if random.random() < 0.05:
                    for _ in range(20):
                        nx = gx + random.uniform(-4, 4)
                        ny = gy + random.uniform(-4, 4)
                        nx = max(1, min(MAP_W-2, nx))
                        ny = max(1, min(MAP_H-2, ny))
                        if WORLD_MAP[int(ny)][int(nx)] in WALKABLE:
                            tx, ty = nx, ny
                            break
            else:
                gx += (dx/dist) * spd
                gy += (dy/dist) * spd

            # orb orbit
            dist_orb = 2.5 if mood not in ("sad","lonely") else 1.5
            ox = gx + math.cos(angle) * dist_orb
            oy = gy + math.sin(angle) * dist_orb * 0.5

            draw_world(stdscr, gx, gy, ox, oy, state)

    curses.wrapper(_run)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--terminal" in sys.argv:
        run_terminal()
    else:
        run_pygame()
