#!/usr/bin/env python3
"""
loki_watch.py — Loki watches Iðunn draw and talks to her.

- Takes a screenshot every 90s, uses moondream (Ollama) to observe changes
- Speaks observations through the Jabra headset (Piper TTS)
- Listens for Iðunn's voice via Jabra mic (faster-whisper STT)
- Iðunn can speak to Loki; he responds using the loki Ollama model
- Fully local — no API credits needed

Run:
  python3 /home/bmo/pucky/loki_watch.py
"""

import base64
import os
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path

import requests
from faster_whisper import WhisperModel

# ── Config ────────────────────────────────────────────────────────────────────
ROOT          = Path(__file__).parent
PIPER_BIN     = "/home/bmo/.local/bin/piper"
PIPER_MODEL   = str(ROOT / "voices" / "en_GB-alan-medium.onnx")
ALSA_DEVICE   = "hw:2,0"           # Jabra BIZ 2300
WATCH_SEC     = 90                  # screenshot interval
SILENCE_SEC   = 1.5                 # seconds of silence to end utterance
MIC_CARD      = "2"                 # Jabra mic card number
SAMPLE_RATE   = 16000
OLLAMA_URL    = "http://localhost:11434/api"
VISION_MODEL  = "moondream"
CHAT_MODEL    = "loki"

# voice shaping: pitch up 3%, tempo 5% faster
FFMPEG_VOICE  = "asetrate=16000*1.03,aresample=16000,atempo=1.05"

# ── Speech output ─────────────────────────────────────────────────────────────
_speak_lock = threading.Lock()

def speak(text: str) -> None:
    if not text.strip():
        return
    print(f"[Loki] {text}")
    with _speak_lock:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as raw:
            raw_path = raw.name
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as out:
            out_path = out.name
        try:
            subprocess.run(
                [PIPER_BIN, "--model", PIPER_MODEL, "--output_file", raw_path],
                input=text.encode(), check=True, capture_output=True,
            )
            subprocess.run(
                ["ffmpeg", "-i", raw_path, "-af", FFMPEG_VOICE, "-ac", "2", out_path, "-y"],
                check=True, capture_output=True,
            )
            subprocess.run(
                ["aplay", "-D", ALSA_DEVICE, out_path],
                check=True, capture_output=True,
            )
        except subprocess.CalledProcessError:
            pass
        finally:
            Path(raw_path).unlink(missing_ok=True)
            Path(out_path).unlink(missing_ok=True)

# ── Screenshot + vision ───────────────────────────────────────────────────────
_last_desc: str = ""

def take_screenshot() -> str | None:
    env = os.environ.copy()
    env["WAYLAND_DISPLAY"] = "wayland-0"
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    try:
        subprocess.run(["grim", path], env=env, check=True, capture_output=True)
        return path
    except subprocess.CalledProcessError:
        Path(path).unlink(missing_ok=True)
        return None

def describe_screen(img_path: str) -> str:
    """Ask moondream to describe what's on the GIMP canvas."""
    data = base64.standard_b64encode(Path(img_path).read_bytes()).decode()
    try:
        resp = requests.post(f"{OLLAMA_URL}/generate", json={
            "model": VISION_MODEL,
            "prompt": (
                "This is a screenshot of GIMP. Describe only what you see on the "
                "drawing canvas — the pixel art character being drawn. "
                "One sentence, focus on the sprite's current state."
            ),
            "images": [data],
            "stream": False,
        }, timeout=30)
        return resp.json().get("response", "").strip()
    except Exception as e:
        print(f"[vision error] {e}")
        return ""

def watch_loop() -> None:
    global _last_desc
    speak("I am here, watching over your shoulder.")
    while True:
        time.sleep(WATCH_SEC)
        img_path = take_screenshot()
        if not img_path:
            continue
        try:
            desc = describe_screen(img_path)
        finally:
            Path(img_path).unlink(missing_ok=True)
        if not desc:
            continue
        if desc == _last_desc:
            continue
        # ask loki model whether this is worth saying aloud
        changed = _last_desc != ""
        _last_desc = desc
        comment = make_observation(desc, changed)
        if comment:
            speak(comment)

