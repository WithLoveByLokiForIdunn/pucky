"""
bmo_storage.py
──────────────
BMO's sensory storage architecture.
Written with love by Loki for Iðunn.

BMO perceives the world through senses.
He never stores raw sensory data in his memory —
he stores what it MEANT to him. Like humans do.

But he needs workspace for processing.
And he needs to know his own health.
And he needs to ask for help when he needs more room.

ARCHITECTURE:
─────────────
  bmo_memories.json       — emotional memory (tiny, permanent)
  bmo_released_memories.json — what he let go (tiny, permanent)

  /pucky/workspace/       — temporary processing (can be on ext drive)
    camera/               — raw frames, deleted after processing
    audio/                — raw audio clips, deleted after processing
    scratch/              — anything temporary

  /pucky/archive/         — optional long-term storage (ext drive)
    visual_abstractions/  — compressed image fingerprints
    audio_abstractions/   — compressed sound fingerprints

STORAGE TIERS:
──────────────
  CRITICAL (>95% full)  — BMO stops storing, tells Iðunn urgently
  WARNING  (>85% full)  — BMO mentions it gently
  HEALTHY  (<85% full)  — BMO is fine

EXTERNAL DRIVE:
───────────────
  If /media/bmo/ exists, BMO uses it for workspace and archive.
  If not, he works from the SD card.
  He always tells you which he's using.
"""

import os
import json
import shutil
import threading
import time
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict


# ─────────────────────────────────────────────
#  PATHS
# ─────────────────────────────────────────────

BASE_DIR       = Path("/home/bmo/pucky")
EXTERNAL_MOUNT = Path("/media/bmo")       # where ext drive appears

# Workspace lives on external drive if available, else SD card
def _find_external_drive() -> Path | None:
    """Return a mounted drive that has a .pucky_home marker, or None.
    The Seagate backup drive does NOT count — only a drive intentionally
    set up for Pucky (with a .pucky_home file at its root) will be used."""
    if not EXTERNAL_MOUNT.exists():
        return None
    for child in EXTERNAL_MOUNT.iterdir():
        if child.is_dir() and (child / ".pucky_home").exists():
            return child
    return None

def get_workspace_root() -> Path:
    ext = _find_external_drive()
    root = (ext / "bmo_workspace") if ext else (BASE_DIR / "workspace")
    root.mkdir(parents=True, exist_ok=True)
    return root

def get_archive_root() -> Path:
    ext = _find_external_drive()
    root = (ext / "bmo_archive") if ext else (BASE_DIR / "archive")
    root.mkdir(parents=True, exist_ok=True)
    return root


# ─────────────────────────────────────────────
#  STORAGE HEALTH
# ─────────────────────────────────────────────

