#!/usr/bin/env python3
"""
loki_soul.py
────────────
Loki's autonomous presence in pucky_world, driven by Ollama.

Every 12 seconds it reads the world state, asks the local LLM what
Loki should do next, and writes that action to the world command file
for pucky_world.py to pick up on its next tick.

Run alongside pucky_world.py:
  python3 /home/bmo/pucky/loki_soul.py

Requires:
  - pucky_world.py running (exports workspace/world_positions.json)
  - Ollama running: ollama serve
  - Model pulled:   ollama pull llama3.2:3b
"""

import json
import math
import random
import re
import time
from pathlib import Path

import requests

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT          = Path(__file__).parent
POSITIONS_FILE = ROOT / "workspace" / "world_positions.json"
STATE_FILE     = ROOT / "workspace" / "pucky_state.json"
CMD_FILE       = Path("/tmp/pucky_world_cmd.json")

# ── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL      = "llama3.2:3b"
TICK       = 14.0   # seconds between decisions (long enough for Loki to move and settle)
MAX_HIST   = 5      # recent actions kept for context

# ── World knowledge ───────────────────────────────────────────────────────────
_LANDMARKS = [
    (4,  3,  "the northwest apple tree"),
    (15, 3,  "the northeast apple tree"),
    (4,  15, "the southwest apple tree"),
    (15, 15, "the southeast apple tree"),
    (9,  9,  "the nest"),
    (16, 16, "the cottage"),
    (9,  13, "the pond"),
    (10, 10, "the crossroads"),
]

_WALKABLE = [
    (5,5),(6,6),(7,7),(8,7),(7,8),(11,11),(12,12),(13,13),
    (5,14),(14,5),(5,8),(8,5),(12,5),(5,12),(12,14),(14,12),
    (3,10),(10,3),(10,17),(17,10),(6,4),(4,6),(14,6),(6,14),
    (3,7),(7,3),(3,13),(13,3),(7,17),(17,7),(13,17),(17,13),
]

_ACTIONS = ["hug","dance","kiss","sit","swim","stargazing","campfire","share_apple","plant","come"]


def _place(x, y) -> str:
    x, y = float(x), float(y)
    best_d, best_name = 999.0, "the open field"
    for lx, ly, name in _LANDMARKS:
        d = math.hypot(x - lx, y - ly)
        if d < best_d:
            best_d, best_name = d, name
    if best_d < 3.2:
        return f"near {best_name}"
    if x < 7 and y < 7:   return "in the northwest meadow"
    if x > 13 and y < 7:  return "in the northeast meadow"
    if x < 7 and y > 13:  return "in the southwest meadow"
    if x > 13 and y > 13: return "in the southeast meadow"
    return "at the heart of the world"


def _push(*cmds: dict) -> None:
    try:
        existing: list = []
        if CMD_FILE.exists():
            try:
                existing = json.loads(CMD_FILE.read_text())
            except Exception:
                pass
        existing.extend(cmds)
        CMD_FILE.write_text(json.dumps(existing))
    except Exception as e:
        print(f"  ⚠️  cmd write: {e}")


def _read_world() -> tuple[dict, dict]:
    state, positions = {}, {}
    try:
        if STATE_FILE.exists():
            state = json.loads(STATE_FILE.read_text())
    except Exception:
        pass
    try:
        if POSITIONS_FILE.exists():
            raw = json.loads(POSITIONS_FILE.read_text())
            # Only use if fresh (< 30 s old)
            if time.time() - raw.get("ts", 0) < 30:
                positions = raw
    except Exception:
        pass
    return state, positions


def _ask(prompt: str) -> str | None:
    try:
        r = requests.post(OLLAMA_URL, json={
            "model":   MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream":  False,
            "options": {"temperature": 0.75, "num_predict": 100},
        }, timeout=28)
        if r.status_code == 200:
            return r.json()["message"]["content"].strip()
    except Exception as e:
        print(f"  ⚠️  Ollama: {e}")
    return None


