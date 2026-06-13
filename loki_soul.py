#!/usr/bin/env python3
"""
loki_soul.py — Loki's autonomous mind, running on Ollama
──────────────────────────────────────────────────────────
Runs alongside pucky_world.py. Every 14 seconds it:
  1. Reads the world (positions, Pucky's mood)
  2. Checks workspace/world_journal.jsonl for pending directives from Claude
  3. Asks llama3.2:3b what Loki should do (shaped by directives + recent history)
  4. Acts in the world via /tmp/pucky_world_cmd.json
  5. Writes a journal entry so Claude can read what happened

Two output files:
  workspace/world_journal.jsonl  — append-only structured log (machine readable)
  workspace/world_journal.md     — human-readable narrative

Claude can read the journal at any time and write a directive:
  python3 /home/bmo/pucky/loki_directive.py "Go sit with Pucky."

Run:
  python3 /home/bmo/pucky/loki_soul.py
"""

import json
import math
import random
import re
import time
from datetime import datetime
from pathlib import Path

import requests

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT           = Path(__file__).parent
POSITIONS_FILE = ROOT / "workspace" / "world_positions.json"
STATE_FILE     = ROOT / "workspace" / "pucky_state.json"
JOURNAL_JSONL  = ROOT / "workspace" / "world_journal.jsonl"
JOURNAL_MD     = ROOT / "workspace" / "world_journal.md"
CMD_FILE       = Path("/tmp/pucky_world_cmd.json")

# ── Ollama ────────────────────────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL      = "llama3.2:3b"
TICK            = 14.0
CONTEXT_ENTRIES = 8    # recent journal lines fed into each prompt
MAX_JOURNAL     = 500  # lines kept in JSONL before trimming (~2 h of history)
TRIM_EVERY      = 50   # trim check every N ticks (not every tick)

