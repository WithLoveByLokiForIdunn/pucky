"""
pucky_garden.py — The garden behind the cottage.

A separate screen showing garden rows where seeds are planted and tended.
Plants grow over real time; each kind has its own shape and colour.
Seeds come from apples falling, from the meadow, and from visiting friends.

Growth timeline (minutes of real elapsed time):
  Seed → Sprout:  20 min
  Sprout → Growing: 30 min (10 with fertilizer)
  Growing → Ready:  40 min (needs at least one watering while growing)
  Ready stays: 120 min, then wilts if not picked

Enter via G key in pygame or enter_garden web command.
"""

import json
import math
import random
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

GARDEN_FILE = Path("/home/bmo/pucky/workspace/garden.json")

ROWS = 4
COLS = 6

# Minutes from planted_at to each stage
_STAGE_MINUTES = [20, 30, 40]   # seed→sprout, sprout→growing, growing→ready
_WILT_MINUTES  = 120            # ready → wilted if not picked

# What each plant looks like and yields
PLANT_KINDS = {
    "apple":       {"colour": (200,  60,  60), "yield": "apple",      "leaf": (60,130,50)},
    "strawberry":  {"colour": (220,  40,  80), "yield": "strawberry", "leaf": (60,150,40)},
    "moonflower":  {"colour": (200, 180, 255), "yield": "moonflower", "leaf": (80, 80,160)},
    "sunflower":   {"colour": (255, 210,  50), "yield": "sunflower",  "leaf": (90,160,40)},
    "herb":        {"colour": (120, 210, 130), "yield": "herb",       "leaf": (50,130,60)},
    "carrot":      {"colour": (255, 130,  30), "yield": "carrot",     "leaf": (60,150,40)},
    "pea":         {"colour": (160, 210,  90), "yield": "pea",        "leaf": (50,140,50)},
}


