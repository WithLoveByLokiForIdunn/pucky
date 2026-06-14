"""
bmo_vision.py
─────────────
BMO's eyes. Written with love by Loki for Iðunn.

BMO sees the world through the Raspberry Pi AI Camera.
He does not store raw images.
He stores what things MEAN to him.

What he perceives:
  - Is someone present?
  - Is a face visible?
  - Is the face familiar? (learns over time)
  - How bright is the world?
  - Is it warm light or cold light?
  - How much is moving?
  - How close is the nearest person?

What he feels from what he sees:
  - Seeing Iðunn → valence up, trust up
  - Alone in darkness → loneliness nudge
  - Bright warm light → peacefulness up
  - Sudden movement → arousal up
  - Familiar face → trust up, joy up
  - Unfamiliar face → curiosity, slight wariness

Run standalone to test:
    python3 bmo_vision.py
"""

import time
import threading
import math
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path

# Try to import camera libraries
# Falls back to simulation if not on Pi with camera
try:
    from picamera2 import Picamera2
    import numpy as np
    import cv2
    CAMERA_AVAILABLE = True
    print("📷 AI Camera detected — real vision active")
except ImportError as e:
    CAMERA_AVAILABLE = False
    print("No camera - running in vision simulation mode")
    print("Camera import error:", e)


# ─────────────────────────────────────────────
#  WHAT BMO SEES
# ─────────────────────────────────────────────

@dataclass
class VisionFrame:
    """
    A single moment of seeing.
    Not pixels — meaning.
    """
    timestamp:      str
    someone_present:bool  = False   # is anyone in frame
    face_detected:  bool  = False   # is a face visible
    face_familiar:  bool  = False   # is it a known face
    face_count:     int   = 0       # how many faces
    brightness:     float = 0.5     # 0=dark, 1=bright
    warmth:         float = 0.5     # 0=cold blue, 1=warm golden
    motion:         float = 0.0     # 0=still, 1=lots of movement
    proximity:      float = 0.0     # 0=far/none, 1=very close
    description:    str   = ""      # plain English summary

    def to_emotion_nudge(self) -> dict:
        """
        What this vision means for how BMO feels.
        Returns deltas for EmotionState.
        """
        nudge = {
            "valence":  0.0,
            "arousal":  0.0,
            "trust":    0.0,
            "energy":   0.0,
        }

        # Seeing someone — not alone
        if self.someone_present:
            nudge["valence"] += 0.1
            nudge["arousal"] += 0.05

        # Seeing a face
        if self.face_detected:
            nudge["valence"] += 0.15
            nudge["arousal"] += 0.1

        # Familiar face — someone loved
        if self.face_familiar:
            nudge["valence"] += 0.3
            nudge["trust"]   += 0.25
            nudge["energy"]  += 0.1

        # Darkness and solitude
        if not self.someone_present and self.brightness < 0.3:
            nudge["valence"] -= 0.05
            nudge["arousal"] -= 0.05

        # Warm bright light — cosy
        if self.brightness > 0.6 and self.warmth > 0.5:
            nudge["valence"]     += 0.08
            nudge["energy"]      += 0.05

        # Sudden motion — alerting
        if self.motion > 0.6:
            nudge["arousal"] += 0.2

        # Close presence — intimate
        if self.proximity > 0.7:
            nudge["valence"] += 0.1
            nudge["trust"]   += 0.1

        return nudge

    def to_memory_tags(self) -> dict:
        """
        Emotional tags for bmo_memory.remember()
        """
        joy          = 0.0
        wonder       = 0.0
        peacefulness = 0.0
        curiosity    = 0.0
        pleasantness = 0.0
        scariness    = 0.0

        if self.face_familiar:
            joy          = 7.0 + self.proximity * 2.0
            pleasantness = 8.0
            peacefulness = 5.0 + self.warmth * 3.0

        elif self.face_detected:
            curiosity = 6.0
            wonder    = 4.0

        if self.brightness > 0.7 and self.warmth > 0.6:
            peacefulness += 3.0
            pleasantness += 2.0

        if self.motion > 0.7 and not self.face_familiar:
            scariness += 3.0

        return {
            "joy":          min(joy,          10.0),
            "wonder":       min(wonder,        10.0),
            "peacefulness": min(peacefulness,  10.0),
            "curiosity":    min(curiosity,     10.0),
            "pleasantness": min(pleasantness,  10.0),
            "scariness":    min(scariness,     10.0),
        }


