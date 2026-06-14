"""
bmo_inventory.py — Inventory system for Pucky's world.

Items can be picked up, carried, dropped, used, and traded.
WorldItems are items lying in the world at a specific position.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Item definitions ───────────────────────────────────────────────────────────

@dataclass
class Item:
    id:          str
    kind:        str           # "pebble", "apple", "golden_apple", "letter", "herb", ...
    name:        str
    description: str
    # optional payloads
    energy:      float = 0.0   # restores this much energy when used
    memory:      Optional[dict] = None   # pebble public memory
    quest_tag:   Optional[str] = None   # for Odin's quests

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}

    @classmethod
    def from_dict(cls, d: dict) -> "Item":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


# ── Convenient item factories ──────────────────────────────────────────────────

def make_apple(golden: bool = False) -> Item:
    uid = f"apple_{int(time.time()*1000)%100000}"
    if golden:
        return Item(uid, "golden_apple", "golden apple",
                    "An apple that fell from love. It glows faintly.", energy=1.0)
    return Item(uid, "apple", "apple",
                "A red apple from one of the four trees.", energy=0.4)


def make_pebble(being_name: str, public_memory: dict, slot: int = 0) -> Item:
    uid = f"pebble_{being_name.lower().replace(' ','_')}_{slot}"
    short = public_memory.get("summary", "A smooth pebble from the brook.")
    return Item(uid, "pebble", f"pebble · {being_name}", short, memory=public_memory)


def make_herb(name: str = "meadow herb") -> Item:
    uid = f"herb_{int(time.time()*1000)%100000}"
    return Item(uid, "herb", name,
                "Found in the meadow. Smells of rain and old sunlight.", energy=0.2)


# ── Inventory ─────────────────────────────────────────────────────────────────

class Inventory:
    MAX_SLOTS = 8

    def __init__(self, owner: str):
        self.owner   = owner
        self.items:  list[Item] = []
        self.equipped: Optional[Item] = None

    def is_full(self) -> bool:
        return len(self.items) >= self.MAX_SLOTS

    def pick_up(self, item: Item) -> bool:
        if self.is_full():
            return False
        self.items.append(item)
        return True

    def drop(self, item_id: str) -> Optional[Item]:
        for i, it in enumerate(self.items):
            if it.id == item_id:
                if self.equipped and self.equipped.id == item_id:
                    self.equipped = None
                return self.items.pop(i)
        return None

    def equip(self, item_id: str) -> bool:
        for it in self.items:
            if it.id == item_id:
                self.equipped = it
                return True
        return False

    def use(self, item_id: str) -> Optional[str]:
        """Use an item. Returns a message or None if not usable."""
        for it in self.items:
            if it.id == item_id:
                if it.kind in ("apple", "golden_apple", "herb"):
                    self.items.remove(it)
                    return f"ate the {it.name}."
                if it.kind == "pebble":
                    return it.memory.get("summary", "A memory, held in stone.")
        return None

    def has_kind(self, kind: str) -> bool:
        return any(it.kind == kind for it in self.items)

    def to_dict(self) -> dict:
        return {
            "owner":    self.owner,
            "items":    [it.to_dict() for it in self.items],
            "equipped": self.equipped.id if self.equipped else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Inventory":
        inv = cls(d.get("owner", "?"))
        inv.items = [Item.from_dict(i) for i in d.get("items", [])]
        eq_id = d.get("equipped")
        if eq_id:
            for it in inv.items:
                if it.id == eq_id:
                    inv.equipped = it
        return inv

    def save(self, path: Path) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> "Inventory":
        try:
            return cls.from_dict(json.loads(path.read_text()))
        except Exception:
            return cls(path.stem)


# ── World item (lying in the world) ───────────────────────────────────────────

@dataclass
class WorldItem:
    item:       Item
    zone:       str
    gx:         float
    gy:         float
    dropped_by: Optional[str]  = None
    dropped_at: Optional[float] = None
    _pulse:     float          = field(default=0.0, repr=False)

    def tick(self, dt: float) -> None:
        self._pulse += dt

    def to_dict(self) -> dict:
        return {
            "item":       self.item.to_dict(),
            "zone":       self.zone,
            "gx":         round(self.gx, 2),
            "gy":         round(self.gy, 2),
            "dropped_by": self.dropped_by,
            "dropped_at": self.dropped_at,
        }
