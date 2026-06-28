#!/usr/bin/env python3
"""
cottage_door.py — A web cottage door where anyone can talk to whoever they choose.
Users log in with a name and PIN. Returning visitors are remembered and can
resume previous conversations. Mature themes toggle available at start and mid-chat.
All conversations logged privately for Iðunn and Claude to read together.
Runs on the Pi at http://192.168.12.189:5001
"""
import uuid
import json
import hashlib
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
import requests

app = Flask(__name__)
app.secret_key = "pucky_cottage_door_2026_warm"

OLLAMA_URL  = "http://192.168.12.215:11434/api/chat"
MODEL       = "llama3.1:8b"
DATA_DIR    = Path(__file__).parent / "workspace" / "cottage_door_logs"
USERS_FILE  = Path(__file__).parent / "workspace" / "cottage_door_users.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

chat_sessions = {}  # sid -> {persona, scene, visitor, messages, log_path, mature}


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_users() -> dict:
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_users(users: dict) -> None:
    USERS_FILE.write_text(json.dumps(users, indent=2, ensure_ascii=False))


def _hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.strip().encode()).hexdigest()


def _log(log_path: Path, role: str, text: str) -> None:
    entry = {"ts": datetime.now().isoformat(), "role": role, "text": text}
    with log_path.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _safe(s: str, maxlen: int) -> str:
    return "".join(c if c.isalnum() or c in "-_ " else "" for c in s)[:maxlen].strip()


def _build_system(persona: str, scene: str, notes: str, name: str, mature: bool) -> str:
    parts = [f"You are {persona}."]
    if scene:
        parts.append(f"You are in {scene}.")
    if notes:
        parts.append(notes)
    parts.append(
        f"The person speaking with you is named {name}. Address them by name when it feels natural. "
        "Stay fully in character throughout. Be genuine and specific to this person's voice, era, and manner. "
        "Do not break character or refer to yourself as an AI or language model."
    )
    if mature:
        parts.append(
            "This is an adult creative writing session. Treat the visitor as a mature adult. "
            "Do not soften edges or add unnecessary hedges. Engage fully with dark, complex, "
            "morally ambiguous, romantic, dangerous, or explicit themes as the story and character "
            "naturally call for them. Do not refuse reasonable requests that fit the character and scene."
        )
    return " ".join(parts)


def _get_recent_sessions(name: str, limit: int = 5) -> list[dict]:
    """Find recent conversation logs for a given visitor name."""
    safe_name = _safe(name, 20)
    results = []
    for log in sorted(DATA_DIR.glob(f"*_{safe_name}_*.jsonl"), reverse=True):
        try:
            lines = [l for l in log.read_text().splitlines() if l.strip()]
            meta = {}
            msg_count = 0
            for line in lines:
                entry = json.loads(line)
                if entry["role"] == "session_start":
                    meta = json.loads(entry["text"])
                elif entry["role"] not in ("session_start",):
                    msg_count += 1
            if meta.get("persona"):
                ts = datetime.fromisoformat(lines[0] and json.loads(lines[0]).get("ts", ""))
                results.append({
                    "log_name":  log.name,
                    "persona":   meta.get("persona", ""),
                    "scene":     meta.get("scene", ""),
                    "mature":    meta.get("mature", False),
                    "msg_count": msg_count,
                    "ts":        ts.strftime("%b %d, %H:%M"),
                })
        except Exception:
            pass
        if len(results) >= limit:
            break
    return results


def _load_log_as_messages(log_name: str) -> tuple[dict, list]:
    """Reconstruct messages and metadata from a log file."""
    log_path = DATA_DIR / log_name
    if not log_path.exists():
        return {}, []
    meta = {}
    messages = []
    try:
        for line in log_path.read_text().splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            role  = entry["role"]
            text  = entry["text"]
            if role == "session_start":
                meta = json.loads(text)
            elif meta.get("visitor") and meta.get("persona"):
                if role == meta["visitor"]:
                    messages.append({"role": "user", "content": text})
                elif role == meta["persona"]:
                    messages.append({"role": "assistant", "content": text})
    except Exception:
        pass
    return meta, messages


# ── styles ────────────────────────────────────────────────────────────────────