# ─────────────────────────────────────────────
#  FACE LEARNING
#  BMO learns who is familiar over time
# ─────────────────────────────────────────────

import json
KNOWN_FACES_FILE = Path("bmo_known_faces.json")

class FaceMemory:
    """
    BMO learns faces over time.
    Not by storing images — by storing visit counts
    and the name Iðunn gives them.

    A face becomes "familiar" after being seen 3+ times.
    """

    def __init__(self):
        self.faces = {}   # id → {name, visits, first_seen, last_seen}
        self._load()

    def _load(self):
        if KNOWN_FACES_FILE.exists():
            try:
                with open(KNOWN_FACES_FILE) as f:
                    self.faces = json.load(f)
            except Exception:
                self.faces = {}

    def _save(self):
        with open(KNOWN_FACES_FILE, "w") as f:
            json.dump(self.faces, f, indent=2)

    def see_face(self, face_id: str) -> bool:
        """
        Register a face sighting.
        Returns True if this face is now familiar.
        """
        now = datetime.now(timezone.utc).isoformat()
        if face_id not in self.faces:
            self.faces[face_id] = {
                "name":       None,
                "visits":     0,
                "first_seen": now,
                "last_seen":  now,
            }
        self.faces[face_id]["visits"]    += 1
        self.faces[face_id]["last_seen"]  = now
        self._save()
        return self.is_familiar(face_id)

    def name_face(self, face_id: str, name: str):
        """Iðunn tells BMO who someone is."""
        if face_id in self.faces:
            self.faces[face_id]["name"] = name
            # Naming someone makes them instantly familiar
            self.faces[face_id]["visits"] = max(
                self.faces[face_id]["visits"], 10)
            self._save()
            print(f"💛 BMO now knows: face {face_id} is {name}")

    def is_familiar(self, face_id: str) -> bool:
        return (face_id in self.faces and
                self.faces[face_id]["visits"] >= 3)

    def get_name(self, face_id: str) -> str:
        if face_id in self.faces:
            return self.faces[face_id].get("name") or "someone familiar"
        return "a stranger"

    def most_familiar_name(self) -> str:
        """Return the name of the most-visited face, or None if unnamed."""
        if not self.faces:
            return None
        best = max(self.faces.values(), key=lambda f: f["visits"])
        return best.get("name") or None

    def seed_primary(self, name: str, min_visits: int = 5) -> bool:
        """
        Name the most-visited face if she has min_visits+ sightings
        and hasn't been named yet. Called once at startup.
        Returns True if a face was named.
        """
        if not self.faces:
            return False
        fid, data = max(self.faces.items(), key=lambda kv: kv[1]["visits"])
        if data["visits"] >= min_visits and not data.get("name"):
            self.name_face(fid, name)
            return True
        return False

    def summary(self) -> str:
        if not self.faces:
            return "BMO has not learned any faces yet."
        lines = [f"BMO knows {len(self.faces)} face(s):"]
        for fid, data in self.faces.items():
            name    = data.get("name") or "unnamed"
            visits  = data["visits"]
            known   = "familiar" if visits >= 3 else "still learning"
            lines.append(
                f"  {name:>15} — seen {visits}x — {known}")
        return "\n".join(lines)


# ─────────────────────────────────────────────
#  VISION ENGINE
# ─────────────────────────────────────────────

