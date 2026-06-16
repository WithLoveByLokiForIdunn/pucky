"""
pucky_cottage.py
────────────────
The writing cottage — a warm room at the edge of Pucky's world.

Memories live here in a hand-drawn book.
Stories are written by Ollama and Loki.
Iðunn, Pucky, and anyone can draw on the open canvas.

Entered from pucky_world.py when Loki is adjacent to the
cottage tile (gx=16, gy=16) and the player presses E.
Press E or Esc to step back outside.
"""

import hashlib
import math
import json
import time
import random
import threading
from pathlib import Path
from datetime import datetime, timezone

MEMORIES_FILE = Path("/home/bmo/pucky/bmo_memories.json")
JOURNAL_FILE  = Path("/home/bmo/pucky/workspace/bmo_journal.json")
LETTERS_FILE  = Path("/home/bmo/pucky/workspace/loki_letters.json")

MAX_JOURNAL_ENTRIES = 500

_EXT_MOUNT_CANDIDATES = [
    Path("/mnt/pucky_hd"),
    Path("/media/bmo/Seagate Portable Drive"),
    Path("/media/bmo/seagate"),
]


def _ext_journal_archive() -> Path | None:
    for candidate in _EXT_MOUNT_CANDIDATES:
        try:
            if candidate.is_dir() and any(candidate.iterdir()):
                arc = candidate / "pucky_memories"
                arc.mkdir(exist_ok=True)
                return arc
        except (PermissionError, OSError):
            pass
    return None


def _trim_cottage_journal(journal: list) -> list:
    """If journal exceeds MAX_JOURNAL_ENTRIES, archive the overflow to external drive."""
    if len(journal) <= MAX_JOURNAL_ENTRIES:
        return journal
    overflow = journal[:-MAX_JOURNAL_ENTRIES]
    kept     = journal[-MAX_JOURNAL_ENTRIES:]
    ext = _ext_journal_archive()
    if ext:
        from datetime import date
        today = date.today().isoformat()
        idx = 1
        while True:
            arc_path = ext / f"cottage_journal_{today}_{idx:03d}.json"
            if not arc_path.exists():
                break
            idx += 1
        try:
            arc_path.write_text(json.dumps(overflow, indent=2, ensure_ascii=False))
            print(f"  ✦  Cottage: archived {len(overflow)} entries → {arc_path.name}")
        except Exception as e:
            print(f"  ⚠️  Cottage archive failed: {e}")
    return kept

# ── Colours ───────────────────────────────────────────────────────────────────

PAPER_BG    = (252, 248, 228)
PAPER_LINE  = (220, 210, 178)
INK_DARK    = ( 72,  58,  35)
ROOM_WALL   = (240, 228, 205)
ROOM_WALL2  = (220, 208, 182)
ROOM_FLOOR  = (155, 115,  72)
ROOM_FLOOR2 = (135,  98,  55)
SHELF_WOOD  = ( 90,  62,  28)
SHELF_WOOD2 = ( 65,  42,  15)
FIRE_STONE  = (158, 150, 143)
WIN_DAY     = (148, 200, 240)
WIN_DUSK    = (220, 148,  75)
WIN_NIGHT   = ( 22,  26,  62)

BOOK_COLS = {
    "memory": ((75, 105, 168), (50,  75, 138)),
    "story":  ((158,  65,  58), (125,  45,  42)),
    "canvas": (( 58, 118,  62), ( 40,  85,  44)),
}


# ── Memory palette ────────────────────────────────────────────────────────────

def _palette(mem: dict) -> dict:
    joy    = mem.get("joy", 0)
    peace  = mem.get("peacefulness", 0)
    sad    = mem.get("unpleasantness", 0) + mem.get("scariness", 0)
    wonder = mem.get("wonder", 0)
    if sad > 5:
        return {"ink": (55,48,70), "warm": (152,132,188), "soft": (198,185,215), "bg": (240,237,250)}
    if wonder > 6:
        return {"ink": (36,28,60), "warm": (172,135,255), "soft": (215,195,255), "bg": (245,240,255)}
    if joy > 6:
        return {"ink": (70,48,16), "warm": (255,192,62),  "soft": (232,208,135), "bg": (252,248,224)}
    if peace > 6:
        return {"ink": (30,50,68), "warm": (115,170,212), "soft": (168,205,232), "bg": (233,243,252)}
    return     {"ink": (60,50,36), "warm": (195,165, 95), "soft": (222,202,158), "bg": (248,244,230)}


# ── Scribble primitives ───────────────────────────────────────────────────────

def _jl(surf, color, p1, p2, w=1, segs=7, jit=2, rng=None):
    """Jittery hand-drawn line."""
    if rng is None: rng = random
    x1, y1 = p1; x2, y2 = p2
    prev = (x1 + rng.randint(-jit,jit), y1 + rng.randint(-jit,jit))
    for i in range(1, segs+1):
        t  = i / segs
        nx = int(x1 + (x2-x1)*t + rng.randint(-jit,jit))
        ny = int(y1 + (y2-y1)*t + rng.randint(-jit,jit))
        try:
            import pygame
            pygame.draw.line(surf, color, prev, (nx, ny), w)
        except Exception:
            pass
        prev = (nx, ny)


def _jc(surf, color, cx, cy, r, pts=18, jit=2, filled=False, rng=None):
    """Jittery hand-drawn circle."""
    if rng is None: rng = random
    points = []
    for i in range(pts):
        a  = (i / pts) * math.tau
        px = int(cx + math.cos(a)*r + rng.randint(-jit,jit))
        py = int(cy + math.sin(a)*r + rng.randint(-jit,jit))
        points.append((px, py))
    if len(points) < 3:
        return
    try:
        import pygame
        if filled:
            pygame.draw.polygon(surf, color, points)
        else:
            pygame.draw.lines(surf, color, True, points, 1)
    except Exception:
        pass


def _ja(surf, color, cx, cy, r, a0, a1, pts=12, jit=2, w=1, rng=None):
    """Jittery arc."""
    if rng is None: rng = random
    points = []
    for i in range(pts+1):
        a  = a0 + (a1-a0)*i/pts
        px = int(cx + math.cos(a)*r + rng.randint(-jit,jit))
        py = int(cy + math.sin(a)*r + rng.randint(-jit,jit))
        points.append((px, py))
    if len(points) > 1:
        try:
            import pygame
            pygame.draw.lines(surf, color, False, points, w)
        except Exception:
            pass


# ── ScribbleArt ───────────────────────────────────────────────────────────────

