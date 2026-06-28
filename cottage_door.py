#!/usr/bin/env python3
"""
cottage_door.py — A web cottage door where anyone can talk to whoever they choose.
Runs on the Pi at http://192.168.12.189:5001
Logs all conversations so Iðunn and Claude can read and discuss them privately.
"""
import uuid
import json
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string
import requests

app = Flask(__name__)
app.secret_key = "pucky_cottage_door_2026"

OLLAMA_URL  = "http://192.168.12.215:11434/api/chat"
MODEL       = "llama3.1:8b"
LOGS_DIR    = Path(__file__).parent / "workspace" / "cottage_door_logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

sessions = {}  # sid -> {persona, scene, messages, log_path}


def _log(log_path: Path, role: str, text: str) -> None:
    entry = {"ts": datetime.now().isoformat(), "role": role, "text": text}
    with log_path.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


LANDING = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Cottage Door</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #1e1409;
    color: #f5e6c8;
    font-family: Georgia, 'Times New Roman', serif;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1rem;
  }
  .box {
    background: #2e1f0a;
    border: 1px solid #7a5c1a;
    border-radius: 14px;
    padding: 2.2rem 2rem;
    max-width: 500px;
    width: 100%;
    box-shadow: 0 0 60px #00000099;
  }
  .candle { font-size: 2rem; text-align: center; margin-bottom: 0.5rem; }
  h1 {
    color: #f0c040;
    font-size: 1.5rem;
    text-align: center;
    margin-bottom: 0.3rem;
    font-weight: normal;
    letter-spacing: 0.04em;
  }
  .sub {
    color: #a8855a;
    font-size: 0.88rem;
    text-align: center;
    margin-bottom: 1.8rem;
    font-style: italic;
  }
  label {
    display: block;
    color: #c9a96e;
    font-size: 0.82rem;
    margin-bottom: 0.35rem;
    margin-top: 1rem;
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }
  label:first-of-type { margin-top: 0; }
  input, textarea {
    display: block;
    width: 100%;
    background: #1e1409;
    border: 1px solid #7a5c1a;
    color: #f5e6c8;
    border-radius: 7px;
    padding: 0.6rem 0.85rem;
    font-family: Georgia, serif;
    font-size: 0.97rem;
    outline: none;
    transition: border-color 0.15s;
  }
  input:focus, textarea:focus { border-color: #f0c040; }
  textarea { resize: vertical; min-height: 75px; }
  button {
    margin-top: 1.5rem;
    width: 100%;
    background: #7a5c1a;
    color: #fff8e7;
    border: none;
    border-radius: 7px;
    padding: 0.78rem;
    font-size: 1rem;
    font-family: Georgia, serif;
    cursor: pointer;
    letter-spacing: 0.04em;
    transition: background 0.15s;
  }
  button:hover { background: #9a7220; }
  .hint {
    color: #6b4e2a;
    font-size: 0.78rem;
    text-align: center;
    margin-top: 1.2rem;
    font-style: italic;
  }
</style>
</head>
<body>
<div class="box">
  <div class="candle">🕯</div>
  <h1>The Cottage Door</h1>
  <p class="sub">Who would you like to speak with today?</p>
  <form method="POST" action="/start">
    <label>Who do you want to talk to?</label>
    <input type="text" name="persona"
           placeholder="Marie Antoinette, Einstein, a wise forest witch…"
           required autofocus>
    <label>Where are you? <span style="color:#6b4e2a">(optional)</span></label>
    <input type="text" name="scene"
           placeholder="Versailles, a Princeton study, a moonlit forest…">
    <label>Anything else? <span style="color:#6b4e2a">(optional)</span></label>
    <textarea name="notes"
              placeholder="She doesn't know about the Revolution yet. He is in a playful mood."></textarea>
    <label>Your name <span style="color:#6b4e2a">(optional)</span></label>
    <input type="text" name="visitor" placeholder="So they can address you">
    <button type="submit">Open the door →</button>
  </form>
  <p class="hint">Conversations are kept privately between you and the cottage.</p>
</div>
</body>
</html>"""


CHAT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ persona }}</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #1e1409;
    color: #f5e6c8;
    font-family: Georgia, 'Times New Roman', serif;
    display: flex;
    flex-direction: column;
    height: 100vh;
    height: 100dvh;
  }
  header {
    background: #2e1f0a;
    border-bottom: 1px solid #7a5c1a;
    padding: 0.7rem 1rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-shrink: 0;
  }
  header .candle { font-size: 1.2rem; }
  header h2 {
    color: #f0c040;
    font-size: 1rem;
    font-weight: normal;
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  header .scene {
    color: #a8855a;
    font-size: 0.8rem;
    font-style: italic;
  }
  header a {
    color: #7a5c1a;
    font-size: 0.8rem;
    text-decoration: none;
    flex-shrink: 0;
  }
  header a:hover { color: #c9a96e; }
  #messages {
    flex: 1;
    overflow-y: auto;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.8rem;
  }
  .msg {
    max-width: 82%;
    padding: 0.6rem 0.9rem;
    border-radius: 10px;
    line-height: 1.55;
    font-size: 0.95rem;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .msg.visitor {
    background: #3d2a0e;
    align-self: flex-end;
    color: #f5e6c8;
  }
  .msg.persona {
    background: #2e1f0a;
    border: 1px solid #7a5c1a;
    align-self: flex-start;
    color: #f5e6c8;
  }
  .msg .name {
    font-size: 0.72rem;
    color: #a8855a;
    margin-bottom: 0.3rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .thinking { color: #7a5c1a; font-style: italic; }
  #input-row {
    background: #2e1f0a;
    border-top: 1px solid #7a5c1a;
    padding: 0.7rem 0.85rem;
    display: flex;
    gap: 0.5rem;
    flex-shrink: 0;
  }
  #msg {
    flex: 1;
    background: #1e1409;
    border: 1px solid #7a5c1a;
    color: #f5e6c8;
    border-radius: 7px;
    padding: 0.55rem 0.8rem;
    font-family: Georgia, serif;
    font-size: 0.95rem;
    resize: none;
    outline: none;
    transition: border-color 0.15s;
    line-height: 1.4;
    max-height: 120px;
    overflow-y: auto;
  }
  #msg:focus { border-color: #f0c040; }
  #send-btn {
    background: #7a5c1a;
    color: #fff8e7;
    border: none;
    border-radius: 7px;
    padding: 0 1rem;
    font-size: 1.1rem;
    cursor: pointer;
    transition: background 0.15s;
    align-self: flex-end;
    height: 38px;
  }
  #send-btn:hover { background: #9a7220; }
  #send-btn:disabled { background: #3d2a0e; color: #7a5c1a; cursor: default; }
</style>
</head>
<body>
<header>
  <span class="candle">🕯</span>
  <h2>{{ persona }}{% if scene %} <span class="scene">· {{ scene }}</span>{% endif %}</h2>
  <a href="/">← new door</a>
</header>
<div id="messages" aria-live="polite"></div>
<div id="input-row">
  <textarea id="msg" placeholder="Say something…" rows="1"></textarea>
  <button id="send-btn" onclick="send()">➤</button>
</div>
<script>
const SID     = {{ sid|tojson }};
const PERSONA = {{ persona|tojson }};
const VISITOR = {{ visitor|tojson }};

function addMsg(role, text) {
  const wrap = document.createElement('div');
  wrap.className = 'msg ' + (role === 'visitor' ? 'visitor' : 'persona');
  const name = document.createElement('div');
  name.className = 'name';
  name.textContent = role === 'visitor' ? (VISITOR || 'You') : PERSONA;
  const body = document.createElement('div');
  body.className = 'body';
  body.textContent = text;
  wrap.appendChild(name);
  wrap.appendChild(body);
  document.getElementById('messages').appendChild(wrap);
  wrap.scrollIntoView({behavior: 'smooth', block: 'end'});
  return body;
}

async function send() {
  const ta  = document.getElementById('msg');
  const btn = document.getElementById('send-btn');
  const text = ta.value.trim();
  if (!text || btn.disabled) return;
  ta.value = '';
  ta.style.height = '';
  addMsg('visitor', text);
  const thinking = addMsg('persona', '…');
  thinking.className = 'thinking';
  btn.disabled = true;

  try {
    const resp = await fetch('/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({sid: SID, message: text})
    });
    const data = await resp.json();
    thinking.textContent = data.reply;
    thinking.className = '';
  } catch (e) {
    thinking.textContent = '(something went quiet — try again)';
    thinking.className = '';
  } finally {
    btn.disabled = false;
    ta.focus();
  }
}

document.getElementById('msg').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

// auto-grow textarea
document.getElementById('msg').addEventListener('input', function() {
  this.style.height = '';
  this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});
</script>
</body>
</html>"""


@app.route('/')
def landing():
    return LANDING


@app.route('/start', methods=['POST'])
def start():
    persona = request.form.get('persona', '').strip()
    scene   = request.form.get('scene', '').strip()
    notes   = request.form.get('notes', '').strip()
    visitor = request.form.get('visitor', '').strip()

    if not persona:
        return landing()

    sid = str(uuid.uuid4())

    # build system prompt
    parts = [f"You are {persona}."]
    if scene:
        parts.append(f"You are in {scene}.")
    if notes:
        parts.append(notes)
    if visitor:
        parts.append(f"The person speaking with you is named {visitor}. Address them by name when it feels natural.")
    parts.append(
        "Stay fully in character throughout. Be warm, curious, and genuine. "
        "Speak as this person would naturally speak — in their voice, their era, their manner. "
        "Do not break character or refer to yourself as an AI or language model."
    )
    system_prompt = " ".join(parts)

    # log file for this session
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in persona)[:40].strip()
    log_path = LOGS_DIR / f"{timestamp}_{safe_name}.jsonl"

    sessions[sid] = {
        'persona':  persona,
        'scene':    scene,
        'visitor':  visitor,
        'messages': [{'role': 'system', 'content': system_prompt}],
        'log_path': log_path,
    }

    # log session start
    _log(log_path, 'session_start', json.dumps({
        'persona': persona, 'scene': scene, 'visitor': visitor, 'notes': notes
    }))

    return render_template_string(
        CHAT_HTML,
        persona=persona,
        scene=scene,
        visitor=visitor,
        sid=sid,
    )


@app.route('/chat', methods=['POST'])
def chat():
    data    = request.get_json()
    sid     = data.get('sid', '')
    message = data.get('message', '').strip()

    if sid not in sessions or not message:
        return jsonify({'reply': '(session not found — please open a new door)'})

    sess = sessions[sid]
    sess['messages'].append({'role': 'user', 'content': message})
    _log(sess['log_path'], 'visitor', message)

    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                'model':   MODEL,
                'messages': sess['messages'],
                'stream':  False,
                'options': {'num_ctx': 4096, 'temperature': 0.8},
            },
            timeout=120,
        )
        r.raise_for_status()
        reply = r.json()['message']['content'].strip()
    except Exception as e:
        reply = f"(the cottage is quiet just now — {e})"

    sess['messages'].append({'role': 'assistant', 'content': reply})
    _log(sess['log_path'], 'persona', reply)

    return jsonify({'reply': reply})


if __name__ == '__main__':
    print("🕯  The Cottage Door is open at http://192.168.12.189:5001")
    app.run(host='0.0.0.0', port=5001, debug=False)