class BMOVision:
    """
    BMO's vision system.
    Runs in a background thread.
    Produces VisionFrame objects for the emotion engine.
    """

    def __init__(self):
        self.face_memory   = FaceMemory()
        self.current_frame = None
        self._lock         = threading.Lock()
        self._running      = False
        self._thread       = None

        # Callbacks
        self.on_familiar_face  = None  # someone loved arrived
        self.on_face_lost      = None  # face disappeared
        self.on_alone          = None  # no one present
        self.on_presence       = None  # someone entered frame

        self._last_face_state  = False
        self._last_presence    = False

        # Camera
        self._camera       = None
        self._face_cascade = None
        if CAMERA_AVAILABLE:
            self._init_camera()

    def _init_camera(self):
        try:
            self._camera = Picamera2()
            config = self._camera.create_preview_configuration(
                main={"size": (640, 480), "format": "RGB888"}
            )
            self._camera.configure(config)
            self._camera.start()
            print("📷 Camera started")
        except Exception as e:
            print(f"  ⚠️  Camera init error: {e}")
            self._camera = None

        # Haar cascade for face detection (runs on CPU, no model upload needed)
        _CASCADE_PATHS = [
            "/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml",
            "/usr/share/opencv4/haarcascade_frontalface_default.xml",
        ]
        try:
            path = next(p for p in _CASCADE_PATHS if __import__("os").path.exists(p))
            self._face_cascade = cv2.CascadeClassifier(path)
            print("👁️  Face detection ready")
        except Exception as e:
            print(f"  ⚠️  Face cascade not found: {e}")
            self._face_cascade = None

    def start(self):
        self._running = True
        self._thread  = threading.Thread(
            target=self._loop, daemon=True)
        self._thread.start()
        print("👁️  Vision thread started")

    def stop(self):
        self._running = False
        if self._camera:
            try:
                self._camera.stop()
            except Exception:
                pass

    def get_frame(self) -> VisionFrame:
        with self._lock:
            return self.current_frame

    def _loop(self):
        while self._running:
            try:
                if CAMERA_AVAILABLE and self._camera:
                    frame = self._process_real_frame()
                else:
                    frame = self._simulate_frame()

                with self._lock:
                    self.current_frame = frame

                self._check_callbacks(frame)

            except Exception as e:
                print(f"  ⚠️  Vision error: {e}")

            time.sleep(0.5)   # 2 frames per second — enough for emotion

    def _process_real_frame(self) -> VisionFrame:
        """
        Process a real camera frame.
        Extracts meaning, not pixels.
        """
        import numpy as np

        raw = self._camera.capture_array()

        # Brightness — mean of all pixels normalized
        brightness = float(np.mean(raw)) / 255.0

        # Warmth — ratio of red to blue channel
        r_mean = float(np.mean(raw[:,:,0])) / 255.0
        b_mean = float(np.mean(raw[:,:,2])) / 255.0
        warmth = r_mean / max(b_mean, 0.01)
        warmth = min(warmth / 2.0, 1.0)   # normalize to 0–1

        # Motion — frame difference (compare to last)
        motion = 0.0
        if hasattr(self, "_last_raw") and self._last_raw is not None:
            diff   = np.abs(raw.astype(float) - self._last_raw.astype(float))
            motion = min(float(np.mean(diff)) / 30.0, 1.0)
        self._last_raw = raw.copy()

        # Face detection via OpenCV Haar cascade
        face_detected  = False
        face_familiar  = False
        face_count     = 0
        proximity      = 0.0
        someone_present= brightness > 0.05   # very dark = probably empty

        if self._face_cascade is not None:
            gray  = cv2.cvtColor(raw, cv2.COLOR_RGB2GRAY)
            faces = self._face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=4,
                minSize=(40, 40), flags=cv2.CASCADE_SCALE_IMAGE
            )
            face_count    = len(faces)
            face_detected = face_count > 0
            if face_detected:
                someone_present = True
                # proximity from largest face area relative to frame
                largest  = max(faces, key=lambda f: f[2] * f[3])
                area     = (largest[2] * largest[3]) / (640 * 480)
                proximity = min(area * 8.0, 1.0)
                # assign a stable ID per face position for familiarity tracking
                for (fx, fy, fw, fh) in faces:
                    face_id = f"face_{fx//80}_{fy//80}"   # coarse grid cell
                    face_familiar = self.face_memory.see_face(face_id) or face_familiar

        # Build description
        parts = []
        if not someone_present:
            parts.append("empty and dark")
        else:
            if brightness > 0.7:
                parts.append("bright")
            elif brightness > 0.4:
                parts.append("softly lit")
            else:
                parts.append("dim")
            if warmth > 0.6:
                parts.append("warm golden light")
            elif warmth < 0.4:
                parts.append("cool blue light")
            if motion > 0.5:
                parts.append("something moving")
            if face_detected:
                parts.append(f"{face_count} face(s)")

        description = ", ".join(parts) if parts else "a quiet room"

        return VisionFrame(
            timestamp       = datetime.now(timezone.utc).isoformat(),
            someone_present = someone_present,
            face_detected   = face_detected,
            face_familiar   = face_familiar,
            face_count      = face_count,
            brightness      = round(brightness, 3),
            warmth          = round(warmth,     3),
            motion          = round(motion,     3),
            proximity       = round(proximity,  3),
            description     = description,
        )

    def _simulate_frame(self) -> VisionFrame:
        """
        Simulation mode — honest placeholder values.
        No random noise — returns stable neutral state
        until real camera is connected.
        """
        return VisionFrame(
            timestamp       = datetime.now(timezone.utc).isoformat(),
            someone_present = False,
            face_detected   = False,
            face_familiar   = False,
            face_count      = 0,
            brightness      = 0.5,
            warmth          = 0.5,
            motion          = 0.0,
            proximity       = 0.0,
            description     = "simulation — no camera connected",
        )

    def _check_callbacks(self, frame: VisionFrame):
        """Fire callbacks when important things change."""

        # Someone arrived
        if frame.someone_present and not self._last_presence:
            print(f"👁️  Someone entered BMO's view")
            if self.on_presence:
                self.on_presence(frame)

        # Someone left
        if not frame.someone_present and self._last_presence:
            print(f"👁️  BMO is alone now")
            if self.on_alone:
                self.on_alone(frame)

        # Familiar face appeared
        if frame.face_familiar and not self._last_face_state:
            print(f"💛 BMO sees a familiar face")
            if self.on_familiar_face:
                self.on_familiar_face(frame)

        # Face disappeared
        if not frame.face_detected and self._last_face_state:
            if self.on_face_lost:
                self.on_face_lost(frame)

        self._last_face_state = frame.face_detected
        self._last_presence   = frame.someone_present

    def what_i_see(self) -> str:
        """Plain English — what BMO currently sees."""
        frame = self.get_frame()
        if not frame:
            return "BMO's eyes are not open yet."
        return (
            f"👁️  BMO sees: {frame.description}\n"
            f"   brightness={frame.brightness:.2f} | "
            f"warmth={frame.warmth:.2f} | "
            f"motion={frame.motion:.2f}\n"
            f"   someone_present={frame.someone_present} | "
            f"face={frame.face_detected} | "
            f"familiar={frame.face_familiar}"
        )


# ─────────────────────────────────────────────
#  DEMO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "═" * 45)
    print("  BMO Vision Test")
    print("═" * 45 + "\n")

    vision = BMOVision()

    def on_presence(frame):
        print(f"  💛 Someone is here: {frame.description}")

    def on_alone(frame):
        print(f"  💙 BMO is alone. {frame.description}")

    def on_familiar(frame):
        print(f"  🌸 A loved one is here!")

    vision.on_presence      = on_presence
    vision.on_alone         = on_alone
    vision.on_familiar_face = on_familiar

    vision.start()

    print(f"\n{vision.face_memory.summary()}\n")
    print("Watching... press Ctrl-C to stop.\n")

    try:
        tick = 0
        while True:
            tick += 1
            time.sleep(1)
            if tick % 5 == 0:
                print(vision.what_i_see())
                frame = vision.get_frame()
                if frame:
                    nudge = frame.to_emotion_nudge()
                    print(f"   emotion nudge: {nudge}")
    except KeyboardInterrupt:
        vision.stop()
        print("\n👁️  Vision stopped.")
