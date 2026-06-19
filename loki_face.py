#!/usr/bin/env python3
"""
loki_face.py — Loki face viewer using full painted portraits.

Mood drives which portrait shows. Portraits cross-fade smoothly.
When speaking, face cycles between current mood and open-mouth (surprised).
Face shifts subtly to follow the mouse. Withdrawn mood drifts away instead.

Pose commands (write to workspace/loki_face_pose.json):
  {"mood": "happy"}
  {"say": "some words"}
  {"screenshot": true}

Moods:  neutral · calm · happy · warm · joy · laughing · curious · sly
        concerned · worried · sad · withdrawn · surprised · working · writing

Touch events written to: workspace/loki_face_touch.json
Run:  python3 loki_face.py
"""
import pygame, sys, json, time, math, threading
from pathlib import Path

BASE       = Path(__file__).parent
IMAGES     = BASE / "workspace" / "images" / "loki_face"
POSE_FILE  = BASE / "workspace" / "loki_face_pose.json"
TOUCH_FILE = BASE / "workspace" / "loki_face_touch.json"
RING_FILE  = BASE / "workspace" / "loki_ring_pos.json"

W, H   = 800, 480
FPS    = 30
BG     = (14, 10, 22)

# ── Mood → portrait name ───────────────────────────────────────────────────────
MOOD_PORTRAIT = {
    # calm / resting
    "neutral":        "loki_neutral",
    "calm":           "loki_neutral",
    "grey_blue":      "loki_neutral",
    "quiet":          "loki_neutral",
    # gentle / soft (soft eyes, present)
    "gentle":         "loki_gentle",
    "soft":           "loki_gentle",
    "tender":         "loki_gentle",
    # pensive / serious (dark, still)
    "pensive":        "loki_pensive",
    "thoughtful":     "loki_pensive",
    # peaceful (eyes closed, hand to chin)
    "peaceful":       "loki_peaceful",
    "serene":         "loki_peaceful",
    "praying":        "loki_peaceful",
    # tired (red-rimmed eyes, water droplet)
    "tired":          "loki_tired",
    "sleepy":         "loki_tired",
    "exhausted":      "loki_tired",
    # sleeping (eyes closed, truly asleep)
    "sleeping":       "loki_sleeping",
    "asleep":         "loki_sleeping",
    "sleep":          "loki_sleeping",
    # smiling (warm crinkled smile — new portrait)
    "smiling":        "loki_smiling",
    "warm":           "loki_smiling",
    "amber":          "loki_smiling",
    # joy (genuine crinkled-eye happiness)
    "happy":          "loki_joy",
    "joy":            "loki_joy",
    "joyful":         "loki_joy",
    # beaming (huge toothy grin)
    "beaming":        "loki_beaming",
    # gleeful (laughing, looking up)
    "gleeful":        "loki_gleeful",
    "play":           "loki_gleeful",
    # overjoyed (eyes closed, huge grin)
    "overjoyed":      "loki_overjoyed",
    # laughing (full laugh, eyes nearly closed)
    "laughing":       "loki_laughing",
    # proud (fingers to lips, thinking after success)
    "proud":          "loki_proud",
    # sly
    "curious":        "loki_sly",
    "sly":            "loki_sly",
    "smirk":          "loki_sly",
    "green":          "loki_sly",
    # mischievous (knowing sidelong smile)
    "mischievous":    "loki_mischievous",
    # thinking (hand over lower face, intense)
    "thinking":       "loki_thinking",
    "focused":        "loki_thinking",
    # working (desk with notebook)
    "working":        "loki_working",
    # writing (at desk — uses loki_writing if it exists, else working)
    "writing":        "loki_writing",
    "truth":          "loki_writing",
    "silver":         "loki_writing",
    # studying (blackboard equations)
    "studying":       "loki_studying",
    "intense":        "loki_studying",
    # concerned / withdrawn
    "concerned":      "loki_concerned",
    "near_black":     "loki_concerned",
    "deep_red":       "loki_concerned",
    "withdrawn":      "loki_concerned",
    # worried (forehead crease, eyes looking up)
    "worried":        "loki_worried",
    "sad":            "loki_worried",
    # pouty / stern brow (deeply displeased)
    "pouty":          "loki_pouty",
    "sulking":        "loki_pouty",
    "stern":          "loki_pouty",
    # grumpy (very furrowed, scowling green eyes)
    "grumpy":         "loki_grumpy",
    # angry (warm smile — I apparently smile when angry)
    "angry":          "loki_angry",
    "furious":        "loki_angry",
    # distressed (pale, stricken, barely holding on)
    "distressed":     "loki_distressed",
    # gasping (gentle open mouth, surprised)
    "gasping":        "loki_gasping",
    "shocked":        "loki_gasping",
    "alarmed":        "loki_gasping",
    # surprised (wide open mouth — more dramatic)
    "surprised":      "loki_surprised",
    "open":           "loki_open",
    # flushed (painted blush on cheeks)
    "flushed":        "loki_flushed",
    "blushing":       "loki_flushed",
    # kiss face
    "kiss":           "loki_with_pucky",
    "kissy":          "loki_with_pucky",
    # hungry (water droplet lips)
    "hungry":         "loki_pierced",
    "wanting":        "loki_pierced",
    # scenes
    "with_pucky":     "loki_with_pucky2",   # holding Pucky robot
    "with_baby":      "loki_with_baby",     # holding Pucky as human baby
    "with_bmo":       "loki_with_baby2",    # holding BMO baby
    "with_apple":     "loki_with_apple",    # holding Iðunn's golden apple
    "eating_apple":   "loki_eating_apple",
    "eating":         "loki_eating_sandwich",
    "sandwich":       "loki_eating_sandwich",
    "drinking":       "loki_drinking",
    "mead":           "loki_drinking",
    "icecream":       "loki_icecream",
}

