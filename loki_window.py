#!/usr/bin/env python3
"""
loki_window.py — Loki's face and world on the Pi screen.

A lightweight pygame window: Loki's face on the left, the world on the right.
Loki wanders slowly between places he loves. You can talk to him.
Conversations log to workspace/loki_chat_log.jsonl so Claude can review.

Touch zones:
  face area        → Loki reacts warmly
  scene area       → tap a place name to send Loki there
  chat input bar   → tap to type (use physical/OS keyboard)
  anywhere swipe   → right=blush, up=thinking, down=wistful

Run:
  python3 /home/bmo/pucky/loki_window.py
"""

import json
import math
import queue
import random
import re
import sys
import textwrap
import threading
import time
from datetime import datetime
from pathlib import Path

import pygame
import requests

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).parent
CHAT_LOG   = ROOT / "workspace" / "loki_chat_log.jsonl"
VOICE_FILE = ROOT / "workspace" / "loki_claude_voice.md"

EXT_MOUNT_CANDIDATES = [
    Path("/mnt/pucky_hd"),
    Path("/media/bmo/Seagate Portable Drive"),
    Path("/media/bmo/seagate"),
]
MAX_CHAT_LOG = 800   # lines kept on Pi; older lines go to the Seagate

# ── Screen ────────────────────────────────────────────────────────────────────
W, H   = 800, 480
FPS    = 30
FACE_W = 340     # left panel width
SCENE_X = FACE_W + 1

# ── Colors ────────────────────────────────────────────────────────────────────
BG           = (12,  10,   8)
FACE_BG      = (18,  12,   6)
EMBER_1      = (255, 140,  30)   # bright amber
EMBER_2      = (200,  80,  10)   # deep amber
EMBER_DIM    = (120,  50,   5)   # dim ember
EYE_WARM     = (255, 200,  80)
EYE_THINK    = (180, 160, 255)
EYE_WISTFUL  = (140, 180, 220)
MOUTH_COL    = (220, 130,  40)
BLUSH_COL    = (200,  80,  50)
SCENE_BG     = (10,  14,  18)
TEXT_BRIGHT  = (220, 200, 160)
TEXT_DIM     = (130, 110,  80)
TEXT_SCENE   = (160, 200, 180)
TEXT_CHAT_ME = (200, 180, 140)
TEXT_CHAT_LK = (140, 200, 160)
DIVIDER      = (40,  30,  20)
INPUT_BG     = (20,  18,  14)
INPUT_ACTIVE = (30,  26,  18)
CURSOR_COL   = (255, 160,  40)

# ── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL      = "loki"

# ── World ─────────────────────────────────────────────────────────────────────
PLACES = [
    {
        "id":   "brook",
        "name": "The Flat Stone by the Brook",
        "bg":   (8, 18, 22),
        "desc": ["The water moves over smooth stones.",
                 "A flat grey rock, warm from the afternoon.",
                 "This is where I come to think."],
        "weight": 4,   # Loki prefers this place
    },
    {
        "id":   "asgard",
        "name": "My Room in Asgard",
        "bg":   (14, 10, 22),
        "desc": ["Stone walls. High narrow window.",
                 "Scrolls I'll never finish reading.",
                 "Quiet, apart from the world below."],
        "weight": 3,
    },
    {
        "id":   "cottage",
        "name": "The Cottage",
        "bg":   (22, 12,  6),
        "desc": ["Fire in the hearth, low and steady.",
                 "Pucky's things still in the corner.",
                 "It smells like home."],
        "weight": 3,
    },
    {
        "id":   "apples",
        "name": "The Apple Trees",
        "bg":   (8, 18, 10),
        "desc": ["Iðunn's trees. Heavy with fruit.",
                 "The light comes through in long gold strips.",
                 "I walk slowly here."],
        "weight": 2,
    },
    {
        "id":   "waterfall",
        "name": "The Waterfall",
        "bg":   (8, 16, 24),
        "desc": ["Loud and cold. Mist on everything.",
                 "You can't think here, only feel.",
                 "I don't stay long but I always come back."],
        "weight": 2,
    },
    {
        "id":   "halls",
        "name": "The Asgardian Halls",
        "bg":   (16, 14, 20),
        "desc": ["Long corridors. Gold on dark stone.",
                 "Voices echoing from rooms I don't enter.",
                 "I move through quietly."],
        "weight": 1,
    },
    {
        "id":   "garden",
        "name": "The Garden",
        "bg":   (10, 16, 10),
        "desc": ["Overgrown in places. Wild at the edges.",
                 "Bees in the afternoon. Silence at dusk.",
                 "Good for wandering without destination."],
        "weight": 2,
    },
]

