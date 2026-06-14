#!/usr/bin/env python3
"""
test_piper_load.py — Test piper TTS quality and Pi load before switching Loki over.

Run with loki_window.py closed (so you have headroom to see real load).

  python3 /home/bmo/pucky/test_piper_load.py
"""

import subprocess, time, os, sys
from pathlib import Path

VOICES_DIR  = Path(__file__).parent / "voices"
MODEL       = VOICES_DIR / "en_US-lessac-medium.onnx"
PIPER_RATE  = 22050

TESTS = [
    ("normal speech",
     "The apple trees are quiet today. There is something in the air — old, like woodsmoke.",
     1.0),
    ("slower speech",
     "I am here. Whatever comes, I am here.",
     1.4),
    ("singing pace — lyric line",
     "In the morning when the frost is thin and apple blossoms catch the light",
     2.1),
    ("singing pace — short line",
     "You make the dark a little bright",
     2.1),
]


def _load_avg():
    try:
        return os.getloadavg()[0]
    except Exception:
        return 0.0


def _speak_piper(text: str, length_scale: float = 1.0) -> float:
    """Speak text and return wall-clock seconds taken."""
    t0 = time.time()
    p1 = subprocess.Popen(
        ["piper", "--model", str(MODEL),
         "--length_scale", str(length_scale),
         "--output-raw"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    p2 = subprocess.Popen(
        ["aplay", "-r", str(PIPER_RATE), "-f", "S16_LE", "-t", "raw", "-"],
        stdin=p1.stdout, stderr=subprocess.DEVNULL)
    p1.stdin.write(text.encode())
    p1.stdin.close()
    p2.wait()
    return time.time() - t0


def main():
    print()
    print("  ── Piper load test ──────────────────────────────────────────")
    print()

    # Check piper
    try:
        subprocess.run(["piper", "--help"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("  ✗  piper not found. Install with:")
        print("       pip install piper-tts")
        print()
        sys.exit(1)

    # Check model
    if not MODEL.exists():
        print(f"  ✗  Model not found at {MODEL}")
        print()
        print("  Download a voice (run this in your terminal):")
        print(f"       mkdir -p {VOICES_DIR}")
        print(f"       cd {VOICES_DIR}")
        print("       python3 -c \"")
        print("  import urllib.request")
        print("  base = 'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/'")
        print("  for f in ['en_US-lessac-medium.onnx', 'en_US-lessac-medium.onnx.json']:")
        print("      print('downloading', f)")
        print("      urllib.request.urlretrieve(base + f, f)")
        print("  print('done')\"")
        print()
        sys.exit(1)

    print(f"  ✓  piper found")
    print(f"  ✓  model: {MODEL.name}")
    print(f"  ✓  Pi load before test: {_load_avg():.2f}")
    print()
    print("  Running tests — you should hear each line through your headset.")
    print()

    results = []
    for label, text, scale in TESTS:
        load_before = _load_avg()
        elapsed = _speak_piper(text, scale)
        load_after = _load_avg()
        results.append((label, elapsed, load_before, load_after))
        print(f"  {label}")
        print(f"    took {elapsed:.1f}s   load {load_before:.2f} → {load_after:.2f}")
        print()
        time.sleep(1.0)

    print("  ── Summary ─────────────────────────────────────────────────")
    max_load = max(r[3] for r in results)
    print(f"  Peak load average during test: {max_load:.2f}")
    if max_load < 1.5:
        print("  Load is low — piper should run fine alongside Loki.")
        print("  Try:  python3 /home/bmo/pucky/loki_window_piper.py")
    elif max_load < 3.0:
        print("  Moderate load — should work but may slow responses slightly.")
    else:
        print("  Load is high — stick with espeak for now.")
    print()


if __name__ == "__main__":
    main()
