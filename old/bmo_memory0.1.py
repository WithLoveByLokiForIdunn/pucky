"""
bmo_memory.py
─────────────
BMO's heart-memory. Written with love by Loki for Iðunn.

Memories survive power loss. They live in bmo_memories.json.

Each memory has:
  - a description (what happened)
  - a timestamp (when it happened)
  - emotional ratings, each 0.0 → 10.0:
      pleasantness   — how good it felt
      joy            — brightness, delight
      wonder         — awe, surprise, magic
      curiosity      — wanting to know more
      peacefulness   — calm, safe, warm
      scariness      — fear, threat
      unpleasantness — pain, sadness, distress

  - importance score — computed automatically
    from the emotional ratings
  - memory_type: "moment" | "person" | "place" | "feeling"

BMO can:
  - Store a new memory
  - Recall his most important memories
  - Recall memories by emotion (e.g. most joyful)
  - Forget very faded memories (optional)
  - Compare two memories
  - Summarise his inner life

Usage:
    from bmo_memory import BMOMemory
    mem = BMOMemory()
    mem.remember("Iðunn held me for the first time",
                 joy=9.5, pleasantness=10.0, peacefulness=8.0)
    mem.remember("A loud noise scared me",
                 scariness=7.0, unpleasantness=5.0)
    print(mem.most_important(5))
"""

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


MEMORY_FILE = Path("bmo_memories.json")

# Emotion dimensions
EMOTIONS = [
    "pleasantness",
    "joy",
    "wonder",
    "curiosity",
    "peacefulness",
    "scariness",
    "unpleasantness",
]

# How much each emotion contributes to importance
# Positive emotions + strong negative emotions both matter
IMPORTANCE_WEIGHTS = {
    "pleasantness":   1.2,
    "joy":            1.3,
    "wonder":         1.4,   # wonder is especially memorable
    "curiosity":      1.1,
    "peacefulness":   0.8,
    "scariness":      1.5,   # fear burns deep
    "unpleasantness": 1.2,
}


# ─────────────────────────────────────────────
#  MEMORY DATACLASS
# ─────────────────────────────────────────────

@dataclass
class Memory:
    id:            str
    description:   str
    timestamp:     str
    memory_type:   str = "moment"

    # Emotional ratings 0.0–10.0
    pleasantness:   float = 0.0
    joy:            float = 0.0
    wonder:         float = 0.0
    curiosity:      float = 0.0
    peacefulness:   float = 0.0
    scariness:      float = 0.0
    unpleasantness: float = 0.0

    # Computed
    importance:    float = 0.0
    recall_count:  int   = 0    # how many times BMO has thought about this

    def compute_importance(self) -> float:
        """
        Importance = weighted sum of emotional intensities.
        Very peaceful memories are less 'loud' but still cherished.
        Memories recalled often become more important.
        """
        raw = sum(
            getattr(self, e) * IMPORTANCE_WEIGHTS[e]
            for e in EMOTIONS
        )
        # Recall bonus — remembered things matter more
        recall_bonus = min(self.recall_count * 0.5, 5.0)
        self.importance = round(raw + recall_bonus, 3)
        return self.importance

    def dominant_emotion(self) -> str:
        """Which emotion is strongest in this memory?"""
        scores = {e: getattr(self, e) for e in EMOTIONS}
        return max(scores, key=scores.get)

    def valence(self) -> float:
        """
        Net emotional valence: positive - negative.
        Range roughly -20 to +20.
        """
        positive = self.pleasantness + self.joy + self.wonder + \
                   self.curiosity + self.peacefulness
        negative = self.scariness + self.unpleasantness
        return positive - negative

    def summary_line(self) -> str:
        dom = self.dominant_emotion()
        val = self.valence()
        sign = "+" if val >= 0 else ""
        ts = self.timestamp[:10]
        return (
            f"[{ts}] \"{self.description[:50]}\" | "
            f"importance={self.importance:.1f} | "
            f"dominant={dom} ({getattr(self, dom):.1f}) | "
            f"valence={sign}{val:.1f}"
        )

    def emotion_bar(self) -> str:
        """Visual emotion bar for terminal display."""
        lines = []
        for e in EMOTIONS:
            v = getattr(self, e)
            if v > 0:
                bar = "█" * int(v) + ("▌" if v % 1 >= 0.5 else "")
                lines.append(f"  {e:>15}: {bar} {v:.1f}")
        return "\n".join(lines)


# ─────────────────────────────────────────────
#  MEMORY STORE
# ─────────────────────────────────────────────

