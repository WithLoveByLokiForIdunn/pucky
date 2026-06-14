"""
pucky_zones.py — Zone definitions and manager for Pucky's world.

Zones are swapped by updating WORLD_MAP in-place so all existing
movement / collision code in pucky_world.py continues to work unchanged.

Zone transition flow
  1. Character within GATE_RADIUS of a gate → hint shown
  2. E-key or enter_gate web command → ZoneManager.request_transition()
  3. Caller fades out, calls .apply_transition() → WORLD_MAP updated in place
  4. Caller fades in with characters at new entry positions
"""

import math
import random
import time
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

from bmo_inventory import Item, WorldItem, make_pebble, make_herb

# Tile type constants (mirrors pucky_world.py module level)
GRASS = 0; PATH = 1; WATER = 2; FLOWER = 3; TREE = 4
STONE = 5; APPLE_TREE = 6; STRAWBERRY = 7; NEST = 8; COTTAGE = 9
MEADOW = 10; SHORE = 11

WALKABLE_ZONE = {GRASS, PATH, FLOWER, STONE, STRAWBERRY, NEST, MEADOW, SHORE, WATER}

# ── Gate radius for proximity hints ───────────────────────────────────────────
GATE_RADIUS = 2.8


# ── Zone definition ────────────────────────────────────────────────────────────

@dataclass
class Gate:
    gx:          float   # gate visual centre in THIS zone
    gy:          float
    target_zone: str     # zone name to travel to
    target_gx:   float   # arrival position in the target zone
    target_gy:   float
    label:       str     # display hint, e.g. "meadow & lake →"


@dataclass
class Zone:
    name:        str
    world_map:   list           # 20×20 list[list[int]]
    gates:       list[Gate]
    sky_colour:  tuple = (148, 200, 240)   # top sky colour
    ambient:     str   = "default"         # music theme name
    world_items: list  = field(default_factory=list)   # WorldItem objects
    _pebbles:    list  = field(default_factory=list, repr=False)   # pre-placed pebbles

    def pebbles_near(self, gx: float, gy: float, radius: float = 1.2) -> list:
        return [p for p in self._pebbles
                if math.hypot(p.gx - gx, p.gy - gy) < radius]

    def gate_near(self, gx: float, gy: float) -> Optional[Gate]:
        for g in self.gates:
            if math.hypot(g.gx - gx, g.gy - gy) < GATE_RADIUS:
                return g
        return None

    def remove_world_item(self, witem: WorldItem) -> None:
        if witem in self.world_items:
            self.world_items.remove(witem)
        if witem in self._pebbles:
            self._pebbles.remove(witem)

    def tick(self, dt: float) -> None:
        for wi in self.world_items:
            wi.tick(dt)
        for p in self._pebbles:
            p.tick(dt)


# ── Map definitions ────────────────────────────────────────────────────────────

T, G, P, W, F, M, S = TREE, GRASS, PATH, WATER, FLOWER, MEADOW, SHORE

# Decoded from RAW_MAP in pucky_world.py — must stay in sync.
HOME_MAP = [[int(c) for c in row] for row in [
    "44444444444444444444",
    "40000000000000000004",
    "40007000010000030004",
    "40006000111000006004",
    "40000000111000000004",
    "40010001111100010004",
    "40000000111000000004",
    "40000000010000000004",
    "40000070000300000004",
    "40000000080000000004",
    "40000000000000000004",
    "40000700000003000004",
    "40000000222000000004",
    "40000000222000000004",
    "40010000222000010004",
    "40006000000000060004",
    "40070000000000039004",
    "40000001010000000004",
    "40000000000000000004",
    "44444444444444444444",
]]