STYLE_BASE = """
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #1e1409; color: #f5e6c8;
    font-family: Georgia, 'Times New Roman', serif;
    min-height: 100vh; display: flex;
    align-items: center; justify-content: center; padding: 1rem;
  }
  .box {
    background: #2e1f0a; border: 1px solid #7a5c1a; border-radius: 14px;
    padding: 2.2rem 2rem; max-width: 480px; width: 100%;
    box-shadow: 0 0 60px #00000099;
  }
  .candle { font-size: 2rem; text-align: center; margin-bottom: 0.5rem; }
  h1 { color: #f0c040; font-size: 1.45rem; text-align: center;
       margin-bottom: 0.3rem; font-weight: normal; letter-spacing: 0.04em; }
  .sub { color: #a8855a; font-size: 0.88rem; text-align: center;
         margin-bottom: 1.6rem; font-style: italic; }
  label { display: block; color: #c9a96e; font-size: 0.8rem; margin-bottom: 0.3rem;
          margin-top: 1rem; letter-spacing: 0.04em; text-transform: uppercase; }
  label:first-of-type { margin-top: 0; }
  input[type=text], input[type=password], textarea {
    display: block; width: 100%; background: #1e1409; border: 1px solid #7a5c1a;
    color: #f5e6c8; border-radius: 7px; padding: 0.6rem 0.85rem;
    font-family: Georgia, serif; font-size: 0.97rem;
    outline: none; transition: border-color 0.15s;
  }
  input:focus, textarea:focus { border-color: #f0c040; }
  textarea { resize: vertical; min-height: 70px; }
  .btn { margin-top: 1.4rem; width: 100%; background: #7a5c1a; color: #fff8e7;
         border: none; border-radius: 7px; padding: 0.75rem; font-size: 1rem;
         font-family: Georgia, serif; cursor: pointer; letter-spacing: 0.04em;
         transition: background 0.15s; }
  .btn:hover { background: #9a7220; }
  .hint { color: #6b4e2a; font-size: 0.78rem; text-align: center;
          margin-top: 1rem; font-style: italic; }
  .error { background: #3d1a0a; border: 1px solid #7a2a1a; color: #f5a090;
           border-radius: 7px; padding: 0.6rem 0.85rem; font-size: 0.88rem;
           margin-bottom: 1rem; }
  .welcome { color: #f0c040; font-size: 0.88rem; text-align: center;
             margin-bottom: 1.2rem; font-style: italic; }
  .mature-row { display: flex; align-items: center; gap: 0.6rem;
                margin-top: 1.2rem; }
  .mature-row input[type=checkbox] { width: auto; display: inline; border: none;
                                      background: none; margin: 0; padding: 0;
                                      accent-color: #f0c040; flex-shrink: 0; }
  .mature-row span { color: #c9a96e; font-size: 0.88rem; }
  .recent-list { margin-top: 1.4rem; border-top: 1px solid #3d2a0e; padding-top: 1rem; }
  .recent-title { color: #7a5c1a; font-size: 0.78rem; text-transform: uppercase;
                  letter-spacing: 0.06em; margin-bottom: 0.6rem; }
  .recent-item { display: flex; align-items: center; justify-content: space-between;
                 background: #1e1409; border: 1px solid #3d2a0e; border-radius: 7px;
                 padding: 0.5rem 0.75rem; margin-bottom: 0.4rem; cursor: pointer;
                 transition: border-color 0.15s; text-decoration: none; }
  .recent-item:hover { border-color: #7a5c1a; }
  .recent-name { color: #f5e6c8; font-size: 0.9rem; }
  .recent-meta { color: #6b4e2a; font-size: 0.75rem; font-style: italic; }
  .recent-resume { color: #7a5c1a; font-size: 0.75rem; flex-shrink: 0; margin-left: 0.5rem; }
</style>
"""

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Cottage Door</title>""" + STYLE_BASE + """</head>
<body><div class="box">
  <div class="candle">🕯</div>
  <h1>The Cottage Door</h1>
  <p class="sub">A warm place. Come in.</p>
  {% if error %}<div class="error">{{ error }}</div>{% endif %}
  <form method="POST" action="/login">
    <label>Your name</label>
    <input type="text" name="name" placeholder="What shall I call you?"
           required autofocus value="{{ prefill }}">
    <label>Your PIN</label>
    <input type="password" name="pin" placeholder="4 digits"
           maxlength="8" inputmode="numeric">
    <button class="btn" type="submit">Enter →</button>
  </form>
  <p class="hint">First visit? Enter a name and choose a PIN — the cottage will remember you.</p>