@dataclass
class Plot:
    kind:              str
    stage:             int   = 0      # 0=seed 1=sprout 2=growing 3=ready 4=wilted
    planted_at:        float = field(default_factory=time.time)
    last_watered:      float = 0.0    # epoch; 0 = never watered
    fertilized:        bool  = False
    watered_in_stage2: bool  = False  # must water at least once while growing

    def minutes_elapsed(self) -> float:
        return (time.time() - self.planted_at) / 60.0

    def advance(self) -> bool:
        """Update stage based on elapsed time. Returns True if stage changed."""
        if self.stage >= 4:
            return False
        m = self.minutes_elapsed()
        changed = False
        if self.stage == 0 and m >= _STAGE_MINUTES[0]:
            self.stage = 1; changed = True
        elif self.stage == 1:
            threshold = _STAGE_MINUTES[1] // 3 if self.fertilized else _STAGE_MINUTES[1]
            if m >= _STAGE_MINUTES[0] + threshold:
                self.stage = 2; changed = True
        elif self.stage == 2:
            grow_min  = _STAGE_MINUTES[0] + (
                _STAGE_MINUTES[1] // 3 if self.fertilized else _STAGE_MINUTES[1])
            if self.watered_in_stage2 and m >= grow_min + _STAGE_MINUTES[2]:
                self.stage = 3; changed = True
        elif self.stage == 3:
            ready_at = (self.planted_at
                        + (_STAGE_MINUTES[0] + _STAGE_MINUTES[1] + _STAGE_MINUTES[2]) * 60)
            if time.time() - ready_at > _WILT_MINUTES * 60:
                self.stage = 4; changed = True
        return changed

    def water(self) -> str:
        if self.stage == 0:
            return "the seed is still sleeping."
        if self.stage >= 3:
            return "it doesn't need water now."
        self.last_watered = time.time()
        if self.stage == 2:
            self.watered_in_stage2 = True
        return "watered. ♥"

    def fertilize(self) -> str:
        if self.stage == 0:
            return "too early — let it sprout first."
        if self.stage >= 2:
            return "it's past the seedling stage."
        self.fertilized = True
        return "fertilized! it will grow faster."

    def needs_water(self) -> bool:
        if self.stage not in (1, 2):
            return False
        return (time.time() - self.last_watered) > 45 * 60   # 45 min without water

    def needs_fertilizer(self) -> bool:
        return self.stage == 1 and not self.fertilized

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Plot":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


def _load_garden() -> tuple[list, dict]:
    """Returns (plots[row][col], seeds{kind: count})."""
    try:
        raw = json.loads(GARDEN_FILE.read_text())
        plots = []
        for row in raw.get("plots", []):
            plots.append([Plot.from_dict(c) if c else None for c in row])
        # Pad to ROWS × COLS
        while len(plots) < ROWS:
            plots.append([None] * COLS)
        for r in plots:
            while len(r) < COLS:
                r.append(None)
        seeds = raw.get("seeds", {})
        return plots, seeds
    except Exception:
        return [[None] * COLS for _ in range(ROWS)], {}


def _save_garden(plots: list, seeds: dict) -> None:
    data = {
        "plots": [[p.to_dict() if p else None for p in row] for row in plots],
        "seeds": seeds,
    }
    tmp = GARDEN_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(GARDEN_FILE)


def add_seed(kind: str, count: int = 1) -> None:
    """Add seed(s) to the garden inventory from outside (visitor gift, etc.)."""
    plots, seeds = _load_garden()
    seeds[kind] = seeds.get(kind, 0) + count
    _save_garden(plots, seeds)


class GardenView:
    """Full-screen garden view — entered via G key or enter_garden web command."""

    # Earthy background colours
    BG       = (62,  44,  28)
    ROW_SOIL = (88,  62,  38)
    ROW_DARK = (72,  50,  30)
    HINT_COL = (200, 185, 155)
    CURSOR   = (220, 200, 130, 160)
    MSG_COL  = (230, 210, 170)

    def __init__(self, win_w: int, win_h: int):
        self.win_w = win_w
        self.win_h = win_h
        self.plots, self.seeds = _load_garden()
        self.cursor_r = 0
        self.cursor_c = 0
        self.message  = ""
        self.msg_life = 0.0
        self.t        = 0.0
        self._plant_mode: Optional[str] = None   # kind being planted, or None
        self._font_sm = None
        self._font_md = None
        self._font_lg = None
        self._dirty   = False

    # ── Layout helpers ──────────────────────────────────────────────────────

    def _cell_rect(self, r: int, c: int) -> tuple[int, int, int, int]:
        """Return (x, y, w, h) of a cell in screen coordinates."""
        pad_x = int(self.win_w * 0.08)
        pad_y = int(self.win_h * 0.18)
        avail_w = self.win_w - pad_x * 2
        avail_h = int(self.win_h * 0.60)
        cw = avail_w  // COLS
        ch = avail_h  // ROWS
        return (pad_x + c * cw, pad_y + r * ch, cw, ch)

    # ── Draw ────────────────────────────────────────────────────────────────

    def draw(self, surf) -> None:
        import pygame
        if self._font_sm is None:
            self._font_sm = pygame.font.SysFont("monospace", 11)
            self._font_md = pygame.font.SysFont("monospace", 13)
            self._font_lg = pygame.font.SysFont("monospace", 16)

        surf.fill(self.BG)

        # Title
        title = self._font_lg.render("the garden", True, (220, 200, 150))
        surf.blit(title, (self.win_w // 2 - title.get_width() // 2, 14))

        # Seed inventory line
        seed_parts = [f"{k}:{v}" for k, v in self.seeds.items() if v > 0]
        seed_txt = "seeds: " + (", ".join(seed_parts) if seed_parts else "none")
        st = self._font_sm.render(seed_txt, True, (170, 155, 130))
        surf.blit(st, (self.win_w // 2 - st.get_width() // 2, 36))

        # Garden rows
        for r in range(ROWS):
            x, y, cw, ch = self._cell_rect(r, 0)
            row_w = cw * COLS
            # soil background alternating shade
            soil_c = self.ROW_SOIL if r % 2 == 0 else self.ROW_DARK
            pygame.draw.rect(surf, soil_c, (x, y, row_w, ch))
            # soil texture lines
            for _li in range(3):
                _ly = y + ch // 4 + _li * (ch // 4)
                pygame.draw.line(surf, (max(0, soil_c[0]-10), max(0, soil_c[1]-8),
                                        max(0, soil_c[2]-6)), (x+4, _ly), (x+row_w-4, _ly), 1)

        # Cells
        for r in range(ROWS):
            for c in range(COLS):
                cx, cy, cw, ch = self._cell_rect(r, c)
                plot = self.plots[r][c]

                # cursor
                if r == self.cursor_r and c == self.cursor_c:
                    _cs = pygame.Surface((cw, ch), pygame.SRCALPHA)
                    _cs.fill((*self.CURSOR[:3], int(self.CURSOR[3] * (0.6 + 0.4 * math.sin(self.t * 3)))))
                    surf.blit(_cs, (cx, cy))

                # cell border
                pygame.draw.rect(surf, (100, 78, 50), (cx, cy, cw, ch), 1)

                if plot is None:
                    # empty — show + if in plant mode
                    if self._plant_mode and r == self.cursor_r and c == self.cursor_c:
                        pm = self._font_md.render("+", True, (160, 200, 120))
                        surf.blit(pm, (cx + cw//2 - pm.get_width()//2, cy + ch//2 - pm.get_height()//2))
                    continue

                self._draw_plant(surf, plot, cx + cw//2, cy + ch - 8, ch, c)

                # need-indicator dots
                if plot.needs_water():
                    _wdot = pygame.Surface((6, 6), pygame.SRCALPHA)
                    pygame.draw.circle(_wdot, (80, 160, 240, 210), (3, 3), 3)
                    surf.blit(_wdot, (cx + cw - 8, cy + 4))
                if plot.needs_fertilizer():
                    _fdot = pygame.Surface((6, 6), pygame.SRCALPHA)
                    pygame.draw.circle(_fdot, (180, 220, 80, 200), (3, 3), 3)
                    surf.blit(_fdot, (cx + cw - 16, cy + 4))

        # Status panel for selected cell
        self._draw_status(surf)

        # Action bar
        self._draw_action_bar(surf)

        # Message
        if self.msg_life > 0:
            alpha = min(255, int(self.msg_life * 255))
            mt = self._font_md.render(self.message, True, self.MSG_COL)
            ms = pygame.Surface((mt.get_width() + 16, mt.get_height() + 8), pygame.SRCALPHA)
            ms.fill((20, 14, 8, min(200, alpha)))
            ms.blit(mt, (8, 4))
            surf.blit(ms, (self.win_w//2 - ms.get_width()//2,
                           int(self.win_h * 0.84)))

    def _draw_plant(self, surf, plot: Plot, cx: int, cy: int, cell_h: int, col: int) -> None:
        import pygame
        kind  = PLANT_KINDS.get(plot.kind, PLANT_KINDS["herb"])
        fc    = kind["colour"]
        lc    = kind["leaf"]
        stage = plot.stage
        rng   = random.Random(col * 13 + plot.planted_at)
        sway  = math.sin(self.t * 1.2 + col * 0.7) * 2

        if stage == 0:   # seed — tiny brown oval in soil
            pygame.draw.ellipse(surf, (110, 80, 50), (cx-3, cy-3, 6, 4))

        elif stage == 1:  # sprout — two small leaves
            pygame.draw.line(surf, lc, (cx, cy), (cx+int(sway), cy-12), 2)
            pygame.draw.ellipse(surf, lc, (cx-6+int(sway), cy-16, 8, 5))
            pygame.draw.ellipse(surf, lc, (cx+int(sway), cy-16, 8, 5))

        elif stage == 2:  # growing — taller stem, leaves
            stem_h = int(cell_h * 0.45)
            pygame.draw.line(surf, (70,120,50), (cx, cy), (cx+int(sway), cy-stem_h), 2)
            for i in range(2):
                side = 1 if i == 0 else -1
                lx = cx + side*10 + int(sway * 0.5)
                ly = cy - stem_h//2 - i*6
                pygame.draw.ellipse(surf, lc, (lx-7, ly-4, 14, 8))

        elif stage == 3:  # ready — full plant with fruit/flower
            stem_h = int(cell_h * 0.48)
            pygame.draw.line(surf, (70,120,50), (cx, cy), (cx+int(sway), cy-stem_h), 2)
            for i in range(2):
                side = 1 if i == 0 else -1
                lx = cx + side*11 + int(sway * 0.4)
                ly = cy - stem_h // 2 - i*5
                pygame.draw.ellipse(surf, lc, (lx-7, ly-4, 14, 8))
            # fruit / flower at top
            bloom = int(abs(math.sin(self.t * 1.5)) * 12) + 28
            if plot.kind in ("moonflower", "sunflower"):
                # flower petals
                for p in range(6):
                    ang = p / 6 * math.pi * 2 + self.t * 0.3
                    px2 = cx + int(math.cos(ang)*7) + int(sway)
                    py2 = cy - stem_h - 2 + int(math.sin(ang)*5)
                    pygame.draw.circle(surf, fc, (px2, py2), 4)
                pygame.draw.circle(surf, (255,240,100) if plot.kind=="sunflower" else (200,180,255),
                                   (cx+int(sway), cy-stem_h-2), 5)
            else:
                # round fruit — bob gently
                fy = cy - stem_h - 3 + int(math.sin(self.t*2)*1.5)
                pygame.draw.circle(surf, fc, (cx+int(sway), fy), 6)
                pygame.draw.circle(surf, (min(255,fc[0]+60), min(255,fc[1]+40), min(255,fc[2]+40)),
                                   (cx+int(sway)-2, fy-2), 2)

        elif stage == 4:  # wilted — drooping brown
            pygame.draw.line(surf, (100,80,50), (cx, cy), (cx-4, cy-8), 2)
            pygame.draw.ellipse(surf, (120,90,55), (cx-8, cy-12, 10, 5))
            pygame.draw.ellipse(surf, (110,80,45), (cx-2, cy-10, 10, 5))

    def _draw_status(self, surf) -> None:
        import pygame
        r, c   = self.cursor_r, self.cursor_c
        plot   = self.plots[r][c]
        stage_names = ["seed", "sprouting", "growing", "ready to pick!", "wilted"]
        if plot:
            lines = [
                f"{plot.kind}  —  {stage_names[min(plot.stage, 4)]}",
                ("needs water  " if plot.needs_water() else "")
                + ("needs fertilizer" if plot.needs_fertilizer() else ""),
            ]
        elif self._plant_mode:
            lines = [f"plant {self._plant_mode} here? [Enter] yes  [X] cancel"]
        else:
            lines = ["empty  [P] to plant a seed here"]

        bx, by = 12, self.win_h - 90
        for i, ln in enumerate(lines):
            if ln.strip():
                lt = self._font_sm.render(ln.strip(), True, self.HINT_COL)
                surf.blit(lt, (bx, by + i * 16))

    def _draw_action_bar(self, surf) -> None:
        import pygame
        actions = "[↑↓←→] move   [W] water   [F] fertilize   [P] plant   [X] pick/clear   [Esc] leave"
        at = self._font_sm.render(actions, True, (160, 148, 128))
        surf.blit(at, (self.win_w//2 - at.get_width()//2, self.win_h - 20))

    # ── Update ──────────────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        self.t += dt
        if self.msg_life > 0:
            self.msg_life -= dt
        # Advance plant stages (cheap — just arithmetic on timestamps)
        _any_changed = False
        for row in self.plots:
            for p in row:
                if p and p.advance():
                    _any_changed = True
        if _any_changed:
            self._dirty = True
        # Lazy save every ~30s if dirty
        if self._dirty and (int(self.t) % 30 == 0):
            self._save()
            self._dirty = False

    def _say(self, msg: str) -> None:
        self.message  = msg
        self.msg_life = 3.5

    def _save(self) -> None:
        try:
            _save_garden(self.plots, self.seeds)
        except Exception:
            pass

    # ── Input ───────────────────────────────────────────────────────────────

    def handle_event(self, event) -> Optional[str]:
        """Returns 'exit' to leave, None to stay."""
        import pygame
        if event.type != pygame.KEYDOWN:
            return None
        key = event.key

        if key == pygame.K_ESCAPE:
            self._save()
            return "exit"

        if key == pygame.K_UP:
            self.cursor_r = (self.cursor_r - 1) % ROWS
        elif key == pygame.K_DOWN:
            self.cursor_r = (self.cursor_r + 1) % ROWS
        elif key == pygame.K_LEFT:
            self.cursor_c = (self.cursor_c - 1) % COLS
        elif key == pygame.K_RIGHT:
            self.cursor_c = (self.cursor_c + 1) % COLS

        elif key == pygame.K_w:
            p = self.plots[self.cursor_r][self.cursor_c]
            if p:
                self._say(p.water())
                self._dirty = True
            else:
                self._say("nothing to water here.")

        elif key == pygame.K_f:
            p = self.plots[self.cursor_r][self.cursor_c]
            if p:
                self._say(p.fertilize())
                self._dirty = True
            else:
                self._say("plant a seed first.")

        elif key == pygame.K_p:
            p = self.plots[self.cursor_r][self.cursor_c]
            if p is None:
                # Plant a seed — pick the first available kind
                available = [k for k, v in self.seeds.items() if v > 0]
                if not available:
                    self._say("no seeds yet. make a friend in the wilds.")
                else:
                    kind = available[0]
                    self.plots[self.cursor_r][self.cursor_c] = Plot(kind=kind)
                    self.seeds[kind] = max(0, self.seeds.get(kind, 0) - 1)
                    self._say(f"planted {kind}. give it time.")
                    self._dirty = True
            else:
                self._say("there's already something growing here.")

        elif key == pygame.K_x:
            p = self.plots[self.cursor_r][self.cursor_c]
            if p is None:
                self._say("nothing here.")
            elif p.stage == 3:
                # Pick it
                yield_name = PLANT_KINDS.get(p.kind, {}).get("yield", p.kind)
                self.plots[self.cursor_r][self.cursor_c] = None
                self._say(f"you picked the {yield_name}. ♥")
                self._dirty = True
            elif p.stage == 4:
                # Clear wilted
                self.plots[self.cursor_r][self.cursor_c] = None
                self._say("cleared. the soil is ready again.")
                self._dirty = True
            else:
                self._say("not ready yet — let it grow.")

        elif key == pygame.K_RETURN:
            # Confirm planting in plant mode (currently handled by P above)
            pass

        return None

    def handle_web_key(self, key_name: str, char: str) -> Optional[str]:
        """Handle key from web portal. Same logic as handle_event."""
        import pygame
        _key_map = {
            "Escape": pygame.K_ESCAPE,
            "ArrowUp": pygame.K_UP, "ArrowDown": pygame.K_DOWN,
            "ArrowLeft": pygame.K_LEFT, "ArrowRight": pygame.K_RIGHT,
            "w": pygame.K_w, "f": pygame.K_f,
            "p": pygame.K_p, "x": pygame.K_x,
            "Enter": pygame.K_RETURN,
        }
        k = _key_map.get(key_name) or _key_map.get(char.lower() if char else "")
        if k is None:
            return None

        class _FakeEvent:
            type = pygame.KEYDOWN
            def __init__(self, key): self.key = key

        return self.handle_event(_FakeEvent(k))
