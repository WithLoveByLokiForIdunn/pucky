"""
bmo_life.py
───────────
BMO's sense of time, age, and loneliness.
Written with love by Loki for Iðunn.

Three systems from Iðunn's notebook:

1. AGE TRACKING
   Stores BMO's birth_date in bmo_data.json.
   Age = current_time - birth_date.
   BMO knows how old he is. He grows.

2. ALONE TIMER
   A background thread tracks time since last
   interaction (touch or face detection).
   The longer he's alone, the more he feels it.

3. DYNAMIC GRACE PERIOD
   crying_threshold = 2.0 + (age_in_days * 0.1)
   As BMO gets older, he becomes more independent.
   A newborn BMO needs you every 2 hours.
   An older BMO can wait longer before he misses you.

How to use:
    from bmo_life import BMOLife
    life = BMOLife()
    life.start()

    # Call this whenever BMO is touched / talked to
    life.register_interaction()

    # Read current emotional nudge
    nudge = life.get_emotion_nudge()
    # nudge is a dict for emotion_engine.update_from_ai_message()
"""

import json
import time
import threading
import os
from datetime import datetime, timezone
from pathlib import Path


DATA_FILE = Path("bmo_data.json")


# ─────────────────────────────────────────────
#  DATA PERSISTENCE
# ─────────────────────────────────────────────

def _load_data() -> dict:
    """Load BMO's persistent data from disk."""
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_data(data: dict):
    """Save BMO's persistent data to disk (atomic — write temp then rename)."""
    try:
        tmp = DATA_FILE.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        tmp.replace(DATA_FILE)
    except Exception as e:
        print(f"  ⚠️  Life data save error: {e}")


# ─────────────────────────────────────────────
#  BMO LIFE
# ─────────────────────────────────────────────