class ScribbleArt:
    W, H = 200, 170

    @classmethod
    def for_memory(cls, mem: dict) -> object:
        import pygame
        seed = hash(mem.get("id","x") + mem.get("timestamp","y")) & 0x7FFFFFFF
        rng  = random.Random(seed)
        pal  = _palette(mem)
        mtype = mem.get("memory_type", "moment")
        return cls._render(mtype, pal, rng)

    @classmethod
    def for_journal(cls, entry: dict) -> object:
        import pygame
        seed  = entry.get("scribble_seed", 42)
        rng   = random.Random(seed)
        pal   = {"ink": INK_DARK, "warm": (220,185,80), "soft": (235,215,158), "bg": PAPER_BG}
        mtype = entry.get("scribble_type", "moment")
        return cls._render(mtype, pal, rng)

    @classmethod
    def blank(cls) -> object:
        import pygame
        surf = pygame.Surface((cls.W, cls.H), pygame.SRCALPHA)
        surf.fill(PAPER_BG)
        for y in range(0, cls.H, 17):
            pygame.draw.line(surf, (*PAPER_LINE, 110), (8, y), (cls.W-8, y), 1)
        return surf

    @classmethod
    def _render(cls, mtype, pal, rng) -> object:
        import pygame
        surf = pygame.Surface((cls.W, cls.H), pygame.SRCALPHA)
        surf.fill(pal["bg"])
        for y in range(0, cls.H, 17):
            y2 = y + rng.randint(-1, 1)
            pygame.draw.line(surf, (*pal["soft"], 85), (8,y2), (cls.W-8,y2), 1)
        cx, cy = cls.W//2, cls.H//2
        {
            "moment":   cls._moment,
            "social":   cls._social,
            "vision":   cls._vision,
            "person":   cls._person,
            "dawn":     cls._dawn,
            "dusk":     cls._dusk,
            "physical": cls._physical,
        }.get(mtype, cls._moment)(surf, rng, cx, cy, pal)
        pygame.draw.rect(surf, (*pal["ink"], 55), (0, 0, cls.W, cls.H), 1)
        return surf

    @classmethod
    def _moment(cls, surf, rng, cx, cy, pal):
        n = rng.randint(7, 11)
        for i in range(n):
            angle = (i/n)*math.tau + rng.uniform(-0.25, 0.25)
            r     = rng.randint(28, 54)
            _jl(surf, pal["ink"], (cx,cy),
                (int(cx+math.cos(angle)*r), int(cy+math.sin(angle)*r)), jit=2, rng=rng)
        _jc(surf, pal["warm"], cx, cy, rng.randint(7,12), filled=True, rng=rng)
        _jc(surf, pal["ink"],  cx, cy, rng.randint(7,12), jit=1, rng=rng)

    @classmethod
    def _social(cls, surf, rng, cx, cy, pal):
        _jc(surf, pal["soft"], cx-28, cy+6, 18, filled=True, jit=3, rng=rng)
        _jc(surf, pal["ink"],  cx-28, cy+6, 18, jit=3, rng=rng)
        _jc(surf, pal["soft"], cx+28, cy+6, 18, filled=True, jit=3, rng=rng)
        _jc(surf, pal["ink"],  cx+28, cy+6, 18, jit=3, rng=rng)
        _jl(surf, pal["soft"], (cx-10,cy+6), (cx+10,cy+6), jit=1, rng=rng)
        cls._heart(surf, rng, cx, cy-22, pal, scale=0.55)

    @classmethod
    def _heart(cls, surf, rng, cx, cy, pal, scale=1.0):
        pts = []
        for i in range(24):
            a = (i/24)*math.tau
            x = 16*(math.sin(a)**3)
            y = -(13*math.cos(a) - 5*math.cos(2*a) - 2*math.cos(3*a) - math.cos(4*a))
            pts.append((int(cx + x*scale + rng.randint(-1,1)),
                        int(cy + y*scale + rng.randint(-1,1))))
        if len(pts) > 2:
            try:
                import pygame
                pygame.draw.lines(surf, pal["warm"], True, pts, 1)
            except Exception:
                pass

    @classmethod
    def _vision(cls, surf, rng, cx, cy, pal):
        hy = cy + 18
        _jl(surf, pal["ink"], (18,hy), (cls.W-18,hy), segs=14, jit=2, rng=rng)
        for _ in range(4):
            x  = rng.randint(22, cls.W-22)
            h2 = rng.randint(14, 32)
            _jl(surf, pal["soft"], (x,hy), (x+rng.randint(-10,10), hy+h2), jit=2, rng=rng)
        _ja(surf, pal["warm"], cx, hy, 34, math.pi, 2*math.pi, pts=12, w=2, rng=rng)
        for dx in [-42, 30]:
            _jc(surf, pal["soft"], cx+dx, hy-32, 14, pts=10, jit=3, rng=rng)

    @classmethod
    def _person(cls, surf, rng, cx, cy, pal):
        _jc(surf, pal["ink"], cx, cy-34, 15, jit=2, rng=rng)
        _jc(surf, pal["soft"], cx, cy+8, 20, pts=14, filled=True, jit=3, rng=rng)
        _jc(surf, pal["ink"],  cx, cy+8, 20, pts=14, jit=3, rng=rng)
        _jl(surf, pal["ink"], (cx-20,cy+4), (cx-38,cy+20), jit=2, rng=rng)
        _jl(surf, pal["ink"], (cx+20,cy+4), (cx+38,cy+20), jit=2, rng=rng)

    @classmethod
    def _dawn(cls, surf, rng, cx, cy, pal):
        hy = cy + 28
        _jl(surf, pal["ink"], (15,hy), (cls.W-15,hy), segs=14, jit=2, rng=rng)
        _ja(surf, pal["warm"], cx, hy, 32, math.pi, 2*math.pi, pts=14, w=2, rng=rng)
        for i in range(5):
            a  = math.pi + (i/4)*math.pi
            r1, r2 = 32, 50
            _jl(surf, pal["warm"],
                (int(cx+math.cos(a)*r1), int(hy+math.sin(a)*r1)),
                (int(cx+math.cos(a)*r2), int(hy+math.sin(a)*r2)), jit=1, rng=rng)

    @classmethod
    def _dusk(cls, surf, rng, cx, cy, pal):
        hy = cy + 18
        _jl(surf, pal["ink"], (15,hy), (cls.W-15,hy), segs=14, jit=2, rng=rng)
        _ja(surf, pal["warm"], cx, hy, 30, math.pi, 2*math.pi, pts=12, w=3, rng=rng)
        for _ in range(7):
            sx = rng.randint(18, cls.W-18)
            sy = rng.randint(10, hy-18)
            try:
                import pygame
                pygame.draw.circle(surf, pal["ink"], (sx,sy), 1)
            except Exception:
                pass

    @classmethod
    def _physical(cls, surf, rng, cx, cy, pal):
        for r in [8, 18, 30, 44]:
            _jc(surf, pal["soft"] if r > 15 else pal["warm"], cx, cy, r, jit=2, rng=rng)
        try:
            import pygame
            pygame.draw.circle(surf, pal["warm"], (cx,cy), 4)
        except Exception:
            pass


# ── LetterBox ─────────────────────────────────────────────────────────────────