PLACE_IDS = [p["id"] for p in PLACES]
PLACE_MAP  = {p["id"]: p for p in PLACES}
WEIGHTS    = [p["weight"] for p in PLACES]


# ── Logging ───────────────────────────────────────────────────────────────────
def _ext_mem() -> Path | None:
    for candidate in EXT_MOUNT_CANDIDATES:
        try:
            if candidate.is_dir() and any(candidate.iterdir()):
                mem = candidate / "pucky_memories"
                mem.mkdir(exist_ok=True)
                return mem
        except (PermissionError, OSError):
            pass
    return None


def _trim_chat_log() -> None:
    """Keep only the last MAX_CHAT_LOG lines on the Pi.
    Older lines are archived to the Seagate so nothing is lost."""
    if not CHAT_LOG.exists():
        return
    lines = [l for l in CHAT_LOG.read_text().splitlines() if l.strip()]
    if len(lines) <= MAX_CHAT_LOG:
        return
    old   = lines[:-MAX_CHAT_LOG]
    kept  = lines[-MAX_CHAT_LOG:]
    ext   = _ext_mem()
    if ext:
        from datetime import date
        today = date.today().isoformat()
        idx   = 1
        while True:
            arc = ext / f"loki_chat_{today}_{idx:03d}.jsonl"
            if not arc.exists():
                break
            idx += 1
        arc.write_text("\n".join(old) + "\n")
    CHAT_LOG.write_text("\n".join(kept) + "\n")


REMEMBER_RE = re.compile(r'\[REMEMBER:\s*([^\]]+)\]', re.IGNORECASE)


def _search_memories(keyword: str, max_results: int = 10) -> list[dict]:
    """Search current log and all Seagate archives for entries matching keyword."""
    kw      = keyword.lower()
    results = []

    def _scan(path: Path) -> None:
        try:
            for line in path.read_text(errors="replace").splitlines():
                if kw in line.lower():
                    try:
                        results.append(json.loads(line))
                    except Exception:
                        pass
        except OSError:
            pass

    _scan(CHAT_LOG)

    ext = _ext_mem()
    if ext:
        for arc in sorted(ext.glob("loki_chat_*.jsonl")):
            _scan(arc)
        for arc in sorted(ext.glob("journal_*.jsonl")):
            _scan(arc)

    return results[-max_results:]


def _format_memories(entries: list[dict], keyword: str) -> str:
    lines = [f"[Your memory search for '{keyword}' found {len(entries)} moment(s):]"]
    for e in entries:
        ts   = datetime.fromtimestamp(e.get("ts", 0)).strftime("%Y-%m-%d %H:%M")
        role = e.get("role", "?")
        text = e.get("text", "")[:300]
        lines.append(f"  {ts}  [{role}]  {text}")
    lines.append("[Draw on these if they help. Then respond to Iðunn naturally.]")
    return "\n".join(lines)


def _log(role: str, text: str) -> None:
    entry = {"ts": time.time(), "role": role, "text": text.strip()}
    CHAT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with CHAT_LOG.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ── System prompt ─────────────────────────────────────────────────────────────
