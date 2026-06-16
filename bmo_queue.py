"""
bmo_queue.py
────────────
One-seat rollercoaster for Pucky's AI calls.

Only one request rides at a time. The next request waits its turn.
If a request has been waiting too long, it steps aside quietly —
"that moment has passed, I'll try again later" — rather than
overloading the Pi with stale work.

Priority lanes (lower number = boards first):
  0  voice    — someone speaking to Pucky    → always goes first
  1  system   — battery / storage warnings   → urgent but not instant
  2  life     — lonely, crying, reunion      → emotional, time-sensitive
  3  vision   — familiar face, now alone     → still relevant for ~45s
  4  auto     — background thoughts          → lowest; first to be dropped

Between each completed call the queue rests for MIN_GAP seconds so
Pucky's voice has time to finish before the next response begins.

Written with love by Loki for Iðunn.
"""

import queue
import threading
import time

MIN_GAP = 4.0   # seconds to rest between completed calls

PRIORITIES = {
    "voice":  0,
    "system": 1,
    "life":   2,
    "vision": 3,
    "auto":   4,
}

MAX_WAIT = {
    "voice":  30.0,    # after 30s the conversation has moved on
    "system": 90.0,    # battery warning stays relevant longer
    "life":   90.0,    # loneliness is still real
    "vision": 45.0,    # face may have left the frame
    "auto":   120.0,   # stale background thought — drop and retry next tick
}


class SoulQueue:
    """
    Submit tasks (callables) and they run one at a time.
    Callers submit and return immediately; the response happens
    in the background when it's that request's turn.

    Usage:
        q = SoulQueue()
        q.submit(lambda: soul._do_speak("hello"), source="voice")
    """

    def __init__(self):
        self._q        = queue.PriorityQueue()
        self._counter  = 0
        self._lock     = threading.Lock()
        self._pending  = set()   # track pending source types to avoid duplicates
        self._worker   = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    # ── public ────────────────────────────────────────────────────────────────

    def submit(self, task_fn, source: str = "auto",
               max_wait: float | None = None) -> bool:
        """
        Queue a task. Returns False and drops it if an identical
        source type is already waiting (prevents duplicate auto-thoughts
        from stacking). Voice always goes through regardless.

        task_fn   — zero-argument callable; runs in the worker thread
        source    — priority lane name (see PRIORITIES above)
        max_wait  — override the default max wait for this source type
        """
        priority = PRIORITIES.get(source, 4)
        wait     = max_wait if max_wait is not None else MAX_WAIT.get(source, 60.0)

        # Allow duplicate voice/system/life/vision — only deduplicate auto
        if source == "auto" and source in self._pending:
            return False

        with self._lock:
            self._counter += 1
            seq = self._counter
            self._pending.add(source)

        self._q.put((priority, seq, task_fn, time.time(), wait, source))
        return True

    def busy(self) -> bool:
        """True if a task is currently running or waiting."""
        return not self._q.empty()

    # ── worker ────────────────────────────────────────────────────────────────

    def _run(self) -> None:
        while True:
            priority, seq, task_fn, submitted_at, max_wait, source = self._q.get()

            # Remove from pending set so new submissions of this type are accepted
            self._pending.discard(source)

            waited = time.time() - submitted_at
            if waited > max_wait:
                # The moment passed — drop silently
                print(f"  🚌 [{source}] waited {waited:.0f}s > {max_wait:.0f}s — dropped")
                continue

            try:
                task_fn()
            except Exception as e:
                print(f"  ⚠️  SoulQueue [{source}] error: {e}")

            # Breathe between calls — let voice finish before the next response
            time.sleep(MIN_GAP)