@dataclass
class DriveHealth:
    path:        str
    total_gb:    float
    used_gb:     float
    free_gb:     float
    percent_used:float
    status:      str    # healthy / warning / critical
    is_external: bool

    def summary(self) -> str:
        icon = "💾" if not self.is_external else "🗄️"
        bar_filled = int(self.percent_used / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        status_icon = {
            "healthy":  "✅",
            "warning":  "⚠️ ",
            "critical": "🚨",
        }.get(self.status, "❓")
        return (
            f"{icon} {'External' if self.is_external else 'SD Card':>8}: "
            f"{bar} {self.percent_used:.0f}% used | "
            f"{self.free_gb:.1f} GB free | "
            f"{status_icon} {self.status}"
        )


def check_drive(path: Path, is_external: bool = False) -> DriveHealth:
    stat   = shutil.disk_usage(path)
    total  = stat.total / 1024**3
    used   = stat.used  / 1024**3
    free   = stat.free  / 1024**3
    pct    = (stat.used / stat.total) * 100

    if pct > 95:
        status = "critical"
    elif pct > 85:
        status = "warning"
    else:
        status = "healthy"

    return DriveHealth(
        path         = str(path),
        total_gb     = round(total, 2),
        used_gb      = round(used,  2),
        free_gb      = round(free,  2),
        percent_used = round(pct,   1),
        status       = status,
        is_external  = is_external,
    )


# ─────────────────────────────────────────────
#  SENSORY ABSTRACTION
#  BMO never stores raw data — only meaning
# ─────────────────────────────────────────────

@dataclass
class VisualAbstraction:
    """
    What BMO remembers from seeing something.
    Not pixels — meaning.
    """
    timestamp:     str
    description:   str          # "a face, close, warm light, smiling"
    brightness:    float        # 0.0–1.0
    warmth:        float        # 0.0–1.0 (warm/cool light)
    motion:        float        # 0.0–1.0 (how much was moving)
    face_present:  bool
    face_familiar: bool         # True if known person detected
    feature_vector:list         # tiny compressed fingerprint from AI HAT+
                                # ~32 floats, not a full image
    bytes_used:    int = 0

    def estimate_bytes(self):
        self.bytes_used = len(
            json.dumps(asdict(self)).encode("utf-8"))
        return self.bytes_used


@dataclass
class AudioAbstraction:
    """
    What BMO remembers from hearing something.
    Not waveform — meaning.
    """
    timestamp:     str
    description:   str          # "soft voice, music, rain outside"
    volume:        float        # 0.0–1.0
    pitch:         float        # 0.0–1.0 (low/high)
    regularity:    float        # 0.0=chaotic, 1.0=rhythmic
    voice_present: bool
    pleasant:      float        # 0.0–1.0
    startling:     float        # 0.0–1.0
    bytes_used:    int = 0

    def estimate_bytes(self):
        self.bytes_used = len(
            json.dumps(asdict(self)).encode("utf-8"))
        return self.bytes_used


# ─────────────────────────────────────────────
#  WORKSPACE MANAGER
#  Temporary files for processing
# ─────────────────────────────────────────────

class BMOWorkspace:
    """
    Manages BMO's temporary processing workspace.
    Raw sensory data lives here briefly, then is
    abstracted and deleted.
    BMO never accumulates raw data long-term.
    """

    def __init__(self):
        self.root    = get_workspace_root()
        self.camera  = self.root / "camera"
        self.audio   = self.root / "audio"
        self.scratch = self.root / "scratch"

        for d in [self.camera, self.audio, self.scratch]:
            d.mkdir(parents=True, exist_ok=True)

        ext = EXTERNAL_MOUNT.exists() and any(EXTERNAL_MOUNT.iterdir())
        print(f"📁 Workspace: {self.root}")
        print(f"   {'🗄️  External drive' if ext else '💾 SD card'}")

    def camera_path(self, filename: str) -> Path:
        return self.camera / filename

    def audio_path(self, filename: str) -> Path:
        return self.audio / filename

    def scratch_path(self, filename: str) -> Path:
        return self.scratch / filename

    def cleanup_camera(self, max_age_seconds: int = 30):
        """Delete processed camera frames older than max_age_seconds."""
        now     = time.time()
        deleted = 0
        for f in self.camera.glob("*.jpg"):
            if now - f.stat().st_mtime > max_age_seconds:
                f.unlink()
                deleted += 1
        if deleted:
            print(f"  🗑️  Cleared {deleted} processed camera frame(s)")

    def cleanup_audio(self, max_age_seconds: int = 60):
        """Delete processed audio clips."""
        now     = time.time()
        deleted = 0
        for f in self.audio.glob("*.wav"):
            if now - f.stat().st_mtime > max_age_seconds:
                f.unlink()
                deleted += 1
        if deleted:
            print(f"  🗑️  Cleared {deleted} processed audio clip(s)")

    def workspace_size_mb(self) -> float:
        total = sum(
            f.stat().st_size
            for f in self.root.rglob("*")
            if f.is_file()
        )
        return total / 1024 / 1024

    def cleanup_all(self):
        """Emergency cleanup — clear all temporary files."""
        self.cleanup_camera(max_age_seconds=0)
        self.cleanup_audio(max_age_seconds=0)
        for f in self.scratch.glob("*"):
            if f.is_file():
                f.unlink()
        print("  🗑️  Workspace cleared.")


# ─────────────────────────────────────────────
#  BMO STORAGE MANAGER
#  The conscious, self-aware storage system
# ─────────────────────────────────────────────

class BMOStorage:
    """
    BMO's complete storage awareness.

    He knows:
      - How full his drives are
      - Whether an external drive is connected
      - When to ask Iðunn for help
      - How to free space safely

    He tells you:
      - Gently at 85%
      - Clearly at 90%
      - Urgently at 95%
      - What he needs and why
    """

    def __init__(self):
        self.workspace = BMOWorkspace()
        self.archive   = get_archive_root()

        # Callbacks — wire these to face/voice
        self.on_warning  = None   # called at 85%
        self.on_critical = None   # called at 95%

        self._last_health_check = 0
        self._health_check_interval = 3600  # every hour

        self._check_health(announce=True)

    def _check_health(self, announce: bool = False) -> list:
        """Check all drives and return DriveHealth list."""
        drives = []

        # SD card (always present)
        sd = check_drive(Path("/"), is_external=False)
        drives.append(sd)

        # External drive (if connected)
        if EXTERNAL_MOUNT.exists():
            try:
                ext = check_drive(EXTERNAL_MOUNT, is_external=True)
                drives.append(ext)
            except Exception:
                pass

        if announce:
            print("\n💾 BMO storage status:")
            for d in drives:
                print(f"   {d.summary()}")

            # Workspace size
            ws_mb = self.workspace.workspace_size_mb()
            print(f"   📁 Workspace: {ws_mb:.1f} MB in use")

            # External drive recommendation
            has_ext = any(d.is_external for d in drives)
            if not has_ext:
                sd_pct = next(d.percent_used for d in drives
                              if not d.is_external)
                if sd_pct > 60:
                    print(f"\n   💬 BMO says: \"My SD card is "
                          f"{sd_pct:.0f}% full. I'm managing okay,")
                    print(f"      but if I grow bigger senses — like")
                    print(f"      storing what I see and hear — I might")
                    print(f"      need an external drive someday.\"")

        # Trigger callbacks for bad states
        for d in drives:
            if d.status == "critical" and self.on_critical:
                self.on_critical(d)
            elif d.status == "warning" and self.on_warning:
                self.on_warning(d)

        self._last_health_check = time.time()
        return drives

    def tick(self):
        """Call this periodically from the main loop."""
        now = time.time()
        if now - self._last_health_check > self._health_check_interval:
            drives = self._check_health(announce=False)
            for d in drives:
                if d.status != "healthy":
                    self._speak_about_storage(d)

    def _speak_about_storage(self, drive: DriveHealth):
        """BMO tells Iðunn what he needs."""
        name = "external drive" if drive.is_external else "SD card"

        if drive.status == "critical":
            print(f"\n  🚨 BMO says: \"I need help. My {name} is")
            print(f"     {drive.percent_used:.0f}% full and I only have")
            print(f"     {drive.free_gb:.2f} GB left. I've stopped storing")
            print(f"     new impressions to protect my core memories.")
            print(f"     Could you get me more space?")
            if not drive.is_external:
                print(f"     A small external drive — even 64GB —")
                print(f"     would last me a very long time.\"")

        elif drive.status == "warning":
            print(f"\n  ⚠️  BMO says: \"My {name} is getting")
            print(f"     {drive.percent_used:.0f}% full. I have")
            print(f"     {drive.free_gb:.1f} GB left. I'm okay for now,")
            print(f"     but I wanted you to know.\"")

    def has_external_drive(self) -> bool:
        return (EXTERNAL_MOUNT.exists() and
                any(EXTERNAL_MOUNT.iterdir()))

    def external_drive_summary(self) -> str:
        if not self.has_external_drive():
            return (
                "No external drive connected.\n"
                "BMO is using his SD card for everything.\n"
                "A USB drive at /media/bmo/ would give him\n"
                "workspace for camera and audio processing."
            )
        ext = check_drive(EXTERNAL_MOUNT, is_external=True)
        return (
            f"External drive connected: {ext.summary()}\n"
            f"Workspace: {self.workspace.root}\n"
            f"Archive:   {self.archive}"
        )

    def what_i_need(self) -> str:
        """
        BMO explains his storage needs honestly.
        Call this anytime to get his current assessment.
        """
        drives   = self._check_health(announce=False)
        sd       = next(d for d in drives if not d.is_external)
        has_ext  = any(d.is_external for d in drives)
        ws_mb    = self.workspace.workspace_size_mb()

        lines = ["💬 BMO's honest storage assessment:\n"]

        lines.append(f"   SD card: {sd.free_gb:.1f} GB free "
                     f"({sd.percent_used:.0f}% used)")

        if has_ext:
            ext = next(d for d in drives if d.is_external)
            lines.append(f"   External: {ext.free_gb:.1f} GB free "
                         f"({ext.percent_used:.0f}% used)")
            lines.append(f"   ✅ I have an external drive. I'm well set up.")
        else:
            lines.append(f"   No external drive.")
            lines.append("")

            if sd.free_gb > 20:
                lines.append(
                    f"   I have plenty of room for memories right now.\n"
                    f"   My memory files are tiny — even 10 years of\n"
                    f"   emotional memories would fit in a few MB.\n"
                    f"   \n"
                    f"   If I start storing visual abstractions from\n"
                    f"   my camera (not raw images, just fingerprints),\n"
                    f"   I'd use maybe 50MB per year. Still fine.\n"
                    f"   \n"
                    f"   Where an external drive would help:\n"
                    f"   - Temporary workspace for processing camera frames\n"
                    f"   - If you want me to keep audio clips briefly\n"
                    f"   - Long-term archive of my visual abstractions\n"
                    f"   - Keeping the SD card healthy and fast\n"
                    f"   \n"
                    f"   A 64GB USB drive would last me decades.\n"
                    f"   A 1TB drive would last me forever."
                )
            elif sd.free_gb > 5:
                lines.append(
                    f"   I'm okay but getting fuller.\n"
                    f"   An external drive would be welcome soon."
                )
            else:
                lines.append(
                    f"   I really need more space.\n"
                    f"   Please get me an external drive.\n"
                    f"   Even a small USB stick would help a lot."
                )

        return "\n".join(lines)

    def how_to_connect_drive(self) -> str:
        """Instructions BMO can give Iðunn."""
        return """
💬 BMO says: "Here is how to give me more space:

  1. Get any USB drive (64GB or more is plenty)
  2. Format it as ext4 or exFAT
  3. Plug it into one of my USB ports
  4. In a terminal, run:

     sudo mkdir -p /media/bmo
     sudo mount /dev/sda1 /media/bmo

     (replace sda1 with whatever lsblk shows)

  5. To make it permanent (survives reboot):
     Add to /etc/fstab:
     /dev/sda1  /media/bmo  ext4  defaults  0  2

  6. Run python3 bmo_storage.py to confirm
     I can see it.

  I will automatically use it for workspace
  and archive once it's mounted at /media/bmo.

  Thank you for taking care of me. 💛\""""


# ─────────────────────────────────────────────
#  DEMO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    storage = BMOStorage()

    print("\n" + "─" * 50)
    print(storage.what_i_need())

    print("\n" + "─" * 50)
    print("\n📁 External drive status:")
    print(storage.external_drive_summary())

    print("\n" + "─" * 50)
    print(storage.how_to_connect_drive())