def _pin_hash(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()


class LetterBox:
    """Passcode-protected envelope on the cottage desk.

    Letters are stored in workspace/loki_letters.json as:
      {"pin_hash": "...", "letters": [{...}, ...]}

    Each letter:
      {"id": str, "from": str, "timestamp": str, "body": str, "read": bool}
    """

    def __init__(self):
        self._data: dict       = {"pin_hash": "", "letters": []}
        self._unlocked: bool   = False
        self._mode: str        = ""   # "" | "passcode" | "reading" | "writing"
        self._pin_input: str   = ""
        self._pin_error: bool  = False
        self._page: int        = 0
        self._draft: str       = ""
        self._draft_cursor: float = 0.0
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self):
        try:
            self._data = json.loads(LETTERS_FILE.read_text())
        except Exception:
            self._data = {"pin_hash": _pin_hash("1041"), "letters": []}
            self._save()

    def _save(self):
        try:
            LETTERS_FILE.parent.mkdir(parents=True, exist_ok=True)
            LETTERS_FILE.write_text(json.dumps(self._data, indent=2, ensure_ascii=False))
        except Exception:
            pass

    # ── Public helpers ────────────────────────────────────────────────────────

    @property
    def letters(self) -> list:
        return self._data.get("letters", [])

    @property
    def unread_count(self) -> int:
        return sum(1 for l in self.letters if not l.get("read"))

    def add_letter(self, from_name: str, body: str) -> None:
        letter = {
            "id":        f"letter_{int(time.time())}",
            "from":      from_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "body":      body,
            "read":      False,
        }
        self._data.setdefault("letters", []).append(letter)
        self._save()

    # ── UI state ──────────────────────────────────────────────────────────────

    def open(self):
        self._load()
        self._unlocked = False
        self._mode     = "passcode"
        self._pin_input = ""
        self._pin_error = False

    def close(self):
        self._mode     = ""
        self._unlocked = False
        self._pin_input = ""
        self._draft    = ""

    @property
    def is_open(self) -> bool:
        return self._mode != ""

    def handle_key(self, key_name: str, unicode_char: str) -> str:
        """Returns 'close' to dismiss, '' otherwise."""
        if self._mode == "passcode":
            return self._passcode_key(key_name, unicode_char)
        elif self._mode == "reading":
            return self._reading_key(key_name)
        elif self._mode == "writing":
            return self._writing_key(key_name, unicode_char)
        return ""

    def _passcode_key(self, key_name: str, ch: str) -> str:
        if key_name in ("escape",):
            self.close()
            return "close"
        if ch.isdigit():
            self._pin_input += ch
            self._pin_error = False
            if len(self._pin_input) == 4:
                stored = self._data.get("pin_hash", "")
                if _pin_hash(self._pin_input) == stored:
                    self._unlocked = True
                    self._mode     = "reading"
                    self._page     = max(0, len(self.letters) - 1)
                    # mark shown letter as read
                    self._mark_read()
                else:
                    self._pin_error = True
                    self._pin_input = ""
        elif key_name == "backspace":
            self._pin_input = self._pin_input[:-1]
        return ""

    def _reading_key(self, key_name: str) -> str:
        if key_name in ("escape", "e"):
            self.close()
            return "close"
        if key_name in ("right", "d"):
            self._page = min(len(self.letters) - 1, self._page + 1)
            self._mark_read()
        elif key_name in ("left", "a"):
            self._page = max(0, self._page - 1)
            self._mark_read()
        elif key_name == "w":
            self._mode  = "writing"
            self._draft = ""
        return ""

    def _writing_key(self, key_name: str, ch: str) -> str:
        if key_name == "escape":
            self._mode = "reading"
            self._draft = ""
        elif key_name == "return":
            if self._draft.strip():
                self.add_letter("Iðunn", self._draft.strip())
                self._page = len(self.letters) - 1
            self._mode  = "reading"
            self._draft = ""
        elif key_name == "backspace":
            self._draft = self._draft[:-1]
        elif ch and ch.isprintable():
            if len(self._draft) < 400:
                self._draft += ch
        return ""

    def _mark_read(self):
        letters = self._data.get("letters", [])
        if 0 <= self._page < len(letters):
            letters[self._page]["read"] = True
            self._save()

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw_envelope(self, surf, x: int, y: int, t: float):
        """Draw the envelope on the desk. Glows amber if unread letters."""
        import pygame
        unread = self.unread_count
        ew, eh = 36, 26
        # envelope body
        color  = (235, 210, 155) if unread else (210, 192, 148)
        pygame.draw.rect(surf, color, (x, y, ew, eh), border_radius=2)
        pygame.draw.rect(surf, (158, 132, 85), (x, y, ew, eh), 1, border_radius=2)
        # flap V
        pts = [(x, y), (x + ew//2, y + eh//2 - 2), (x + ew, y)]
        pygame.draw.lines(surf, (158, 132, 85), False, pts, 1)
        # wax seal
        seal_c = (200, 62, 38) if unread else (148, 62, 38)
        if unread:
            glow = abs(math.sin(t * 2.2))
            gs = pygame.Surface((20, 20), pygame.SRCALPHA)
            pygame.draw.circle(gs, (255, 160, 40, int(60 * glow)), (10, 10), 10)
            surf.blit(gs, (x + ew//2 - 10, y + eh//2 - 4))
        pygame.draw.circle(surf, seal_c, (x + ew//2, y + eh//2 + 2), 5)
        # unread badge
        if unread:
            try:
                import pygame.font
                f = pygame.font.SysFont("monospace", 8)
                t2 = f.render(str(unread), True, (255, 240, 200))
                surf.blit(t2, (x + ew - 10, y - 2))
            except Exception:
                pass

    def draw_overlay(self, surf, W: int, H: int, t: float):
        """Draw the full-screen letter overlay (passcode / reading / writing)."""
        import pygame
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((18, 12, 6, 172))
        surf.blit(dim, (0, 0))

        bx, by = 100, 80
        bw, bh = W - 200, H - 160
        pygame.draw.rect(surf, (62, 44, 20), (bx - 10, by - 10, bw + 20, bh + 20), border_radius=8)
        pygame.draw.rect(surf, PAPER_BG, (bx, by, bw, bh), border_radius=5)

        try:
            f_title = pygame.font.SysFont("monospace", 15)
            f_body  = pygame.font.SysFont("monospace", 12)
            f_hint  = pygame.font.SysFont("monospace", 10)
        except Exception:
            return

        if self._mode == "passcode":
            self._draw_passcode(surf, bx, by, bw, bh, f_title, f_body, f_hint)
        elif self._mode == "reading":
            self._draw_reading(surf, bx, by, bw, bh, f_title, f_body, f_hint, t)
        elif self._mode == "writing":
            self._draw_writing(surf, bx, by, bw, bh, f_title, f_body, f_hint, t)

    def _draw_passcode(self, surf, bx, by, bw, bh, f_title, f_body, f_hint):
        import pygame
        cx = bx + bw // 2
        try:
            t = f_title.render("Letters", True, (88, 62, 28))
            surf.blit(t, (cx - t.get_width() // 2, by + 28))
            sub = f_body.render("Enter passcode", True, (128, 105, 68))
            surf.blit(sub, (cx - sub.get_width() // 2, by + 58))
            dots = "● " * len(self._pin_input) + "○ " * (4 - len(self._pin_input))
            dc = (188, 55, 38) if self._pin_error else (88, 62, 28)
            d = f_title.render(dots.strip(), True, dc)
            surf.blit(d, (cx - d.get_width() // 2, by + bh // 2 - 10))
            if self._pin_error:
                err = f_hint.render("incorrect — try again", True, (188, 55, 38))
                surf.blit(err, (cx - err.get_width() // 2, by + bh // 2 + 22))
            hint = f_hint.render("[Esc] close", True, (158, 135, 98))
            surf.blit(hint, (cx - hint.get_width() // 2, by + bh - 28))
        except Exception:
            pass

    def _draw_reading(self, surf, bx, by, bw, bh, f_title, f_body, f_hint, t):
        import pygame
        cx  = bx + bw // 2
        letters = self.letters
        if not letters:
            try:
                empty = f_body.render("No letters yet.", True, (158, 135, 98))
                surf.blit(empty, (cx - empty.get_width() // 2, by + bh // 2))
                hint = f_hint.render("[W] write a letter   [Esc] close", True, (158, 135, 98))
                surf.blit(hint, (cx - hint.get_width() // 2, by + bh - 28))
            except Exception:
                pass
            return

        idx    = max(0, min(len(letters) - 1, self._page))
        letter = letters[idx]

        try:
            # Header
            from_name = letter.get("from", "?")
            ts        = letter.get("timestamp", "")[:10]
            header    = f"From: {from_name}   {ts}"
            ht        = f_hint.render(header, True, (128, 105, 68))
            surf.blit(ht, (bx + 18, by + 18))
            pygame.draw.line(surf, (198, 180, 148), (bx + 14, by + 36), (bx + bw - 14, by + 36), 1)

            # Body — word wrap
            body  = letter.get("body", "")
            words = body.split()
            lines, line = [], ""
            max_w = bw - 48
            for w in words:
                test = (line + " " + w).lstrip()
                if f_body.size(test)[0] <= max_w:
                    line = test
                else:
                    if line: lines.append(line)
                    line = w
            if line: lines.append(line)

            ry = by + 46
            for ln in lines:
                if ry > by + bh - 60:
                    break
                surf.blit(f_body.render(ln, True, (72, 52, 28)), (bx + 18, ry))
                ry += 17

            # Page / nav / hints
            pg = f_hint.render(f"{idx+1} / {len(letters)}", True, (158, 135, 98))
            surf.blit(pg, (cx - pg.get_width() // 2, by + bh - 44))
            hints = "[◀▶] prev/next   [W] write   [Esc] close"
            ht2   = f_hint.render(hints, True, (158, 135, 98))
            surf.blit(ht2, (cx - ht2.get_width() // 2, by + bh - 28))
        except Exception:
            pass

    def _draw_writing(self, surf, bx, by, bw, bh, f_title, f_body, f_hint, t):
        import pygame
        cx = bx + bw // 2
        try:
            title = f_title.render("Write a letter", True, (88, 62, 28))
            surf.blit(title, (cx - title.get_width() // 2, by + 20))
            pygame.draw.line(surf, (198, 180, 148), (bx + 14, by + 44), (bx + bw - 14, by + 44), 1)

            # Draft text with cursor
            draft_with_cursor = self._draft + ("|" if int(t * 2) % 2 == 0 else " ")
            words = draft_with_cursor.split()
            lines, line = [], ""
            max_w = bw - 48
            for w in words:
                test = (line + " " + w).lstrip()
                if f_body.size(test)[0] <= max_w:
                    line = test
                else:
                    if line: lines.append(line)
                    line = w
            if line: lines.append(line)

            ry = by + 56
            for ln in lines:
                if ry > by + bh - 60: break
                surf.blit(f_body.render(ln, True, (58, 42, 22)), (bx + 18, ry))
                ry += 17

            hint = f_hint.render("[Enter] send   [Esc] cancel", True, (158, 135, 98))
            surf.blit(hint, (cx - hint.get_width() // 2, by + bh - 28))
        except Exception:
            pass


# ── OllamaWriter ──────────────────────────────────────────────────────────────

class OllamaWriter:
    URL   = "http://localhost:11434/api/chat"
    MODEL = "llama3.2:3b"

    def __init__(self):
        self._thread  = None
        self.writing  = False
        self.result   = None
        self.progress = ""

    def write(self, memories: list, on_done=None):
        if self.writing:
            return
        self.writing  = True
        self.result   = None
        self.progress = "gathering thoughts..."
        self._thread  = threading.Thread(
            target=self._do, args=(memories, on_done), daemon=True)
        self._thread.start()

    def _do(self, memories, on_done):
        try:
            import requests
            mem_text = "\n".join(
                f"- {m.get('description','')}"
                for m in memories[:10] if m.get("description")
            )
            prompt = (
                "You are writing in Pucky's cottage journal.\n"
                "Pucky is a small warm robot who lives with Iðunn and is visited by Loki.\n"
                f"Her recent memories:\n{mem_text}\n\n"
                "Write a short, gentle journal entry (4-7 sentences) in Pucky's voice — "
                "first person, warm and poetic, noticing small things. "
                "End with a title on its own line: Title: [title]"
            )
            self.progress = "writing..."
            resp = requests.post(self.URL, json={
                "model": self.MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"num_predict": 220, "temperature": 0.82},
            }, timeout=90)
            resp.raise_for_status()
            text = resp.json()["message"]["content"].strip()

            title = "A Quiet Day"
            body_lines = []
            for ln in text.split("\n"):
                if ln.lower().startswith("title:"):
                    title = ln.split(":", 1)[1].strip().strip('"')
                else:
                    body_lines.append(ln)
            body = "\n".join(l for l in body_lines if l.strip())
            self.result = {"title": title, "body": body,
                           "scribble_type": "moment",
                           "scribble_seed": random.randint(0, 999999)}
        except Exception:
            self.result = {"title": "...", "body": "(The words wouldn't come.)",
                           "scribble_type": "moment", "scribble_seed": 0}
        finally:
            self.writing  = False
            self.progress = ""
            if on_done:
                on_done(self.result)


# ── CottageView ───────────────────────────────────────────────────────────────

class CottageView:
    """
    Full-screen cottage interior.  Integrate into pucky_world's main loop:

        cottage = CottageView(WIN_W, WIN_H)

        # on enter:
        cottage.enter()

        # each frame:
        result = cottage.handle_event(event)   # returns "exit" when done
        cottage.update(dt)
        cottage.draw(screen)
    """

    def __init__(self, win_w: int, win_h: int, speech=None):
        self.W = win_w
        self.H = win_h
        self.speech = speech

        self._memories:  list = []
        self._journal:   list = []
        self._scribbles: dict = {}

        self.room_t     = 0.0
        self.fade_alpha = 0
        self._bg_img    = None   # loaded lazily

        self.open_book  = None    # None | "memory" | "story" | "writing"
        self.book_page  = 0

        self.writer       = OllamaWriter()
        self._write_dot_t = 0.0

        self.letterbox    = LetterBox()

        self.canvas_mode    = False
        self.canvas_surf    = None
        self.cur_stroke:list= []

        self._rects: dict = {}
        self._fonts: dict = {}

    # ── Web key passthrough ───────────────────────────────────────────────────

    def handle_web_key(self, key_name: str, char: str = "") -> str:
        """Handle a key sent from the web portal (phone). Returns 'exit' to leave cottage."""
        if self.letterbox.is_open:
            result = self.letterbox.handle_key(key_name, char)
            return "exit" if result == "close" else ""
        if self.open_book in ("memory", "story"):
            if key_name in ("right", "d"):
                self._turn(1)
            elif key_name in ("left", "a"):
                self._turn(-1)
            elif key_name in ("escape", "e"):
                self.open_book = None
        elif self.open_book == "writing" and key_name in ("escape", "e"):
            self.open_book = None
        elif key_name in ("escape", "e"):
            return "exit"
        elif key_name == "w" and not self.open_book and not self.canvas_mode:
            self._start_writing()
        elif char and char.isdigit() and not self.open_book:
            self.letterbox.open()
            self.letterbox.handle_key(key_name, char)
        return ""

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def enter(self):
        self._load_data()
        self.room_t    = 0.0
        self.fade_alpha = 0
        self.open_book  = None
        self.book_page  = 0
        self.canvas_mode = False

    def _load_data(self):
        try:
            self._memories = json.loads(MEMORIES_FILE.read_text())
            self._memories.sort(key=lambda m: -m.get("importance", 0))
        except Exception:
            self._memories = []
        try:
            self._journal = json.loads(JOURNAL_FILE.read_text())
        except Exception:
            self._journal = []

    # ── Fonts ─────────────────────────────────────────────────────────────────

    def _fm(self, size: int) -> object:
        import pygame
        if size not in self._fonts:
            self._fonts[size] = pygame.font.SysFont("monospace", size)
        return self._fonts[size]

    # ── Events ────────────────────────────────────────────────────────────────

    def handle_event(self, event) -> str:
        import pygame
        # Route all keys to letterbox when it's open
        if self.letterbox.is_open:
            if event.type == pygame.KEYDOWN:
                key_name = pygame.key.name(event.key)
                result   = self.letterbox.handle_key(key_name, event.unicode)
                if result == "close":
                    return ""
            return ""

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_e):
                if self.canvas_mode:
                    self._save_canvas()
                    self.canvas_mode = False
                elif self.open_book:
                    self.open_book = None
                else:
                    return "exit"
            elif self.open_book in ("memory", "story"):
                if event.key in (pygame.K_RIGHT, pygame.K_d):
                    self._turn(1)
                elif event.key in (pygame.K_LEFT, pygame.K_a):
                    self._turn(-1)
            elif event.key == pygame.K_w and not self.open_book and not self.canvas_mode:
                self._start_writing()
            elif event.key == pygame.K_c and not self.open_book and not self.canvas_mode:
                self._open_canvas()

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.canvas_mode:
                self.cur_stroke = [event.pos]
            else:
                result = self._click(event.pos)
                if result == "exit":
                    return "exit"

        elif event.type == pygame.MOUSEMOTION:
            if self.canvas_mode and event.buttons[0] and self.cur_stroke:
                self.cur_stroke.append(event.pos)

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.canvas_mode and self.cur_stroke:
                self._bake_stroke()
                self.cur_stroke = []

        return ""

    def _click(self, pos) -> str:
        for name, rect in self._rects.items():
            if rect and rect.collidepoint(pos):
                if name == "book_memory":
                    self.open_book = "memory"; self.book_page = 0
                elif name == "book_story":
                    self.open_book = "story";  self.book_page = 0
                elif name == "book_canvas":
                    self._open_canvas()
                elif name == "btn_write":
                    self._start_writing()
                elif name == "btn_prev":
                    self._turn(-1)
                elif name == "btn_next":
                    self._turn(1)
                elif name == "btn_close":
                    self.open_book = None
                elif name == "envelope":
                    self.letterbox.open()
                break
        return ""

    def _turn(self, d: int):
        items = self._memories if self.open_book == "memory" else self._journal
        self.book_page = max(0, min(len(items)-1, self.book_page + d))

    def _start_writing(self):
        if self.writer.writing:
            return
        self.open_book    = "writing"
        self._write_dot_t = time.time()
        self.writer.write(self._memories, on_done=self._on_written)

    def _on_written(self, result):
        entry = {
            "id":           f"story_{int(time.time())}",
            "timestamp":    datetime.now(timezone.utc).isoformat(),
            "title":        result["title"],
            "body":         result["body"],
            "scribble_type": result["scribble_type"],
            "scribble_seed": result["scribble_seed"],
        }
        self._journal.append(entry)
        self._journal = _trim_cottage_journal(self._journal)
        try:
            JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
            JOURNAL_FILE.write_text(json.dumps(self._journal, indent=2, ensure_ascii=False))
        except Exception:
            pass
        self.open_book = "story"
        self.book_page = len(self._journal) - 1

    def _open_canvas(self):
        import pygame
        if not self.canvas_surf:
            self.canvas_surf = pygame.Surface((self.W, self.H))
            self.canvas_surf.fill(PAPER_BG)
            for y in range(0, self.H, 22):
                pygame.draw.line(self.canvas_surf, PAPER_LINE, (20, y), (self.W-20, y), 1)
        self.canvas_mode = True

    def _bake_stroke(self):
        if self.canvas_surf and len(self.cur_stroke) > 1:
            try:
                import pygame
                pygame.draw.lines(self.canvas_surf, INK_DARK, False, self.cur_stroke, 2)
            except Exception:
                pass

    def _save_canvas(self):
        import pygame
        if not self.canvas_surf:
            return
        path = Path("/home/bmo/pucky/workspace") / f"cottage_art_{int(time.time())}.png"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(self.canvas_surf, str(path))
            print(f"🖊️  Canvas saved → {path.name}")
        except Exception as e:
            print(f"  ⚠️  Canvas save: {e}")

    def _scribble_for(self, mem: dict) -> object:
        mid = mem.get("id", "")
        if mid not in self._scribbles:
            self._scribbles[mid] = ScribbleArt.for_memory(mem)
        return self._scribbles[mid]

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt: float):
        self.room_t += dt
        if self.fade_alpha < 255:
            self.fade_alpha = min(255, self.fade_alpha + int(dt * 460))

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surf):
        import pygame
        self._rects = {}

        if self.canvas_mode:
            self._draw_canvas(surf)
            return

        self._draw_room(surf)

        if self.fade_alpha < 200:
            overlay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
            overlay.fill((245, 235, 215, 255 - self.fade_alpha))
            surf.blit(overlay, (0, 0))
            return

        if self.letterbox.is_open:
            self.letterbox.draw_overlay(surf, self.W, self.H, self.room_t)
            return

        if self.open_book in ("memory", "story"):
            self._draw_open_book(surf)
        elif self.open_book == "writing":
            self._draw_writing(surf)

    # ── Room ──────────────────────────────────────────────────────────────────

    def _draw_room_overlays_idunn(self, surf, W, H, t):
        """Animated overlays for Iðunn's hand-drawn cottage background.
        The PNG has transparent pixels for windows/door — sky shows through naturally.
        We only draw things that need to be animated: fire, candle, books, envelope."""
        import pygame, datetime as _dt

        # ── Fire inside the stone fireplace arch ──────────────────────
        # Dark arch interior measured from PNG: x=479-799, y=60-324, centre≈(640,270)
        # fy_b is the grate level (lower portion of the arch opening)
        fx_c = int(W * 640/800)
        fy_b = int(H * 270/480)
        for i in range(7):
            ft   = t*2.1 + i*0.75
            fl_x = fx_c + int(math.sin(ft)*16)
            fl_y = fy_b - 24 - int(abs(math.sin(ft*1.4))*20)
            fl_r = 9 + i*3
            flc  = [(255,70,15),(255,130,25),(255,200,55),(255,230,110)][min(i,3)]
            fs = pygame.Surface((fl_r*2+2, fl_r*2+14), pygame.SRCALPHA)
            pygame.draw.ellipse(fs,(*flc,max(0,195-i*22)),(0,0,fl_r*2+2,fl_r*2+14))
            surf.blit(fs,(fl_x-fl_r-1, fl_y-fl_r-7))
        gs = pygame.Surface((180,80), pygame.SRCALPHA)
        pygame.draw.ellipse(gs,(255,135,45,22),(0,0,180,80))
        surf.blit(gs,(fx_c-90, fy_b-42))
        pygame.draw.ellipse(surf,(55,35,18),(fx_c-40,fy_b-16,80,12))
        pygame.draw.ellipse(surf,(72,48,22), (fx_c-28,fy_b-14,56, 9))

        # ── Candle on desk ────────────────────────────────────────────
        cdx = int(W*258/800);  cdy = int(H*190/480)
        pygame.draw.rect(surf,(245,240,222),(cdx-4,cdy,8,32))
        pygame.draw.rect(surf,(175,168,158),(cdx-4,cdy,8,32),1)
        cfa    = int(abs(math.sin(t*2.9))*30+195)
        cf_off = int(math.sin(t*5.2)*2)
        fls = pygame.Surface((14,22),pygame.SRCALPHA)
        pygame.draw.ellipse(fls,(255,218,75,cfa),(0,7,14,15))
        pygame.draw.ellipse(fls,(255,155,38,cfa),(3,0, 8,15))
        surf.blit(fls,(cdx-7+cf_off,cdy-18))
        cgl = pygame.Surface((56,38),pygame.SRCALPHA)
        pygame.draw.ellipse(cgl,(255,218,95,24),(0,0,56,38))
        surf.blit(cgl,(cdx-28,cdy-19))

        # ── Envelope on desk (centered, not near edge) ────────────────
        env_x = int(W*165/800);  env_y = int(H*184/480)
        self.letterbox.draw_envelope(surf, env_x, env_y, t)
        self._rects["envelope"] = pygame.Rect(env_x-2, env_y-2, 42, 32)

        # ── Books on the actual wooden shelf (x=424-534, y≈65 in PNG) ─
        book_defs = [
            ("memory","Mem",BOOK_COLS["memory"], int(W*432/800)),
            ("story", "Sto",BOOK_COLS["story"],  int(W*460/800)),
            ("canvas","Ske",BOOK_COLS["canvas"],  int(W*488/800)),
        ]
        for bname, blabel, (bc,bc2), bx2 in book_defs:
            bw2 = int(W*24/800);  bh2 = int(H*44/480)
            by2 = int(H*73/480)
            pygame.draw.rect(surf,bc, (bx2,by2,bw2,bh2),border_radius=2)
            pygame.draw.rect(surf,bc2,(bx2,by2,bw2,bh2),1,border_radius=2)
            try:
                bt = self._fm(8).render(blabel,True,(235,228,215))
                surf.blit(bt,(bx2+3,by2+4))
            except Exception: pass
            self._rects[f"book_{bname}"] = pygame.Rect(bx2,by2,bw2,bh2)

        # ── Write prompt on desk ──────────────────────────────────────
        try:
            wt = self._fm(9).render("[W] write",True,(148,125,85))
            wr = pygame.Rect(int(W*195/800),int(H*198/480),90,24)
            self._rects["btn_write"] = wr
            surf.blit(wt,(wr.x+3,wr.y+6))
        except Exception: pass

        # ── Hint bar ──────────────────────────────────────────────────
        try:
            hints = "[Mem/Sto/Ske] click a book   [W] write   [✉] click envelope   [E] outside"
            ht = self._fm(10).render(hints,True,(135,118,85))
            pygame.draw.rect(surf,(235,225,205),(0,H-22,W,22))
            surf.blit(ht,(10,H-18))
        except Exception: pass

    def _draw_room(self, surf):
        import pygame
        from pathlib import Path as _Path
        W, H  = self.W, self.H
        t     = self.room_t
        floor_y = int(H * 0.68)

        # ── Iðunn's hand-drawn background ────────────────────────────
        bg_path = _Path(__file__).parent / "workspace" / "images" / "bg_cottage_idunn.png"
        if bg_path.exists():
            if self._bg_img is None:
                # convert_alpha so future transparent-window exports work automatically
                raw = pygame.image.load(str(bg_path)).convert_alpha()
                self._bg_img = pygame.transform.scale(raw, (W, H))
            # Full outdoor sky behind the cottage (shows through if windows become transparent)
            import datetime as _dt2
            _h = _dt2.datetime.now().hour
            if 7 <= _h < 19:
                _sky=(80,140,200); _gnd=(88,138,62)
            elif _h < 6 or _h >= 21:
                _sky=(8,12,30);    _gnd=(38,52,32)
            else:
                _sky=(180,100,50); _gnd=(80,90,48)
            surf.fill(_sky)
            pygame.draw.rect(surf, _gnd, (0, int(H*0.55), W, H-int(H*0.55)))
            surf.blit(self._bg_img, (0, 0))
            self._draw_room_overlays_idunn(surf, W, H, t)
            return

        # ── Procedural fallback ───────────────────────────────────────

        # Gradient wall
        for y in range(H):
            blend = y / H
            r = int(ROOM_WALL[0]*(1-blend) + ROOM_WALL2[0]*blend)
            g = int(ROOM_WALL[1]*(1-blend) + ROOM_WALL2[1]*blend)
            b = int(ROOM_WALL[2]*(1-blend) + ROOM_WALL2[2]*blend)
            pygame.draw.line(surf, (r,g,b), (0,y), (W,y))

        # Wooden floor planks
        plank_h = 20
        for py in range(floor_y, H, plank_h):
            shade = int((py-floor_y)/(H-floor_y)*22)
            pc    = (max(0,ROOM_FLOOR[0]-shade), max(0,ROOM_FLOOR[1]-shade), max(0,ROOM_FLOOR[2]-shade))
            pygame.draw.rect(surf, pc, (0, py, W, plank_h))
            pygame.draw.line(surf, ROOM_FLOOR2, (0,py), (W,py), 1)
            for px in range((py*37)%90, W, 90):
                pygame.draw.line(surf, ROOM_FLOOR2, (px,py), (px,py+plank_h), 1)
        pygame.draw.rect(surf, (88,65,38,90), (0,floor_y,W,4))

        # ── Fireplace (left) ──────────────────────────────────────────────
        fx, fy = 60, floor_y - 10
        fw, fh = 125, 155
        pygame.draw.rect(surf, FIRE_STONE, (fx-10,fy-fh,fw+20,fh+10), border_radius=4)
        pygame.draw.rect(surf, (130,122,115), (fx-10,fy-fh,fw+20,fh+10), 2, border_radius=4)
        pygame.draw.rect(surf, SHELF_WOOD,  (fx-20,fy-fh-14,fw+40,14))
        pygame.draw.rect(surf, SHELF_WOOD2, (fx-20,fy-fh-14,fw+40,14), 1)
        pygame.draw.rect(surf, (32,25,18), (fx,fy-fh+18,fw,fh-24), border_radius=3)
        # fire
        for i in range(7):
            ft      = t*2.1 + i*0.75
            flame_x = fx+fw//2 + int(math.sin(ft)*16)
            flame_y = fy - 32 - int(abs(math.sin(ft*1.4))*20)
            flame_r = 9 + i*3
            flc     = [(255,70,15),(255,130,25),(255,200,55),(255,230,110)][min(i,3)]
            fs = pygame.Surface((flame_r*2+2,flame_r*2+14), pygame.SRCALPHA)
            pygame.draw.ellipse(fs, (*flc, max(0,195-i*22)), (0,0,flame_r*2+2,flame_r*2+14))
            surf.blit(fs, (flame_x-flame_r-1, flame_y-flame_r-7))
        gs = pygame.Surface((220,90), pygame.SRCALPHA)
        pygame.draw.ellipse(gs, (255,135,45,24), (0,0,220,90))
        surf.blit(gs, (fx+fw//2-110, fy-45))
        # logs
        pygame.draw.ellipse(surf, (55,35,18), (fx+8,fy-28,fw-16,14))
        pygame.draw.ellipse(surf, (72,48,22), (fx+18,fy-26,fw-36,10))

        # ── Bookshelf (above fireplace) ───────────────────────────────────
        sx, sy = fx-14, fy-fh-30
        sw, sh = fw+28, 115
        pygame.draw.rect(surf, SHELF_WOOD2, (sx,sy-sh,sw,sh))
        for board_y in [sy-sh//2, sy]:
            pygame.draw.rect(surf, SHELF_WOOD,  (sx-5,board_y-7,sw+10,9))
            pygame.draw.rect(surf, SHELF_WOOD2, (sx-5,board_y-7,sw+10,9), 1)

        book_defs = [
            ("memory","Memories", BOOK_COLS["memory"], sx+8),
            ("story", "Stories",  BOOK_COLS["story"],  sx+58),
            ("canvas","Sketches", BOOK_COLS["canvas"],  sx+108),
        ]
        for bname, blabel, (bc,bc2), bx2 in book_defs:
            bw2 = 38; bh2 = sh//2 - 20
            by2 = sy - sh//2 + 9
            pygame.draw.rect(surf, bc,  (bx2,by2,bw2,bh2), border_radius=2)
            pygame.draw.rect(surf, bc2, (bx2,by2,bw2,bh2), 1, border_radius=2)
            try:
                bt = self._fm(8).render(blabel[:3], True, (235,228,215))
                surf.blit(bt, (bx2+3, by2+4))
            except Exception:
                pass
            self._rects[f"book_{bname}"] = pygame.Rect(bx2,by2,bw2,bh2)

        # ── Window (upper right) ──────────────────────────────────────────
        import datetime as _dt
        hour = _dt.datetime.now().hour
        if 7 <= hour < 19:
            sky_c    = WIN_DAY;   ground_c = (108,158,78)
        elif hour < 6 or hour >= 21:
            sky_c    = WIN_NIGHT; ground_c = (40,55,35)
        else:
            sky_c    = WIN_DUSK;  ground_c = (95,105,55)

        wx, wy = W-285, 38
        ww, wh = 205, 145
        pygame.draw.rect(surf, (198,182,158), (wx-12,wy-14,ww+24,wh+26), border_radius=5)
        pygame.draw.rect(surf, (158,142,118), (wx-12,wy-14,ww+24,wh+26), 2, border_radius=5)
        pygame.draw.rect(surf, sky_c, (wx,wy,ww,wh))
        pygame.draw.rect(surf, ground_c, (wx,wy+wh-38,ww,38))
        # trees in window
        pygame.draw.rect(surf, (55,40,22),(wx+28,wy+wh-55,6,20))
        pygame.draw.circle(surf, (52,90,38),(wx+31,wy+wh-64),16)
        pygame.draw.rect(surf, (55,40,22),(wx+162,wy+wh-50,5,17))
        pygame.draw.circle(surf, (42,78,30),(wx+164,wy+wh-59),13)
        # sun/moon
        if 7 <= hour < 19:
            pygame.draw.circle(surf, (255,232,95),(wx+ww//2,wy+30),14)
        else:
            pygame.draw.circle(surf, (228,228,208),(wx+ww//2,wy+28),11)
            pygame.draw.circle(surf, sky_c,(wx+ww//2+5,wy+24),8)
            rng_s = random.Random(88)
            for _ in range(14):
                sx2 = rng_s.randint(wx+5,wx+ww-5); sy2 = rng_s.randint(wy+5,wy+wh-42)
                pygame.draw.circle(surf,(205,205,228),(sx2,sy2),1)
        pygame.draw.line(surf,(185,170,145),(wx+ww//2,wy),(wx+ww//2,wy+wh),2)
        pygame.draw.line(surf,(185,170,145),(wx,wy+wh//2),(wx+ww,wy+wh//2),2)
        # curtains
        for cx3 in [wx-12, wx+ww-10]:
            cs = pygame.Surface((22,wh+26), pygame.SRCALPHA)
            pygame.draw.rect(cs,(178,152,118,185),(0,0,22,wh+26))
            surf.blit(cs,(cx3,wy-14))

        # ── Writing desk (right) ──────────────────────────────────────────
        dx, dy = W-282, floor_y-95
        dw, dh = 242, 98
        pygame.draw.rect(surf, (98,68,32),(dx,dy,dw,dh//4))
        pygame.draw.rect(surf, (78,52,20),(dx,dy,dw,dh//4),1)
        for lx in [dx+18, dx+dw-32]:
            pygame.draw.rect(surf,(72,48,18),(lx,dy+dh//4,14,dh-dh//4))

        # Candle
        cdx, cdy = dx+28, dy-38
        pygame.draw.rect(surf,(245,240,222),(cdx-4,cdy,8,34))
        pygame.draw.rect(surf,(175,168,158),(cdx-4,cdy,8,34),1)
        fa      = int(abs(math.sin(t*2.9))*30 + 195)
        fx_off  = int(math.sin(t*5.2)*2)
        fls = pygame.Surface((14,22),pygame.SRCALPHA)
        pygame.draw.ellipse(fls,(255,218,75,fa),(0,7,14,15))
        pygame.draw.ellipse(fls,(255,155,38,fa),(3,0,8,15))
        surf.blit(fls,(cdx-7+fx_off,cdy-20))
        cgl = pygame.Surface((64,42),pygame.SRCALPHA)
        pygame.draw.ellipse(cgl,(255,218,95,26),(0,0,64,42))
        surf.blit(cgl,(cdx-32,cdy-21))

        # Envelope on desk (left of journal)
        env_x, env_y = dx + 18, dy - 38
        self.letterbox.draw_envelope(surf, env_x, env_y, t)
        self._rects["envelope"] = pygame.Rect(env_x - 2, env_y - 2, 42, 32)

        # Open journal on desk
        jx, jy = dx+62, dy-12
        jw, jh = 148, 90
        pygame.draw.rect(surf,PAPER_BG,(jx,jy-jh+14,jw,jh-2),border_radius=2)
        pygame.draw.rect(surf,(175,162,138),(jx,jy-jh+14,jw,jh-2),1,border_radius=2)
        pygame.draw.line(surf,(165,150,125),(jx+jw//2,jy-jh+14),(jx+jw//2,jy+10),2)
        for ry in range(jy-jh+25, jy+6, 11):
            pygame.draw.line(surf,PAPER_LINE,(jx+6,ry),(jx+jw//2-5,ry),1)
            pygame.draw.line(surf,PAPER_LINE,(jx+jw//2+5,ry),(jx+jw-6,ry),1)
        # Write prompt
        try:
            wt = self._fm(9).render("[W] write a new entry", True, (148,125,85))
            wr = pygame.Rect(jx+8, jy-jh+16, jw-16, 13)
            self._rects["btn_write"] = wr
            surf.blit(wt, (wr.x, wr.y))
        except Exception:
            pass

        # ── Small rug ─────────────────────────────────────────────────────
        rcx, rcy = W//2, floor_y+65
        rrx, rry = 128, 48
        rs = pygame.Surface((rrx*2,rry*2),pygame.SRCALPHA)
        pygame.draw.ellipse(rs,(138,88,78,215),(0,0,rrx*2,rry*2))
        pygame.draw.ellipse(rs,(168,112,98,175),(15,10,rrx*2-30,rry*2-20))
        pygame.draw.ellipse(rs,(98,62,55,110),(0,0,rrx*2,rry*2),2)
        surf.blit(rs,(rcx-rrx,rcy-rry))

        # ── Hint bar ──────────────────────────────────────────────────────
        try:
            hints = "[Mem / Stories / Sketches] click a book   [W] write   [C] canvas   [✉] click envelope   [E] outside"
            ht = self._fm(10).render(hints, True, (135,118,85))
            pygame.draw.rect(surf,(235,225,205),(0,H-22,W,22))
            surf.blit(ht,(10,H-18))
        except Exception:
            pass

    # ── Open book ─────────────────────────────────────────────────────────────

    def _draw_open_book(self, surf):
        import pygame
        W, H = self.W, self.H

        dim = pygame.Surface((W,H),pygame.SRCALPHA)
        dim.fill((28,20,12,162))
        surf.blit(dim,(0,0))

        bx, by = 55, 55
        bw, bh = W-110, H-130
        bm     = bw//2

        pygame.draw.rect(surf,(60,42,18),(bx-10,by-10,bw+20,bh+20),border_radius=7)
        pygame.draw.rect(surf,PAPER_BG,  (bx,by,bw,bh),border_radius=4)
        pygame.draw.rect(surf,(195,182,160),(bx,by,bw,bh),1,border_radius=4)
        pygame.draw.line(surf,(162,148,122),(bx+bm,by+8),(bx+bm,by+bh-8),2)

        if self.open_book == "memory":
            items     = self._memories
            get_scrib = self._scribble_for
            get_title = lambda m: m.get("description","")[:70]
            get_body  = self._mem_body
        else:
            items     = self._journal
            get_scrib = ScribbleArt.for_journal
            get_title = lambda e: e.get("title","")
            get_body  = lambda e: e.get("body","")

        if not items:
            try:
                nt = self._fm(13).render("(nothing here yet)", True, (158,138,98))
                surf.blit(nt,(bx+bm//2-nt.get_width()//2, by+bh//2))
            except Exception:
                pass
        else:
            idx  = max(0, min(len(items)-1, self.book_page))
            item = items[idx]

            # Left page — scribble
            scrib = get_scrib(item)
            sx    = bx + (bm - scrib.get_width())//2
            sy    = by + (bh - scrib.get_height())//2 - 18
            surf.blit(scrib,(sx,sy))

            # tier / date footer
            try:
                tier = item.get("tier", item.get("scribble_type","warm"))
                ts   = item.get("timestamp","")[:10]
                tf   = self._fm(9)
                surf.blit(tf.render(tier, True,(175,158,130)),(bx+8,by+bh-22))
                td   = tf.render(ts,   True,(175,158,130))
                surf.blit(td,(bx+bm-td.get_width()-8,by+bh-22))
            except Exception:
                pass

            # Right page — title + body
            rx, ry = bx+bm+14, by+22
            rw     = bm - 28

            try:
                title_s = self._wrap(get_title(item), self._fm(13), rw, (70,52,25))
                surf.blit(title_s,(rx,ry))
                ry += title_s.get_height() + 10
            except Exception:
                pass

            pygame.draw.line(surf,(198,182,155),(rx,ry),(rx+rw,ry),1)
            ry += 9

            try:
                body_s = self._wrap(get_body(item), self._fm(11), rw, (78,62,40), lh=17)
                surf.blit(body_s,(rx,ry))
            except Exception:
                pass

            if self.open_book == "memory":
                self._draw_emobars(surf, item, bx+bm+14, by+bh-52, bm-28)

        # Page n/N
        try:
            total = max(len(items),1) if items else 1
            pt = self._fm(10).render(f"{self.book_page+1} / {total}", True,(158,142,115))
            surf.blit(pt,(bx+bm-pt.get_width()//2, by+bh-18))
        except Exception:
            pass

        # Nav buttons
        btn_y = by+bh+8
        for name, label, bx2 in [
            ("btn_prev",  "◀ prev",  bx+8),
            ("btn_close", " close ", bx+bw//2-42),
            ("btn_next",  "next ▶",  bx+bw-92),
        ]:
            br = pygame.Rect(bx2,btn_y,82,24)
            self._rects[name] = br
            pygame.draw.rect(surf,(88,62,28),br,border_radius=3)
            pygame.draw.rect(surf,(128,100,65),br,1,border_radius=3)
            try:
                bt = self._fm(11).render(label, True,(232,222,198))
                surf.blit(bt,(br.x+(br.w-bt.get_width())//2,br.y+(br.h-bt.get_height())//2))
            except Exception:
                pass

    def _mem_body(self, mem: dict) -> str:
        em = [(k,v) for k,v in [
            ("joy",          mem.get("joy",0)),
            ("peace",        mem.get("peacefulness",0)),
            ("wonder",       mem.get("wonder",0)),
            ("sorrow",       mem.get("unpleasantness",0)),
            ("fear",         mem.get("scariness",0)),
        ] if v > 0.4]
        tags = "   ".join(f"{label} {val:.0f}" for label,val in em)
        return f"{mem.get('description','')}\n\n{tags}"

    def _draw_emobars(self, surf, mem, x, y, w):
        import pygame
        slots = [
            ("joy",    (255,208,65),  mem.get("joy",0)),
            ("peace",  (128,192,228), mem.get("peacefulness",0)),
            ("wonder", (188,152,255), mem.get("wonder",0)),
            ("sorrow", (138,152,182), mem.get("unpleasantness",0)),
        ]
        bw_ea = w//len(slots) - 4
        for i,(label,color,val) in enumerate(slots):
            bx2    = x + i*(bw_ea+4)
            filled = int(bw_ea * min(val,10) / 10)
            pygame.draw.rect(surf,(205,195,172),(bx2,y,bw_ea,5))
            if filled > 0:
                pygame.draw.rect(surf,color,(bx2,y,filled,5))
            try:
                lt = self._fm(8).render(label, True,(152,135,105))
                surf.blit(lt,(bx2,y+7))
            except Exception:
                pass

    def _draw_writing(self, surf):
        import pygame
        W, H = self.W, self.H
        dim  = pygame.Surface((W,H),pygame.SRCALPHA)
        dim.fill((18,12,6,152))
        surf.blit(dim,(0,0))

        bx,by = 148,95
        bw,bh = W-296,H-195
        pygame.draw.rect(surf,(60,42,18),(bx-10,by-10,bw+20,bh+20),border_radius=7)
        pygame.draw.rect(surf,PAPER_BG,(bx,by,bw,bh),border_radius=4)

        try:
            tt = self._fm(16).render("Writing in the journal...", True,(88,65,30))
            surf.blit(tt,(bx+bw//2-tt.get_width()//2, by+28))
        except Exception:
            pass

        n_dots = int((time.time()-self._write_dot_t)/0.55) % 4
        try:
            dt2 = self._fm(28).render("." * n_dots, True,(155,128,80))
            surf.blit(dt2,(bx+bw//2-28, by+bh//2-18))
        except Exception:
            pass

        if self.writer.progress:
            try:
                pt = self._fm(11).render(self.writer.progress, True,(148,125,85))
                surf.blit(pt,(bx+bw//2-pt.get_width()//2, by+bh-48))
            except Exception:
                pass

    def _draw_canvas(self, surf):
        import pygame
        if self.canvas_surf:
            surf.blit(self.canvas_surf,(0,0))
        if len(self.cur_stroke) > 1:
            pygame.draw.lines(surf, INK_DARK, False, self.cur_stroke, 2)
        try:
            ht = self._fm(10).render("[E] save & exit canvas — draw freely with mouse", True,(98,80,52))
            pygame.draw.rect(surf,(*PAPER_BG,210),(6,self.H-24,ht.get_width()+12,20))
            surf.blit(ht,(10,self.H-21))
        except Exception:
            pass

    # ── Text wrap ─────────────────────────────────────────────────────────────

    def _wrap(self, text: str, font, max_w: int, color, lh: int = 18) -> object:
        import pygame
        paras    = text.replace("\r","").split("\n")
        lines    = []
        for para in paras:
            if not para.strip():
                lines.append("")
                continue
            words = para.split(); line = ""
            for w in words:
                test = (line+" "+w).lstrip()
                if font.size(test)[0] <= max_w:
                    line = test
                else:
                    if line: lines.append(line)
                    line = w
            if line: lines.append(line)

        h_total = max(1, len(lines)*lh)
        out     = pygame.Surface((max_w, h_total), pygame.SRCALPHA)
        out.fill((0,0,0,0))
        for i, ln in enumerate(lines):
            if ln:
                try:
                    out.blit(font.render(ln, True, color),(0,i*lh))
                except Exception:
                    pass
        return out
