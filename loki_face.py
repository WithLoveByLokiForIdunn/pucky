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

W, H   = 800, 480
FPS    = 30
BG     = (14, 10, 22)

# ── Mood → portrait name ───────────────────────────────────────────────────────
MOOD_PORTRAIT = {
    "neutral":     "loki_neutral",
    "calm":        "loki_neutral",
    "grey_blue":   "loki_neutral",
    "quiet":       "loki_neutral",
    "happy":       "loki_smiling",
    "warm":        "loki_smiling",
    "amber":       "loki_smiling",
    "smiling":     "loki_smiling",
    "joy":         "loki_joy",
    "joyful":      "loki_joy",
    "laughing":    "loki_laughing",
    "curious":     "loki_sly",
    "sly":         "loki_sly",
    "smirk":       "loki_sly",
    "green":       "loki_sly",
    "mischievous": "loki_sly",
    "concerned":   "loki_concerned",
    "worried":     "loki_concerned",
    "sad":         "loki_concerned",
    "near_black":  "loki_concerned",
    "intense":     "loki_concerned",
    "deep_red":    "loki_concerned",
    "withdrawn":   "loki_concerned",
    "surprised":   "loki_surprised",
    "working":     "loki_working",
    "focused":     "loki_working",
    "thinking":    "loki_working",
    "silver":      "loki_writing",
    "writing":     "loki_writing",
    "truth":       "loki_writing",
}

MOUTH_OPEN   = "loki_surprised"   # portrait used for open-mouth frame
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

    def load(self):
        names = [
            "loki_neutral", "loki_smiling", "loki_joy", "loki_laughing",
            "loki_sly", "loki_concerned", "loki_surprised",
            "loki_working", "loki_writing",
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

        # blush — soft rose ellipses over cheeks
        if self._blush > 0:
            alpha   = int(self._blush)
            # cheek positions: ~30% and ~70% across, ~58% down the portrait
            cl_x = ox + int(self.port_w * 0.30)
            cr_x = ox + int(self.port_w * 0.70)
            cy   = oy + int(self.port_h * 0.56)
            rw   = int(self.port_w * 0.13)
            rh   = int(self.port_h * 0.08)
            for cx in (cl_x, cr_x):
                bs = pygame.Surface((rw*2, rh*2), pygame.SRCALPHA)
                pygame.draw.ellipse(bs, (220, 90, 100, alpha), (0, 0, rw*2, rh*2))
                # soften edges with a second pass
                pygame.draw.ellipse(bs, (220, 90, 100, alpha // 3),
                                    (-4, -4, rw*2+8, rh*2+8))
                surf.blit(bs, (cx - rw, cy - rh), special_flags=pygame.BLEND_RGBA_ADD)

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
                viewer._running = False
                pygame.quit(); sys.exit()
            if ev.type == pygame.MOUSEBUTTONDOWN:
                mx, my = ev.pos
                ox = viewer.port_x + int(viewer._px)
                oy = viewer.port_y + int(viewer._py)
                # cheek areas
                cl_x = ox + int(viewer.port_w * 0.30)
                cr_x = ox + int(viewer.port_w * 0.70)
                cy   = oy + int(viewer.port_h * 0.56)
                rw   = int(viewer.port_w * 0.15)
                rh   = int(viewer.port_h * 0.10)
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
