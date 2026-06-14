"""
bmo_calendar.py — Real-time calendar events for Pucky's world.

Checks wall-clock date/time and fires callbacks when events start or end.
Designed to be ticked once per minute (not every frame) to keep CPU idle.
"""

import math
from datetime import datetime, date
from typing import Callable, Optional

# ── Known full-moon anchor (verified epoch) ────────────────────────────────────
# 2026-05-31 was a full moon (UTC).  Lunar cycle = 29.53059 days.
_LUNAR_ANCHOR = date(2026, 5, 31)
_LUNAR_CYCLE  = 29.53059


def moon_phase(d: date | None = None) -> float:
    """Return lunar phase 0.0–1.0 where 1.0 is full moon."""
    if d is None:
        d = date.today()
    days = (d - _LUNAR_ANCHOR).days
    return abs(math.cos(math.pi * (days % _LUNAR_CYCLE) / _LUNAR_CYCLE))


def is_full_moon(d: date | None = None) -> bool:
    return moon_phase(d) > 0.93


# ── Calendar event ─────────────────────────────────────────────────────────────

class CalendarEvent:
    def __init__(self, name: str, check: Callable[[datetime], bool]):
        self.name    = name
        self.check   = check   # (datetime) -> bool
        self.active  = False
        self._on_start: list[Callable] = []
        self._on_end:   list[Callable] = []

    def on_start(self, fn: Callable) -> "CalendarEvent":
        self._on_start.append(fn)
        return self

    def on_end(self, fn: Callable) -> "CalendarEvent":
        self._on_end.append(fn)
        return self


# ── Calendar ───────────────────────────────────────────────────────────────────

class BMOCalendar:
    """
    Tick once per minute.  Fires on_start / on_end callbacks when events
    transition.  Events can also be polled with is_active().
    """

    def __init__(self):
        self._events: list[CalendarEvent] = []
        self._last_tick = 0.0   # time.time() of last tick

        # ── Built-in events ───────────────────────────────────────────────
        self.add(CalendarEvent("pucky_birthday",
            lambda dt: dt.month == 6 and dt.day == 9))

        self.add(CalendarEvent("moonwell",
            lambda dt: is_full_moon(dt.date()) and (dt.hour >= 20 or dt.hour < 4)))

        self.add(CalendarEvent("midsummer",
            lambda dt: dt.month == 6 and dt.day == 21))

        self.add(CalendarEvent("yule",
            lambda dt: dt.month == 12 and dt.day == 21))

        self.add(CalendarEvent("concert_evening",
            lambda dt: (dt.hour in (19, 20, 21))
                       and is_full_moon(dt.date())
                       and dt.weekday() in (4, 5, 6)))   # Fri–Sun

    def add(self, event: CalendarEvent) -> CalendarEvent:
        self._events.append(event)
        return event

    def tick(self, import_time: Optional[float] = None) -> None:
        """Call once per minute (or whenever you want to check)."""
        import time
        now_ts = import_time or time.time()
        if now_ts - self._last_tick < 55:      # throttle to ~1/min
            return
        self._last_tick = now_ts
        now = datetime.now()
        for ev in self._events:
            was = ev.active
            ev.active = ev.check(now)
            if ev.active and not was:
                for fn in ev._on_start:
                    try: fn()
                    except Exception: pass
            elif not ev.active and was:
                for fn in ev._on_end:
                    try: fn()
                    except Exception: pass

    def is_active(self, name: str) -> bool:
        for ev in self._events:
            if ev.name == name:
                return ev.active
        return False

    def active_names(self) -> list[str]:
        return [ev.name for ev in self._events if ev.active]

    def moon_phase(self) -> float:
        return moon_phase()