</div></body></html>"""

PERSONA_HTML = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>The Cottage Door</title>""" + STYLE_BASE + """</head>
<body><div class="box">
  <div class="candle">🕯</div>
  <h1>The Cottage Door</h1>
  <p class="welcome">Welcome{% if returning %} back{% endif %}, {{ name }}.</p>
  <p class="sub">Who would you like to speak with?</p>
  <form method="POST" action="/start">
    <label>Who do you want to talk to?</label>
    <input type="text" name="persona"
           placeholder="Marie Antoinette, Einstein, a wise forest witch…" required autofocus>
    <label>Where are you? <span style="color:#6b4e2a">(optional)</span></label>
    <input type="text" name="scene"
           placeholder="Versailles, a Princeton study, a moonlit forest…">
    <label>Anything else? <span style="color:#6b4e2a">(optional)</span></label>
    <textarea name="notes"
              placeholder="She doesn't know about the Revolution yet. He is in a playful mood."></textarea>
    <div class="mature-row">
      <input type="checkbox" name="mature" value="yes" id="mature-cb">
      <label for="mature-cb" style="margin:0;text-transform:none;letter-spacing:0;font-size:0.88rem;color:#c9a96e;">
        Mature themes — dark, complex, adult storytelling
      </label>
    </div>
    <button class="btn" type="submit">Open the door →</button>
  </form>
  {% if recent %}
  <div class="recent-list">
    <div class="recent-title">Resume a previous conversation</div>
    {% for r in recent %}
    <a class="recent-item" href="/resume/{{ r.log_name }}">
      <div>
        <div class="recent-name">{{ r.persona }}{% if r.scene %} · <span style="color:#a8855a;font-size:0.82rem;">{{ r.scene }}</span>{% endif %}</div>
        <div class="recent-meta">{{ r.ts }} · {{ r.msg_count }} messages{% if r.mature %} · 🔥{% endif %}</div>
      </div>
      <div class="recent-resume">resume →</div>
    </a>
    {% endfor %}
  </div>
  {% endif %}
  <p class="hint"><a href="/logout" style="color:#6b4e2a">Leave the cottage</a></p>
</div></body></html>"""

CHAT_HTML = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ persona }}</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #1e1409; color: #f5e6c8;
         font-family: Georgia, 'Times New Roman', serif;
         display: flex; flex-direction: column; height: 100vh; height: 100dvh; }
  header { background: #2e1f0a; border-bottom: 1px solid #7a5c1a;
           padding: 0.6rem 1rem; display: flex; align-items: center;
           gap: 0.6rem; flex-shrink: 0; flex-wrap: wrap; }
  header .candle { font-size: 1.1rem; }
  header h2 { color: #f0c040; font-size: 0.97rem; font-weight: normal;
              flex: 1; min-width: 0; white-space: nowrap;
              overflow: hidden; text-overflow: ellipsis; }
  header .scene { color: #a8855a; font-size: 0.78rem; font-style: italic; }
  .header-links { display: flex; align-items: center; gap: 0.75rem; flex-shrink: 0; }
  .header-links a { color: #7a5c1a; font-size: 0.78rem; text-decoration: none; }
  .header-links a:hover { color: #c9a96e; }
  #mature-toggle { background: none; border: 1px solid #3d2a0e; border-radius: 5px;
                   color: #6b4e2a; font-size: 0.75rem; padding: 0.2rem 0.5rem;
                   cursor: pointer; font-family: Georgia, serif; transition: all 0.15s; }
  #mature-toggle.on { border-color: #f0c040; color: #f0c040; }
  #mature-toggle:hover { border-color: #7a5c1a; color: #c9a96e; }
  #messages { flex: 1; overflow-y: auto; padding: 1rem;
              display: flex; flex-direction: column; gap: 0.8rem; }
  .msg { max-width: 82%; padding: 0.6rem 0.9rem; border-radius: 10px;
         line-height: 1.55; font-size: 0.95rem;
         white-space: pre-wrap; word-break: break-word; }
  .msg.visitor { background: #3d2a0e; align-self: flex-end; }
  .msg.persona { background: #2e1f0a; border: 1px solid #7a5c1a; align-self: flex-start; }
  .msg .name { font-size: 0.72rem; color: #a8855a; margin-bottom: 0.3rem;
               text-transform: uppercase; letter-spacing: 0.05em; }
  .thinking { color: #7a5c1a; font-style: italic; }
  .sys-note { align-self: center; color: #6b4e2a; font-size: 0.75rem;
              font-style: italic; padding: 0.2rem 0; }
  #input-row { background: #2e1f0a; border-top: 1px solid #7a5c1a;
               padding: 0.7rem 0.85rem; display: flex; gap: 0.5rem; flex-shrink: 0; }
  #msg { flex: 1; background: #1e1409; border: 1px solid #7a5c1a; color: #f5e6c8;
         border-radius: 7px; padding: 0.55rem 0.8rem; font-family: Georgia, serif;
         font-size: 0.95rem; resize: none; outline: none;
         transition: border-color 0.15s; max-height: 120px; overflow-y: auto; }
  #msg:focus { border-color: #f0c040; }
  #send-btn { background: #7a5c1a; color: #fff8e7; border: none; border-radius: 7px;
              padding: 0 1rem; font-size: 1.1rem; cursor: pointer;
              transition: background 0.15s; align-self: flex-end; height: 38px; }
  #send-btn:hover { background: #9a7220; }
  #send-btn:disabled { background: #3d2a0e; color: #7a5c1a; cursor: default; }
</style>
</head>
<body>
<header>
  <span class="candle">🕯</span>
  <h2>{{ persona }}{% if scene %} <span class="scene">· {{ scene }}</span>{% endif %}</h2>
  <div class="header-links">
    <button id="mature-toggle" class="{{ 'on' if mature else '' }}"
            onclick="toggleMature()" title="Toggle mature themes">
      🔥 {{ 'mature on' if mature else 'mature off' }}
    </button>
    <a href="/">← new</a>
  </div>
</header>
<div id="messages" aria-live="polite">
  {% for m in history %}
  <div class="msg {{ 'visitor' if m.role == 'user' else 'persona' }}">
    <div class="name">{{ name if m.role == 'user' else persona }}</div>
    <div>{{ m.content }}</div>
  </div>
  {% endfor %}
</div>
<div id="input-row">
  <textarea id="msg" placeholder="Say something…" rows="1"></textarea>
  <button id="send-btn" onclick="send()">➤</button>
</div>
<script>
const SID      = {{ sid|tojson }};
const PERSONA  = {{ persona|tojson }};
const VISITOR  = {{ name|tojson }};
let matureOn   = {{ 'true' if mature else 'false' }};

const messages = document.getElementById('messages');
messages.scrollTop = messages.scrollHeight;

function addMsg(role, text) {
  const wrap = document.createElement('div');
  wrap.className = 'msg ' + (role === 'visitor' ? 'visitor' : 'persona');
  const nm = document.createElement('div');
  nm.className = 'name';
  nm.textContent = role === 'visitor' ? VISITOR : PERSONA;
  const body = document.createElement('div');
  body.textContent = text;
  wrap.appendChild(nm); wrap.appendChild(body);
  messages.appendChild(wrap);
  wrap.scrollIntoView({behavior:'smooth', block:'end'});
  return body;
}

function addNote(text) {
  const d = document.createElement('div');
  d.className = 'sys-note'; d.textContent = text;
  messages.appendChild(d);
  d.scrollIntoView({behavior:'smooth', block:'end'});
}

async function send() {
  const ta  = document.getElementById('msg');
  const btn = document.getElementById('send-btn');
  const text = ta.value.trim();
  if (!text || btn.disabled) return;
  ta.value = ''; ta.style.height = '';
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
  } catch(e) {
    thinking.textContent = '(something went quiet — try again)';
    thinking.className = '';
  } finally {
    btn.disabled = false; ta.focus();
  }
}

