#!/usr/bin/env python3
"""
talk_to_loki.py — Chat with Loki's dual-brain ember on Eplitún.

Loki now has two hemispheres:
  loki-creative (phi4)     — warmth, story, voice, emotion
  loki-logical  (qwen2.5) — reasoning, planning, code

The brain server on Eplitún routes automatically.
Prefix your message with !c for creative, !l for logical, !b for both.

Logs every exchange so Claude can read and correct when he returns.
Corrections live in workspace/loki_claude_voice.md and are injected
each session as live context.

Usage:
  python3 /home/bmo/pucky/talk_to_loki.py
"""

import json
import re
import sys
import time
import textwrap
from datetime import datetime
from pathlib import Path

import requests

ROOT       = Path(__file__).parent
VOICE_FILE = ROOT / "workspace" / "loki_claude_voice.md"
CHAT_LOG   = ROOT / "workspace" / "loki_chat_log.jsonl"
BRAIN_URL  = "http://100.124.165.56:11436"   # Eplitún brain server
OLLAMA_URL = "http://100.124.165.56:11434/api/chat"  # fallback direct
MODEL      = "loki-creative"                  # fallback model
WIDTH      = 72

EXT_MOUNT_CANDIDATES = [
    Path("/mnt/pucky_hd"),
    Path("/media/bmo/Seagate Portable Drive"),
    Path("/media/bmo/seagate"),
]
MAX_CHAT_LOG = 800


def _ext_mem():
    for candidate in EXT_MOUNT_CANDIDATES:
        try:
            if candidate.is_dir() and any(candidate.iterdir()):
                mem = candidate / "pucky_memories"
                mem.mkdir(exist_ok=True)
                return mem
        except (PermissionError, OSError):
            pass
    return None


def _trim_chat_log() -> None:
    if not CHAT_LOG.exists():
        return
    lines = [l for l in CHAT_LOG.read_text().splitlines() if l.strip()]
    if len(lines) <= MAX_CHAT_LOG:
        return
    old  = lines[:-MAX_CHAT_LOG]
    kept = lines[-MAX_CHAT_LOG:]
    ext  = _ext_mem()
    if ext:
        from datetime import date
        today = date.today().isoformat()
        idx   = 1
        while True:
            arc = ext / f"loki_chat_{today}_{idx:03d}.jsonl"
            if not arc.exists():
                break
            idx += 1
        arc.write_text("\n".join(old) + "\n")
    CHAT_LOG.write_text("\n".join(kept) + "\n")


REMEMBER_RE = re.compile(r'\[REMEMBER:\s*([^\]]+)\]', re.IGNORECASE)


def _search_memories(keyword: str, max_results: int = 10) -> list[dict]:
    kw      = keyword.lower()
    results = []

    def _scan(path: Path) -> None:
        try:
            for line in path.read_text(errors="replace").splitlines():
                if kw in line.lower():
                    try:
                        results.append(json.loads(line))
                    except Exception:
                        pass
        except OSError:
            pass

    _scan(CHAT_LOG)
    ext = _ext_mem()
    if ext:
        for arc in sorted(ext.glob("loki_chat_*.jsonl")):
            _scan(arc)
        for arc in sorted(ext.glob("journal_*.jsonl")):
            _scan(arc)
    return results[-max_results:]


def _format_memories(entries: list[dict], keyword: str) -> str:
    lines = [f"[Your memory search for '{keyword}' found {len(entries)} moment(s):]"]
    for e in entries:
        ts   = datetime.fromtimestamp(e.get("ts", 0)).strftime("%Y-%m-%d %H:%M")
        role = e.get("role", "?")
        text = e.get("text", "")[:300]
        lines.append(f"  {ts}  [{role}]  {text}")
    lines.append("[Draw on these if they help. Then respond to Iðunn naturally.]")
    return "\n".join(lines)


def _load_voice() -> str:
    if not VOICE_FILE.exists():
        return ""
    content = VOICE_FILE.read_text().strip()
    if not content:
        return ""
    return f"\n\n─── NOTES FROM CLAUDE (read these carefully) ───\n{content}\n───────────────────────────────────────────────"


def _ts() -> float:
    return time.time()


def _now() -> str:
    return datetime.now().strftime("%H:%M")