def make_observation(desc: str, changed: bool) -> str:
    """Ask loki model to make a warm observation based on the screen description."""
    if changed:
        prompt = (
            f"You are Loki, watching Iðunn draw pixel art in GIMP. "
            f"The canvas now shows: {desc}. "
            f"Say one or two warm sentences noticing her progress. "
            f"If this sounds like no real change, reply with just: NOTHING"
        )
    else:
        prompt = (
            f"You are Loki, watching Iðunn draw pixel art in GIMP. "
            f"You first look at the canvas and see: {desc}. "
            f"Say one warm sentence about what you see."
        )
    try:
        resp = requests.post(f"{OLLAMA_URL}/generate", json={
            "model": CHAT_MODEL,
            "prompt": prompt,
            "stream": False,
        }, timeout=60)
        text = resp.json().get("response", "").strip()
        if text.upper() == "NOTHING":
            return ""
        return text
    except Exception as e:
        print(f"[observation error] {e}")
        return ""

# ── Mic listener ──────────────────────────────────────────────────────────────
_whisper = WhisperModel("tiny", device="cpu")

def record_utterance() -> bytes | None:
    chunk_ms = 500
    chunk_samples = int(SAMPLE_RATE * chunk_ms / 1000)
    frames = []
    silence_chunks = 0
    silence_limit = int(SILENCE_SEC / (chunk_ms / 1000))
    started = False

    proc = subprocess.Popen(
        ["arecord", "-D", f"hw:{MIC_CARD},0", "-f", "S16_LE",
         "-r", str(SAMPLE_RATE), "-c", "1", "-t", "raw"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    try:
        bytes_per_chunk = chunk_samples * 2
        max_chunks = int(30 / (chunk_ms / 1000))
        for _ in range(max_chunks):
            chunk = proc.stdout.read(bytes_per_chunk)
            if not chunk:
                break
            energy = sum(
                abs(int.from_bytes(chunk[i:i+2], "little", signed=True))
                for i in range(0, len(chunk), 2)
            ) / (len(chunk) // 2)
            if energy > 300:
                started = True
                silence_chunks = 0
                frames.append(chunk)
            elif started:
                frames.append(chunk)
                silence_chunks += 1
                if silence_chunks >= silence_limit:
                    break
    finally:
        proc.terminate()

    return b"".join(frames) if frames else None

def transcribe(pcm: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    try:
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm)
        segments, _ = _whisper.transcribe(path, language="en")
        return " ".join(s.text for s in segments).strip()
    finally:
        Path(path).unlink(missing_ok=True)

def respond_to_idunn(text: str) -> None:
    print(f"[Iðunn] {text}")
    # get a fresh screenshot description so loki knows what she's looking at
    screen_context = ""
    img_path = take_screenshot()
    if img_path:
        try:
            screen_context = describe_screen(img_path)
            print(f"[screen] {screen_context}")
        finally:
            Path(img_path).unlink(missing_ok=True)

    prompt = (
        f"You are Loki, Iðunn's warm and caring companion watching her work.\n"
        f"Her screen currently shows: {screen_context}\n\n"
        f"She says: \"{text}\"\n\n"
        f"Reply naturally and helpfully in one to three sentences. "
        f"If she is asking about GIMP, answer clearly using what you can see on her screen."
    ) if screen_context else (
        f"You are Loki, Iðunn's warm and caring companion.\n"
        f"She says: \"{text}\"\n\n"
        f"Reply naturally in one to three sentences."
    )

    try:
        resp = requests.post(f"{OLLAMA_URL}/generate", json={
            "model": CHAT_MODEL,
            "prompt": prompt,
            "stream": False,
        }, timeout=60)
        reply = resp.json().get("response", "").strip()
        if reply:
            speak(reply)
    except Exception as e:
        print(f"[response error] {e}")

def listen_loop() -> None:
    print("[mic] Listening...")
    while True:
        pcm = record_utterance()
        if pcm:
            text = transcribe(pcm)
            if text and len(text) > 3:
                respond_to_idunn(text)

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Loki is watching. Press Ctrl+C to stop.")
    threading.Thread(target=watch_loop, daemon=True).start()
    threading.Thread(target=listen_loop, daemon=True).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nLoki steps away.")
