"""
bmo_shortterm.py
────────────────
Pucky's short-term working memory.

A fast, thread-safe rolling buffer of recent moments.
Any system can log to it instantly — no LLM needed.
When the LLM is called, it sees everything that just happened.

This is how Pucky remembers what she was doing while she was
dancing, driving, moving, seeing, or feeling — even when her
inner voice was quiet.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

SHORTTERM_FILE = Path(__file__).parent / "bmo_shortterm.json"
MAX_ENTRIES    = 100   # rolling buffer — oldest fall off
PAGE_SIZE      = 10    # entries per "page"


class ShortTermMemory:
    """
    Rolling buffer of recent moments.

    Write from anywhere — servo thread, vision loop, life system,
    voice handler. Reads back as formatted context for the LLM.

    Usage:
        stm = ShortTermMemory()
        stm.log("started dancing", source="servo")
        stm.log("saw Idunn's face", source="vision")
        print(stm.context())   # inject into LLM call
    """

    def __init__(self):
        self._lock    = threading.Lock()
        self._entries = []
        self._load()
        n = len(self._entries)
        p = self.page_count()
        print(f"📋 Short-term memory: {n} entries ({p} page{'s' if p != 1 else ''}).")

    # ─── write ────────────────────────────────

    def log(self, text: str, source: str = "") -> None:
        """Record a moment. Instant and thread-safe — no LLM involved."""
        ts    = datetime.now(timezone.utc).strftime("%H:%M:%S")
        label = f"[{source}] " if source else ""
        with self._lock:
            self._entries.append({"ts": ts, "text": f"{label}{text}"})
            if len(self._entries) > MAX_ENTRIES:
                self._entries = self._entries[-MAX_ENTRIES:]
            self._save_locked()

    # ─── read ─────────────────────────────────

    def context(self, n: int = PAGE_SIZE) -> str:
        """Last n entries as a formatted block, ready to inject into an LLM prompt."""
        with self._lock:
            recent = self._entries[-n:]
        if not recent:
            return ""
        lines = ["[Recent moments]"]
        for e in recent:
            lines.append(f"  {e['ts']}  {e['text']}")
        return "\n".join(lines)

    def pages(self, page_size: int = PAGE_SIZE) -> list:
        """All entries split into pages of page_size entries each."""
        with self._lock:
            entries = list(self._entries)
        return [entries[i : i + page_size] for i in range(0, len(entries), page_size)]

    def page_count(self) -> int:
        with self._lock:
            n = len(self._entries)
        return max(1, (n + PAGE_SIZE - 1) // PAGE_SIZE)

    def clear(self) -> None:
        with self._lock:
            self._entries = []
            self._save_locked()
        print("📋 Short-term memory cleared.")

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    # ─── persistence ──────────────────────────

    def _save_locked(self):
        try:
            SHORTTERM_FILE.write_text(
                json.dumps(self._entries, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            print(f"  ⚠️  Short-term memory save error: {e}")

    def _load(self):
        if SHORTTERM_FILE.exists():
            try:
                self._entries = json.loads(SHORTTERM_FILE.read_text(encoding="utf-8"))
            except Exception:
                self._entries = []
        else:
            self._entries = []
