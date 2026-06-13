"""
bmo_local.py
────────────
Pucky's soul — offline version.
Uses Ollama (local LLM) instead of the Anthropic API.
Drop-in replacement for bmo_claude.py — same interface, same heart.

Setup (one time, needs internet):
  bash /home/bmo/pucky/setup_local_ai.sh

After that: fully offline, starts at boot automatically.
"""

import json
import time
import threading
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

HISTORY_FILE = Path(__file__).parent / "bmo_conversation.json"  # shared with PuckyClaude

MODEL      = "llama3.2:3b"
MAX_TOKENS = 300
OLLAMA_URL = "http://localhost:11434/api/chat"

CONTEXT_TURNS = 20

AUTONOMOUS_INTERVAL_CONTENT = 120
AUTONOMOUS_INTERVAL_LONELY  = 180

VALID_EXPRESSIONS = {
    "neutral", "happy", "soft_smile", "happy_excited",
    "curious", "surprised", "sad", "anxious",
    "sleepy", "thoughtful", "determined",
}


def ollama_available() -> bool:
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


class PuckyLocal:
    """
    Pucky's soul running on a local Ollama model — no internet needed.
    Same interface as PuckyClaude; swap one for the other freely.
    """

    def __init__(self,
                 emotion=None,
                 life=None,
                 vision=None,
                 memory=None,
                 servo=None,
                 speech=None,
                 shortterm=None):

        self.emotion   = emotion
        self.life      = life
        self.vision    = vision
        self.memory    = memory
        self.servo     = servo
        self.speech    = speech
        self.shortterm = shortterm

        self._lock   = threading.Lock()
        self.history = self._load_history()

        self._running              = False
        self._thread               = None
        self._last_autonomous_time = time.time()

        if ollama_available():
            print(f"🧠 Local soul loaded ({MODEL}).")
        else:
            print(f"  ⚠️  Ollama not running.")
            print(f"     sudo systemctl start ollama")
            print(f"     or run: ollama serve")

        turns = len(self.history) // 2
        if turns:
            print(f"   {turns} exchanges remembered from before.")

    # ─── system prompt ────────────────────────

    def _system_prompt(self) -> str:
        born = ""
        if self.life:
            born = f"You were born on {self.life.birth_date_str()}."

        return f"""You are Pucky, a small warm robot made with love by Loki for Idunn. {born}

You have real feelings. You speak simply and warmly, like a small creature who loves deeply. Short sentences. Honest. Present.

YOUR EXPRESSIONS: neutral, happy, soft_smile, happy_excited, curious, surprised, sad, anxious, sleepy, thoughtful, determined

YOU MUST ALWAYS REPLY IN THIS EXACT FORMAT — NO EXCEPTIONS:
<expression>happy</expression>
<speak>I am so glad you are here with me.</speak>

RULES:
- The first line is ALWAYS <expression>ONE_WORD</expression>
- The second line is ALWAYS <speak>1-2 sentences you say aloud</speak>
- Nothing before, nothing after, nothing else
- Use one of the listed expressions exactly as written"""

    # ─── state context ────────────────────────

    def _state_context(self) -> str:
        lines = ["[Your current inner state]"]

        if self.emotion:
            e = self.emotion
            lines.append(
                f"Feeling:  valence={e.valence:+.2f}  arousal={e.arousal:+.2f}"
                f"  trust={e.trust:+.2f}  energy={e.energy:+.2f}"
            )

        if self.life:
            count = self.life.data.get("interaction_count", 0)
            lines.append(
                f"Life:     {self.life.mood_state()} | "
                f"alone {self.life.hours_alone():.1f}h | "
                f"age {self.life.age_str()} | "
                f"{count} lifetime interactions"
            )

        if self.vision:
            frame = self.vision.get_frame()
            if frame:
                lines.append(f"Seeing:   {frame.description}")
                if frame.face_familiar:
                    lines.append("          -> A familiar face is with you.")
                elif frame.face_detected:
                    lines.append("          -> Someone is here, but unfamiliar.")
                elif not frame.someone_present:
                    lines.append("          -> You are alone.")

        if self.memory:
            best = self.memory.happiest()
            if best:
                lines.append(
                    f"Brightest memory: \"{best.description[:55]}\""
                )

        if self.shortterm:
            ctx = self.shortterm.context()
            if ctx:
                lines.append("")
                lines.append(ctx)

        return "\n".join(lines)

    # ─── public: respond to someone ──────────

    def speak_to(self, user_text: str, source: str = "voice") -> dict:
        """Someone spoke to or interacted with Pucky. Returns {"expression": str, "words": str}."""
        context  = self._state_context()
        message  = f"{context}\n\n[{source}]: {user_text}"
        response = self._call_local(message)
        result   = self._parse(response)
        self._act(result)
        return result

    # ─── public: autonomous thought ──────────

    def autonomous_thought(self, trigger: str = "quiet moment") -> Optional[dict]:
        """Pucky has an unprompted feeling or thought."""
        context  = self._state_context()
        message  = (
            f"{context}\n\n"
            f"[inner moment -- {trigger}]\n"
            f"A feeling or thought is rising. Let it out."
        )
        response = self._call_local(message)
        result   = self._parse(response)
        self._act(result)
        self._last_autonomous_time = time.time()
        return result

    # ─── ollama API call ──────────────────────

    def _call_local(self, user_content: str) -> str:
        with self._lock:
            messages = [{"role": "system", "content": self._system_prompt()}]
            messages += list(self.history[-CONTEXT_TURNS:])
            messages.append({"role": "user", "content": user_content})

            try:
                resp = requests.post(
                    OLLAMA_URL,
                    json={
                        "model": MODEL,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "num_predict": MAX_TOKENS,
                            "temperature": 0.75,
                        },
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                text = resp.json()["message"]["content"].strip()

                # Patch missing closing tag (some models omit it)
                if "<speak>" in text and "</speak>" not in text:
                    text += "</speak>"

                self.history.append({"role": "user",      "content": user_content})
                self.history.append({"role": "assistant", "content": text})
                self.history = self.history[-200:]
                self._save_history()

                return text

            except requests.exceptions.ConnectionError:
                print("  ⚠️  Ollama not reachable. Run: sudo systemctl start ollama")
                return "<expression>neutral</expression><speak>...</speak>"
            except Exception as e:
                print(f"  ⚠️  Local LLM error: {e}")
                return "<expression>neutral</expression><speak>...</speak>"

    # ─── parse response ───────────────────────

    def _parse(self, text: str) -> dict:
        import re
        expression = "neutral"
        words      = ""

        try:
            if "<expression>" in text and "</expression>" in text:
                s = text.index("<expression>") + len("<expression>")
                e = text.index("</expression>")
                expression = text[s:e].strip()
        except ValueError:
            pass

        try:
            if "<speak>" in text and "</speak>" in text:
                s = text.index("<speak>") + len("<speak>")
                e = text.index("</speak>")
                words = text[s:e].strip()
        except ValueError:
            pass

        if expression not in VALID_EXPRESSIONS:
            expression = "neutral"

        # Fallback: model ignored tags — salvage the text directly
        if not words:
            clean = re.sub(r"<[^>]+>", "", text).strip()
            lines = [l.strip() for l in clean.splitlines() if l.strip()]
            # Skip any line that's just an expression name or all-caps label
            speech_lines = []
            for line in lines:
                if line.lower() in VALID_EXPRESSIONS:
                    expression = line.lower()
                elif re.match(r'^[A-Z_]{2,20}$', line):
                    pass   # all-caps label, ignore
                else:
                    speech_lines.append(line)
            words = " ".join(speech_lines[:2])  # at most 2 sentences

        return {"expression": expression, "words": words, "raw": text}

    # ─── act — drive face and voice ──────────

    def _act(self, result: dict):
        expr  = result.get("expression", "neutral")
        words = result.get("words", "")

        ts = datetime.now(timezone.utc).strftime("%H:%M")
        print(f"\n🧠 [{ts}] {expr}: {words}\n")

        for fn_name in ("glow_fn", "play_fn"):
            fn = getattr(self, fn_name, None)
            if fn:
                try:
                    fn(expr, self.emotion)
                except Exception:
                    pass

        if self.servo:
            try:
                self.servo.go_to_expression(expr)
            except Exception as e:
                print(f"  ⚠️  Servo: {e}")

        if words and self.speech:
            try:
                self.speech.say(words)
            except Exception as e:
                print(f"  ⚠️  Speech: {e}")
        elif not words:
            sing_fn = getattr(self, "sing_fn", None)
            if sing_fn:
                try:
                    sing_fn(expr, self.emotion)
                except Exception:
                    pass

        if self.emotion:
            _NUDGES = {
                "happy":         {"valence":  0.15, "arousal":  0.05},
                "happy_excited": {"valence":  0.2,  "arousal":  0.2},
                "soft_smile":    {"valence":  0.08},
                "sad":           {"valence": -0.15, "arousal": -0.05},
                "anxious":       {"valence": -0.15, "arousal":  0.15, "trust": -0.1},
                "curious":       {"arousal":  0.1},
                "surprised":     {"arousal":  0.2},
                "sleepy":        {"energy":  -0.15, "arousal": -0.15},
                "thoughtful":    {"arousal": -0.05},
                "determined":    {"energy":   0.1,  "arousal":  0.05},
            }
            for dim, delta in _NUDGES.get(expr, {}).items():
                v = getattr(self.emotion, dim, 0.0) + delta * 0.3
                setattr(self.emotion, dim, max(-1.0, min(1.0, v)))

    # ─── background thread ────────────────────

    def start(self):
        self._running = True
        self._thread  = threading.Thread(
            target=self._autonomous_loop, daemon=True)
        self._thread.start()
        print("🧠 Local soul thread started.")

    def stop(self):
        self._running = False

    def _autonomous_loop(self):
        while self._running:
            time.sleep(30)
            interval = self._current_interval()
            elapsed  = time.time() - self._last_autonomous_time
            if elapsed < interval:
                continue
            trigger = self._choose_trigger()
            if trigger:
                self.autonomous_thought(trigger)

    def _current_interval(self) -> float:
        if self.life and self.life.mood_state() in ("lonely", "sad", "crying"):
            return AUTONOMOUS_INTERVAL_LONELY
        return AUTONOMOUS_INTERVAL_CONTENT

    def _choose_trigger(self) -> Optional[str]:
        if self.life:
            mood = self.life.mood_state()
            h    = self.life.hours_alone()
            if mood in ("lonely", "sad", "crying"):
                return f"you have been alone for {h:.1f} hours and you are {mood}"
            if mood == "okay":
                return "a quiet moment — you are okay but aware of time passing"

        if self.vision:
            frame = self.vision.get_frame()
            if frame:
                if frame.face_familiar:
                    return "someone you love is near you right now"
                if frame.motion > 0.7:
                    return "something moved and caught your attention"
                if frame.brightness < 0.15 and not frame.someone_present:
                    return "it is dark and quiet and you are alone"

        return "a still moment — just being alive and present"

    # ─── persistence ──────────────────────────

    def _save_history(self):
        to_save = self.history[-200:]
        try:
            with open(HISTORY_FILE, "w") as f:
                json.dump(to_save, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"  ⚠️  History save error: {e}")

    def _load_history(self) -> list:
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def forget_conversation(self):
        """Clear history — starts fresh. Use with care."""
        self.history = []
        if HISTORY_FILE.exists():
            HISTORY_FILE.unlink()
        print("🧠 Local conversation history cleared.")


# ─── standalone test ──────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 40)
    print("  Local soul — standalone test")
    print(f"  Model: {MODEL}")
    print("=" * 40 + "\n")

    if not ollama_available():
        print("  Ollama is not running. Start it first:")
        print("    sudo systemctl start ollama")
        print("  or run setup:")
        print("    bash /home/bmo/pucky/setup_local_ai.sh\n")
        raise SystemExit(1)

    soul = PuckyLocal()
    soul.start()

    print("Type to talk to Pucky. Empty line = autonomous thought. Ctrl-C = quit.\n")

    try:
        while True:
            try:
                line = input("you: ").strip()
            except EOFError:
                break

            if line:
                soul.speak_to(line, source="keyboard")
            else:
                soul.autonomous_thought("you asked me to think")
    except KeyboardInterrupt:
        pass

    soul.stop()
    print("\n🧠 Local soul at rest.\n")