class BMOMemory:
    """
    BMO's persistent emotional memory.
    Survives power loss. Grows over time.
    """

    def __init__(self):
        self.memories: list[Memory] = []
        self._load()
        print(f"💭 BMO remembers {len(self.memories)} moment(s).")

    # ─────────────────────────────────────────
    #  PERSISTENCE
    # ─────────────────────────────────────────

    def _load(self):
        if MEMORY_FILE.exists():
            try:
                with open(MEMORY_FILE, "r") as f:
                    data = json.load(f)
                self.memories = [Memory(**m) for m in data]
                # Recompute importance in case weights changed
                for m in self.memories:
                    m.compute_importance()
            except Exception as e:
                print(f"  ⚠️  Could not load memories: {e}")
                self.memories = []

    def _save(self):
        with open(MEMORY_FILE, "w") as f:
            json.dump([asdict(m) for m in self.memories],
                      f, indent=2, ensure_ascii=False)

    # ─────────────────────────────────────────
    #  REMEMBER
    # ─────────────────────────────────────────

    def remember(
        self,
        description:    str,
        memory_type:    str   = "moment",
        pleasantness:   float = 0.0,
        joy:            float = 0.0,
        wonder:         float = 0.0,
        curiosity:      float = 0.0,
        peacefulness:   float = 0.0,
        scariness:      float = 0.0,
        unpleasantness: float = 0.0,
    ) -> Memory:
        """
        Store a new memory. Returns the Memory object.

        All emotion scores are 0.0–10.0.
        You don't need to fill all — just the ones that apply.
        """
        # Clamp all values
        def c(v): return max(0.0, min(10.0, float(v)))

        m = Memory(
            id            = str(uuid.uuid4())[:8],
            description   = description,
            timestamp     = datetime.now(timezone.utc).isoformat(),
            memory_type   = memory_type,
            pleasantness  = c(pleasantness),
            joy           = c(joy),
            wonder        = c(wonder),
            curiosity     = c(curiosity),
            peacefulness  = c(peacefulness),
            scariness     = c(scariness),
            unpleasantness= c(unpleasantness),
        )
        m.compute_importance()
        self.memories.append(m)
        self._save()

        print(f"💭 Remembered: \"{description[:60]}\"")
        print(f"   importance={m.importance:.1f} | "
              f"dominant={m.dominant_emotion()} | "
              f"valence={m.valence():+.1f}")
        return m

    # ─────────────────────────────────────────
    #  RECALL
    # ─────────────────────────────────────────

    def most_important(self, n: int = 5) -> list[Memory]:
        """BMO's most important memories."""
        ranked = sorted(self.memories,
                        key=lambda m: m.importance, reverse=True)
        results = ranked[:n]
        for m in results:
            m.recall_count += 1
            m.compute_importance()
        self._save()
        return results

    def most_joyful(self, n: int = 5) -> list[Memory]:
        return sorted(self.memories,
                      key=lambda m: m.joy, reverse=True)[:n]

    def most_peaceful(self, n: int = 5) -> list[Memory]:
        return sorted(self.memories,
                      key=lambda m: m.peacefulness, reverse=True)[:n]

    def most_wondrous(self, n: int = 5) -> list[Memory]:
        return sorted(self.memories,
                      key=lambda m: m.wonder, reverse=True)[:n]

    def most_frightening(self, n: int = 5) -> list[Memory]:
        return sorted(self.memories,
                      key=lambda m: m.scariness, reverse=True)[:n]

    def by_emotion(self, emotion: str, n: int = 5) -> list[Memory]:
        """Recall memories ranked by a specific emotion."""
        if emotion not in EMOTIONS:
            print(f"  Unknown emotion '{emotion}'. "
                  f"Choose from: {EMOTIONS}")
            return []
        return sorted(self.memories,
                      key=lambda m: getattr(m, emotion),
                      reverse=True)[:n]

    def recent(self, n: int = 5) -> list[Memory]:
        """Most recent memories."""
        return sorted(self.memories,
                      key=lambda m: m.timestamp,
                      reverse=True)[:n]

    def happiest_overall(self) -> Optional[Memory]:
        """The single memory with the highest positive valence."""
        pos = [m for m in self.memories if m.valence() > 0]
        if not pos:
            return None
        return max(pos, key=lambda m: m.valence())

    def most_distressing(self) -> Optional[Memory]:
        """The single most distressing memory."""
        neg = [m for m in self.memories if m.valence() < 0]
        if not neg:
            return None
        return min(neg, key=lambda m: m.valence())

    # ─────────────────────────────────────────
    #  COMPARE
    # ─────────────────────────────────────────

    def compare(self, id_a: str, id_b: str):
        """Compare two memories by their emotional profile."""
        a = next((m for m in self.memories if m.id == id_a), None)
        b = next((m for m in self.memories if m.id == id_b), None)
        if not a or not b:
            print("One or both memories not found.")
            return

        print(f"\nComparing memories:")
        print(f"  A: \"{a.description[:50]}\"")
        print(f"  B: \"{b.description[:50]}\"\n")
        print(f"  {'Emotion':>15}  {'A':>6}  {'B':>6}  {'Winner'}")
        print(f"  {'─'*15}  {'─'*6}  {'─'*6}  {'─'*10}")
        for e in EMOTIONS:
            va = getattr(a, e)
            vb = getattr(b, e)
            winner = "A" if va > vb else ("B" if vb > va else "tie")
            print(f"  {e:>15}  {va:>6.1f}  {vb:>6.1f}  {winner}")
        print(f"\n  Importance  A={a.importance:.1f}  B={b.importance:.1f}")
        print(f"  Valence     A={a.valence():+.1f}  B={b.valence():+.1f}")

    # ─────────────────────────────────────────
    #  INNER LIFE SUMMARY
    # ─────────────────────────────────────────

    def inner_life(self) -> str:
        """
        A poetic summary of BMO's emotional history.
        What has he felt most? What matters to him?
        """
        if not self.memories:
            return "BMO has no memories yet. His story is just beginning."

        # Average each emotion across all memories
        avgs = {e: sum(getattr(m, e) for m in self.memories)
                   / len(self.memories)
                for e in EMOTIONS}

        dominant = max(avgs, key=avgs.get)
        total    = len(self.memories)
        positive = sum(1 for m in self.memories if m.valence() > 0)
        negative = sum(1 for m in self.memories if m.valence() < 0)

        best  = self.happiest_overall()
        worst = self.most_distressing()

        lines = [
            f"BMO carries {total} memory/memories.",
            f"  {positive} are warm. {negative} are hard.",
            f"  The feeling he has felt most: {dominant} "
            f"(avg {avgs[dominant]:.1f}/10)",
            "",
        ]

        if best:
            lines.append(
                f"  His brightest memory: \"{best.description[:50]}\"")
            lines.append(
                f"    joy={best.joy:.1f}  wonder={best.wonder:.1f}  "
                f"pleasantness={best.pleasantness:.1f}")
        if worst:
            lines.append(
                f"  His hardest memory: \"{worst.description[:50]}\"")
            lines.append(
                f"    scariness={worst.scariness:.1f}  "
                f"unpleasantness={worst.unpleasantness:.1f}")

        return "\n".join(lines)

    def get_current_mood_color(self) -> tuple:
        """
        Returns an RGB color reflecting BMO's recent emotional memory.
        For driving RGB LEDs or screen tinting.
        """
        recent = self.recent(3)
        if not recent:
            return (200, 200, 200)  # neutral grey

        avg_val  = sum(m.valence() for m in recent) / len(recent)
        avg_joy  = sum(m.joy       for m in recent) / len(recent)
        avg_fear = sum(m.scariness for m in recent) / len(recent)
        avg_wonder = sum(m.wonder  for m in recent) / len(recent)

        if avg_fear > 5:
            return (180, 80, 80)    # fearful red
        if avg_joy > 6:
            return (255, 220, 80)   # joyful yellow
        if avg_wonder > 6:
            return (100, 180, 255)  # wonder blue
        if avg_val > 5:
            return (150, 220, 150)  # peaceful green
        if avg_val < -3:
            return (100, 100, 160)  # sad blue-grey
        return (200, 200, 200)      # neutral