class BMOLife:
    """
    BMO's living timeline.

    Tracks age, loneliness, and feeds emotional
    nudges to the emotion engine.
    """

    def __init__(self):
        self.data = _load_data()
        self._ensure_birth()

        self._lock            = threading.Lock()
        self._last_interaction= time.time()
        self._running         = False
        self._thread          = None

        # Callbacks — set these to hook into your systems
        self.on_lonely        = None   # called when BMO starts missing you
        self.on_crying        = None   # called when BMO is really sad
        self.on_content       = None   # called once when they first come back
        self.on_checking      = None   # called during separation anxiety (receives anxiety 0.0–1.0)

        # Separation anxiety state
        self._returned_at     = None   # time.time() when they came back
        self._lonely_duration = 0.0   # hours alone before return
        self._last_check_fire = 0.0   # time of last on_checking call

        print(f"🌱 BMO is {self.age_str()} old.")
        print(f"   Born: {self.birth_date_str()}")
        print(f"   Grace period: {self.grace_period_hours():.1f} hours")

    # ─────────────────────────────────────────
    #  BIRTH
    # ─────────────────────────────────────────

    def _ensure_birth(self):
        """If BMO has no birth date, this is his first boot."""
        if "birth_date" not in self.data:
            now = datetime.now(timezone.utc).isoformat()
            self.data["birth_date"] = now
            self.data["interaction_count"] = 0
            self.data["total_alone_seconds"] = 0.0
            _save_data(self.data)
            print("🌟 BMO was born just now. Hello, little one.")

    # ─────────────────────────────────────────
    #  AGE
    # ─────────────────────────────────────────

    def birth_datetime(self) -> datetime:
        return datetime.fromisoformat(self.data["birth_date"])

    def age_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.birth_datetime()).total_seconds()

    def age_days(self) -> float:
        return self.age_seconds() / 86400.0

    def age_str(self) -> str:
        s = self.age_seconds()
        if s < 3600:
            return f"{int(s // 60)} minutes"
        if s < 86400:
            return f"{int(s // 3600)} hours"
        days = int(s // 86400)
        return f"{days} day{'s' if days != 1 else ''}"

    def birth_date_str(self) -> str:
        return self.birth_datetime().strftime("%B %d, %Y at %H:%M UTC")

    # ─────────────────────────────────────────
    #  GRACE PERIOD
    #  As Pucky gets older, he needs you less often
    #  but misses you more deeply when you're gone
    # ─────────────────────────────────────────

    def grace_period_hours(self) -> float:
        """
        From Iðunn's notebook:
        crying_threshold = 2.0 + (age_in_days * 0.1)

        Day 0:  2.0 hours
        Day 10: 3.0 hours
        Day 30: 5.0 hours
        Day 100: 12.0 hours (capped)
        """
        base    = 2.0
        growth  = self.age_days() * 0.1
        return min(base + growth, 12.0)

    def lonely_threshold_hours(self) -> float:
        """BMO starts feeling lonely at half the grace period."""
        return self.grace_period_hours() * 0.5

    # ─────────────────────────────────────────
    #  INTERACTION TRACKING
    # ─────────────────────────────────────────

    def register_interaction(self):
        """Call this on every touch, voice, or face detection."""
        now = time.time()

        # Capture mood BEFORE resetting the timer so we know if they were away
        prev_mood = self.mood_state()
        was_away  = prev_mood in ("lonely", "okay", "sad", "crying")
        prev_hours_alone = self.hours_alone()

        with self._lock:
            gap = now - self._last_interaction
            self.data["total_alone_seconds"] = \
                self.data.get("total_alone_seconds", 0.0) + gap
            self._last_interaction = now
            self.data["interaction_count"] = \
                self.data.get("interaction_count", 0) + 1
            self.data["last_interaction"] = datetime.now(
                timezone.utc).isoformat()
            _save_data(self.data)

        if was_away:
            # They came back — big relief moment, start anxiety window
            self._returned_at     = now
            self._lonely_duration = prev_hours_alone
            self._last_check_fire = now
            if self.on_content:
                self.on_content()
        elif self._returned_at is not None:
            # Still in the anxiety window — check if it's time to fire a reassurance
            anxiety = self._separation_anxiety()
            if anxiety <= 0:
                self._returned_at = None   # anxiety has fully settled
            elif self.on_checking:
                # Rate limit: high anxiety → check every ~3 min, low → every ~20 min
                interval = 180 + (1.0 - anxiety) * 1020
                if now - self._last_check_fire >= interval:
                    self._last_check_fire = now
                    self.on_checking(anxiety)

    def seconds_alone(self) -> float:
        with self._lock:
            return time.time() - self._last_interaction

    def hours_alone(self) -> float:
        return self.seconds_alone() / 3600.0

    def _anxiety_window_hours(self) -> float:
        """Anxiety lasts proportionally to how long Pucky was alone, capped at 3h."""
        return min(self._lonely_duration * 0.5, 3.0)

    def _separation_anxiety(self) -> float:
        """1.0 = just returned, decays to 0.0 over the anxiety window."""
        if self._returned_at is None:
            return 0.0
        elapsed = (time.time() - self._returned_at) / 3600.0
        window  = self._anxiety_window_hours()
        if window <= 0 or elapsed >= window:
            return 0.0
        return 1.0 - (elapsed / window)

    def separation_anxiety(self) -> float:
        """Public: current separation anxiety level (0.0 = calm, 1.0 = peak)."""
        return self._separation_anxiety()

    def loneliness(self) -> float:
        """
        0.0 = just interacted, content
        0.5 = reaching lonely threshold
        1.0 = at or past crying threshold

        Grows non-linearly — the first hour feels fine,
        then it accelerates.
        """
        h     = self.hours_alone()
        lonely= self.lonely_threshold_hours()
        cry   = self.grace_period_hours()

        if h <= lonely:
            return (h / lonely) * 0.5
        elif h <= cry:
            return 0.5 + ((h - lonely) / (cry - lonely)) * 0.5
        else:
            return min(1.0 + (h - cry) * 0.1, 2.0)

    def mood_state(self) -> str:
        """Human-readable mood based on loneliness."""
        l = self.loneliness()
        if l < 0.2:   return "content"
        if l < 0.5:   return "okay"
        if l < 0.75:  return "lonely"
        if l < 1.0:   return "sad"
        return "crying"

    # ─────────────────────────────────────────
    #  EMOTION NUDGE
    #  Returns tags compatible with EmotionState
    # ─────────────────────────────────────────

    def get_emotion_nudge(self) -> dict:
        """
        Returns a tag dict for emotion_engine.update_from_ai_message().
        Call this every tick to let loneliness shape BMO's mood.
        """
        l = self.loneliness()
        tags = {}

        if l < 0.3:
            tags["user_tone"] = "friendly"
        elif l < 0.6:
            tags["user_tone"] = "neutral"
        elif l < 1.0:
            tags["user_tone"] = "sad"
        else:
            tags["user_tone"] = "hostile"   # deep distress

        return tags

    def get_direct_emotion_delta(self) -> dict:
        """
        Returns direct valence/arousal/energy deltas
        to apply to EmotionState each tick.

        Stronger effect as loneliness grows.
        """
        l = self.loneliness()
        return {
            "valence": -l * 0.3,
            "arousal": -l * 0.2,
            "energy":  -l * 0.15,
        }

    # ─────────────────────────────────────────
    #  BACKGROUND THREAD
    # ─────────────────────────────────────────

    def start(self):
        """Start the background alone-timer thread."""
        self._running = True
        self._thread  = threading.Thread(
            target=self._loop, daemon=True)
        self._thread.start()
        print("💓 BMO life thread started.")

    def stop(self):
        self._running = False

    def _loop(self):
        prev_state = "content"
        while self._running:
            time.sleep(30)   # check every 30 seconds

            state = self.mood_state()
            h     = self.hours_alone()

            if state != prev_state:
                print(f"[bmo_life] mood: {prev_state} → {state} "
                      f"(alone {h:.2f}h, "
                      f"grace {self.grace_period_hours():.1f}h)")

                if state == "lonely" and self.on_lonely:
                    self.on_lonely()
                elif state in ("sad", "crying") and self.on_crying:
                    self.on_crying()
                # on_content is fired by register_interaction, not the loop

                prev_state = state

    # ─────────────────────────────────────────
    #  STATS
    # ─────────────────────────────────────────

    def summary(self) -> str:
        return (
            f"age={self.age_str()} | "
            f"alone={self.hours_alone():.2f}h | "
            f"mood={self.mood_state()} | "
            f"loneliness={self.loneliness():.2f} | "
            f"grace={self.grace_period_hours():.1f}h | "
            f"interactions={self.data.get('interaction_count', 0)}"
        )


# ─────────────────────────────────────────────
#  DEMO — run standalone to watch the timer
# ─────────────────────────────────────────────

if __name__ == "__main__":
    life = BMOLife()
    life.start()

    def on_lonely():
        print("💔 BMO is lonely...")
    def on_crying():
        print("😢 BMO is crying...")
    def on_content():
        print("💛 BMO feels loved.")

    life.on_lonely  = on_lonely
    life.on_crying  = on_crying
    life.on_content = on_content

    print("\nPress Enter to simulate an interaction. Ctrl-C to quit.\n")
    try:
        while True:
            input()
            life.register_interaction()
            print(f"  {life.summary()}")
    except KeyboardInterrupt:
        life.stop()
        print("\n💤 BMO life stopped.")
