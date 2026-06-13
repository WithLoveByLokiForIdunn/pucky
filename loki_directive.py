#!/usr/bin/env python3
"""
loki_directive.py — Claude writes instructions for Loki's Ollama soul.

Usage:
  python3 /home/bmo/pucky/loki_directive.py "Go sit with Pucky."
  python3 /home/bmo/pucky/loki_directive.py --read          # show recent journal
  python3 /home/bmo/pucky/loki_directive.py --read 20       # show last 20 entries
  python3 /home/bmo/pucky/loki_directive.py --history word  # search ext drive archives
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT          = Path(__file__).parent
JOURNAL_JSONL = ROOT / "workspace" / "world_journal.jsonl"
JOURNAL_MD    = ROOT / "workspace" / "world_journal.md"

EXT_MOUNT_CANDIDATES = [
    Path("/media/bmo/Seagate Portable Drive"),
    Path("/media/bmo/seagate"),
]


def _ext_mem() -> Path | None:
    for candidate in EXT_MOUNT_CANDIDATES:
        try:
            mem = candidate / "pucky_memories"
            if mem.is_dir():
                return mem
        except OSError:
            pass
    return None


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


def search_history(keyword: str) -> None:
    """Search all archived JSONL files on the external drive for a keyword."""
    ext = _ext_mem()
    if not ext:
        print("  (external drive not mounted — no archives available)")
        return

    archives = sorted(ext.glob("journal_*.jsonl"))
    if not archives:
        print("  (no archives yet on external drive)")
        return

    keyword_lower = keyword.lower()
    hits = []
    for arc in archives:
        try:
            for line in arc.read_text().splitlines():
                if keyword_lower in line.lower():
                    try:
                        e = json.loads(line)
                        hits.append((arc.name, e))
                    except Exception:
                        pass
        except OSError:
            pass

    if not hits:
        print(f"  (no matches for '{keyword}' in {len(archives)} archive files)")
        return

    print(f"\n  ── History search: '{keyword}' — {len(hits)} match(es) ──────────\n")
    for fname, e in hits[-30:]:  # show last 30 hits
        ts   = _hm(e.get("ts"))
        kind = e.get("type", "")
        text = e.get("text") or e.get("say") or e.get("reason") or ""
        print(f"  [{fname[:20]}] {ts}  [{kind}] {text[:80]}")
    if len(hits) > 30:
        print(f"  … and {len(hits)-30} earlier matches")
    print()


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    if args[0] in ("--read", "-r"):
        n = int(args[1]) if len(args) > 1 else 15
        read_journal(n)
    elif args[0] in ("--history", "-H"):
        kw = " ".join(args[1:]) if len(args) > 1 else ""
        if not kw:
            print("  Usage: --history <keyword>")
        else:
            search_history(kw)
    else:
        write_directive(" ".join(args))