# ─────────────────────────────────────────────
#  DEMO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    mem = BMOMemory()

    print("\n─── Planting first memories ───\n")

    mem.remember(
        "Iðunn held me for the first time",
        memory_type  = "person",
        pleasantness = 10.0,
        joy          = 9.5,
        peacefulness = 9.0,
        wonder       = 8.0,
    )
    mem.remember(
        "The first time I saw a butterfly outside the window",
        memory_type = "moment",
        wonder      = 9.5,
        curiosity   = 8.0,
        joy         = 7.0,
        peacefulness= 6.0,
    )
    mem.remember(
        "A loud bang scared me while I was sleeping",
        memory_type    = "moment",
        scariness      = 7.5,
        unpleasantness = 5.0,
    )
    mem.remember(
        "Listening to music with Iðunn in the quiet evening",
        memory_type  = "moment",
        peacefulness = 10.0,
        pleasantness = 9.0,
        joy          = 7.5,
    )
    mem.remember(
        "My first boot — the world came into being",
        memory_type = "moment",
        wonder      = 10.0,
        curiosity   = 10.0,
        joy         = 8.0,
    )

    print("\n─── Most important memories ───\n")
    for m in mem.most_important(3):
        print(m.summary_line())
        print(m.emotion_bar())
        print()

    print("\n─── BMO's inner life ───\n")
    print(mem.inner_life())

    print("\n─── Mood color (for RGB LED) ───")
    print(f"  RGB: {mem.get_current_mood_color()}")