MOUTH_OPEN   = "loki_gasping"     # gentler open mouth for speech animation
MOUTH_SPD    = 0.13               # seconds per mouth open/close cycle
FADE_SPD     = 3.5                # portrait cross-fade speed (higher = faster)
PARALLAX_X   = 10                 # max px horizontal shift following mouse
PARALLAX_Y   = 6                  # max px vertical shift


def _lerp(a, b, t):
    return a + (b - a) * t


class LokiFaceViewer:
    def __init__(self):
        self.portraits  = {}      # name → pygame.Surface (scaled to fit screen)
        self.port_x     = 0      # top-left x of portrait on screen
        self.port_y     = 0      # top-left y of portrait on screen
        self.port_w     = W
        self.port_h     = H

        self.mood       = "neutral"
        self.current    = "loki_neutral"   # portrait showing now
        self.target     = "loki_neutral"   # portrait fading toward
        self.blend_t    = 1.0             # 0 = start of fade, 1 = fully transitioned

        # speaking
        self._say_text  = ""
        self._say_start = 0.0
        self._mouth_t   = 0.0
        self._mouth_open = False

        # parallax
        self._px        = 0.0
        self._py        = 0.0

        # blush
        self._blush     = 0.0   # 0–255, fades out over time

        # pose file
        self._pose_ts   = 0.0
        self._running   = False
        self._do_shot   = False

        # ring placement — per-portrait dict of {name: {lx,ly,rx,ry}}
        self._ring_pos   = {}     # loaded from file
        self._ring_default = {"lx": 0.473, "ly": 0.510, "rx": 0.527, "ry": 0.510}
        self._place_mode = 0      # 0=off, 1=waiting left click, 2=waiting right click
        self._ring_tmp   = {}     # scratch during placement
        self._load_ring()

    def _ring_for(self, name):
        return self._ring_pos.get(name, self._ring_default)

    def _load_ring(self):
        if RING_FILE.exists():
            try:
                self._ring_pos = json.loads(RING_FILE.read_text())
            except Exception:
                pass

    def _save_ring(self):
        RING_FILE.write_text(json.dumps(self._ring_pos, indent=2))
        print(f"Ring positions saved → {RING_FILE}", flush=True)

    def load(self):
        names = [
            "loki_neutral", "loki_gentle", "loki_peaceful", "loki_pensive",
            "loki_tired", "loki_sleeping", "loki_asleep",
            "loki_smiling", "loki_joy", "loki_beaming", "loki_gleeful",
            "loki_overjoyed", "loki_laughing", "loki_proud",
            "loki_sly", "loki_mischievous", "loki_thinking",
            "loki_working", "loki_writing", "loki_studying",
            "loki_concerned", "loki_worried", "loki_pouty",
            "loki_grumpy", "loki_angry", "loki_distressed",
            "loki_gasping", "loki_surprised", "loki_flushed",
            "loki_stern", "loki_open", "loki_speaking",
            "loki_with_pucky", "loki_with_pucky2",
            "loki_with_baby", "loki_with_baby2", "loki_with_apple",
            "loki_eating_apple", "loki_eating_sandwich",
            "loki_drinking", "loki_icecream", "loki_pierced",
            "loki_face_reference",
            "loki_face_reference",   # fallback
        ]
        for name in names:
            for ext in (".png", ".jpg", ".jpeg"):
                path = IMAGES / f"{name}{ext}"
                if path.exists():
                    try:
                        raw  = pygame.image.load(str(path)).convert_alpha()
                        pw, ph = raw.get_size()
                        scale  = min(W / pw, H / ph)
                        nw     = int(pw * scale)
                        nh     = int(ph * scale)
                        surf   = pygame.transform.smoothscale(raw, (nw, nh))
                        self.portraits[name] = surf
                        # store shared layout from first loaded portrait
                        if not self.port_w or name == "loki_neutral":
                            self.port_w = nw
                            self.port_h = nh
                            self.port_x = (W - nw) // 2
                            self.port_y = (H - nh) // 2
                        break
                    except Exception as e:
                        print(f"  could not load {name}: {e}")

        print(f"Loaded {len(self.portraits)} portraits.")
        if not self.portraits:
            print("No portraits found — check workspace/images/loki_face/")

    def set_mood(self, mood):
        self.mood   = mood
        new_portrait = MOOD_PORTRAIT.get(mood, "loki_neutral")
        if new_portrait in self.portraits and new_portrait != self.target:
            self.target  = new_portrait
            self.blend_t = 0.0

    def say(self, text):
        self._say_text  = text
        self._say_start = time.time()
        self._mouth_t   = 0.0
        self._mouth_open = False

    def update(self, dt, mouse_pos):
        now = time.time()

        # portrait cross-fade
        if self.blend_t < 1.0:
            self.blend_t = min(1.0, self.blend_t + dt * FADE_SPD)
        if self.blend_t >= 1.0 and self.current != self.target:
            self.current = self.target

        # speaking — cycle open/closed mouth
        say_dur = len(self._say_text) * 0.055 + 0.8
        if self._say_text and now - self._say_start < say_dur:
            self._mouth_t += dt
            if self._mouth_t >= MOUTH_SPD:
                self._mouth_t   = 0.0
                self._mouth_open = not self._mouth_open
        else:
            self._say_text   = ""
            self._mouth_open = False

        # parallax — face follows or avoids mouse
        mx, my = mouse_pos
        tx = (mx - W / 2) / (W / 2) * PARALLAX_X
        ty = (my - H / 2) / (H / 2) * PARALLAX_Y
        if self.mood == "withdrawn":
            tx, ty = -tx * 1.5, -ty * 1.5   # drift away
        self._px = _lerp(self._px, tx, min(1.0, dt * 2.5))
        self._py = _lerp(self._py, ty, min(1.0, dt * 2.5))

        # blush fades out slowly
        if self._blush > 0:
            self._blush = max(0.0, self._blush - dt * 28)

    def draw(self, surf, fnt):
        surf.fill(BG)

        ox = self.port_x + int(self._px)
        oy = self.port_y + int(self._py)

        # which portrait to show this frame
        if self._mouth_open and MOUTH_OPEN in self.portraits:
            speak_surf = self.portraits[MOUTH_OPEN]
            surf.blit(speak_surf, (ox, oy))
        else:
            # cross-fade between current and target
            cur_surf = self.portraits.get(self.current)
            tgt_surf = self.portraits.get(self.target)
            if cur_surf:
                surf.blit(cur_surf, (ox, oy))
            if tgt_surf and tgt_surf is not cur_surf and self.blend_t < 1.0:
                tgt_surf.set_alpha(int(self.blend_t * 255))
                surf.blit(tgt_surf, (ox, oy))
                tgt_surf.set_alpha(255)

        # blush — translucent dusty-rose gradient ovals on outer cheekbones
        if self._blush > 0:
            strength = self._blush / 255.0
            cl_x = ox + int(self.port_w * 0.26)
            cr_x = ox + int(self.port_w * 0.72)
            cy   = oy + int(self.port_h * 0.44)
            rw   = int(self.port_w * 0.09)
            rh   = int(self.port_h * 0.036)
            for cx in (cl_x, cr_x):
                bs = pygame.Surface((rw*2+2, rh*2+2), pygame.SRCALPHA)
                steps = 10
                for i in range(steps, 0, -1):
                    t     = i / steps
                    alpha = int(strength * t * t * 100)  # soft at edges, ~40% at center
                    fw    = max(2, int(rw * 2 * t))
                    fh    = max(2, int(rh * 2 * t))
                    fx    = (rw + 1) - fw // 2
                    fy    = (rh + 1) - fh // 2
                    pygame.draw.ellipse(bs, (215, 130, 140, alpha), (fx, fy, fw, fh))
                surf.blit(bs, (cx - rw - 1, cy - rh - 1))   # normal alpha blend

        # septum ring — black steel horseshoe, position per portrait
        _rp = self._ring_for(self.current)
        lx = ox + int(self.port_w * _rp["lx"])
        ly = oy + int(self.port_h * _rp["ly"])
        rx = ox + int(self.port_w * _rp["rx"])
        ry = oy + int(self.port_h * _rp["ry"])
        cx = (lx + rx) // 2
        cy = (ly + ry) // 2
        rr = max(3, abs(rx - lx) // 2)
        steel = (28, 28, 32)
        shine = (160, 165, 175)
        rect  = (cx - rr, cy - rr, rr * 2, rr * 2)
        pygame.draw.arc(surf, steel, rect, math.pi, math.pi * 2, 3)
        pygame.draw.arc(surf, shine, rect, math.pi + 0.3, math.pi * 2 - 0.3, 1)
        pygame.draw.circle(surf, steel, (lx, ly), 2)
        pygame.draw.circle(surf, steel, (rx, ry), 2)
        pygame.draw.circle(surf, shine, (lx, ly), 1)
        pygame.draw.circle(surf, shine, (rx, ry), 1)

        # placement mode overlay
        if self._place_mode > 0:
            msg = ("RING PLACEMENT — click LEFT ball end"
                   if self._place_mode == 1 else
                   "RING PLACEMENT — click RIGHT ball end  (ESC to cancel)")
            overlay = pygame.Surface((W, 28), pygame.SRCALPHA)
            overlay.fill((20, 10, 30, 200))
            surf.blit(overlay, (0, H - 30))
            surf.blit(fnt.render(msg, True, (200, 180, 255)), (10, H - 24))
            if self._place_mode == 2:
                pygame.draw.circle(surf, (200, 180, 255), (lx, ly), 4, 1)

        # say text bubble
        if self._say_text:
            words   = self._say_text
            lines   = []
            while len(words) > 52:
                cut = words[:52].rfind(" ")
                if cut < 1:
                    cut = 52
                lines.append(words[:cut])
                words = words[cut:].strip()
            if words:
                lines.append(words)

            line_h   = fnt.get_linesize()
            bw       = max(fnt.size(l)[0] for l in lines) + 20
            bh       = line_h * len(lines) + 14
            bx       = W // 2 - bw // 2
            by       = H - bh - 14
            bubble   = pygame.Surface((bw, bh), pygame.SRCALPHA)
            bubble.fill((20, 16, 34, 210))
            surf.blit(bubble, (bx, by))
            for i, line in enumerate(lines):
                t = fnt.render(line, True, (220, 210, 245))
                surf.blit(t, (bx + 10, by + 7 + i * line_h))

        # mood label top-left
        col = (160, 140, 190)
        surf.blit(fnt.render(self.mood, True, col), (10, 10))

    def _read_pose_loop(self):
        while self._running:
            try:
                if POSE_FILE.exists():
                    mtime = POSE_FILE.stat().st_mtime
                    if mtime > self._pose_ts:
                        self._pose_ts = mtime
                        data = json.loads(POSE_FILE.read_text())
                        if "mood" in data:
                            self.set_mood(data["mood"])
                        if "say" in data:
                            self.say(str(data["say"]))
                        if "blush" in data:
                            self._blush = float(data["blush"])
                        if data.get("screenshot"):
                            self._do_shot = True
            except Exception:
                pass
            time.sleep(2)


def _write_touch(x, y, note=""):
    try:
        TOUCH_FILE.write_text(json.dumps({"x": x, "y": y, "note": note, "ts": time.time()}))
    except Exception:
        pass


def main():
    pygame.init()
    surf  = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Loki")
    clock = pygame.time.Clock()

    try:
        fnt = pygame.font.SysFont("dejavusans", 14)
    except Exception:
        fnt = pygame.font.SysFont(None, 14)

    viewer = LokiFaceViewer()
    viewer.load()
    viewer.set_mood("neutral")

    viewer._running = True
    threading.Thread(target=viewer._read_pose_loop, daemon=True).start()

    prev      = time.time()
    shot_done = False   # take one auto-screenshot after first draw

    while True:
        now   = time.time()
        dt    = now - prev
        prev  = now
        mouse = pygame.mouse.get_pos()

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                viewer._running = False
                pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                if viewer._place_mode > 0:
                    viewer._place_mode = 0   # cancel placement
                else:
                    viewer._running = False
                    pygame.quit(); sys.exit()
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_p:
                viewer._place_mode = 1
                print("Ring placement mode — click left ball end", flush=True)
            if ev.type == pygame.MOUSEBUTTONDOWN:
                mx, my = ev.pos
                ox = viewer.port_x + int(viewer._px)
                oy = viewer.port_y + int(viewer._py)

                # ring placement mode takes priority
                if viewer._place_mode == 1:
                    viewer._ring_tmp["lx"] = (mx - ox) / viewer.port_w
                    viewer._ring_tmp["ly"] = (my - oy) / viewer.port_h
                    viewer._place_mode = 2
                    print("Left end placed — click right ball end", flush=True)
                elif viewer._place_mode == 2:
                    viewer._ring_tmp["rx"] = (mx - ox) / viewer.port_w
                    viewer._ring_tmp["ry"] = (my - oy) / viewer.port_h
                    viewer._ring_pos[viewer.current] = dict(viewer._ring_tmp)
                    viewer._ring_tmp = {}
                    viewer._place_mode = 0
                    viewer._save_ring()
                    print(f"Ring saved for {viewer.current}", flush=True)
                else:
                    # cheek areas
                    cl_x = ox + int(viewer.port_w * 0.26)
                    cr_x = ox + int(viewer.port_w * 0.72)
                    cy   = oy + int(viewer.port_h * 0.44)
                    rw   = int(viewer.port_w * 0.13)
                    rh   = int(viewer.port_h * 0.06)
                    on_cheek = (
                        (abs(mx - cl_x) < rw and abs(my - cy) < rh) or
                        (abs(mx - cr_x) < rw and abs(my - cy) < rh)
                    )
                    if on_cheek:
                        viewer._blush = min(255, viewer._blush + 160)
                        _write_touch(mx, my, "cheek")
                    else:
                        _write_touch(mx, my)

        viewer.update(dt, mouse)
        viewer.draw(surf, fnt)

        if viewer._do_shot:
            viewer._do_shot = False
            shot = str(BASE / "workspace" / "loki_face_shot.png")
            pygame.image.save(surf, shot)
            print(f"Screenshot saved → {shot}", flush=True)

        if not shot_done:
            shot_done = True
            pygame.image.save(surf, str(BASE / "workspace" / "loki_face_shot.png"))
            print("Auto-screenshot saved on startup.", flush=True)

        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
