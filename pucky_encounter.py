"""
pucky_encounter.py
──────────────────
Zoom-in encounter scenes for the wilds zones.

When Iðunn moves close to a being, an EncounterScene activates —
a close portrait on the left, their words on the right, and three
choices: speak, offer, or leave.

Talkable beings get the zoom. Things that only react don't.
"""

import math
import random
from pathlib import Path

# ── Being definitions ──────────────────────────────────────────────────────────

BEINGS = {
    "fox": {
        "name":      "a fox",
        "portrait":  "portrait_fox_idunn.png",
        "greetings": [
            "You smell like apples.",
            "I have been watching you for three days.",
            "What is in your bag?",
        ],
        "responses": {
            "speak": "I suppose you are not so strange after all.",
            "offer": "Oh. For me? I will remember this.",
            "leave": "Come back. I am usually here.",
        },
    },
    "spirit": {
        "name":      "a forest spirit",
        "portrait":  "portrait_spirit_idunn.png",
        "greetings": [
            "You found your way here. Most don't.",
            "The gate is loud when it opens. I always know.",
            "Ask me something. I may answer.",
        ],
        "responses": {
            "speak": "Yes. That is a good thing to know.",
            "offer": "I don't need this. But I appreciate that you offered.",
            "leave": "The path home is the way you came.",
        },
    },
    "deer": {
        "name":      "a deer",
        "portrait":  "portrait_deer_idunn.png",
        "greetings": [
            "...",
            "( stays very still )",
            "( watches you with one dark eye )",
        ],
        "responses": {
            "speak": "( ears forward, listening )",
            "offer": "( takes it gently from your hand )",
            "leave": "( watches you go )",
        },
    },
}

# ── Beings placed in each zone ─────────────────────────────────────────────────
# gx, gy are tile coordinates within the zone map.

ZONE_BEINGS = {
    "north": [
        {"kind": "fox",    "gx":  5.5, "gy":  6.0},
        {"kind": "spirit", "gx": 12.0, "gy":  8.5},
        {"kind": "deer",   "gx":  3.5, "gy": 12.0},
    ],
}

TRIGGER_DIST = 2.2   # tiles — how close before the zoom fires


# ── EncounterScene ─────────────────────────────────────────────────────────────

