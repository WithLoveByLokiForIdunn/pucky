#!/usr/bin/env python3
"""
bmo_memory2.py — Pucky's emotional memory system. Second generation.

Changes from bmo_memory.py:
  - Memory deduplication: if the same description arrives again, weight goes up
    instead of creating a new entry. Weight is used as an importance multiplier.
  - consolidate() — collapses existing duplicates in the JSON file.
  - Atomic file writes (write to .tmp, then rename) prevent crash corruption.
  - All saves go through _atomic_write().

Drop-in replacement: BMOMemory2 has the same public interface as BMOMemory.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

ROOT      = Path(__file__).parent
MEM_FILE  = ROOT / "bmo_memories.json"
FADE_DAYS = {"core": None, "warm": 90, "impression": 14}
MAX_TIERS = {"core": 50, "warm": 500, "impression": 5000}


# ── Atomic write ──────────────────────────────────────────────────────────────
def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    except OSError as e:
        print(f"  ⚠ memory write failed: {e}")
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


# ── Memory dataclass ──────────────────────────────────────────────────────────
@dataclass
class Memory:
    description:   str
    tier:          str              = "impression"
    created_at:    float            = field(default_factory=time.time)
    last_recalled: float            = field(default_factory=time.time)
    recall_count:  int              = 0
    weight:        int              = 1     # NEW — incremented on duplicate
    pleasantness:  float            = 0.0
    joy:           float            = 0.0
    wonder:        float            = 0.0
    curiosity:     float            = 0.0
    peacefulness:  float            = 0.0
    scariness:     float            = 0.0
    unpleasantness:float            = 0.0
    tags:          list[str]        = field(default_factory=list)

    def compute_importance(self) -> float:
        emotion_total = (
            self.pleasantness * 1.2 +
            self.joy          * 1.5 +
            self.wonder       * 1.1 +
            self.curiosity    * 0.9 +
            self.peacefulness * 0.7 +
            self.scariness    * 1.3 +
            self.unpleasantness * 1.0
        )
        recall_bonus = min(self.recall_count * 0.5, 5.0)
        tier_bonus   = {"core": 10.0, "warm": 4.0, "impression": 0.0}.get(self.tier, 0.0)
        weight_bonus = min(math.log1p(self.weight) * 2.0, 10.0)
        return emotion_total + recall_bonus + tier_bonus + weight_bonus

    def is_faded(self) -> bool:
        fade = FADE_DAYS.get(self.tier)
        if fade is None:
            return False
        cutoff = datetime.now() - timedelta(days=fade)
        return datetime.fromtimestamp(self.last_recalled) < cutoff

    def emotion_vector(self) -> dict:
        return {
            "pleasantness":   self.pleasantness,
            "joy":            self.joy,
            "wonder":         self.wonder,
            "curiosity":      self.curiosity,
            "peacefulness":   self.peacefulness,
            "scariness":      self.scariness,
            "unpleasantness": self.unpleasantness,
        }


def _memory_from_dict(d: dict) -> Memory:
    known = set(Memory.__dataclass_fields__)
    safe  = {k: v for k, v in d.items() if k in known}
    return Memory(**safe)


# ── Main class ────────────────────────────────────────────────────────────────
class BMOMemory2:
    """
    Pucky's emotional long-term memory — second generation.

    Key difference: calling remember() with the same description no longer
    creates a duplicate. Instead, the existing entry gains weight (which raises
    its importance score), has its emotion scores updated to the max of old/new,
    and its timestamp refreshed.
    """

    def __init__(self, path: Path = MEM_FILE):
        self.path      = path
        self.memories: list[Memory] = []
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────
    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:
            print(f"  ⚠ bmo_memory2 load error: {e}")
            return
        if isinstance(raw, list):
            for item in raw:
                try:
                    self.memories.append(_memory_from_dict(item))
                except Exception:
                    pass

    def _save(self) -> None:
        data = [asdict(m) for m in self.memories]
        _atomic_write(self.path, json.dumps(data, indent=2, ensure_ascii=False))

    # ── Deduplication helpers ─────────────────────────────────────────────────
    def _find_by_description(self, description: str) -> Optional[Memory]:
        desc_norm = description.strip().lower()
        for m in self.memories:
            if m.description.strip().lower() == desc_norm:
                return m
        return None

    # ── Public API ────────────────────────────────────────────────────────────
    def remember(
        self,
        description:    str,
        tier:           str   = "impression",
        pleasantness:   float = 0.0,
        joy:            float = 0.0,
        wonder:         float = 0.0,
        curiosity:      float = 0.0,
        peacefulness:   float = 0.0,
        scariness:      float = 0.0,
        unpleasantness: float = 0.0,
        tags:           list[str] | None = None,
    ) -> Memory:
        """
        Add a memory, or strengthen an existing one if the description matches.
        Returns the memory object (new or updated).
        """
        existing = self._find_by_description(description)

        if existing is not None:
            # Strengthen: bump weight, take max of emotion scores, refresh ts
            existing.weight       += 1
            existing.last_recalled = time.time()
            existing.recall_count += 1
            existing.pleasantness   = max(existing.pleasantness,   pleasantness)
            existing.joy            = max(existing.joy,            joy)
            existing.wonder         = max(existing.wonder,         wonder)
            existing.curiosity      = max(existing.curiosity,      curiosity)
            existing.peacefulness   = max(existing.peacefulness,   peacefulness)
            existing.scariness      = max(existing.scariness,      scariness)
            existing.unpleasantness = max(existing.unpleasantness, unpleasantness)
            if tags:
                for t in tags:
                    if t not in existing.tags:
                        existing.tags.append(t)
            # Promote tier if new call requests a higher tier
            tier_rank = {"impression": 0, "warm": 1, "core": 2}
            if tier_rank.get(tier, 0) > tier_rank.get(existing.tier, 0):
                existing.tier = tier
            self._save()
            return existing

        m = Memory(
            description    = description.strip(),
            tier           = tier,
            pleasantness   = pleasantness,
            joy            = joy,
            wonder         = wonder,
            curiosity      = curiosity,
            peacefulness   = peacefulness,
            scariness      = scariness,
            unpleasantness = unpleasantness,
            tags           = list(tags or []),
        )
        self.memories.append(m)
        self._enforce_limits()
        self._save()
        return m

    def recall(self, description: str) -> Optional[Memory]:
        """Bump recall count on the matching memory."""
        m = self._find_by_description(description)
        if m:
            m.recall_count += 1
            m.last_recalled = time.time()
            self._save()
        return m

    def forget(self, description: str) -> bool:
        m = self._find_by_description(description)
        if m:
            self.memories.remove(m)
            self._save()
            return True
        return False

    def top(self, n: int = 5, tier: str | None = None) -> list[Memory]:
        pool = self.memories if tier is None else [m for m in self.memories if m.tier == tier]
        pool = [m for m in pool if not m.is_faded()]
        return sorted(pool, key=lambda m: m.compute_importance(), reverse=True)[:n]

    def search(self, keyword: str, n: int = 10) -> list[Memory]:
        kw   = keyword.lower()
        hits = [m for m in self.memories
                if kw in m.description.lower() or any(kw in t for t in m.tags)]
        return sorted(hits, key=lambda m: m.compute_importance(), reverse=True)[:n]

    def prune_faded(self) -> int:
        before = len(self.memories)
        self.memories = [m for m in self.memories if not m.is_faded()]
        removed = before - len(self.memories)
        if removed:
            self._save()
        return removed

    def consolidate(self) -> int:
        """
        Collapse existing duplicates in the loaded memory list.
        Keeps the copy with the highest importance, merges emotion scores
        (max), sums weights, and accumulates recall counts.
        Returns the number of entries removed.
        """
        seen:    dict[str, Memory] = {}
        removed = 0

        for m in self.memories:
            key = m.description.strip().lower()
            if key not in seen:
                seen[key] = m
            else:
                existing        = seen[key]
                existing.weight        += m.weight
                existing.recall_count  += m.recall_count
                existing.last_recalled  = max(existing.last_recalled, m.last_recalled)
                existing.pleasantness   = max(existing.pleasantness,   m.pleasantness)
                existing.joy            = max(existing.joy,            m.joy)
                existing.wonder         = max(existing.wonder,         m.wonder)
                existing.curiosity      = max(existing.curiosity,      m.curiosity)
                existing.peacefulness   = max(existing.peacefulness,   m.peacefulness)
                existing.scariness      = max(existing.scariness,      m.scariness)
                existing.unpleasantness = max(existing.unpleasantness, m.unpleasantness)
                for t in m.tags:
                    if t not in existing.tags:
                        existing.tags.append(t)
                tier_rank = {"impression": 0, "warm": 1, "core": 2}
                if tier_rank.get(m.tier, 0) > tier_rank.get(existing.tier, 0):
                    existing.tier = m.tier
                removed += 1

        self.memories = list(seen.values())
        if removed:
            self._save()
        return removed

    def stats(self) -> dict:
        tiers = {"core": 0, "warm": 0, "impression": 0}
        for m in self.memories:
            tiers[m.tier] = tiers.get(m.tier, 0) + 1
        top = self.top(1)
        return {
            "total":    len(self.memories),
            "by_tier":  tiers,
            "top_memory": top[0].description[:80] if top else None,
            "top_importance": round(top[0].compute_importance(), 2) if top else 0,
        }

    def _enforce_limits(self) -> None:
        for tier, limit in MAX_TIERS.items():
            tier_mems = [m for m in self.memories if m.tier == tier]
            if len(tier_mems) > limit:
                tier_mems.sort(key=lambda m: m.compute_importance())
                to_drop = len(tier_mems) - limit
                for m in tier_mems[:to_drop]:
                    self.memories.remove(m)


# ── CLI helper ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    mem = BMOMemory2()

    if len(sys.argv) > 1 and sys.argv[1] == "consolidate":
        removed = mem.consolidate()
        pruned  = mem.prune_faded()
        st      = mem.stats()
        print(f"Consolidated: {removed} duplicates removed.")
        print(f"Pruned:       {pruned} faded entries removed.")
        print(f"Remaining:    {st['total']} memories.")
        print(f"  core:       {st['by_tier']['core']}")
        print(f"  warm:       {st['by_tier']['warm']}")
        print(f"  impression: {st['by_tier']['impression']}")
        if st["top_memory"]:
            print(f"Top memory ({st['top_importance']}): {st['top_memory']}")
    else:
        st = mem.stats()
        print(f"bmo_memory2 — {st['total']} memories loaded.")
        print(f"  core: {st['by_tier']['core']}  warm: {st['by_tier']['warm']}  impression: {st['by_tier']['impression']}")
        if st["top_memory"]:
            print(f"Top ({st['top_importance']}): {st['top_memory']}")
        print("\nUsage:")
        print("  python3 bmo_memory2.py consolidate   — collapse duplicates")