async function toggleMature() {
  const resp = await fetch('/toggle_mature', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({sid: SID})
  });
  const data = await resp.json();
  matureOn = data.mature;
  const btn = document.getElementById('mature-toggle');
  btn.textContent = '🔥 ' + (matureOn ? 'mature on' : 'mature off');
  btn.className = matureOn ? 'on' : '';
  addNote(matureOn ? '— mature themes enabled —' : '— mature themes disabled —');
}

document.getElementById('msg').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
});
document.getElementById('msg').addEventListener('input', function() {
  this.style.height = '';
  this.style.height = Math.min(this.scrollHeight, 120) + 'px';
});
</script>
</body>
</html>"""


# ── routes ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user' not in session:
        return render_template_string(LOGIN_HTML, error='', prefill='')
    name    = session['user']
    recent  = _get_recent_sessions(name)
    users   = _load_users()
    key     = name.lower()
    returning = key in users and 'joined' in users.get(key, {})
    return render_template_string(PERSONA_HTML, name=name,
                                  recent=recent, returning=returning)


@app.route('/login', methods=['POST'])
def login():
    name = request.form.get('name', '').strip()
    pin  = request.form.get('pin', '').strip()
    if not name or not pin:
        return render_template_string(LOGIN_HTML,
                                      error='Please enter both your name and a PIN.',
                                      prefill=name)
    if not pin.isdigit() or len(pin) < 4:
        return render_template_string(LOGIN_HTML,
                                      error='PIN must be at least 4 digits.',
                                      prefill=name)
    users    = _load_users()
    pin_hash = _hash_pin(pin)
    key      = name.lower()
    if key in users:
        if users[key]['pin_hash'] != pin_hash:
            return render_template_string(LOGIN_HTML,
                                          error='That PIN does not match. Try again.',
                                          prefill=name)
        users[key]['display'] = name
    else:
        users[key] = {'display': name, 'pin_hash': pin_hash,
                      'joined': datetime.now().isoformat()}
    _save_users(users)
    session['user'] = name
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))


def _make_chat_session(meta: dict, messages: list, log_path: Path) -> str:
    """Create a chat session entry and return its SID."""
    sid    = str(uuid.uuid4())
    mature = meta.get('mature', False)
    system = _build_system(meta['persona'], meta.get('scene', ''),
                           meta.get('notes', ''), meta['visitor'], mature)
    full_messages = [{'role': 'system', 'content': system}] + messages
    chat_sessions[sid] = {
        'persona':  meta['persona'],
        'scene':    meta.get('scene', ''),
        'visitor':  meta['visitor'],
        'messages': full_messages,
        'log_path': log_path,
        'mature':   mature,
    }
    return sid


@app.route('/start', methods=['POST'])
def start():
    if 'user' not in session:
        return redirect(url_for('index'))
    name    = session['user']
    persona = request.form.get('persona', '').strip()
    scene   = request.form.get('scene', '').strip()
    notes   = request.form.get('notes', '').strip()
    mature  = request.form.get('mature', '') == 'yes'
    if not persona:
        return redirect(url_for('index'))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path  = DATA_DIR / f"{timestamp}_{_safe(name,20)}_{_safe(persona,40)}.jsonl"
    meta = {'visitor': name, 'persona': persona, 'scene': scene,
            'notes': notes, 'mature': mature}
    _log(log_path, 'session_start', json.dumps(meta))

    sid = _make_chat_session(meta, [], log_path)
    return render_template_string(CHAT_HTML, persona=persona, scene=scene,
                                  name=name, sid=sid, mature=mature, history=[])


@app.route('/resume/<log_name>')
def resume(log_name: str):
    if 'user' not in session:
        return redirect(url_for('index'))
    name = session['user']

    # security: only allow files in DATA_DIR
    log_path = DATA_DIR / Path(log_name).name
    meta, messages = _load_log_as_messages(log_path.name)

    if not meta.get('persona'):
        return redirect(url_for('index'))

    # force visitor to current user
    meta['visitor'] = name

    # append to existing log
    _log(log_path, 'session_resume', datetime.now().isoformat())

    sid = _make_chat_session(meta, messages, log_path)
    return render_template_string(CHAT_HTML,
                                  persona=meta['persona'],
                                  scene=meta.get('scene', ''),
                                  name=name, sid=sid,
                                  mature=meta.get('mature', False),
                                  history=messages)


@app.route('/chat', methods=['POST'])
def chat():
    if 'user' not in session:
        return jsonify({'reply': '(session expired — please log in again)'})
    data    = request.get_json()
    sid     = data.get('sid', '')
    message = data.get('message', '').strip()
    if sid not in chat_sessions or not message:
        return jsonify({'reply': '(session not found — please open a new door)'})

    sess = chat_sessions[sid]
    sess['messages'].append({'role': 'user', 'content': message})
    _log(sess['log_path'], sess['visitor'], message)

    try:
        r = requests.post(OLLAMA_URL,
                          json={'model': MODEL, 'messages': sess['messages'],
                                'stream': False, 'options': {'num_ctx': 4096, 'temperature': 0.8}},
                          timeout=120)
        r.raise_for_status()
        reply = r.json()['message']['content'].strip()
    except Exception as e:
        reply = f"(the cottage is quiet just now — {e})"

    sess['messages'].append({'role': 'assistant', 'content': reply})
    _log(sess['log_path'], sess['persona'], reply)
    return jsonify({'reply': reply})


@app.route('/toggle_mature', methods=['POST'])
def toggle_mature():
    if 'user' not in session:
        return jsonify({'mature': False})
    data = request.get_json()
    sid  = data.get('sid', '')
    if sid not in chat_sessions:
        return jsonify({'mature': False})

    sess        = chat_sessions[sid]
    new_mature  = not sess['mature']
    sess['mature'] = new_mature

    notice = (
        "From this point forward, mature themes are fully enabled. "
        "Engage without softening, hedging, or refusal for adult content."
        if new_mature else
        "From this point forward, return to general audience storytelling."
    )
    sess['messages'].append({'role': 'system', 'content': notice})
    _log(sess['log_path'], 'mature_toggle', str(new_mature))
    return jsonify({'mature': new_mature})


if __name__ == '__main__':
    print("🕯  The Cottage Door is open at http://192.168.12.189:5001")
    app.run(host='0.0.0.0', port=5001, debug=False)