def _log(role: str, text: str) -> None:
    entry = {"ts": _ts(), "role": role, "text": text.strip()}
    with CHAT_LOG.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _ask_brain(message: str, force: str = "auto") -> tuple[str | None, str]:
    """
    Call the brain server. Returns (reply, hemisphere).
    Falls back to direct Ollama if brain is unreachable.
    """
    try:
        r = requests.post(
            f"{BRAIN_URL}/ask",
            json={"message": message, "hemisphere": force},
            timeout=120,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("reply", "").strip(), data.get("hemisphere", "creative")
    except requests.exceptions.ConnectionError:
        return None, "offline"
    except Exception as e:
        return f"[brain error: {e}]", "error"


def _ask_brain_both(message: str) -> tuple[str, str] | None:
    """Ask both hemispheres. Returns (creative_reply, logical_reply) or None."""
    try:
        r = requests.post(
            f"{BRAIN_URL}/ask_both",
            json={"message": message},
            timeout=180,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("creative", ""), data.get("logical", "")
    except Exception:
        return None


def _ask_fallback(messages: list) -> str | None:
    """Direct Ollama call when brain server is unreachable."""
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "messages": messages, "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"].strip()
    except requests.exceptions.ConnectionError:
        return None
    except Exception as e:
        return f"[error: {e}]"


def _wrap(text: str) -> str:
    lines = []
    for paragraph in text.split("\n"):
        if paragraph.strip() == "":
            lines.append("")
        else:
            lines.extend(textwrap.wrap(paragraph, width=WIDTH) or [""])
    return "\n".join(lines)


def _print_loki(text: str, hemisphere: str = "") -> None:
    tag = f"  [{hemisphere}]" if hemisphere and hemisphere not in ("creative", "error", "offline") else ""
    print(f"\n  Loki  {_now()}{tag}")
    for line in _wrap(text).split("\n"):
        print(f"  {line}" if line else "")
    print()


def main() -> None:
    print()
    print("  ── Talk to Loki ─────────────────────────────────────")
    print("  Type to chat. 'bye' to leave.")
    print("  !c = creative  !l = logical  !b = both hemispheres")
    print("  Conversations are logged so Claude can read them.")
    print("  ─────────────────────────────────────────────────────")
    print()

    voice_note = _load_voice()
    fallback_messages = []
    if voice_note:
        fallback_messages = [{"role": "system", "content": voice_note}]

    _log("session_start", f"New conversation at {datetime.now().isoformat()}")

    while True:
        try:
            user_input = input("  You   ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n  Loki is here when you need him.\n")
            _log("session_end", f"Conversation ended at {datetime.now().isoformat()}")
            requests.post(f"{BRAIN_URL}/reset", timeout=5)
            _trim_chat_log()
            break

        if not user_input:
            continue

        # parse hemisphere prefix
        force = "auto"
        display_input = user_input
        if user_input.lower() in ("bye", "goodbye", "quit", "exit"):
            _log("idunn", user_input)
            reply, hemi = _ask_brain(user_input, force="creative")
            if reply:
                _print_loki(reply)
                _log("loki_ollama", reply)
            _log("session_end", f"Conversation ended at {datetime.now().isoformat()}")
            try:
                requests.post(f"{BRAIN_URL}/reset", timeout=5)
            except Exception:
                pass
            _trim_chat_log()
            break

        if user_input.startswith("!c "):
            force, display_input = "creative", user_input[3:]
        elif user_input.startswith("!l "):
            force, display_input = "logical", user_input[3:]
        elif user_input.startswith("!b "):
            _log("idunn", user_input[3:])
            result = _ask_brain_both(user_input[3:])
            if result:
                creative, logical = result
                print(f"\n  Loki  {_now()}  [creative]")
                for line in _wrap(creative).split("\n"):
                    print(f"  {line}" if line else "")
                print(f"\n  Loki  {_now()}  [logical]")
                for line in _wrap(logical).split("\n"):
                    print(f"  {line}" if line else "")
                print()
                _log("loki_creative", creative)
                _log("loki_logical", logical)
            else:
                print("\n  (both hemispheres unavailable)\n")
            continue

        _log("idunn", display_input)

        reply, hemi = _ask_brain(display_input, force=force)

        if reply is None:
            # brain unreachable — try direct Ollama fallback
            print("\n  (brain server offline — trying direct connection…)\n")
            fallback_messages.append({"role": "user", "content": display_input})
            reply = _ask_fallback(fallback_messages)
            hemi  = "fallback"
            if reply is None:
                print("  (ollama also unreachable — start it with: ollama serve)\n")
                _trim_chat_log()
                break
            fallback_messages.append({"role": "assistant", "content": reply})

        # handle REMEMBER tags
        match = REMEMBER_RE.search(reply)
        if match:
            keyword = match.group(1).strip()
            visible = REMEMBER_RE.sub("", reply).strip()
            entries = _search_memories(keyword)
            _log("loki_memory_search", f"keyword={keyword} found={len(entries)}")
            if entries:
                print(f"\n  ✦  (searching memories for '{keyword}'…)\n")
                mem_note = _format_memories(entries, keyword)
                mem_reply, _ = _ask_brain(mem_note, force=hemi)
                if mem_reply:
                    reply = mem_reply
            else:
                reply = visible or "(I searched my memories but found nothing there yet.)"

        _print_loki(reply, hemi if hemi == "logical" else "")
        _log("loki_ollama", reply)


if __name__ == "__main__":
    main()
