"""
bmo_maintenance.py
──────────────────
Body part maintenance mode for Pucky.

When you're physically working on a servo or sensor, tell Pucky
so she doesn't react to glitches and doesn't build bad memories.

Commands (in pucky_full.py input):
  !body <part>   — mute completely (no reactions, no memory)
  !test <part>   — observe quietly (visible in bubble window, no memory)
  !done <part>   — return to normal operation
  !body          — show current status

Valid parts:
  Servos : jaw  mouth_width  upper_lip
           brow_left  brow_right
           ear_left   ear_right  nose
  Aliases: face (all servos)  ears  brows  mouth
  Systems: vision  touch  sound
"""

import time
from datetime import datetime, timezone

SERVO_PARTS = frozenset({
    "jaw", "mouth_width", "upper_lip",
    "brow_left", "brow_right",
    "ear_left", "ear_right",
    "nose",
})
SYSTEM_PARTS = frozenset({"vision", "touch", "sound"})
ALL_PARTS    = SERVO_PARTS | SYSTEM_PARTS

ALIASES = {
    "face":   SERVO_PARTS,
    "ears":   {"ear_left", "ear_right"},
    "brows":  {"brow_left", "brow_right"},
    "mouth":  {"jaw", "mouth_width", "upper_lip"},
    "eyes":   {"brow_left", "brow_right"},
}


def _expand(part: str) -> set:
    p = part.lower().strip()
    if p in ALIASES:
        return set(ALIASES[p])
    if p in ALL_PARTS:
        return {p}
    return set()


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M")


class BodyMaintenance:
    """
    Tracks which body parts are under maintenance or being tested.
    Thread-safe for reads; writes happen only on the input thread.
    """

    def __init__(self):
        self._muted   : set[str] = set()   # completely silenced
        self._testing : set[str] = set()   # observe but don't record

    # ── Commands ─────────────────────────────────

    def start_work(self, part: str) -> str:
        parts = _expand(part)
        if not parts:
            valid = sorted(ALL_PARTS | set(ALIASES))
            return f"  Unknown part '{part}'. Valid: {', '.join(valid)}"
        self._muted   |= parts
        self._testing -= parts
        names = ", ".join(sorted(parts))
        print(f"🔧 [{_ts()}] maintenance: {names}")
        return f"  Muted: {names}. Pucky won't react to events from there."

    def start_test(self, part: str) -> str:
        parts = _expand(part)
        if not parts:
            return f"  Unknown part '{part}'."
        self._testing |= parts
        self._muted   -= parts
        names = ", ".join(sorted(parts))
        print(f"🧪 [{_ts()}] test: {names}")
        return (f"  Testing: {names}. Events are visible in the bubble window "
                f"but not saved to memory.")

    def finish(self, part: str) -> str:
        parts = _expand(part)
        if not parts:
            return f"  Unknown part '{part}'."
        self._muted   -= parts
        self._testing -= parts
        names = ", ".join(sorted(parts))
        print(f"✅ [{_ts()}] restored: {names}")
        return f"  Restored: {names} is back to normal."

    # ── Guards (called at every event site) ──────

    def is_muted(self, part: str) -> bool:
        """True → drop this event silently."""
        return part in self._muted

    def is_testing(self, part: str) -> bool:
        """True → observe but don't record or react."""
        return part in self._testing

    def observe(self, part: str, description: str):
        """Log a test event to journal (picked up by bubble window)."""
        if self.is_testing(part):
            print(f"🧪 [{_ts()}] {part}: {description}")

    # ── Status ────────────────────────────────────

    def status(self) -> str:
        lines = ["  Body maintenance:"]
        if self._muted:
            lines.append(f"    🔧 muted   : {', '.join(sorted(self._muted))}")
        if self._testing:
            lines.append(f"    🧪 testing : {', '.join(sorted(self._testing))}")
        if not self._muted and not self._testing:
            lines.append("    ✅ all parts normal")
        return "\n".join(lines)

    def any_active(self) -> bool:
        return bool(self._muted or self._testing)