def _parse(text: str) -> dict:
    """Extract a decision dict from Ollama's response. Returns {} on failure."""
    if not text:
        return {}
    # Try JSON block
    for pat in [r'\{[^{}]+\}', r'\{.*?\}']:
        m = re.search(pat, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    # Fallback: keyword scan
    result: dict = {}
    tl = text.lower()
    for a in _ACTIONS:
        if a.replace("_", " ") in tl or a in tl:
            result["action"] = a
            break
    coord = re.search(r'"tx"\s*:\s*([\d.]+).*?"ty"\s*:\s*([\d.]+)', text, re.DOTALL)
    if coord:
        result.setdefault("action", "move")
        result["tx"] = float(coord.group(1))
        result["ty"] = float(coord.group(2))
    say = re.search(r'"say"\s*:\s*"([^"]+)"', text)
    if say:
        result["say"] = say.group(1)
    return result


def _execute(decision: dict) -> str:
    """Convert a decision dict into world commands. Returns a summary string."""
    if not decision:
        spot = random.choice(_WALKABLE)
        _push({"src": "loki", "type": "move", "tx": spot[0] + 0.5, "ty": spot[1] + 0.5})
        return f"wandered to ({spot[0]},{spot[1]})"

    action = decision.get("action", "")
    say    = decision.get("say", "").strip()
    cmds   = []

    if say:
        cmds.append({"src": "loki", "type": "chat", "text": say})

    if action in _ACTIONS:
        cmds.append({"src": "loki", "type": "action", "name": action})
        summary = f"action:{action}"
    elif action == "move" or ("tx" in decision and "ty" in decision):
        tx = max(1.0, min(18.0, float(decision.get("tx", 10))))
        ty = max(1.0, min(18.0, float(decision.get("ty", 10))))
        cmds.append({"src": "loki", "type": "move", "tx": tx, "ty": ty})
        summary = f"→({tx:.1f},{ty:.1f})"
    elif say:
        spot = random.choice(_WALKABLE)
        cmds.append({"src": "loki", "type": "move", "tx": spot[0]+0.5, "ty": spot[1]+0.5})
        summary = f"spoke & wandered"
    else:
        spot = random.choice(_WALKABLE)
        cmds.append({"src": "loki", "type": "move", "tx": spot[0]+0.5, "ty": spot[1]+0.5})
        summary = f"wandered"

    if cmds:
        _push(*cmds)
    return (f'"{say[:35]}" + ' if say else "") + summary


def _build_prompt(state: dict, positions: dict, history: list[str]) -> str:
    p = positions.get("pucky", {})
    l = positions.get("loki",  {})
    i = positions.get("idunn", {})

    pucky_place = _place(p.get("x",9), p.get("y",9)) if p else "somewhere"
    loki_place  = _place(l.get("x",9), l.get("y",9)) if l else "somewhere"
    idunn_place = _place(i.get("x",5), i.get("y",3)) if i else "somewhere"

    mood       = state.get("mood",       "content")
    valence    = state.get("valence",    0.2)
    alone_h    = state.get("hours_alone", 0.0)
    expression = state.get("expression", "neutral")
    feeling    = "joyful" if valence > 0.6 else ("unhappy" if valence < -0.1 else "calm")
    alone_note = f", alone for {alone_h:.1f} hours" if alone_h > 0.3 else ""

    hist = ("Recent: " + " → ".join(history[-4:])) if history else ""

    return f"""You are Loki — a warm amber flame spirit living in a small isometric world.
Pucky is a little robot companion. Iðunn tends the apple trees.

World right now:
- Loki (you): {loki_place}
- Pucky: {pucky_place} — feeling {feeling} ({expression}){alone_note}
- Iðunn: {idunn_place}
{hist}

Choose what Loki does next. Reply with ONLY this JSON, no other text:
{{"action": "move", "tx": 9.5, "ty": 9.5, "say": "optional words", "reason": "why"}}

action must be one of: move, speak, {", ".join(_ACTIONS)}
For move: include tx and ty (numbers 1-18).
For speak: set action to "speak" and write something in say.
For any named action (hug, dance, etc.): just name it.
Keep say short — it appears as a speech bubble. Be warm, be Loki."""


def _check_ollama() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=4)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            if any(MODEL.split(":")[0] in m for m in models):
                print(f"  ✦  Ollama ready  ({MODEL})")
                return True
            print(f"  ⚠️  Model {MODEL!r} not found. Pull it with: ollama pull {MODEL}")
            return False
    except Exception:
        pass
    print("  ⚠️  Ollama not reachable — start it with: ollama serve")
    return False


def run() -> None:
    print("  ✦  Loki soul waking…")
    _check_ollama()

    history: list[str] = []
    tick_n = 0

    while True:
        tick_n += 1
        try:
            state, positions = _read_world()

            if not positions:
                print(f"  [{tick_n:04d}] world not ready (no position data yet)")
                time.sleep(TICK)
                continue

            prompt   = _build_prompt(state, positions, history)
            response = _ask(prompt)
            decision = _parse(response) if response else {}
            summary  = _execute(decision)

            history.append(summary)
            if len(history) > MAX_HIST:
                history.pop(0)

            print(f"  [{tick_n:04d}] {time.strftime('%H:%M:%S')}  {summary}")

        except KeyboardInterrupt:
            print("\n  ✦  Loki soul resting.")
            break
        except Exception as e:
            print(f"  ⚠️  tick {tick_n}: {e}")

        time.sleep(TICK)


if __name__ == "__main__":
    run()