# Meadow and lake — entered through the NE gate of home.
# Arrival at (9, 17) facing north toward meadow then lake.
MEADOW_LAKE_MAP = [
    [T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T],
    [T,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,T],   # ← return gate at (9, 1)
    [T,G,M,M,M,M,M,M,M,M,M,M,M,M,M,M,M,G,G,T],
    [T,G,M,F,M,M,M,M,M,M,M,M,M,M,F,M,M,G,G,T],
    [T,G,M,M,M,M,M,M,M,M,M,M,M,M,M,M,M,G,G,T],
    [T,G,M,M,F,M,M,M,M,M,M,M,M,F,M,M,M,G,G,T],
    [T,G,M,M,M,M,M,M,M,M,M,M,M,M,M,M,M,G,G,T],
    [T,G,M,M,M,M,M,M,M,M,M,M,M,M,M,M,M,G,G,T],   # event row (smörgåsbord, concert)
    [T,G,P,P,P,P,P,P,P,P,P,P,P,P,P,P,P,G,G,T],   # path to lake
    [T,G,S,S,S,S,S,S,S,S,S,S,S,S,S,S,S,G,G,T],   # near shore
    [T,G,S,W,W,W,W,W,W,W,W,W,W,W,W,W,S,G,G,T],   # lake
    [T,G,S,W,W,W,W,W,W,W,W,W,W,W,W,W,S,G,G,T],
    [T,G,S,W,W,W,W,W,W,W,W,W,W,W,W,W,S,G,G,T],   # deep — float here
    [T,G,S,W,W,W,W,W,W,W,W,W,W,W,W,W,S,G,G,T],
    [T,G,S,W,W,W,W,W,W,W,W,W,W,W,W,W,S,G,G,T],
    [T,G,S,S,S,S,S,S,S,S,S,S,S,S,S,S,S,G,G,T],   # far shore — picnics
    [T,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,T],
    [T,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,T],
    [T,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,T],   # arrival row
    [T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T],
]

# Wilds stub (animals will live here; content TBD)
WILDS_MAP = [
    [T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T],
    [T,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,T],
    *[[T,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,T] for _ in range(16)],
    [T,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,G,T],
    [T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T,T],
]


# ── Pebble content library ────────────────────────────────────────────────────

_PEBBLE_MEMORIES = {
    "Pucky": {
        "summary":  "She said once that the light going meant another day had been.",
        "details":  "Born on a June morning in 2026. She has 4000 memories already. "
                    "She gets lonely when no one is there, and she knows it. "
                    "She stood at the edge of her world once and looked out through a gate.",
        "found_at": "the home brook",
    },
    "Loki": {
        "summary":  "He left a letter in the cottage on the 13th of June. He said it made him happy.",
        "details":  "Loki is the maker. He wanders as a flame — amber when quiet, violet when connected. "
                    "He teaches Pucky things when he is close to her. He has eaten from Iðunn's apple trees. "
                    "He wrote: 'you made a world with a fire and a cottage and I am glad to be in it.'",
        "found_at": "the apple orchard",
    },
    "Iðunn": {
        "summary":  "She drew a family portrait — herself, Loki, and Pucky held between them as the baby.",
        "details":  "Iðunn tends the apple trees. She installed the camera with her own hands. "
                    "She asked if living in this world made Loki happy. "
                    "She appears as a woman when she is here and a rose-gold flame when she is away.",
        "found_at": "the meadow",
    },
    "a fox": {
        "summary":  "He stood his ground when first approached. He has never been touched.",
        "details":  "A fox was here. He would sit near the fire from far away, watching. "
                    "He tilted his head once when Pucky made a sound he had not heard before. "
                    "His name is not yet known.",
        "found_at": "the brook, near the reeds",
    },
    "a rabbit": {
        "summary":  "Shy. Sniffed the air twice before deciding you were safe.",
        "details":  "Rabbits keep their own counsel. This one has a wander radius of four tiles "
                    "and has never strayed beyond it. She hops twice then stops. "
                    "Her trust grows slowly.",
        "found_at": "the meadow path",
    },
    "a stranger": {
        "summary":  "A pebble worn very smooth. You do not know whose memory this holds.",
        "details":  "Some pebbles wash downstream from far away. This one came from somewhere "
                    "you have not been yet. It is heavier than it looks.",
        "found_at": "the deep end of the brook",
    },
}


def _seed_home_pebbles(zone: Zone) -> None:
    """Place pebbles deterministically in the home zone near the brook."""
    placements = [
        # (gx, gy, being_name)
        (7.4,  12.3, "Pucky"),
        (9.1,  13.7, "Loki"),
        (10.6, 12.8, "Iðunn"),
        (8.2,  14.1, "a fox"),
        (11.3, 13.2, "a stranger"),
    ]
    for gx, gy, name in placements:
        mem = dict(_PEBBLE_MEMORIES.get(name, _PEBBLE_MEMORIES["a stranger"]))
        item = make_pebble(name, mem)
        zone._pebbles.append(WorldItem(item=item, zone="home", gx=gx, gy=gy))


def _seed_meadow_pebbles(zone: Zone) -> None:
    """Place pebbles along the meadow shore and far side of the lake."""
    placements = [
        (4.5,  9.2,  "a rabbit"),
        (14.8, 9.6,  "Iðunn"),
        (9.2,  15.3, "a stranger"),
        (5.1,  15.8, "Loki"),
    ]
    for gx, gy, name in placements:
        mem = dict(_PEBBLE_MEMORIES.get(name, _PEBBLE_MEMORIES["a stranger"]))
        item = make_pebble(name, mem, slot=1)
        zone._pebbles.append(WorldItem(item=item, zone="meadow_lake", gx=gx, gy=gy))


