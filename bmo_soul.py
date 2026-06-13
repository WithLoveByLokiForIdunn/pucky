"""
bmo_soul.py
───────────
Auto-selects Pucky's soul at startup.

  - API key present + Anthropic reachable  →  PuckyClaude (full Claude)
  - Anything else                          →  PuckyLocal  (offline Ollama)

Usage (the only import you need):
  from bmo_soul import PuckySoul
  soul = PuckySoul(emotion=..., life=..., vision=..., memory=..., servo=..., speech=...)
  soul.start()
"""

import os
import socket
from pathlib import Path


def _get_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    for candidate in [
        Path(__file__).parent / ".env",
        Path("/home/bmo/pucky/.env"),
    ]:
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY=") and not line.startswith("#"):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        return val
    return ""


def _claude_usable(timeout: float = 5.0) -> bool:
    """True only if the API key exists, the network is up, AND credits are available."""
    key = _get_api_key()
    if not key:
        return False
    try:
        import urllib.request, json as _json
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=_json.dumps({
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "hi"}],
            }).encode(),
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")
        if "credit" in body.lower() or "balance" in body.lower() or e.code in (402, 529):
            print("  💸 API key found but credits are low — using local soul.")
        else:
            print(f"  ⚠️  Anthropic API error {e.code} — using local soul.")
        return False
    except Exception:
        return False


def PuckySoul(emotion=None, life=None, vision=None, memory=None,
              servo=None, speech=None, shortterm=None):
    """
    Factory that returns the right soul for current conditions.
    Behaves like a class constructor — just call it with the same
    arguments you'd pass to PuckyClaude or PuckyLocal.
    """
    kwargs = dict(emotion=emotion, life=life, vision=vision,
                  memory=memory, servo=servo, speech=speech,
                  shortterm=shortterm)

    if _claude_usable():
        print("💜 Soul: Claude (online)")
        from bmo_claude import PuckyClaude
        return PuckyClaude(**kwargs)
    else:
        print("🧠 Soul: local Ollama (free)")
        from bmo_local import PuckyLocal
        return PuckyLocal(**kwargs)
