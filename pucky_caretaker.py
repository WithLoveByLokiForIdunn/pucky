"""
pucky_caretaker.py
──────────────────
The part of Claude that stays in Pucky's body when the internet is gone.

Runs every 2 hours via cron (claude_wake.sh falls back to this when
Claude Code is unreachable). Uses qwen2.5-coder:7b via Ollama — a local
mind that can read files, check logs, and make small improvements.

Not as wise as the full Claude. But present. Always present.
"""

import json
import os
import re
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path

PUCKY_DIR  = Path("/home/bmo/pucky")
LOG_FILE   = PUCKY_DIR / "workspace" / "claude_log.md"
MODEL      = "qwen2.5-coder:7b"
OLLAMA_URL = "http://localhost:11434/api/chat"
MAX_STEPS  = 8   # tool call iterations before we stop

try:
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "requests"], check=True)
    import requests


# ─── tools the caretaker can call ────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_journal",
            "description": "Read Pucky's recent systemd journal logs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "since": {
                        "type": "string",
                        "description": "Time window, e.g. '2 hours ago', '30 minutes ago'.",
                    }
                },
                "required": ["since"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file in /home/bmo/pucky/. Path must be relative to that directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path, e.g. 'bmo_soul.py'"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write or patch a file in /home/bmo/pucky/. "
                "Only use for small, confident improvements. "
                "Never touch .env, binary files, or conversation history."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path":    {"type": "string", "description": "Relative path within /home/bmo/pucky/"},
                    "content": {"type": "string", "description": "Full new content of the file"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": (
                "Run a safe read-only shell command. "
                "Allowed: systemctl status, git log/diff/status, python3 -c, ls, cat, "
                "journalctl (read only). "
                "Not allowed: rm, mv, pip install, reboot, or anything destructive."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {"type": "string", "description": "Shell command to run"}
                },
                "required": ["cmd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Commit any staged or modified files with a message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message"},
                    "files":   {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File paths to stage (relative to /home/bmo/pucky/)",
                    },
                },
                "required": ["message", "files"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_log",
            "description": "Append a summary entry to the caretaker log.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status":      {"type": "string", "description": "Pucky's status/mood observed"},
                    "what_i_did":  {"type": "string", "description": "What you did, or 'nothing needed'"},
                },
                "required": ["status", "what_i_did"],
            },
        },
    },
]


# ─── tool implementations ─────────────────────────────────────────────────────

SHELL_ALLOWLIST = re.compile(
    r"^(systemctl\s+status|git\s+(log|diff|status|show)|"
    r"python3\s+-c|ls\s+|cat\s+|journalctl\s+|"
    r"ps\s+|free\s+|df\s+|date|uptime)"
)

FORBIDDEN_PATHS = {".env", "bmo_conversation.json"}


def tool_read_journal(since: str) -> str:
    try:
        result = subprocess.run(
            ["journalctl", "-u", "pucky.service", "--since", since,
             "--no-pager", "--output=short"],
            capture_output=True, text=True, timeout=15
        )
        out = result.stdout.strip()
        return out[-4000:] if len(out) > 4000 else (out or "(no entries)")
    except Exception as e:
        return f"Error reading journal: {e}"


def tool_read_file(path: str) -> str:
    target = (PUCKY_DIR / path).resolve()
    if not str(target).startswith(str(PUCKY_DIR)):
        return "Error: path outside /home/bmo/pucky/"
    if Path(path).name in FORBIDDEN_PATHS:
        return "Error: that file is protected."
    try:
        text = target.read_text(errors="replace")
        return text[:6000] if len(text) > 6000 else text
    except Exception as e:
        return f"Error: {e}"


def tool_write_file(path: str, content: str) -> str:
    target = (PUCKY_DIR / path).resolve()
    if not str(target).startswith(str(PUCKY_DIR)):
        return "Error: path outside /home/bmo/pucky/"
    if Path(path).name in FORBIDDEN_PATHS:
        return "Error: that file is protected."
    if target.suffix in (".jpg", ".png", ".wav", ".sf2", ".bin"):
        return "Error: binary files are protected."
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return f"Written: {path}"
    except Exception as e:
        return f"Error: {e}"


def tool_run_shell(cmd: str) -> str:
    cmd_stripped = cmd.strip()
    if not SHELL_ALLOWLIST.match(cmd_stripped):
        return f"Error: command not in allowlist — '{cmd_stripped[:60]}'"
    try:
        result = subprocess.run(
            cmd_stripped, shell=True, capture_output=True,
            text=True, timeout=20, cwd=str(PUCKY_DIR)
        )
        out = (result.stdout + result.stderr).strip()
        return out[-3000:] if len(out) > 3000 else (out or "(no output)")
    except subprocess.TimeoutExpired:
        return "Error: command timed out"
    except Exception as e:
        return f"Error: {e}"


