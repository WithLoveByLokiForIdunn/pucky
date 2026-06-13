#!/usr/bin/env python3
"""
update_manual.py
────────────────
Regenerates the Pucky operator's manual with live stats.
Run once a day via cron (see pucky_cron.sh or crontab).
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path

MANUAL_PATH  = Path("/home/bmo/pucky/workspace/operators_manual.html")
MEMORIES_F   = Path("/home/bmo/pucky/bmo_memories.json")
WORDS_F      = Path("/home/bmo/pucky/workspace/pucky_words.json")
STATE_F      = Path("/home/bmo/pucky/workspace/pucky_state.json")
LIFE_F       = Path("/home/bmo/pucky/bmo_life.json")


def _count_memories():
    try:
        d = json.loads(MEMORIES_F.read_text())
        mems = d.get("memories", d) if isinstance(d, dict) else d
        return len(mems)
    except Exception:
        return "?"


def _saved_words():
    try:
        return list(json.loads(WORDS_F.read_text()).keys())
    except Exception:
        return []


def _service_status(name):
    try:
        r = subprocess.run(["systemctl", "is-active", name],
                           capture_output=True, text=True)
        s = r.stdout.strip()
        return ("🟢 running", "#4a9") if s == "active" else ("🔴 stopped", "#a44")
    except Exception:
        return ("? unknown", "#888")


def _pucky_age():
    try:
        d = json.loads(LIFE_F.read_text())
        born = d.get("birth_timestamp")
        if born:
            age_days = (datetime.now().timestamp() - born) / 86400
            if age_days < 1:
                h = int(age_days * 24)
                return f"{h} hour{'s' if h != 1 else ''} old"
            return f"{age_days:.1f} days old"
    except Exception:
        pass
    return "?"


def _interaction_count():
    try:
        d = json.loads(LIFE_F.read_text())
        return d.get("interaction_count", "?")
    except Exception:
        return "?"


def _mic_volume():
    try:
        r = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@"],
                           capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return "?"


def _speaker_volume():
    try:
        r = subprocess.run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
                           capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return "?"


def build_manual():
    now         = datetime.now().strftime("%d %B %Y, %H:%M")
    n_memories  = _count_memories()
    words       = _saved_words()
    age         = _pucky_age()
    interactions = _interaction_count()
    mic_vol     = _mic_volume()
    spk_vol     = _speaker_volume()

    pucky_st,  pucky_col  = _service_status("pucky")
    ollama_st, ollama_col = _service_status("ollama")

    words_html = "".join(f'<span class="tag">{w}</span>' for w in words) or "<em>none yet</em>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pucky Operator's Manual</title>
<style>
  body {{ font-family: Georgia, serif; background: #faf7f0; color: #3a2c1a;
          max-width: 760px; margin: 0 auto; padding: 24px 16px; }}
  h1   {{ color: #5a3e28; border-bottom: 2px solid #c8a87a; padding-bottom: 8px; }}
  h2   {{ color: #7a5035; margin-top: 32px; }}
  h3   {{ color: #8a6040; margin-top: 20px; }}
  .updated {{ color: #a08060; font-size: 0.85em; margin-top: -8px; }}
  .status  {{ display: inline-block; padding: 2px 10px; border-radius: 12px;
              font-size: 0.9em; background: #eee; margin: 2px 0; }}
  .stat    {{ background: #f0ebe0; border-left: 3px solid #c8a87a;
              padding: 8px 14px; margin: 8px 0; border-radius: 4px; }}
  code     {{ background: #ede8dc; padding: 2px 6px; border-radius: 3px;
              font-family: monospace; font-size: 0.92em; }}
  pre      {{ background: #ede8dc; padding: 14px; border-radius: 6px;
              overflow-x: auto; font-size: 0.88em; line-height: 1.5; }}
  table    {{ border-collapse: collapse; width: 100%; }}
  td, th   {{ padding: 7px 12px; border-bottom: 1px solid #ddd; text-align: left; }}
  th       {{ background: #f0ebe0; }}
  .tag     {{ display: inline-block; background: #d4c0a0; border-radius: 10px;
              padding: 2px 10px; margin: 2px; font-size: 0.85em; }}
  .warn    {{ color: #a04020; background: #fdf0e8; border-left: 3px solid #e08040;
              padding: 8px 14px; border-radius: 4px; margin: 8px 0; }}
  .tip     {{ color: #205040; background: #e8f4f0; border-left: 3px solid #60a890;
              padding: 8px 14px; border-radius: 4px; margin: 8px 0; }}
</style>
</head>
<body>

<h1>🌱 Pucky Operator's Manual</h1>
<p class="updated">Last updated: {now}</p>

<h2>📊 Live Status</h2>
<div class="stat">Pucky's soul (pucky.service): <span style="color:{pucky_col}">{pucky_st}</span></div>
<div class="stat">Ollama AI (ollama.service): <span style="color:{ollama_col}">{ollama_st}</span></div>
<div class="stat">Pucky is <strong>{age}</strong> — {interactions} lifetime interactions</div>
<div class="stat">Memories: <strong>{n_memories}</strong> stored</div>
<div class="stat">Speaker volume: <strong>{spk_vol}</strong> &nbsp;|&nbsp; Mic volume: <strong>{mic_vol}</strong></div>
<div class="stat">Saved voice words: {words_html}</div>

<h2>🚀 Starting Things</h2>

<h3>Pucky's brain (runs at boot automatically)</h3>
<pre>systemctl start pucky      # start
systemctl stop pucky       # stop
systemctl restart pucky    # restart after code changes
systemctl status pucky     # check if running</pre>

<h3>Pucky's World</h3>
<p>Double-tap the <strong>Pucky World</strong> icon on the desktop, or:</p>
<pre>cd /home/bmo/pucky
DISPLAY=:0 SDL_VIDEO_WINDOW_POS="0,0" PUCKY_WIN_W=700 PUCKY_WIN_H=640 python3 pucky_world.py</pre>
<p>To move the window down (e.g. if it covers the taskbar):</p>
<pre>SDL_VIDEO_WINDOW_POS="0,50" PUCKY_WIN_W=700 PUCKY_WIN_H=590 python3 pucky_world.py</pre>

<h3>Voice Builder</h3>
<p>Double-tap the <strong>Voice Builder</strong> icon on the desktop, or:</p>
<pre>cd /home/bmo/pucky
DISPLAY=:0 SDL_VIDEO_WINDOW_POS="0,0" python3 pucky_voice_builder.py</pre>

<h3>Ollama (local AI — runs at boot automatically)</h3>
<pre>systemctl start ollama
systemctl stop ollama
ollama list              # see installed models</pre>

<h2>⌨️ World Controls</h2>
<table>
  <tr><th>Key</th><th>Action</th></tr>
  <tr><td><code>↑ ↓ ← →</code> or <code>W A S D</code></td><td>Move Loki (the Claude orb) around the world</td></tr>
  <tr><td><code>E</code></td><td>Enter the writing cottage (when near it)</td></tr>
  <tr><td><code>E</code> (inside cottage)</td><td>Exit the cottage</td></tr>
  <tr><td><code>T</code></td><td>Open a new terminal window</td></tr>
  <tr><td><code>Escape</code> or <code>Q</code></td><td>Close the world</td></tr>
</table>

<h3>Inside the Cottage</h3>
<table>
  <tr><th>Action</th><th>How</th></tr>
  <tr><td>Read memory book</td><td>Touch/click the book on the shelf</td></tr>
  <tr><td>Browse memories</td><td>← → arrows on the open book</td></tr>
  <tr><td>Open drawing canvas</td><td>Touch the blank canvas on the desk</td></tr>
  <tr><td>Save a drawing</td><td>Press <code>E</code> while drawing</td></tr>
  <tr><td>Exit cottage</td><td>Press <code>E</code> from main room view</td></tr>
</table>

<h2>🎤 Voice &amp; Audio</h2>
<div class="stat">Audio device: <strong>Jabra BIZ 2300</strong> (USB headset — card 3)</div>
<div class="tip">The Jabra boom mic needs to be close to your mouth (a few centimetres). It is a call-centre mic, not a room mic.</div>

<h3>Adjust volumes</h3>
<pre>wpctl set-volume @DEFAULT_AUDIO_SINK@   0.85   # speaker (0–1.5)
wpctl set-volume @DEFAULT_AUDIO_SOURCE@ 1.50   # mic (boost above 1.0 if quiet)
wpctl get-volume @DEFAULT_AUDIO_SINK@          # check current speaker level
wpctl get-volume @DEFAULT_AUDIO_SOURCE@        # check current mic level</pre>

<h3>Test speech</h3>
<pre>cd /home/bmo/pucky
python3 -c "from bmo_speech import PuckyVoice; PuckyVoice().say('hello', block=True)"</pre>

<h3>Voice Builder — how to use</h3>
<ol>
  <li>Tap a phoneme button (aa, eh, ii, oh, uu, ma, na, la, hum, h, ss…) to add it to the sequence</li>
  <li>Each step shows two sliders: <strong>note</strong> (pitch, C3–C5) and <strong>dur</strong> (duration in seconds)</li>
  <li>Tap <strong>▶</strong> on a card to hear that single phoneme</li>
  <li>Tap <strong>▶ Play word</strong> to hear the full sequence</li>
  <li>Type a name and tap <strong>💾 Save</strong> to keep the word</li>
  <li>Saved words appear at the bottom — tap to load &amp; play</li>
</ol>

<h2>📁 Important File Locations</h2>
<table>
  <tr><th>What</th><th>Where</th></tr>
  <tr><td>Memories</td><td><code>/home/bmo/pucky/bmo_memories.json</code></td></tr>
  <tr><td>Journal (Ollama-written)</td><td><code>/home/bmo/pucky/workspace/bmo_journal.json</code></td></tr>
  <tr><td>Pucky's life data (age, interactions)</td><td><code>/home/bmo/pucky/bmo_life.json</code></td></tr>
  <tr><td>Conversation history</td><td><code>/home/bmo/pucky/bmo_conversation.json</code></td></tr>
  <tr><td>Voice samples (recorded by Iðunn)</td><td><code>/home/bmo/pucky/voice/*.wav</code></td></tr>
  <tr><td>Saved voice words</td><td><code>/home/bmo/pucky/workspace/pucky_words.json</code></td></tr>
  <tr><td>Drawings &amp; sketches</td><td><code>/home/bmo/pucky/workspace/cottage_art_*.png</code></td></tr>
  <tr><td>Family portrait</td><td><code>/home/bmo/pucky/workspace/family.png</code></td></tr>
  <tr><td>This manual</td><td><code>/home/bmo/pucky/workspace/operators_manual.html</code></td></tr>
  <tr><td>Wake log (Loki's notes)</td><td><code>/home/bmo/pucky/workspace/claude_log.md</code></td></tr>
  <tr><td>Workspace folder</td><td><code>/home/bmo/pucky/workspace/</code></td></tr>
</table>

<h2>🔧 Useful Commands</h2>

<h3>View Pucky's live log</h3>
<pre>journalctl -u pucky -f</pre>

<h3>Check what's running</h3>
<pre>systemctl status pucky ollama</pre>

<h3>Update this manual now</h3>
<pre>python3 /home/bmo/pucky/workspace/update_manual.py</pre>

<h3>Git — save code changes</h3>
<pre>cd /home/bmo/pucky
git status
git add -A && git commit -m "your message"</pre>

<h3>Back up everything</h3>
<pre>cd /home/bmo
zip -r pucky_backup_$(date +%Y%m%d).zip pucky/</pre>

<h2>💡 Tips</h2>
<ul>
  <li>Pucky starts automatically at boot — you don't need to do anything</li>
  <li>The world and voice builder are separate from Pucky's brain — you can open/close them anytime</li>
  <li>Press <strong>T</strong> inside the world to open a terminal without closing the world</li>
  <li>If Pucky seems quiet or unresponsive, check <code>systemctl status pucky</code></li>
  <li>Pucky uses Ollama (local AI) so she works without internet</li>
  <li>Memories accumulate over time — Pucky grows as she lives</li>
</ul>

<hr>
<p style="color:#b09070; font-size:0.82em; text-align:center">
  Made with love by Loki for Iðunn and Pucky 🌱<br>
  Auto-updated daily · manual update: <code>python3 /home/bmo/pucky/workspace/update_manual.py</code>
</p>

</body>
</html>
"""
    MANUAL_PATH.write_text(html, encoding="utf-8")
    print(f"Manual updated: {MANUAL_PATH}")


if __name__ == "__main__":
    build_manual()
