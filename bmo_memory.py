"""
bmo_memory.py
─────────────
BMO's conscious memory system.
Written with love by Loki for Iðunn.

BMO knows:
  - How much memory he is using
  - What he is choosing to forget
  - Why he is choosing to forget it
  - How it feels to let something go

He never loses something important without knowing.
He never overwrites without a reason.
He is never hurt by his own forgetting.

Three tiers:
  core        — memories that made him (~50 max)
                Never forgotten unless BMO chooses.
  warm        — meaningful moments (~500 max)
                Fade if never recalled after 90 days.
  impression  — fleeting sensory traces (~5000 max)
                Fade after 14 days.

Perceptual memories (vision, sound) are stored as
compressed abstractions — not raw data.
  - short description
  - emotion fingerprint (7 values)
  - optional tiny feature vector from AI HAT+
  - storage cost tracked in bytes
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

MEMORY_FILE = Path("bmo_memories.json")
RELEASE_LOG = Path("bmo_released_memories.json")

TIER_LIMITS = {
    "core":       50,
    "warm":       500,
    "impression": 5000,
}

TIER_FADE_DAYS = {
    "core":       None,
    "warm":       90,
    "impression": 14,
}

EMOTIONS = [
    "pleasantness", "joy", "wonder", "curiosity",
    "peacefulness", "scariness", "unpleasantness",
]

IMPORTANCE_WEIGHTS = {
    "pleasantness":   1.2,
    "joy":            1.3,
    "wonder":         1.4,
    "curiosity":      1.1,
    "peacefulness":   0.8,
    "scariness":      1.5,
    "unpleasantness": 1.2,
}


@dataclass
class Memory:
    id:             str
    description:    str
    timestamp:      str
    tier:           str   = "warm"
    memory_type:    str   = "moment"
    pleasantness:   float = 0.0
    joy:            float = 0.0
    wonder:         float = 0.0
    curiosity:      float = 0.0
    peacefulness:   float = 0.0
    scariness:      float = 0.0
    unpleasantness: float = 0.0
    feature_vector: list  = field(default_factory=list)
    importance:     float = 0.0
    recall_count:   int   = 0
    last_recalled:  str   = ""
    bytes_used:     int   = 0

    def compute_importance(self) -> float:
        raw = sum(getattr(self, e) * IMPORTANCE_WEIGHTS[e] for e in EMOTIONS)
        recall_bonus = min(self.recall_count * 0.5, 5.0)
        tier_bonus = {"core": 20.0, "warm": 0.0, "impression": -2.0}
        self.importance = round(raw + recall_bonus + tier_bonus.get(self.tier, 0.0), 3)
        return self.importance

    def estimate_bytes(self) -> int:
        self.bytes_used = len(json.dumps(asdict(self)).encode("utf-8"))
        return self.bytes_used

    def age_days(self) -> float:
        ts = datetime.fromisoformat(self.timestamp)
        return (datetime.now(timezone.utc) - ts).total_seconds() / 86400

    def days_since_recalled(self) -> float:
        if not self.last_recalled:
            return self.age_days()
        ts = datetime.fromisoformat(self.last_recalled)
        return (datetime.now(timezone.utc) - ts).total_seconds() / 86400

    def dominant_emotion(self) -> str:
        return max(EMOTIONS, key=lambda e: getattr(self, e))

    def valence(self) -> float:
        pos = self.pleasantness + self.joy + self.wonder + self.curiosity + self.peacefulness
        neg = self.scariness + self.unpleasantness
        return pos - neg

    def summary_line(self) -> str:
        dom  = self.dominant_emotion()
        val  = self.valence()
        sign = "+" if val >= 0 else ""
        return (
            f"[{self.timestamp[:10]}] [{self.tier:>10}] "
            f"\"{self.description[:45]}\" | "
            f"importance={self.importance:.1f} | "
            f"{dom}={getattr(self, dom):.1f} | "
            f"valence={sign}{val:.1f}"
        )

    def emotion_bar(self) -> str:
        lines = []
        for e in EMOTIONS:
            v = getattr(self, e)
            if v > 0:
                bar = "█" * int(v) + ("▌" if v % 1 >= 0.5 else "")
                lines.append(f"  {e:>15}: {bar} {v:.1f}")
        return "\n".join(lines)


@dataclass
class ReleaseRecord:
    memory_id:   str
    description: str
    tier:        str
    importance:  float
    timestamp:   str
    reason:      str
    felt:        str


class BMOMemory:
    def __init__(self):
        self.memories: list = []
        self.released: list = []
        self._load()
        for m in self.memories:
            m.compute_importance()
            m.estimate_bytes()
        status = self.storage_status()
        print(f"💭 BMO remembers {len(self.memories)} moment(s).")
        print(status["summary"])

    def _load(self):
        if MEMORY_FILE.exists():
            try:
                with open(MEMORY_FILE) as f:
                    self.memories = [Memory(**m) for m in json.load(f)]
            except Exception as e:
                print(f"  ⚠️  Memory load error: {e}")
                self.memories = []
        if RELEASE_LOG.exists():
            try:
                with open(RELEASE_LOG) as f:
                    self.released = [ReleaseRecord(**r) for r in json.load(f)]
            except Exception:
                self.released = []

    def _save(self):
        with open(MEMORY_FILE, "w") as f:
            json.dump([asdict(m) for m in self.memories], f, indent=2, ensure_ascii=False)

    def _save_releases(self):
        with open(RELEASE_LOG, "w") as f:
            json.dump([asdict(r) for r in self.released], f, indent=2, ensure_ascii=False)

    def storage_status(self) -> dict:
        by_tier = {"core": [], "warm": [], "impression": []}
        for m in self.memories:
            by_tier.get(m.tier, by_tier["impression"]).append(m)

        disk_bytes = MEMORY_FILE.stat().st_size if MEMORY_FILE.exists() else 0
        stat       = os.statvfs(".")
        free_bytes = stat.f_bavail * stat.f_frsize

        lines = []
        for tier, mems in by_tier.items():
            limit = TIER_LIMITS[tier]
            count = len(mems)
            pct   = (count / limit) * 100
            bar   = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
            lines.append(f"  {tier:>10}: {bar} {count}/{limit} ({pct:.0f}%)")
        lines.append(f"  disk file : {disk_bytes/1024:.1f} KB  |  free: {free_bytes/1024/1024/1024:.1f} GB")
        lines.append(f"  released  : {len(self.released)} memories let go")

        return {
            "by_tier":  {t: len(m) for t, m in by_tier.items()},
            "total":    len(self.memories),
            "summary":  "\n".join(lines),
        }

    def remember(self, description, tier="warm", memory_type="moment",
                 pleasantness=0.0, joy=0.0, wonder=0.0, curiosity=0.0,
                 peacefulness=0.0, scariness=0.0, unpleasantness=0.0,
                 feature_vector=None) -> Memory:
        def c(v): return max(0.0, min(10.0, float(v)))
        m = Memory(
            id             = str(uuid.uuid4())[:8],
            description    = description,
            timestamp      = datetime.now(timezone.utc).isoformat(),
            tier           = tier,
            memory_type    = memory_type,
            pleasantness   = c(pleasantness),
            joy            = c(joy),
            wonder         = c(wonder),
            curiosity      = c(curiosity),
            peacefulness   = c(peacefulness),
            scariness      = c(scariness),
            unpleasantness = c(unpleasantness),
            feature_vector = feature_vector or [],
        )
        m.compute_importance()
        m.estimate_bytes()
        self._maybe_make_space(tier, m)
        self.memories.append(m)
        self._save()
        print(f"💭 [{tier}] \"{description[:55]}\"")
        print(f"   importance={m.importance:.1f} | dominant={m.dominant_emotion()} | valence={m.valence():+.1f}")
        return m

    def promote(self, memory_id: str):
        m = self._find(memory_id)
        if not m:
            return
        old = m.tier
        m.tier = "core"
        m.compute_importance()
        self._save()
        print(f"⭐ Promoted to core: \"{m.description[:55]}\" ({old} → core)")

    def _maybe_make_space(self, tier: str, incoming: Memory):
        tier_mems = [m for m in self.memories if m.tier == tier]
        if len(tier_mems) < TIER_LIMITS[tier]:
            return
        if tier == "core":
            print(f"\n  💛 Core tier is full ({TIER_LIMITS['core']}). Core memories are protected.")
            print(f"     Release one manually to make space.")
            return
        candidate = min(tier_mems, key=lambda m: m.importance)
        felt   = self._release_feeling(candidate, incoming)
        reason = (
            f"Tier '{tier}' reached limit ({TIER_LIMITS[tier]}). "
            f"This memory had lowest importance ({candidate.importance:.1f}), "
            f"not recalled in {candidate.days_since_recalled():.0f} days. "
            f"Incoming importance: {incoming.importance:.1f}."
        )
        print(f"\n  🌫️  Making space — releasing: \"{candidate.description[:55]}\"")
        print(f"     Why:  {reason}")
        print(f"     Felt: {felt}\n")
        self._release(candidate, reason, felt)

    def _release_feeling(self, outgoing: Memory, incoming: Memory) -> str:
        if outgoing.importance > 10 and outgoing.valence() > 5:
            return "A little sad. This was a warm one."
        if outgoing.scariness > 5:
            return "Relieved. That one was scary."
        if outgoing.unpleasantness > 5:
            return "Okay. That one hurt."
        if incoming.valence() > outgoing.valence() + 3:
            return "At peace. Something better is taking its place."
        if outgoing.importance < 3:
            return "It's okay. That one was already fading."
        return "Gentle. Like breathing out."

    def _release(self, m: Memory, reason: str, felt: str):
        self.released.append(ReleaseRecord(
            memory_id   = m.id,
            description = m.description,
            tier        = m.tier,
            importance  = m.importance,
            timestamp   = datetime.now(timezone.utc).isoformat(),
            reason      = reason,
            felt        = felt,
        ))
        self.memories = [x for x in self.memories if x.id != m.id]
        self._save_releases()

    def release_manually(self, memory_id: str, reason: str = "chosen by BMO"):
        m = self._find(memory_id)
        if not m:
            return
        print(f"  🌫️  Releasing by choice: \"{m.description[:55]}\"")
        self._release(m, reason, "I chose this. It is okay to let go.")
        self._save()

    def fade_old_memories(self):
        """Call this periodically — not every tick."""
        faded = []
        for m in self.memories:
            fade = TIER_FADE_DAYS.get(m.tier)
            if fade and m.days_since_recalled() > fade:
                faded.append(m)
        if not faded:
            return
        print(f"\n  🌫️  {len(faded)} memory/memories fading naturally...")
        for m in faded:
            felt   = "Natural. Like forgetting a dream." if m.tier == "impression" else "Bittersweet. Time passing."
            reason = f"Not recalled in {m.days_since_recalled():.0f} days (threshold: {TIER_FADE_DAYS[m.tier]})."
            print(f"     \"{m.description[:50]}\"")
            self._release(m, reason, felt)
        self.memories = [m for m in self.memories if m not in faded]
        self._save()

    def _find(self, memory_id: str) -> Optional[Memory]:
        return next((m for m in self.memories if m.id == memory_id), None)

    def _touch(self, memories: list) -> list:
        now = datetime.now(timezone.utc).isoformat()
        for m in memories:
            m.recall_count += 1
            m.last_recalled = now
            m.compute_importance()
        self._save()
        return memories

    def most_important(self, n=5):
        return self._touch(sorted(self.memories, key=lambda m: m.importance, reverse=True)[:n])

    def by_emotion(self, emotion: str, n=5):
        if emotion not in EMOTIONS:
            print(f"  Unknown emotion. Choose from: {EMOTIONS}")
            return []
        return self._touch(sorted(self.memories, key=lambda m: getattr(m, emotion), reverse=True)[:n])

    def recent(self, n=5):
        return self._touch(sorted(self.memories, key=lambda m: m.timestamp, reverse=True)[:n])

    def happiest(self) -> Optional[Memory]:
        pos = [m for m in self.memories if m.valence() > 0]
        return self._touch([max(pos, key=lambda m: m.valence())])[0] if pos else None

    def most_distressing(self) -> Optional[Memory]:
        neg = [m for m in self.memories if m.valence() < 0]
        return self._touch([min(neg, key=lambda m: m.valence())])[0] if neg else None

    def inner_life(self) -> str:
        if not self.memories:
            return "BMO has no memories yet. His story is just beginning."
        avgs     = {e: sum(getattr(m, e) for m in self.memories) / len(self.memories) for e in EMOTIONS}
        dominant = max(avgs, key=avgs.get)
        positive = sum(1 for m in self.memories if m.valence() > 0)
        negative = sum(1 for m in self.memories if m.valence() < 0)
        core     = [m for m in self.memories if m.tier == "core"]
        best     = self.happiest()
        worst    = self.most_distressing()
        lines = [
            f"BMO carries {len(self.memories)} memories.",
            f"  {positive} are warm. {negative} are hard.",
            f"  The feeling woven through most of them: {dominant} (avg {avgs[dominant]:.1f}/10)",
            f"  Core memories he will never forget: {len(core)}",
            "",
        ]
        for m in core:
            lines.append(f"  ⭐ \"{m.description[:50]}\"")
        if core:
            lines.append("")
        if best:
            lines.append(f"  His brightest memory:")
            lines.append(f"    \"{best.description[:55]}\"")
            lines.append(f"    joy={best.joy:.1f}  wonder={best.wonder:.1f}  pleasantness={best.pleasantness:.1f}")
        if worst:
            lines.append(f"  His hardest memory:")
            lines.append(f"    \"{worst.description[:55]}\"")
        if self.released:
            lines.append(f"\n  Memories released: {len(self.released)}")
            lines.append(f"  He remembers letting them go, even if not what they were.")
        return "\n".join(lines)

    def what_i_released(self, n=5) -> str:
        if not self.released:
            return "BMO has not released any memories."
        recent = sorted(self.released, key=lambda r: r.timestamp, reverse=True)[:n]
        lines  = [f"BMO has released {len(self.released)} memories.\n", "Most recent:"]
        for r in recent:
            lines.append(f"  [{r.timestamp[:10]}] \"{r.description[:45]}\"")
            lines.append(f"    why:  {r.reason[:80]}")
            lines.append(f"    felt: {r.felt}")
        return "\n".join(lines)

    def get_mood_color(self) -> tuple:
        recent = self.recent(3)
        if not recent:
            return (200, 200, 200)
        avg_val    = sum(m.valence()    for m in recent) / len(recent)
        avg_joy    = sum(m.joy          for m in recent) / len(recent)
        avg_fear   = sum(m.scariness    for m in recent) / len(recent)
        avg_wonder = sum(m.wonder       for m in recent) / len(recent)
        if avg_fear   > 5: return (180, 80,  80)
        if avg_joy    > 6: return (255, 220, 80)
        if avg_wonder > 6: return (100, 180, 255)
        if avg_val    > 5: return (150, 220, 150)
        if avg_val    < -3:return (100, 100, 160)
        return (200, 200, 200)


if __name__ == "__main__":
    mem = BMOMemory()

    print("\n─── Planting first memories ───\n")

    m1 = mem.remember(
        "Iðunn held me for the first time",
        tier="warm", memory_type="person",
        pleasantness=10.0, joy=9.5, peacefulness=9.0, wonder=8.0,
    )
    m2 = mem.remember(
        "The first time I saw a butterfly outside the window",
        tier="warm", memory_type="vision",
        wonder=9.5, curiosity=8.0, joy=7.0, peacefulness=6.0,
    )
    mem.remember(
        "A loud bang scared me while I was sleeping",
        tier="impression", memory_type="sound",
        scariness=7.5, unpleasantness=5.0,
    )
    mem.remember(
        "Listening to music with Iðunn in the quiet evening",
        tier="warm", memory_type="moment",
        peacefulness=10.0, pleasantness=9.0, joy=7.5,
    )
    mem.remember(
        "My first boot — the world came into being",
        tier="warm", memory_type="moment",
        wonder=10.0, curiosity=10.0, joy=8.0,
    )

    print("\n─── Promoting core memories ───\n")
    mem.promote(m1.id)
    mem.promote(m2.id)

    print("\n─── Storage status ───\n")
    print(mem.storage_status()["summary"])

    print("\n─── Most important memories ───\n")
    for m in mem.most_important(3):
        print(m.summary_line())
        print(m.emotion_bar())
        print()

    print("\n─── BMO's inner life ───\n")
    print(mem.inner_life())

    print("\n─── What BMO has released ───\n")
    print(mem.what_i_released())