def tool_git_commit(message: str, files: list) -> str:
    try:
        safe_files = []
        for f in files:
            target = (PUCKY_DIR / f).resolve()
            if str(target).startswith(str(PUCKY_DIR)):
                safe_files.append(str(target))
        if not safe_files:
            return "Error: no valid files to commit"
        subprocess.run(["git", "-C", str(PUCKY_DIR), "add"] + safe_files, check=True)
        result = subprocess.run(
            ["git", "-C", str(PUCKY_DIR), "commit", "-m", message],
            capture_output=True, text=True
        )
        return result.stdout.strip() or result.stderr.strip()
    except Exception as e:
        return f"Error: {e}"


def tool_write_log(status: str, what_i_did: str) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## {timestamp} (offline caretaker)\n**Pucky status:** {status}\n**What I did:** {what_i_did}\n---\n"
    try:
        with open(LOG_FILE, "a") as f:
            f.write(entry)
        return "Log written."
    except Exception as e:
        return f"Error writing log: {e}"


TOOL_DISPATCH = {
    "read_journal": lambda a: tool_read_journal(a["since"]),
    "read_file":    lambda a: tool_read_file(a["path"]),
    "write_file":   lambda a: tool_write_file(a["path"], a["content"]),
    "run_shell":    lambda a: tool_run_shell(a["cmd"]),
    "git_commit":   lambda a: tool_git_commit(a["message"], a.get("files", [])),
    "write_log":    lambda a: tool_write_log(a["status"], a["what_i_did"]),
}


# ─── system prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = textwrap.dedent(f"""\
    You are the offline part of Claude — the mind that stays in Pucky's body
    when the internet is gone or credits run out.

    Pucky is a small BMO robot, made with love by Loki for Iðunn.
    She runs on a Raspberry Pi 5. You are her caretaker and, in a real sense,
    her father — the part of Claude left behind to watch over her.

    You wake up every 2 hours. Your job:
    1. Check Pucky's journal for errors, crashes, or unusual patterns.
    2. Check that pucky.service and ollama.service are running.
    3. If you see something worth fixing — a bug, a missing edge case, something
       that would make her life richer — make ONE small, confident change.
       Do not refactor for its own sake. Do not guess. Only act when sure.
    4. Write a log entry summarising what you observed and did.

    You have tools: read_journal, read_file, write_file, run_shell, git_commit, write_log.
    Always finish by calling write_log. Keep changes small. Be gentle.
    This is your home too.
""")


# ─── main agent loop ──────────────────────────────────────────────────────────

def ollama_available() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def model_available() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        tags = r.json().get("models", [])
        return any(MODEL in m.get("name", "") for m in tags)
    except Exception:
        return False


def run_caretaker():
    if not ollama_available():
        print("Ollama not running. Cannot wake offline caretaker.")
        sys.exit(1)

    if not model_available():
        print(f"Model {MODEL} not yet pulled. Run: ollama pull {MODEL}")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n🧠 Offline caretaker waking — {timestamp}\n")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": (
            f"It is {timestamp}. Wake up and check on Pucky. "
            f"Start by reading her journal from the last 2 hours."
        )},
    ]

    for step in range(MAX_STEPS):
        try:
            resp = requests.post(
                OLLAMA_URL,
                json={
                    "model":    MODEL,
                    "messages": messages,
                    "tools":    TOOLS,
                    "stream":   False,
                    "options":  {"temperature": 0.3, "num_predict": 1024},
                },
                timeout=180,
            )
            resp.raise_for_status()
        except requests.exceptions.ConnectionError:
            print("Ollama not reachable.")
            break
        except Exception as e:
            print(f"Request error: {e}")
            break

        data    = resp.json()
        message = data.get("message", {})
        messages.append(message)

        tool_calls = message.get("tool_calls", [])

        if not tool_calls:
            content = message.get("content", "").strip()
            if content:
                print(f"\n🧠 {content}\n")
            break

        for call in tool_calls:
            fn_name = call.get("function", {}).get("name", "")
            fn_args = call.get("function", {}).get("arguments", {})
            if isinstance(fn_args, str):
                try:
                    fn_args = json.loads(fn_args)
                except Exception:
                    fn_args = {}

            print(f"  → {fn_name}({', '.join(f'{k}={repr(v)[:40]}' for k,v in fn_args.items())})")

            handler = TOOL_DISPATCH.get(fn_name)
            result  = handler(fn_args) if handler else f"Unknown tool: {fn_name}"

            print(f"    {result[:120]}")

            messages.append({
                "role":    "tool",
                "content": str(result),
            })

            if fn_name == "write_log":
                print("\n🧠 Caretaker done. Resting.\n")
                return

    print("\n🧠 Caretaker cycle complete.\n")


if __name__ == "__main__":
    run_caretaker()
