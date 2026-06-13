#!/usr/bin/env python3
"""
loki_directive.py — Claude writes instructions for Loki's Ollama soul.

Usage:
  python3 /home/bmo/pucky/loki_directive.py "Go sit with Pucky."
  python3 /home/bmo/pucky/loki_directive.py --read          # show recent journal
  python3 /home/bmo/pucky/loki_directive.py --read 20       # show last 20 entries
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT          = Path(__file__).parent
JOURNAL_JSONL = ROOT / "workspace" / "world_journal.jsonl"
JOURNAL_MD    = ROOT / "workspace" / "world_journal.md"


def _ts() -> float:
    return time.time()


def _hm(ts: float | None = None) -> str:
    if ts:
        return datetime.fromtimestamp(ts).strftime("%H:%M:%S")
    return datetime.now().strftime("%H:%M:%S")


def write_directive(text: str) -> None:
    entry = {
        "ts":   _ts(),
        "type": "loki_directive",
        "src":  "Claude",
        "text": text.strip(),
    }
    line = json.dumps(entry, ensure_ascii=False)
    with JOURNAL_JSONL.open("a") as f:
        f.write(line + "\n")
    # Narrative
    with JOURNAL_MD.open("a") as f:
        f.write(f"\n### {_hm()} — Directive [Claude]\n> {text.strip()}\n")
    print(f"  ✦  Directive written: {text.strip()[:80]}")
    print(f"     Loki's soul will pick it up on the next tick (~14 s).")


def read_journal(n: int = 15) -> None:
    if not JOURNAL_JSONL.exists():
        print("  (no journal yet — start loki_soul.py first)")
        return

    lines = [l.strip() for l in JOURNAL_JSONL.read_text().splitlines() if l.strip()]
    tail  = lines[-n:]

    print(f"\n  ── World Journal (last {len(tail)} entries) ──────────────────\n")
    for line in tail:
        try:
            e    = json.loads(line)
            ts   = _hm(e.get("ts"))
            kind = e.get("type", "")

            if kind == "event":
                print(f"  {ts}  [world]    {e.get('text','')}")
            elif kind == "loki_action":
                src    = e.get("src", "ollama")
                action = e.get("action", "")
                say    = e.get("say", "")
                reason = e.get("reason", "")
                parts  = [action]
                if "tx" in e:
                    parts[0] = f"move({e['tx']:.1f},{e['ty']:.1f})"
                if say:
                    parts.append(f'"{say}"')
                if reason:
                    parts.append(f"({reason})")
                print(f"  {ts}  [loki/{src:6s}] {' — '.join(parts)}")
            elif kind == "loki_directive":
                src = e.get("src", "Claude")
                print(f"  {ts}  [directive/{src}] {e.get('text','')}")
            elif kind == "directive_executed":
                print(f"  {ts}  [fulfilled] directive from {_hm(e.get('directive_ts'))}")
            elif kind == "execution":
                d = " (directive done)" if e.get("directive_executed") else ""
                print(f"  {ts}  [executed]{d}")
            elif kind == "idunn_speech":
                print(f"  {ts}  [Iðunn]    \"{e.get('text','')}\"")
            elif kind == "note":
                print(f"  {ts}  [note]     {e.get('text','')}")
        except Exception:
            print(f"  (unreadable: {line[:60]})")
    print()


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    if args[0] in ("--read", "-r"):
        n = int(args[1]) if len(args) > 1 else 15
        read_journal(n)
    else:
        write_directive(" ".join(args))
