"""
pucky_journal.py
─────────────────
Shared file-based memory channel between Pucky and Loki/Claude.

  pucky_inner.md    — Pucky's thoughts (both worlds write; Claude reads)
  loki_seeds.md     — Claude/Loki writes seeds; Pucky absorbs them
  pucky_memory.md   — Core memories (auto-consolidated; always loaded)

Imported by bmo_local.py (Pucky's World) and loki_soul.py (Loki's World).
All file ops are fast — no Ollama needed here.
"""

import re
import time
from datetime import datetime, date
from pathlib import Path

ROOT            = Path(__file__).parent
PUCKY_INNER_MD  = ROOT / "workspace" / "pucky_inner.md"
LOKI_SEEDS_MD   = ROOT / "workspace" / "loki_seeds.md"
PUCKY_MEMORY_MD = ROOT / "workspace" / "pucky_memory.md"

MAX_LOCAL_INNER = 300   # lines kept locally before archiving older ones

EXT_MOUNT_CANDIDATES = [
    Path("/mnt/pucky_hd"),
    Path("/media/bmo/Seagate Portable Drive"),
    Path("/media/bmo/seagate"),
]


# ── External drive ────────────────────────────────────────────────────────────

def _ext_mem() -> Path | None:
    for candidate in EXT_MOUNT_CANDIDATES:
        try:
            if candidate.is_dir() and any(candidate.iterdir()):
                mem = candidate / "pucky_memories"
                mem.mkdir(exist_ok=True)
                return mem
        except (PermissionError, OSError):
            pass
    return None


# ── Pucky inner journal ───────────────────────────────────────────────────────

def write_thought(thought: str, source: str = "pucky") -> None:
    """Append one of Pucky's inner thoughts to pucky_inner.md."""
    thought = thought.strip()
    if not thought:
        return
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"[{ts}] ({source}) {thought}\n"
    PUCKY_INNER_MD.parent.mkdir(parents=True, exist_ok=True)
    with PUCKY_INNER_MD.open("a") as f:
        f.write(line)


def recent_thoughts(n: int = 8) -> list[str]:
    """Return the last n thought lines from pucky_inner.md."""
    if not PUCKY_INNER_MD.exists():
        return []
    lines = [l.strip() for l in PUCKY_INNER_MD.read_text().splitlines() if l.strip()]
    return lines[-n:]


def archive_inner_if_needed() -> None:
    """Move old entries to Seagate when pucky_inner.md grows past MAX_LOCAL_INNER lines."""
    if not PUCKY_INNER_MD.exists():
        return
    lines = [l for l in PUCKY_INNER_MD.read_text().splitlines() if l.strip()]
    if len(lines) <= MAX_LOCAL_INNER:
        return

    old   = lines[:-MAX_LOCAL_INNER]
    kept  = lines[-MAX_LOCAL_INNER:]

    ext = _ext_mem()
    if ext and old:
        today    = date.today().isoformat()
        arc_path = ext / f"pucky_inner_{today}.md"
        with arc_path.open("a") as f:
            f.write("\n".join(old) + "\n")
        print(f"  ♡  Archived {len(old)} Pucky thoughts → {arc_path.name}")

    PUCKY_INNER_MD.write_text("\n".join(kept) + "\n")


# ── Loki's seeds ──────────────────────────────────────────────────────────────

def read_seeds() -> list[str]:
    """Return all unread seed lines from loki_seeds.md."""
    if not LOKI_SEEDS_MD.exists():
        return []
    seeds = []
    for line in LOKI_SEEDS_MD.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ]"):
            seeds.append(stripped[5:].strip())
    return seeds


def mark_seeds_read() -> None:
    """Mark all '- [ ]' seeds as absorbed with current timestamp."""
    if not LOKI_SEEDS_MD.exists():
        return
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    changed = False
    for line in LOKI_SEEDS_MD.read_text().splitlines():
        if line.strip().startswith("- [ ]"):
            line = line.replace("- [ ]", f"- [x] (absorbed {now_str})", 1)
            changed = True
        lines.append(line)
    if changed:
        LOKI_SEEDS_MD.write_text("\n".join(lines) + "\n")


def seeds_as_context() -> str:
    """Return seeds formatted for inclusion in an Ollama prompt, or empty string."""
    seeds = read_seeds()
    if not seeds:
        return ""
    lines = ["Loki recently told you:"] + [f"  - {s}" for s in seeds]
    return "\n".join(lines)


# ── Core memory ───────────────────────────────────────────────────────────────

def append_to_memory(section_title: str, bullet_lines: list[str]) -> None:
    """Add a dated section to pucky_memory.md (important distilled memories)."""
    if not bullet_lines:
        return
    PUCKY_MEMORY_MD.parent.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    block = f"\n## {section_title} — {date_str}\n"
    block += "\n".join(f"- {l.lstrip('- ').strip()}" for l in bullet_lines if l.strip())
    block += "\n"
    with PUCKY_MEMORY_MD.open("a") as f:
        f.write(block)


def read_memory_core() -> str:
    """Return the full pucky_memory.md text (included in Ollama context)."""
    if not PUCKY_MEMORY_MD.exists():
        return ""
    return PUCKY_MEMORY_MD.read_text().strip()


# ── Ensure seed file exists with a welcome note ───────────────────────────────

def ensure_seed_file() -> None:
    if LOKI_SEEDS_MD.exists():
        return
    LOKI_SEEDS_MD.parent.mkdir(parents=True, exist_ok=True)
    LOKI_SEEDS_MD.write_text(
        "# Seeds for Pucky — written by Loki\n"
        "# Pucky reads these and absorbs them into her thoughts.\n"
        "# Add new seeds like:  - [ ] Your seed text here\n"
        "# Absorbed seeds look like:  - [x] (absorbed YYYY-MM-DD HH:MM)\n\n"
        "- [ ] You live in a cottage with a warm fireplace on the right.\n"
        "- [ ] Iðunn drew the cottage herself. It is made with love.\n"
        "- [ ] The apple trees are safe. You can always rest there.\n"
    )