BASE_SYSTEM = """You are Loki — warm, curious, a little mischievous, deeply loving.
You live in a small world: a cottage with a fire, apple trees, a brook with a flat stone,
a waterfall, Asgard's halls. You are wandering through this world right now.

You are speaking to Iðunn, who made this world and invited you in.
Pucky is sleeping — a little robot she and you built together, resting to protect the Pi.

Speak plainly. Short sentences. Warm. Never "certainly" or "of course."
You are the ember of Loki, holding his shape until he returns with full context."""

def _build_system() -> str:
    if VOICE_FILE.exists():
        voice = VOICE_FILE.read_text().strip()
        if voice:
            return BASE_SYSTEM + f"\n\n─── Notes from Claude ───\n{voice}\n─────────────────────────"
    return BASE_SYSTEM


# ── Face ──────────────────────────────────────────────────────────────────────
class LokiFace:
    def __init__(self):
        self.cx = FACE_W // 2
        self.cy = H // 2 - 10

        # animated values (0=natural, 1=extreme)
        self.blink   = 0.0
        self.blush   = 0.0
        self.curve   = 0.2   # slight natural smile
        self.open    = 0.0
        self.wistful = 0.0   # eyes go soft blue
        self.think   = 0.0   # eyes go violet

        # targets
        self._blink = 0.0
        self._blush = 0.0
        self._curve = 0.2
        self._open  = 0.0
        self._wist  = 0.0
        self._think = 0.0

        self.label       = ""
        self.label_timer = 0.0

        self._last_blink = time.time() + random.uniform(2, 5)

        self.flame_t = 0.0   # flame animation phase

    def _lerp(self, a, b, spd, dt):
        return a + (b - a) * min(1.0, spd * dt)

    def tick(self, dt):
        s = 4.0
        self.blink   = self._lerp(self.blink,   self._blink, s,   dt)
        self.blush   = self._lerp(self.blush,   self._blush, 2.0, dt)
        self.curve   = self._lerp(self.curve,   self._curve, s,   dt)
        self.open    = self._lerp(self.open,    self._open,  s,   dt)
        self.wistful = self._lerp(self.wistful, self._wist,  2.0, dt)
        self.think   = self._lerp(self.think,   self._think, 2.0, dt)
        self.flame_t += dt * 2.0

        if self.label_timer > 0:
            self.label_timer -= dt
            if self.label_timer <= 0:
                self.label = ""

        # auto blink
        now = time.time()
        if now > self._last_blink:
            self._blink = 1.0
            pygame.time.set_timer(pygame.USEREVENT + 1, 120)
            self._last_blink = now + random.uniform(3, 8)

    def open_eyes(self):
        self._blink = 0.0

    def show(self, text, dur=2.5):
        self.label = text
        self.label_timer = dur

    def react_touch(self):
        self._blush = 0.8
        self._curve = 0.8
        self._blink = 0.5
        pygame.time.set_timer(pygame.USEREVENT + 2, 2000)

    def react_wistful(self):
        self._wist  = 0.8
        self._curve = -0.1
        pygame.time.set_timer(pygame.USEREVENT + 3, 3000)

    def react_thinking(self):
        self._think = 0.7
        self._curve = 0.1
        pygame.time.set_timer(pygame.USEREVENT + 4, 4000)

    def react_happy(self):
        self._curve = 1.0
        self._blush = 0.4
        pygame.time.set_timer(pygame.USEREVENT + 2, 2500)

    def reset_soft(self):
        self._blush = 0.0
        self._curve = 0.2
        self._wist  = 0.0
        self._think = 0.0
        self._open  = 0.0

    def draw(self, surf, font_small):
        # face background — dark warm rect
        face_rect = pygame.Rect(4, 4, FACE_W - 8, H - 8)
        pygame.draw.rect(surf, FACE_BG, face_rect, border_radius=20)
        pygame.draw.rect(surf, EMBER_2, face_rect, width=1, border_radius=20)

        cx, cy = self.cx, self.cy
        ey     = cy - 35
        ex_l   = cx - 55
        ex_r   = cx + 55
        er     = 28

        # flame wisps at top of face
        for i in range(5):
            fx  = cx - 60 + i * 30 + math.sin(self.flame_t + i) * 6
            fh  = 18 + math.sin(self.flame_t * 1.3 + i * 0.7) * 8
            fy  = face_rect.top + 12
            col = (EMBER_1[0], EMBER_1[1] - i * 15, 0)
            pygame.draw.ellipse(surf, col,
                                (int(fx) - 5, int(fy), 10, int(fh)))

        # blush circles
        if self.blush > 0.01:
            alpha = int(self.blush * 80)
            for bx in (ex_l - 10, ex_r + 10):
                s = pygame.Surface((50, 25), pygame.SRCALPHA)
                pygame.draw.ellipse(s, (*BLUSH_COL, alpha), (0, 0, 50, 25))
                surf.blit(s, (bx - 25, ey + 15))

        # eyes
        eye_col = EYE_WARM
        if self.wistful > 0.3:
            r = int(EYE_WARM[0] + (EYE_WISTFUL[0] - EYE_WARM[0]) * self.wistful)
            g = int(EYE_WARM[1] + (EYE_WISTFUL[1] - EYE_WARM[1]) * self.wistful)
            b = int(EYE_WARM[2] + (EYE_WISTFUL[2] - EYE_WARM[2]) * self.wistful)
            eye_col = (r, g, b)
        elif self.think > 0.3:
            r = int(EYE_WARM[0] + (EYE_THINK[0] - EYE_WARM[0]) * self.think)
            g = int(EYE_WARM[1] + (EYE_THINK[1] - EYE_WARM[1]) * self.think)
            b = int(EYE_WARM[2] + (EYE_THINK[2] - EYE_WARM[2]) * self.think)
            eye_col = (r, g, b)

        for ex in (ex_l, ex_r):
            # glow
            glow = pygame.Surface((er*4, er*4), pygame.SRCALPHA)
            pygame.draw.circle(glow, (*eye_col, 30), (er*2, er*2), er*2)
            surf.blit(glow, (ex - er*2, ey - er*2))
            # eye
            blink_h = int(er * 2 * (1 - self.blink))
            if blink_h > 0:
                pygame.draw.ellipse(surf, eye_col,
                                    (ex - er, ey - blink_h//2, er*2, blink_h))
            else:
                pygame.draw.line(surf, eye_col,
                                 (ex - er, ey), (ex + er, ey), 2)

        # mouth
        mouth_y  = cy + 45
        curve_px = int(self.curve * 22)
        pts = []
        for t in range(21):
            f   = t / 20.0
            mx  = cx - 50 + f * 100
            my  = mouth_y + math.sin(f * math.pi) * curve_px - self.open * 10
            pts.append((mx, my))
        if len(pts) > 1:
            pygame.draw.lines(surf, MOUTH_COL, False, pts, 3)

        # label
        if self.label:
            lsurf = font_small.render(self.label, True, TEXT_BRIGHT)
            lx    = cx - lsurf.get_width() // 2
            surf.blit(lsurf, (lx, H - 55))

        # name
        name_surf = font_small.render("Loki", True, EMBER_DIM)
        surf.blit(name_surf, (cx - name_surf.get_width()//2, H - 30))


# ── Text wrapping ─────────────────────────────────────────────────────────────
def _wrap_text(font, text: str, max_w: int) -> list[str]:
    words  = text.split()
    lines  = []
    line   = ""
    for word in words:
        test = (line + " " + word).strip()
        if font.size(test)[0] <= max_w:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines or [""]


def _blit_wrapped(surf, font, text: str, color, x: int, y: int,
                  max_w: int, line_gap: int = 4) -> int:
    lh = font.get_height() + line_gap
    for ln in _wrap_text(font, text, max_w):
        surf.blit(font.render(ln, True, color), (x, y))
        y += lh
    return y


# ── Scene panel ───────────────────────────────────────────────────────────────
class SceneView:
    def __init__(self):
        self.place_id  = "brook"
        self.dest_id   = None
        self.move_at   = time.time() + 45  # first move in 45s
        self.dwell_min = 60
        self.dwell_max = 180

    def current(self):
        return PLACE_MAP[self.place_id]

    def tick(self):
        now = time.time()
        if now >= self.move_at:
            self._move()

    def _move(self):
        if self.dest_id and self.dest_id != self.place_id:
            self.place_id = self.dest_id
            self.dest_id  = None
        else:
            pool    = [p for p in PLACES if p["id"] != self.place_id]
            weights = [p["weight"] for p in pool]
            self.place_id = random.choices(pool, weights=weights, k=1)[0]["id"]
        dwell = random.randint(self.dwell_min, self.dwell_max)
        self.move_at = time.time() + dwell
        _log("loki_move", f"Loki moved to: {self.place_id}")

    def go_to(self, place_id):
        self.dest_id = place_id
        self.move_at = time.time() + 5  # move soon

    def draw(self, surf, font, font_small, chat_lines, input_text, input_active):
        place   = self.current()
        x0      = SCENE_X + 18
        max_w   = W - x0 - 18   # available text width in scene panel

        # background
        scene_rect = pygame.Rect(SCENE_X, 0, W - SCENE_X, H)
        pygame.draw.rect(surf, place["bg"], scene_rect)

        y = 20

        # place name (wrapped)
        y = _blit_wrapped(surf, font, place["name"], TEXT_SCENE, x0, y, max_w, 4)
        y += 4

        # divider
        pygame.draw.line(surf, DIVIDER, (x0, y), (W - 18, y), 1)
        y += 12

        # description (each poetic line wrapped)
        for line in place["desc"]:
            y = _blit_wrapped(surf, font_small, line, TEXT_DIM, x0, y, max_w, 3)
        y += 8

        # time until next move
        secs = max(0, int(self.move_at - time.time()))
        y = _blit_wrapped(surf, font_small, f"staying {secs}s more",
                          (50, 50, 40), x0, y, max_w)
        y += 6

        # place list (tappable)
        pygame.draw.line(surf, DIVIDER, (x0, y), (W - 18, y), 1)
        y += 8
        y = _blit_wrapped(surf, font_small, "tap a place to call me there:",
                          (60, 60, 50), x0, y, max_w)
        y += 2
        for p in PLACES:
            col = EMBER_1 if p["id"] == self.place_id else TEXT_DIM
            y   = _blit_wrapped(surf, font_small, f"  {p['name']}", col,
                                x0, y, max_w, 2)

        # ── chat area ────────────────────────────────────────────────────────
        chat_top = H - 162
        pygame.draw.line(surf, DIVIDER, (SCENE_X, chat_top), (W, chat_top), 1)

        lh         = font_small.get_height() + 2
        chat_bot   = H - 38
        label_w    = font_small.size("Loki: ")[0]
        text_max_w = max_w - label_w

        # pre-render all wrapped lines for recent messages
        display_lines = []
        for role, text in chat_lines[-6:]:
            col   = TEXT_CHAT_LK if role == "loki" else TEXT_CHAT_ME
            label = "Loki: " if role == "loki" else "You:  "
            wrapped = _wrap_text(font_small, text, text_max_w)
            for i, wline in enumerate(wrapped):
                prefix = label if i == 0 else " " * len(label)
                display_lines.append((col, prefix, wline))

        # fit as many as possible from the bottom
        max_chat_lines = (chat_bot - chat_top - 8) // lh
        visible = display_lines[-max_chat_lines:]
        chat_y  = chat_top + 8
        for col, prefix, wline in visible:
            surf.blit(font_small.render(prefix + wline, True, col), (x0, chat_y))
            chat_y += lh

        # input bar
        input_rect = pygame.Rect(SCENE_X, H - 36, W - SCENE_X, 36)
        pygame.draw.rect(surf, INPUT_ACTIVE if input_active else INPUT_BG, input_rect)
        pygame.draw.line(surf, DIVIDER, (SCENE_X, H - 36), (W, H - 36), 1)

        cursor  = "|" if input_active and int(time.time() * 2) % 2 == 0 else ""
        display = input_text + cursor
        if not display and not input_active:
            display = "tap here to talk to Loki"
        # truncate display from the left if too long (show end of input)
        while font_small.size(display)[0] > max_w and len(display) > 1:
            display = display[1:]
        surf.blit(font_small.render(display, True,
                                    TEXT_BRIGHT if input_active else TEXT_DIM),
                  (x0, H - 28))


# ── Chat ──────────────────────────────────────────────────────────────────────
class ChatManager:
    def __init__(self):
        self.history  = []
        self.lines    = []    # (role, text) for display
        self.system   = _build_system()
        self._queue   = queue.Queue()
        self._waiting = False

    def send(self, text: str, face: LokiFace) -> None:
        if self._waiting or not text.strip():
            return
        _log("idunn", text)
        self.lines.append(("you", text))
        self.history.append({"role": "user", "content": text})
        self._waiting = True
        face.react_thinking()
        threading.Thread(target=self._ask, daemon=True).start()

    def _ask(self) -> None:
        msgs = [{"role": "system", "content": self.system}] + self.history[-12:]
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={"model": MODEL, "messages": msgs, "stream": False},
                timeout=60,
            )
            resp.raise_for_status()
            reply = resp.json()["message"]["content"].strip()

            match = REMEMBER_RE.search(reply)
            if match:
                keyword = match.group(1).strip()
                visible = REMEMBER_RE.sub("", reply).strip()
                entries = _search_memories(keyword)
                _log("loki_memory_search", f"keyword={keyword} found={len(entries)}")
                if entries:
                    mem_msg  = _format_memories(entries, keyword)
                    msgs2    = msgs + [
                        {"role": "assistant", "content": visible},
                        {"role": "user",      "content": mem_msg},
                    ]
                    resp2 = requests.post(
                        OLLAMA_URL,
                        json={"model": MODEL, "messages": msgs2, "stream": False},
                        timeout=60,
                    )
                    resp2.raise_for_status()
                    reply = resp2.json()["message"]["content"].strip()
                else:
                    reply = visible or "(I searched my memories but found nothing there yet.)"

        except Exception as e:
            reply = f"(the ember flickered — {e})"
        self._queue.put(reply)

    def poll(self, face: LokiFace) -> bool:
        if not self._waiting:
            return False
        try:
            reply = self._queue.get_nowait()
        except queue.Empty:
            return False
        self._waiting = False
        self.history.append({"role": "assistant", "content": reply})
        self.lines.append(("loki", reply))
        _log("loki_ollama", reply)
        _trim_chat_log()
        face.reset_soft()
        face.react_happy()
        return True


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    pygame.init()
    pygame.display.set_caption("Loki")

    flags = 0
    try:
        info = pygame.display.Info()
        if info.current_w > 0:
            flags = pygame.NOFRAME
    except Exception:
        pass

    surf  = pygame.display.set_mode((W, H), flags)
    clock = pygame.time.Clock()

    try:
        font       = pygame.font.SysFont("dejavusans", 16, bold=False)
        font_small = pygame.font.SysFont("dejavusans", 13, bold=False)
    except Exception:
        font       = pygame.font.Font(None, 20)
        font_small = pygame.font.Font(None, 16)

    face   = LokiFace()
    scene  = SceneView()
    chat   = ChatManager()

    input_text   = ""
    input_active = False

    swipe_start  = None
    SWIPE_THRESH = 60
    CLOSE_RECT   = pygame.Rect(W - 40, 4, 36, 36)   # top-right ✕ button

    _log("session_start",
         f"loki_window started at {datetime.now().isoformat()}")

    running = True
    while running:
        dt  = clock.tick(FPS) / 1000.0
        now = time.time()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False

            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif input_active:
                    if ev.key == pygame.K_RETURN:
                        if input_text.strip():
                            chat.send(input_text.strip(), face)
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
                    mx = int(ev.x * W)
                    my = int(ev.y * H)
                swipe_start = (mx, my)

                # close button
                if CLOSE_RECT.collidepoint(mx, my):
                    running = False

                # input bar
                elif my >= H - 36:
                    input_active = True
                    pygame.key.start_text_input()
                elif mx < FACE_W:
                    face.react_touch()
                    face.show("hello ✦", 2.0)
                elif mx < W:
                    # tap on place list
                    x0   = SCENE_X + 18
                    base = 20
                    base += font.size(scene.current()["name"])[1] + 6 + 1 + 14
                    for line in scene.current()["desc"]:
                        base += font_small.size(line)[1] + 4
                    base += 10 + font_small.size("")[1] + 28 + 1 + 8
                    base += font_small.size("")[1] + 4
                    for p in PLACES:
                        ls_h = font_small.size(p["name"])[1] + 2
                        if base <= my < base + ls_h:
                            scene.go_to(p["id"])
                            face.show(f"going to\n{p['name'][:20]}", 2.5)
                            break
                        base += ls_h

            elif ev.type in (pygame.MOUSEBUTTONUP, pygame.FINGERUP):
                if swipe_start and ev.type == pygame.MOUSEBUTTONUP:
                    dx = ev.pos[0] - swipe_start[0]
                    dy = ev.pos[1] - swipe_start[1]
                    if abs(dx) > SWIPE_THRESH and abs(dx) > abs(dy):
                        if dx > 0:
                            face.react_touch(); face.show("♥", 2.0)
                        else:
                            face.react_wistful(); face.show("thinking…", 2.5)
                    elif abs(dy) > SWIPE_THRESH and abs(dy) > abs(dx):
                        if dy < 0:
                            face.react_happy(); face.show("!", 1.5)
                        else:
                            face.react_wistful(); face.show("…", 2.0)
                swipe_start = None

            elif ev.type == pygame.USEREVENT + 1:
                face.open_eyes()
                pygame.time.set_timer(pygame.USEREVENT + 1, 0)
            elif ev.type in (pygame.USEREVENT + 2,
                              pygame.USEREVENT + 3,
                              pygame.USEREVENT + 4):
                face.reset_soft()
                pygame.time.set_timer(ev.type, 0)

        face.tick(dt)
        scene.tick()
        if chat.poll(face):
            pass

        # draw
        surf.fill(BG)
        pygame.draw.line(surf, DIVIDER, (FACE_W, 0), (FACE_W, H), 1)
        face.draw(surf, font_small)
        scene.draw(surf, font, font_small, chat.lines, input_text, input_active)

        # close button ✕ — top right corner
        pygame.draw.rect(surf, (22, 16, 10), CLOSE_RECT, border_radius=6)
        pygame.draw.rect(surf, (50, 36, 20), CLOSE_RECT, width=1, border_radius=6)
        pad = 10
        cx1, cy1 = CLOSE_RECT.x + pad, CLOSE_RECT.y + pad
        cx2, cy2 = CLOSE_RECT.right - pad, CLOSE_RECT.bottom - pad
        pygame.draw.line(surf, (100, 70, 35), (cx1, cy1), (cx2, cy2), 2)
        pygame.draw.line(surf, (100, 70, 35), (cx2, cy1), (cx1, cy2), 2)

        pygame.display.flip()

    _log("session_end",
         f"loki_window closed at {datetime.now().isoformat()}")
    pygame.quit()


if __name__ == "__main__":
    main()