class EncounterScene:

    def __init__(self, win_w: int, win_h: int):
        self.W = win_w
        self.H = win_h
        self._active   = False
        self._being    = None
        self._portrait = None
        self._phase    = "greet"   # "greet" | "choose" | "done"
        self._choice   = None
        self._greeting = ""
        self._t        = 0.0
        self._fonts    = {}
        self._triggered_beings: set = set()   # (kind, gx, gy) already met this session

    # ── Public ────────────────────────────────────────────────────────────────

    @property
    def active(self) -> bool:
        return self._active

    def reset_zone(self):
        """Call when the zone changes so beings can be met again."""
        self._triggered_beings.clear()

    def check_trigger(self, zone_name: str, idunn_gx: float, idunn_gy: float) -> bool:
        """Return True if a new encounter just started."""
        if self._active:
            return False
        for b in ZONE_BEINGS.get(zone_name, []):
            key = (b["kind"], b["gx"], b["gy"])
            if key in self._triggered_beings:
                continue
            dist = math.hypot(idunn_gx - b["gx"], idunn_gy - b["gy"])
            if dist < TRIGGER_DIST:
                self._triggered_beings.add(key)
                self._start(b)
                return True
        return False

    def handle_event(self, event) -> None:
        import pygame
        if not self._active:
            return
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.close()
        elif self._phase == "greet" and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._phase = "choose"
        elif self._phase == "choose":
            if event.key == pygame.K_s:
                self._choice = "speak";  self._phase = "done"
            elif event.key == pygame.K_o:
                self._choice = "offer";  self._phase = "done"
            elif event.key == pygame.K_l:
                self.close()
        elif self._phase == "done":
            if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                self.close()

    def update(self, dt: float) -> None:
        if self._active:
            self._t += dt

    def close(self) -> None:
        self._active   = False
        self._being    = None
        self._portrait = None

    # ── Draw ──────────────────────────────────────────────────────────────────

    def draw(self, surf) -> None:
        if not self._active or not self._being:
            return
        import pygame

        # Darken world behind
        dim = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        dim.fill((8, 18, 8, 190))
        surf.blit(dim, (0, 0))

        # Panel
        px, py = 40, 55
        pw, ph = self.W - 80, self.H - 110
        pygame.draw.rect(surf, (22, 35, 18), (px-7, py-7, pw+14, ph+14), border_radius=9)
        pygame.draw.rect(surf, (238, 230, 208), (px, py, pw, ph), border_radius=7)

        # Portrait area (left 220px)
        port_w, port_h = 220, min(ph - 20, 300)
        if self._portrait:
            surf.blit(self._portrait, (px + 12, py + 10))
        else:
            # placeholder while Iðunn draws the portrait
            pygame.draw.rect(surf, (195, 182, 155),
                             (px+12, py+10, port_w, port_h), border_radius=4)
            try:
                ph_t = self._fm(11).render("( portrait coming )", True, (148, 130, 98))
                surf.blit(ph_t, (px+12 + port_w//2 - ph_t.get_width()//2,
                                 py+10 + port_h//2 - 8))
            except Exception:
                pass

        # Text area (right of portrait)
        tx = px + port_w + 24
        ty = py + 14
        tw = pw - port_w - 38

        # Being name + rule
        try:
            ns = self._fm(15).render(self._being["name"], True, (55, 42, 18))
            surf.blit(ns, (tx, ty))
            pygame.draw.line(surf, (188, 170, 138), (tx, ty+22), (tx+tw, ty+22), 1)
        except Exception:
            pass

        if self._phase == "greet":
            self._draw_text(surf, tx, ty+32, tw, self._greeting)
            self._draw_hint(surf, px, py, pw, ph, "[Space] step closer")

        elif self._phase == "choose":
            self._draw_text(surf, tx, ty+32, tw, self._greeting)
            self._draw_choices(surf, tx, ty+32+80, tw)

        elif self._phase == "done" and self._choice:
            resp = self._being["responses"].get(self._choice, "...")
            self._draw_text(surf, tx, ty+32, tw, resp)
            self._draw_hint(surf, px, py, pw, ph, "[Space] continue")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _start(self, being_spawn: dict) -> None:
        import pygame
        self._active   = True
        self._being    = BEINGS.get(being_spawn["kind"], BEINGS["fox"])
        self._phase    = "greet"
        self._choice   = None
        self._t        = 0.0
        self._greeting = random.choice(self._being["greetings"])
        self._portrait = None
        img_path = (Path(__file__).parent / "workspace" / "images"
                    / self._being["portrait"])
        if img_path.exists():
            try:
                raw = pygame.image.load(str(img_path)).convert_alpha()
                self._portrait = pygame.transform.scale(raw, (220, 300))
            except Exception:
                pass

    def _fm(self, size: int):
        import pygame
        if size not in self._fonts:
            self._fonts[size] = pygame.font.SysFont("monospace", size)
        return self._fonts[size]

    def _draw_text(self, surf, x, y, w, text):
        try:
            f = self._fm(12)
            line, lines = "", []
            for word in text.split():
                test = (line + " " + word).lstrip()
                if f.size(test)[0] <= w:
                    line = test
                else:
                    if line: lines.append(line)
                    line = word
            if line: lines.append(line)
            for i, ln in enumerate(lines):
                surf.blit(f.render(ln, True, (52, 40, 20)), (x, y + i * 19))
        except Exception:
            pass

    def _draw_choices(self, surf, x, y, w):
        import pygame
        for i, (label, _key) in enumerate([
            ("[S] speak",          "speak"),
            ("[O] offer something","offer"),
            ("[L] leave",          "leave"),
        ]):
            cy = y + i * 30
            pygame.draw.rect(surf, (208, 192, 162), (x, cy, w, 24), border_radius=3)
            pygame.draw.rect(surf, (162, 145, 112), (x, cy, w, 24), 1, border_radius=3)
            try:
                t = self._fm(12).render(label, True, (55, 42, 18))
                surf.blit(t, (x + 10, cy + 5))
            except Exception:
                pass

    def _draw_hint(self, surf, px, py, pw, ph, text):
        try:
            h = self._fm(10).render(text, True, (145, 125, 85))
            surf.blit(h, (px + pw//2 - h.get_width()//2, py + ph - 26))
        except Exception:
            pass