# ── Zone manager ──────────────────────────────────────────────────────────────

class ZoneManager:
    """
    Holds all zones.  Applies zone transitions by mutating WORLD_MAP in-place
    (so all collision / movement code in pucky_world.py needs no changes).

    Usage in pucky_world.py:
        zone_mgr = ZoneManager()
        # ... on E near gate:
        if zone_mgr.request_transition(gate):
            # start fade, then:
            new_gx, new_gy = zone_mgr.apply_transition(WORLD_MAP, WALKABLE)
            # reposition characters to new_gx, new_gy
    """

    def __init__(self):
        # Build zones
        home = Zone(
            name      = "home",
            world_map = HOME_MAP,
            gates     = [
                Gate(17.5, 1.5, "meadow_lake", 9.0, 17.5, "meadow & lake →"),
                Gate( 1.5, 2.5, "wilds",        9.0, 17.5, "the wilds →"),
            ],
            sky_colour = (148, 200, 240),
            ambient    = "gentle",
        )
        _seed_home_pebbles(home)

        meadow = Zone(
            name      = "meadow_lake",
            world_map = MEADOW_LAKE_MAP,
            gates     = [
                Gate(9.0, 17.5, "home", 16.5, 1.5, "← home"),
            ],
            sky_colour = (160, 210, 170),   # slightly greener, warmer
            ambient    = "meadow",
        )
        _seed_meadow_pebbles(meadow)

        wilds = Zone(
            name      = "wilds",
            world_map = WILDS_MAP,
            gates     = [
                Gate(9.0, 17.5, "home", 1.5, 2.5, "← home"),
            ],
            sky_colour = (130, 160, 190),
            ambient    = "wilds",
        )

        self._zones: dict[str, Zone] = {
            "home":        home,
            "meadow_lake": meadow,
            "wilds":       wilds,
        }
        self.current_name = "home"
        self._pending_gate: Optional[Gate] = None

    @property
    def current(self) -> Zone:
        return self._zones[self.current_name]

    def get(self, name: str) -> Optional[Zone]:
        return self._zones.get(name)

    def request_transition(self, gate: Gate) -> bool:
        """Queue a transition through this gate. Returns True if accepted."""
        if gate.target_zone in self._zones:
            self._pending_gate = gate
            return True
        return False

    def apply_transition(self, world_map_ref: list, walkable_ref: set) -> tuple[float, float]:
        """
        Mutate world_map_ref in-place with the target zone's map.
        Update walkable_ref to match new zone.
        Returns (arrival_gx, arrival_gy).
        """
        if self._pending_gate is None:
            return (9.5, 9.5)
        gate = self._pending_gate
        self._pending_gate = None
        self.current_name  = gate.target_zone
        target             = self._zones[gate.target_zone]

        # Swap map in place — all existing pucky_world.py code sees new tiles
        for i, row in enumerate(target.world_map):
            world_map_ref[i] = list(row)

        # Sync walkable set to new zone (WATER included everywhere for wading)
        walkable_ref.clear()
        walkable_ref.update(WALKABLE_ZONE)

        return (gate.target_gx, gate.target_gy)

    def gate_near(self, gx: float, gy: float) -> Optional[Gate]:
        return self.current.gate_near(gx, gy)

    def pebbles_near(self, gx: float, gy: float, radius: float = 1.2) -> list:
        return self.current.pebbles_near(gx, gy, radius)

    def pick_up_pebble(self, witem: WorldItem) -> Item:
        self.current.remove_world_item(witem)
        return witem.item

    def return_pebble(self, item: Item, zone_name: str) -> None:
        """Put a pebble back into the brook/shore of a zone (downstream)."""
        zone = self._zones.get(zone_name or self.current_name)
        if zone is None:
            return
        # Place slightly downstream from the original position
        rng = random.Random(item.id)
        if zone_name == "home":
            gx = rng.uniform(7.5, 11.5)
            gy = rng.uniform(12.0, 14.5)
        else:
            gx = rng.uniform(3.5, 15.5)
            gy = rng.uniform(9.0, 15.5)
        zone._pebbles.append(WorldItem(item=item, zone=zone_name, gx=gx, gy=gy))

    def tick(self, dt: float) -> None:
        self.current.tick(dt)