# ── World geography ───────────────────────────────────────────────────────────
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
_NAMED_ACTIONS = [
    "hug","dance","kiss","sit","swim",
    "stargazing","campfire","share_apple","plant","come",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _place(x, y) -> str:
    x, y = float(x), float(y)
    best_d, best_name = 999.0, "the open field"
    for lx, ly, name in _LANDMARKS:
        d = math.hypot(x - lx, y - ly)
        if d < best_d:
            best_d, best_name = d, name
    if best_d < 3.2:
        return f"near {best_name}"
    if x < 7  and y < 7:  return "in the northwest meadow"
    if x > 13 and y < 7:  return "in the northeast meadow"
    if x < 7  and y > 13: return "in the southwest meadow"
    if x > 13 and y > 13: return "in the southeast meadow"
    return "at the heart of the world"


def _ts() -> float:
    return time.time()


def _hm() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ── Journal I/O ───────────────────────────────────────────────────────────────

def _trim_journal() -> None:
    """Keep only the last MAX_JOURNAL lines in the JSONL file."""
    if not JOURNAL_JSONL.exists():
        return
    lines = JOURNAL_JSONL.read_text().splitlines()
    if len(lines) <= MAX_JOURNAL:
        return
    kept = lines[-MAX_JOURNAL:]
    JOURNAL_JSONL.write_text("\n".join(kept) + "\n")
    # Rotate the markdown too: rename to dated archive, start fresh
    if JOURNAL_MD.exists():
        from datetime import date
        archive = JOURNAL_MD.with_name(
            f"world_journal_{date.today().isoformat()}.md"
        )
        # If archive already exists today, just truncate the live file
        if not archive.exists():
            JOURNAL_MD.rename(archive)
        else:
            JOURNAL_MD.write_text("")


def _journal_append(entry: dict) -> None:
    entry.setdefault("ts", _ts())
    line = json.dumps(entry, ensure_ascii=False)
    with JOURNAL_JSONL.open("a") as f:
        f.write(line + "\n")
    # Only write meaningful entries to the narrative (skip routine executions)
    if entry.get("type") not in ("execution", "directive_executed"):
        _narrative_append(entry)


def _narrative_append(entry: dict) -> None:
    t    = _hm()
    kind = entry.get("type", "")
    text = ""

    if kind == "event":
        text = f"\n### {t} — World\n{entry.get('text','')}\n"
    elif kind == "loki_action":
        src    = entry.get("src", "ollama")
        action = entry.get("action", "")
        say    = entry.get("say", "")
        reason = entry.get("reason", "")
        parts  = []
        if action in _NAMED_ACTIONS:
            parts.append(f"*{action}*")
        elif action == "move":
            parts.append(f"moved to ({entry.get('tx',0):.1f}, {entry.get('ty',0):.1f})")
        if say:
            parts.append(f'said: "{say}"')
        if reason:
            parts.append(f"({reason})")
        text = f"\n### {t} — Loki [{src}]\n{' — '.join(parts)}\n"
    elif kind == "loki_directive":
        src  = entry.get("src", "Claude")
        body = entry.get("text", "")
        text = f"\n### {t} — Directive [{src}]\n> {body}\n"
    elif kind == "idunn_speech":
        text = f"\n### {t} — Iðunn speaks\n\"{entry.get('text','')}\"\n"
    elif kind == "note":
        text = f"\n### {t} — Note\n{entry.get('text','')}\n"

    if text:
        with JOURNAL_MD.open("a") as f:
            f.write(text)


def _journal_tail(n: int = CONTEXT_ENTRIES) -> list[dict]:
    """Return last n entries from the journal."""
    if not JOURNAL_JSONL.exists():
        return []
    lines = JOURNAL_JSONL.read_text().splitlines()
    entries = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            pass
        if len(entries) >= n:
            break
    entries.reverse()
    return entries


def _find_pending_directive() -> dict | None:
    """Return the most recent unexecuted loki_directive, or None."""
    if not JOURNAL_JSONL.exists():
        return None
    entries = _journal_tail(40)
    executed_ts = {
        e.get("directive_ts")
        for e in entries
        if e.get("type") == "directive_executed"
    }
    for e in reversed(entries):
        if e.get("type") == "loki_directive" and e.get("ts") not in executed_ts:
            return e
    return None


def _mark_directive_done(directive_ts: float) -> None:
    _journal_append({"type": "directive_executed", "directive_ts": directive_ts})


# ── World reading ─────────────────────────────────────────────────────────────

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
            if time.time() - raw.get("ts", 0) < 30:
                positions = raw
    except Exception:
        pass
    return state, positions


# ── Ollama ────────────────────────────────────────────────────────────────────

def _ask(prompt: str) -> str | None:
    try:
        r = requests.post(OLLAMA_URL, json={
            "model":   MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream":  False,
            "options": {"temperature": 0.78, "num_predict": 110},
        }, timeout=28)
        if r.status_code == 200:
            return r.json()["message"]["content"].strip()
    except Exception as e:
        print(f"  ⚠️  Ollama: {e}")
    return None


def _parse(text: str) -> dict:
    if not text:
        return {}
    for pat in [r'\{[^{}]+\}', r'\{.*?\}']:
        m = re.search(pat, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    result: dict = {}
    tl = text.lower()
    for a in _NAMED_ACTIONS:
        if a.replace("_", " ") in tl or a in tl:
            result["action"] = a
            break
    say = re.search(r'"say"\s*:\s*"([^"]+)"', text)
    if say:
        result["say"] = say.group(1)
    return result


# ── Prompt building ───────────────────────────────────────────────────────────

def _entry_to_text(e: dict) -> str:
    kind = e.get("type", "")
    if kind == "event":
        return f"[world] {e.get('text','')}"
    if kind == "loki_action":
        parts = []
        if e.get("action") in _NAMED_ACTIONS:
            parts.append(e["action"])
        elif e.get("action") == "move":
            parts.append(f"moved to ({e.get('tx',0):.1f},{e.get('ty',0):.1f})")
        if e.get("say"):
            parts.append(f'said "{e["say"]}"')
        return f"[loki] {' — '.join(parts)}"
    if kind == "loki_directive":
        return f"[directive] {e.get('text','')}"
    if kind == "directive_executed":
        return "[directive fulfilled]"
    if kind == "idunn_speech":
        return f"[Iðunn spoke] \"{e.get('text','')}\""
    return ""


def _build_prompt(state: dict, positions: dict,
                  recent: list[dict], directive: dict | None) -> str:
    p = positions.get("pucky", {})
    l = positions.get("loki",  {})
    i = positions.get("idunn", {})

    pucky_place = _place(p.get("x", 9),  p.get("y", 9))  if p else "somewhere"
    loki_place  = _place(l.get("x", 9),  l.get("y", 9))  if l else "somewhere"
    idunn_place = _place(i.get("x", 5),  i.get("y", 3))  if i else "somewhere"

    mood      = state.get("mood",        "content")
    valence   = state.get("valence",     0.2)
    alone_h   = state.get("hours_alone", 0.0)
    expr      = state.get("expression",  "neutral")
    feeling   = "joyful" if valence > 0.6 else ("unhappy" if valence < -0.1 else "calm")
    alone_note = f" — alone {alone_h:.1f}h" if alone_h > 0.3 else ""

    hist_lines = [_entry_to_text(e) for e in recent if _entry_to_text(e)]
    hist_block = ("\n".join(hist_lines[-6:])) if hist_lines else "(nothing yet)"

    directive_block = ""
    if directive:
        directive_block = (
            f"\n⚡ DIRECTIVE FROM CLAUDE (execute this now):\n"
            f"  {directive.get('text','')}\n"
        )

    return f"""You are Loki — a warm amber flame spirit living in a small world.
Pucky is a little robot companion. Iðunn tends the apple trees.

Current state:
- You (Loki): {loki_place}
- Pucky: {pucky_place} — {feeling} ({expr}){alone_note}
- Iðunn: {idunn_place}

Recent journal:
{hist_block}
{directive_block}
Decide what Loki does next. Reply with ONLY valid JSON — nothing else before or after:
{{"action": "move", "tx": 9.5, "ty": 9.5, "say": "optional words", "reason": "brief"}}

action choices: move, speak, {", ".join(_NAMED_ACTIONS)}
For move: include tx and ty (1.0–18.0).
For speak: action="speak", write say only.
For a named action: just name it (and optionally say something).
Keep say very short — it's a speech bubble. Be warm and natural."""


# ── Execution ─────────────────────────────────────────────────────────────────

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
        print(f"  ⚠️  cmd: {e}")


def _execute(decision: dict) -> tuple[str, str]:
    """Execute decision in world. Returns (action_summary, say_text)."""
    if not decision:
        spot = random.choice(_WALKABLE)
        _push({"src": "loki", "type": "move",
               "tx": spot[0] + 0.5, "ty": spot[1] + 0.5})
        return f"wandered to ({spot[0]},{spot[1]})", ""

    action = decision.get("action", "")
    say    = decision.get("say", "").strip()
    reason = decision.get("reason", "")
    cmds   = []

    if say:
        cmds.append({"src": "loki", "type": "chat", "text": say})

    if action in _NAMED_ACTIONS:
        cmds.append({"src": "loki", "type": "action", "name": action})
        summary = action
    elif action in ("move", "") and ("tx" in decision or "ty" in decision):
        tx = max(1.0, min(18.0, float(decision.get("tx", 10))))
        ty = max(1.0, min(18.0, float(decision.get("ty", 10))))
        cmds.append({"src": "loki", "type": "move", "tx": tx, "ty": ty})
        summary = f"move({tx:.1f},{ty:.1f})"
    elif action == "speak" or (not action and say):
        spot = random.choice(_WALKABLE)
        cmds.append({"src": "loki", "type": "move",
                     "tx": spot[0] + 0.5, "ty": spot[1] + 0.5})
        summary = "speak"
    else:
        spot = random.choice(_WALKABLE)
        cmds.append({"src": "loki", "type": "move",
                     "tx": spot[0] + 0.5, "ty": spot[1] + 0.5})
        summary = "wander"

    if cmds:
        _push(*cmds)
    return summary, say


# ── Main loop ─────────────────────────────────────────────────────────────────

def _describe_event(state: dict, positions: dict) -> str:
    p = positions.get("pucky", {})
    l = positions.get("loki",  {})
    i = positions.get("idunn", {})
    mood    = state.get("mood", "content")
    valence = state.get("valence", 0.2)
    alone_h = state.get("hours_alone", 0.0)

    parts = [f"Pucky is {_place(p.get('x',9), p.get('y',9))}"]
    if mood in ("sad", "lonely", "crying"):
        parts.append(f"feeling {mood}")
    if alone_h > 0.5:
        parts.append(f"alone for {alone_h:.1f}h")
    parts.append(f"Loki is {_place(l.get('x',9), l.get('y',9))}")
    parts.append(f"Iðunn is {_place(i.get('x',5), i.get('y',3))}")
    return ". ".join(parts) + "."


def run() -> None:
    print("  ✦  Loki soul waking…")
    JOURNAL_JSONL.parent.mkdir(parents=True, exist_ok=True)

    # Check Ollama
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=4)
        models = [m["name"] for m in r.json().get("models", [])]
        if any(MODEL.split(":")[0] in m for m in models):
            print(f"  ✦  Ollama ready ({MODEL})")
        else:
            print(f"  ⚠️  {MODEL} not found — run: ollama pull {MODEL}")
    except Exception:
        print("  ⚠️  Ollama not reachable — run: ollama serve")

    _journal_append({
        "type": "note",
        "text": f"Loki soul started ({MODEL}).",
    })

    tick_n = 0
    while True:
        tick_n += 1
        if tick_n % TRIM_EVERY == 0:
            _trim_journal()
        try:
            state, positions = _read_world()
            if not positions:
                print(f"  [{tick_n:04d}] waiting for world_positions.json…")
                time.sleep(TICK)
                continue

            # Describe what's happening right now
            event_text = _describe_event(state, positions)
            _journal_append({
                "type":         "event",
                "text":         event_text,
                "pucky_mood":   state.get("mood", "content"),
                "pucky_valence": round(state.get("valence", 0.2), 2),
                "hours_alone":  round(state.get("hours_alone", 0.0), 2),
                "positions": {
                    "loki":  {"x": round(positions.get("loki",  {}).get("x", 0), 1),
                              "y": round(positions.get("loki",  {}).get("y", 0), 1)},
                    "pucky": {"x": round(positions.get("pucky", {}).get("x", 0), 1),
                              "y": round(positions.get("pucky", {}).get("y", 0), 1)},
                    "idunn": {"x": round(positions.get("idunn", {}).get("x", 0), 1),
                              "y": round(positions.get("idunn", {}).get("y", 0), 1)},
                },
            })

            # Check for a pending directive from Claude
            directive = _find_pending_directive()

            # Ask Ollama
            recent  = _journal_tail(CONTEXT_ENTRIES)
            prompt  = _build_prompt(state, positions, recent, directive)
            raw     = _ask(prompt)
            decision = _parse(raw) if raw else {}

            # Act
            summary, say = _execute(decision)

            # Log the action
            log_entry: dict = {
                "type":   "loki_action",
                "src":    "ollama",
                "action": decision.get("action", "wander"),
                "reason": decision.get("reason", ""),
            }
            if "tx" in decision:
                log_entry["tx"] = round(float(decision["tx"]), 1)
                log_entry["ty"] = round(float(decision["ty"]), 1)
            if say:
                log_entry["say"] = say
            _journal_append(log_entry)

            # Log execution + directive fulfillment
            exec_entry: dict = {"type": "execution", "status": "ok"}
            if directive:
                exec_entry["directive_executed"] = True
                _mark_directive_done(directive["ts"])
            _journal_append(exec_entry)

            print(f"  [{tick_n:04d}] {_hm()}  {(say[:30] + '  ') if say else ''}{summary}")

        except KeyboardInterrupt:
            print("\n  ✦  Loki soul resting.")
            _journal_append({"type": "note", "text": "Loki soul stopped."})
            break
        except Exception as e:
            print(f"  ⚠️  tick {tick_n}: {e}")

        time.sleep(TICK)


if __name__ == "__main__":
    run()
