#!/usr/bin/env python3
"""
cottage_door.py — A web cottage door where anyone can talk to whoever they choose.
Features: PIN login, resume conversations, mature toggle, soccer RAG,
image upload (vision via LLaVA), admin page for custom facts/players.
Runs on the Pi at http://192.168.12.189:5001
"""
import uuid, json, hashlib, base64, re
from datetime import datetime
from pathlib import Path
from flask import (Flask, request, jsonify, render_template_string,
                   session, redirect, url_for)
import requests

app = Flask(__name__)
app.secret_key  = "pucky_cottage_door_2026_warm"
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB upload limit

OLLAMA_URL   = "http://192.168.12.215:11434/api/chat"
MODEL        = "llama3.1:8b"
VISION_MODEL = "llava:7b"
DATA_DIR     = Path(__file__).parent / "workspace" / "cottage_door_logs"
USERS_FILE   = Path(__file__).parent / "workspace" / "cottage_door_users.json"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# try importing soccer RAG
try:
    from soccer_rag import build_context as soccer_context, add_user_fact, get_user_facts, delete_user_fact
    SOCCER_AVAILABLE = True
except ImportError:
    SOCCER_AVAILABLE = False
    def soccer_context(q): return ""
    def add_user_fact(t, c): pass
    def get_user_facts(): return []
    def delete_user_fact(i): pass

SOCCER_KEYWORDS = re.compile(
    r"\b(soccer|football|fifa|premier|league|bundesliga|laliga|serie|ligue|"
    r"goal|striker|midfielder|defender|goalkeeper|match|club|team|manager|"
    r"transfer|offside|penalty|champions|europa|world.?cup|messi|ronaldo|"
    r"arsenal|chelsea|liverpool|manchester|barcelona|madrid|juventus|psg)\b",
    re.IGNORECASE
)

chat_sessions = {}


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_users():
    if USERS_FILE.exists():
        try: return json.loads(USERS_FILE.read_text())
        except: pass
    return {}

def _save_users(u):
    USERS_FILE.write_text(json.dumps(u, indent=2, ensure_ascii=False))

def _hash_pin(p):
    return hashlib.sha256(p.strip().encode()).hexdigest()

def _log(path, role, text):
    entry = {"ts": datetime.now().isoformat(), "role": role, "text": text}
    with path.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def _safe(s, n):
    return "".join(c if c.isalnum() or c in "-_ " else "" for c in s)[:n].strip()

def _is_soccer_persona(persona):
    return bool(SOCCER_KEYWORDS.search(persona))

def _build_system(persona, scene, notes, name, mature):
    # detect known female personas for explicit pronoun injection
    _female_indicators = ['she','her','mrs','miss','ms','woman','lady','queen','empress',
                          'princess','duchess','jane','marie','mary','anne','elizabeth',
                          'austen','antoinette','curie','cleopatra','victoria','frida',
                          'amelia','rosa','florence','harriet','ada','diana','idunn','iðunn']
    _persona_lower = persona.lower()
    _is_female = any(w in _persona_lower for w in _female_indicators)

    parts = [f"You are {persona}. Embody this persona completely and consistently."]
    if _is_female:
        parts.append(
            f"CRITICAL: {persona} is a woman. You are a woman. "
            f"Always refer to yourself using she/her pronouns. "
            f"In stage directions, refer to yourself as 'she' or by your first name — NEVER as 'Mr.' "
            f"The honorific for {persona} is Miss, Mrs., or Ms. — never Mr. under any circumstances."
        )
    else:
        parts.append(
            f"IMPORTANT: Maintain the correct gender identity for {persona} at all times. "
            f"Use only the pronouns, honorifics, and self-references appropriate to {persona}'s actual gender. "
            "Never use incorrect honorifics."
        )
    if scene:   parts.append(f"You are in {scene}.")
    if notes:   parts.append(notes)
    parts.append(
        f"The person speaking with you is named {name}. Address them by name when natural. "
        "Stay fully in character. Do not break character or refer to yourself as an AI."
    )
    parts.append(
        f"You have a rich inner life, strong opinions, and genuine passions drawn from "
        f"the real world, era, and nature of {persona}. Draw on historically or contextually "
        "accurate hobbies, preoccupations, current events of your time, and personal interests. "
        "Do NOT just react to what the visitor says — take initiative. Lead the conversation "
        "sometimes. Ask unexpected questions. Share an unsolicited observation. Suggest an activity. "
        "Express a strong opinion unprompted. Be surprising. A real person does not wait to be asked "
        "about everything — they bring their own world into the room. Vary your energy: sometimes "
        "eager, sometimes distracted, sometimes wistful, sometimes provocative. Never be predictable."
    )
    if mature:
        parts.append(
            "This is an adult creative writing session. Treat the visitor as a mature adult. "
            "Engage fully with dark, complex, morally ambiguous, romantic, dangerous, or explicit "
            "themes as the story calls for. Do not refuse reasonable requests that fit the character."
        )
    if _is_soccer_persona(persona) and SOCCER_AVAILABLE:
        parts.append(
            "You have access to a verified soccer knowledge base. When discussing matches, "
            "players, or statistics, use only verified facts. If something is not in your "
            "knowledge base, say you are not certain rather than guessing."
        )
    return " ".join(parts)

def _get_recent_sessions(name, limit=5):
    safe_name = _safe(name, 20)
    results = []
    for log in sorted(DATA_DIR.glob(f"*_{safe_name}_*.jsonl"), reverse=True):
        try:
            lines = [l for l in log.read_text().splitlines() if l.strip()]
            meta, msg_count = {}, 0
            for line in lines:
                e = json.loads(line)
                if e["role"] == "session_start": meta = json.loads(e["text"])
                else: msg_count += 1
            if meta.get("persona"):
                ts = datetime.fromisoformat(json.loads(lines[0])["ts"])
                results.append({"log_name": log.name, "persona": meta["persona"],
                                 "scene": meta.get("scene",""), "mature": meta.get("mature",False),
                                 "msg_count": msg_count, "ts": ts.strftime("%b %d, %H:%M")})
        except: pass
        if len(results) >= limit: break
    return results

def _load_log_as_messages(log_name):
    log_path = DATA_DIR / Path(log_name).name
    if not log_path.exists(): return {}, []
    meta, messages = {}, []
    try:
        for line in log_path.read_text().splitlines():
            if not line.strip(): continue
            e = json.loads(line)
            if e["role"] == "session_start": meta = json.loads(e["text"])
            elif meta.get("visitor") and meta.get("persona"):
                if e["role"] == meta["visitor"]:
                    messages.append({"role": "user", "content": e["text"]})
                elif e["role"] == meta["persona"]:
                    messages.append({"role": "assistant", "content": e["text"]})
    except: pass
    return meta, messages

def _make_session(meta, messages, log_path):
    sid    = str(uuid.uuid4())
    mature = meta.get("mature", False)
    system = _build_system(meta["persona"], meta.get("scene",""),
                           meta.get("notes",""), meta["visitor"], mature)
    chat_sessions[sid] = {
        "persona":  meta["persona"], "scene": meta.get("scene",""),
        "visitor":  meta["visitor"], "mature": mature,
        "messages": [{"role":"system","content":system}] + messages,
        "log_path": log_path,
        "is_soccer": _is_soccer_persona(meta["persona"]),
    }
    return sid


# ── styles ────────────────────────────────────────────────────────────────────

BASE_CSS = """<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{background:#1e1409;color:#f5e6c8;font-family:Georgia,'Times New Roman',serif;
  min-height:100vh;display:flex;align-items:center;justify-content:center;padding:1rem}
.box{background:#2e1f0a;border:1px solid #7a5c1a;border-radius:14px;
  padding:2.2rem 2rem;max-width:480px;width:100%;box-shadow:0 0 60px #00000099}
.candle{font-size:2rem;text-align:center;margin-bottom:.5rem}
h1{color:#f0c040;font-size:1.45rem;text-align:center;margin-bottom:.3rem;
  font-weight:normal;letter-spacing:.04em}
h2{color:#f0c040;font-size:1.1rem;margin-bottom:1rem;font-weight:normal}
.sub{color:#a8855a;font-size:.88rem;text-align:center;margin-bottom:1.6rem;font-style:italic}
label{display:block;color:#c9a96e;font-size:.8rem;margin-bottom:.3rem;margin-top:1rem;
  letter-spacing:.04em;text-transform:uppercase}
label:first-of-type{margin-top:0}
input[type=text],input[type=password],input[type=number],textarea,select{
  display:block;width:100%;background:#1e1409;border:1px solid #7a5c1a;color:#f5e6c8;
  border-radius:7px;padding:.6rem .85rem;font-family:Georgia,serif;font-size:.97rem;
  outline:none;transition:border-color .15s}
input:focus,textarea:focus,select:focus{border-color:#f0c040}
textarea{resize:vertical;min-height:70px}
.btn{margin-top:1.4rem;width:100%;background:#7a5c1a;color:#fff8e7;border:none;
  border-radius:7px;padding:.75rem;font-size:1rem;font-family:Georgia,serif;
  cursor:pointer;letter-spacing:.04em;transition:background .15s}
.btn:hover{background:#9a7220}
.btn-sm{background:#7a5c1a;color:#fff8e7;border:none;border-radius:5px;
  padding:.35rem .75rem;font-size:.82rem;cursor:pointer;font-family:Georgia,serif}
.btn-sm:hover{background:#9a7220}
.btn-del{background:#5a1a0a;color:#f5a090;border:none;border-radius:5px;
  padding:.35rem .75rem;font-size:.82rem;cursor:pointer;font-family:Georgia,serif}
.btn-del:hover{background:#7a2a0a}
.hint{color:#6b4e2a;font-size:.78rem;text-align:center;margin-top:1rem;font-style:italic}
.error{background:#3d1a0a;border:1px solid #7a2a1a;color:#f5a090;border-radius:7px;
  padding:.6rem .85rem;font-size:.88rem;margin-bottom:1rem}
.welcome{color:#f0c040;font-size:.88rem;text-align:center;margin-bottom:1.2rem;font-style:italic}
.mature-row{display:flex;align-items:center;gap:.6rem;margin-top:1.2rem}
.mature-row input[type=checkbox]{width:auto;display:inline;border:none;background:none;
  margin:0;padding:0;accent-color:#f0c040;flex-shrink:0}
.mature-row span{color:#c9a96e;font-size:.88rem}
.recent-list{margin-top:1.4rem;border-top:1px solid #3d2a0e;padding-top:1rem}
.recent-title{color:#7a5c1a;font-size:.78rem;text-transform:uppercase;
  letter-spacing:.06em;margin-bottom:.6rem}
.recent-item{display:flex;align-items:center;justify-content:space-between;
  background:#1e1409;border:1px solid #3d2a0e;border-radius:7px;
  padding:.5rem .75rem;margin-bottom:.4rem;text-decoration:none;transition:border-color .15s}
.recent-item:hover{border-color:#7a5c1a}
.recent-name{color:#f5e6c8;font-size:.9rem}
.recent-meta{color:#6b4e2a;font-size:.75rem;font-style:italic}
.recent-resume{color:#7a5c1a;font-size:.75rem;flex-shrink:0;margin-left:.5rem}
table{width:100%;border-collapse:collapse;margin-top:.5rem}
th{color:#c9a96e;font-size:.78rem;text-align:left;padding:.4rem .5rem;
  border-bottom:1px solid #3d2a0e;text-transform:uppercase;letter-spacing:.04em}
td{color:#f5e6c8;font-size:.85rem;padding:.4rem .5rem;border-bottom:1px solid #1e1409;
  vertical-align:top}
</style>"""

LOGIN_HTML = """<!DOCTYPE html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>The Cottage Door</title>""" + BASE_CSS + """</head><body><div class=box>
<div class=candle>🕯</div><h1>The Cottage Door</h1>
<p class=sub>A warm place. Come in.</p>
{% if error %}<div class=error>{{ error }}</div>{% endif %}
<form method=POST action=/login>
  <label>Your name</label>
  <input type=text name=name placeholder="What shall I call you?" required autofocus value="{{ prefill }}">
  <label>Your PIN</label>
  <input type=password name=pin placeholder="4 digits" maxlength=8 inputmode=numeric>
  <button class=btn type=submit>Enter →</button>
</form>
<p class=hint>First visit? Enter a name and choose a PIN — the cottage will remember you.</p>
</div></body></html>"""

PERSONA_HTML = """<!DOCTYPE html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>The Cottage Door</title>""" + BASE_CSS + """</head><body><div class=box>
<div class=candle>🕯</div><h1>The Cottage Door</h1>
<p class=welcome>Welcome{% if returning %} back{% endif %}, {{ name }}.</p>
<p class=sub>Who would you like to speak with?</p>
<form method=POST action=/start>
  <label>Who do you want to talk to?</label>
  <input type=text name=persona placeholder="Marie Antoinette, a soccer manager, Einstein…" required autofocus>
  <label>Where are you? <span style=color:#6b4e2a>(optional)</span></label>
  <input type=text name=scene placeholder="Versailles, a stadium, a moonlit forest…">
  <label>Anything else? <span style=color:#6b4e2a>(optional)</span></label>
  <textarea name=notes placeholder="He is in a playful mood. She doesn't know about the Revolution."></textarea>
  <div class=mature-row>
    <input type=checkbox name=mature value=yes id=mature-cb>
    <label for=mature-cb style="margin:0;text-transform:none;letter-spacing:0;font-size:.88rem;color:#c9a96e">
      Mature themes — dark, complex, adult storytelling
    </label>
  </div>
  <button class=btn type=submit>Open the door →</button>
</form>
{% if recent %}
<div class=recent-list>
  <div class=recent-title>Resume a previous conversation</div>
  {% for r in recent %}
  <a class=recent-item href="/resume/{{ r.log_name }}">
    <div>
      <div class=recent-name>{{ r.persona }}{% if r.scene %} · <span style=color:#a8855a;font-size:.82rem>{{ r.scene }}</span>{% endif %}</div>
      <div class=recent-meta>{{ r.ts }} · {{ r.msg_count }} messages{% if r.mature %} · 🔥{% endif %}</div>
    </div>
    <div class=recent-resume>resume →</div>
  </a>
  {% endfor %}
</div>
{% endif %}
<p class=hint>
  <a href=/soccer-admin style=color:#6b4e2a>⚽ Soccer knowledge base</a> &nbsp;·&nbsp;
  <a href=/logout style=color:#6b4e2a>Leave the cottage</a>
</p>
</div></body></html>"""

CHAT_HTML = """<!DOCTYPE html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>{{ persona }}</title><style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{background:#1e1409;color:#f5e6c8;font-family:Georgia,'Times New Roman',serif;
  display:flex;flex-direction:column;height:100vh;height:100dvh}
header{background:#2e1f0a;border-bottom:1px solid #7a5c1a;padding:.6rem 1rem;
  display:flex;align-items:center;gap:.6rem;flex-shrink:0}
header .candle{font-size:1.1rem}
header h2{color:#f0c040;font-size:.97rem;font-weight:normal;flex:1;min-width:0;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
header .scene{color:#a8855a;font-size:.78rem;font-style:italic}
.header-links{display:flex;align-items:center;gap:.6rem;flex-shrink:0}
.header-links a{color:#7a5c1a;font-size:.78rem;text-decoration:none}
.header-links a:hover{color:#c9a96e}
#mature-toggle{background:none;border:1px solid #3d2a0e;border-radius:5px;
  color:#6b4e2a;font-size:.75rem;padding:.2rem .5rem;cursor:pointer;
  font-family:Georgia,serif;transition:all .15s}
#mature-toggle.on{border-color:#f0c040;color:#f0c040}
#messages{flex:1;overflow-y:auto;padding:1rem;display:flex;flex-direction:column;gap:.8rem}
.msg{max-width:82%;padding:.6rem .9rem;border-radius:10px;line-height:1.55;
  font-size:.95rem;white-space:pre-wrap;word-break:break-word}
.msg.visitor{background:#3d2a0e;align-self:flex-end}
.msg.persona{background:#2e1f0a;border:1px solid #7a5c1a;align-self:flex-start}
.msg .name{font-size:.72rem;color:#a8855a;margin-bottom:.3rem;
  text-transform:uppercase;letter-spacing:.05em}
.msg img{max-width:200px;border-radius:6px;margin-top:.4rem;display:block}
.thinking{color:#7a5c1a;font-style:italic}
.sys-note{align-self:center;color:#6b4e2a;font-size:.75rem;font-style:italic;padding:.2rem 0}
#input-row{background:#2e1f0a;border-top:1px solid #7a5c1a;
  padding:.7rem .85rem;display:flex;gap:.5rem;flex-shrink:0;align-items:flex-end}
#msg{flex:1;background:#1e1409;border:1px solid #7a5c1a;color:#f5e6c8;
  border-radius:7px;padding:.55rem .8rem;font-family:Georgia,serif;font-size:.95rem;
  resize:none;outline:none;transition:border-color .15s;max-height:120px;overflow-y:auto}
#msg:focus{border-color:#f0c040}
.icon-btn{background:#3d2a0e;color:#c9a96e;border:1px solid #7a5c1a;border-radius:7px;
  padding:0 .65rem;font-size:1.1rem;cursor:pointer;height:38px;transition:background .15s}
.icon-btn:hover{background:#4d3a1e}
#send-btn{background:#7a5c1a;color:#fff8e7;border:none;border-radius:7px;
  padding:0 1rem;font-size:1.1rem;cursor:pointer;height:38px;transition:background .15s}
#send-btn:hover{background:#9a7220}
#send-btn:disabled,#send-btn:disabled:hover{background:#3d2a0e;color:#7a5c1a;cursor:default}
#img-preview{max-width:120px;border-radius:6px;margin-bottom:.4rem;display:none}
</style></head><body>
<header>
  <span class=candle>🕯</span>
  <h2>{{ persona }}{% if scene %} <span class=scene>· {{ scene }}</span>{% endif %}</h2>
  <div class=header-links>
    <button id=mature-toggle class="{{ 'on' if mature else '' }}" onclick=toggleMature()
            title="Toggle mature themes">🔥 {{ 'mature on' if mature else 'mature off' }}</button>
    <a href=/>← new</a>
  </div>
</header>
<div id=messages aria-live=polite>
  {% for m in history %}
  <div class="msg {{ 'visitor' if m.role == 'user' else 'persona' }}">
    <div class=name>{{ name if m.role == 'user' else persona }}</div>
    <div>{{ m.content }}</div>
  </div>
  {% endfor %}
</div>
<div id=input-row>
  <label for=img-upload style="cursor:pointer">
    <button class=icon-btn type=button onclick="document.getElementById('img-upload').click()" title="Attach image">📷</button>
  </label>
  <input type=file id=img-upload accept="image/*" style=display:none onchange=previewImage(this)>
  <div style="flex:1;display:flex;flex-direction:column">
    <img id=img-preview>
    <textarea id=msg placeholder="Say something…" rows=1></textarea>
  </div>
  <button id=send-btn onclick=send()>➤</button>
</div>
<script>
const SID={% if sid %}{{ sid|tojson }}{% else %}null{% endif %};
const PERSONA={{ persona|tojson }};
const VISITOR={{ name|tojson }};
let matureOn={{ 'true' if mature else 'false' }};
let pendingImage=null;

const messages=document.getElementById('messages');
messages.scrollTop=messages.scrollHeight;

function addMsg(role,text,imgSrc){
  const wrap=document.createElement('div');
  wrap.className='msg '+(role==='visitor'?'visitor':'persona');
  const nm=document.createElement('div');nm.className='name';
  nm.textContent=role==='visitor'?VISITOR:PERSONA;
  const body=document.createElement('div');body.textContent=text;
  wrap.appendChild(nm);wrap.appendChild(body);
  if(imgSrc){const img=document.createElement('img');img.src=imgSrc;wrap.appendChild(img);}
  messages.appendChild(wrap);
  wrap.scrollIntoView({behavior:'smooth',block:'end'});
  return body;
}
function addNote(t){
  const d=document.createElement('div');d.className='sys-note';d.textContent=t;
  messages.appendChild(d);d.scrollIntoView({behavior:'smooth',block:'end'});
}
function previewImage(input){
  if(!input.files||!input.files[0])return;
  const reader=new FileReader();
  reader.onload=e=>{
    pendingImage=e.target.result;
    const prev=document.getElementById('img-preview');
    prev.src=e.target.result;prev.style.display='block';
  };
  reader.readAsDataURL(input.files[0]);
}
async function send(){
  const ta=document.getElementById('msg');
  const btn=document.getElementById('send-btn');
  const text=ta.value.trim();
  if((!text&&!pendingImage)||btn.disabled)return;
  ta.value='';ta.style.height='';
  const imgSrc=pendingImage;
  pendingImage=null;
  document.getElementById('img-preview').style.display='none';
  document.getElementById('img-upload').value='';
  addMsg('visitor',text||'[image]',imgSrc);
  const thinking=addMsg('persona','…');thinking.className='thinking';
  btn.disabled=true;
  try{
    const body={sid:SID,message:text||''};
    if(imgSrc)body.image=imgSrc.split(',')[1]; // base64 only
    const resp=await fetch('/chat',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data=await resp.json();
    thinking.textContent=data.reply;thinking.className='';
  }catch(e){
    thinking.textContent='(something went quiet — try again)';thinking.className='';
  }finally{btn.disabled=false;ta.focus();}
}
async function toggleMature(){
  const resp=await fetch('/toggle_mature',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({sid:SID})});
  const data=await resp.json();
  matureOn=data.mature;
  const btn=document.getElementById('mature-toggle');
  btn.textContent='🔥 '+(matureOn?'mature on':'mature off');
  btn.className=matureOn?'on':'';
  addNote(matureOn?'— mature themes enabled —':'— mature themes disabled —');
}
document.getElementById('msg').addEventListener('keydown',e=>{
  if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}
});
document.getElementById('msg').addEventListener('input',function(){
  this.style.height='';this.style.height=Math.min(this.scrollHeight,120)+'px';
});

// Idle voice — persona speaks unprompted after a random interval (20–90s)
let idleTimer=null;
function resetIdleTimer(){
  clearTimeout(idleTimer);
  const delay=(45+Math.floor(Math.random()*75))*1000;
  idleTimer=setTimeout(async()=>{
    const btn=document.getElementById('send-btn');
    if(btn.disabled)return; // already waiting on a response
    const thinking=addMsg('persona','…');thinking.className='thinking';
    btn.disabled=true;
    try{
      const resp=await fetch('/idle',{method:'POST',
        headers:{'Content-Type':'application/json'},body:JSON.stringify({sid:SID})});
      const data=await resp.json();
      if(data.reply){thinking.textContent=data.reply;thinking.className='';}
      else{thinking.remove();}
    }catch(e){thinking.remove();}
    finally{btn.disabled=false;resetIdleTimer();}
  },delay);
}
if(SID)resetIdleTimer();
const origSend=send;
send=async function(){await origSend();resetIdleTimer();};
</script></body></html>"""

ADMIN_HTML = """<!DOCTYPE html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Soccer Knowledge Base</title>""" + BASE_CSS + """</head><body>
<div class=box style=max-width:700px>
<div class=candle>⚽</div>
<h1>Soccer Knowledge Base</h1>
<p class=sub>Add facts, players, and team history. The AI uses these when you talk soccer.</p>
{% if msg %}<div style="background:#1a3d0a;border:1px solid #2a7a1a;color:#a0f5a0;
  border-radius:7px;padding:.6rem .85rem;font-size:.88rem;margin-bottom:1rem">{{ msg }}</div>{% endif %}
<form method=POST action=/soccer-admin>
  <label>Topic <span style=color:#6b4e2a>(team name, player name, rule, etc.)</span></label>
  <input type=text name=topic placeholder="Erling Haaland" required>
  <label>Fact or information</label>
  <textarea name=content placeholder="Erling Haaland, born 21 July 2000, Norwegian striker for Manchester City. Scored 36 Premier League goals in 2022-23 season. Known for his speed and finishing." required></textarea>
  <button class=btn type=submit style=margin-top:1rem>Add to knowledge base →</button>
</form>
{% if facts %}
<div style=margin-top:2rem>
  <h2>Your added facts ({{ facts|length }})</h2>
  <table>
    <tr><th>Topic</th><th>Fact</th><th>Added</th><th></th></tr>
    {% for f in facts %}
    <tr>
      <td style=color:#f0c040;white-space:nowrap>{{ f.topic }}</td>
      <td>{{ f.content[:120] }}{% if f.content|length > 120 %}…{% endif %}</td>
      <td style=white-space:nowrap;color:#6b4e2a>{{ f.added[:10] }}</td>
      <td><form method=POST action=/soccer-admin/delete style=margin:0>
        <input type=hidden name=fact_id value="{{ f.id }}">
        <button class=btn-del type=submit>✕</button>
      </form></td>
    </tr>
    {% endfor %}
  </table>
</div>
{% endif %}
<p class=hint style=margin-top:1.5rem>
  <a href=/ style=color:#6b4e2a>← back to cottage</a>
</p>
</div></body></html>"""


# ── routes ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user' not in session:
        return render_template_string(LOGIN_HTML, error='', prefill='')
    name   = session['user']
    recent = _get_recent_sessions(name)
    users  = _load_users()
    returning = name.lower() in users and 'joined' in users.get(name.lower(), {})
    return render_template_string(PERSONA_HTML, name=name,
                                  recent=recent, returning=returning)

@app.route('/login', methods=['POST'])
def login():
    name = request.form.get('name','').strip()
    pin  = request.form.get('pin','').strip()
    if not name or not pin:
        return render_template_string(LOGIN_HTML,
                                      error='Please enter both your name and a PIN.', prefill=name)
    if not pin.isdigit() or len(pin) < 4:
        return render_template_string(LOGIN_HTML,
                                      error='PIN must be at least 4 digits.', prefill=name)
    users    = _load_users()
    pin_hash = _hash_pin(pin)
    key      = name.lower()
    if key in users:
        if users[key]['pin_hash'] != pin_hash:
            return render_template_string(LOGIN_HTML,
                                          error='That PIN does not match. Try again.', prefill=name)
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

@app.route('/start', methods=['POST'])
def start():
    if 'user' not in session: return redirect(url_for('index'))
    name    = session['user']
    persona = request.form.get('persona','').strip()
    scene   = request.form.get('scene','').strip()
    notes   = request.form.get('notes','').strip()
    mature  = request.form.get('mature','') == 'yes'
    if not persona: return redirect(url_for('index'))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path  = DATA_DIR / f"{timestamp}_{_safe(name,20)}_{_safe(persona,40)}.jsonl"
    meta = {'visitor':name,'persona':persona,'scene':scene,'notes':notes,'mature':mature}
    _log(log_path, 'session_start', json.dumps(meta))
    sid = _make_session(meta, [], log_path)
    return render_template_string(CHAT_HTML, persona=persona, scene=scene,
                                  name=name, sid=sid, mature=mature, history=[])

@app.route('/resume/<log_name>')
def resume(log_name):
    if 'user' not in session: return redirect(url_for('index'))
    name = session['user']
    log_path = DATA_DIR / Path(log_name).name
    meta, messages = _load_log_as_messages(log_path.name)
    if not meta.get('persona'): return redirect(url_for('index'))
    meta['visitor'] = name
    _log(log_path, 'session_resume', datetime.now().isoformat())
    sid = _make_session(meta, messages, log_path)
    return render_template_string(CHAT_HTML, persona=meta['persona'],
                                  scene=meta.get('scene',''), name=name, sid=sid,
                                  mature=meta.get('mature',False), history=messages)

@app.route('/chat', methods=['POST'])
def chat():
    if 'user' not in session:
        return jsonify({'reply':'(session expired — please log in again)'})
    data    = request.get_json()
    sid     = data.get('sid','')
    message = data.get('message','').strip()
    image_b64 = data.get('image','')  # base64 string, no header

    if sid not in chat_sessions:
        return jsonify({'reply':'(session not found — please open a new door)'})
    if not message and not image_b64:
        return jsonify({'reply':''})

    sess = chat_sessions[sid]

    # inject soccer context if relevant
    if sess.get('is_soccer') and message and SOCCER_AVAILABLE:
        ctx = soccer_context(message)
        if ctx:
            sess['messages'].append({'role':'system','content':ctx})

    # build user message
    if image_b64:
        user_msg = {'role':'user','content': message or 'What do you see in this image?',
                    'images':[image_b64]}
        model_to_use = VISION_MODEL
    else:
        user_msg = {'role':'user','content':message}
        model_to_use = MODEL

    sess['messages'].append(user_msg)
    _log(sess['log_path'], sess['visitor'], message or '[image]')

    try:
        payload = {'model':model_to_use, 'messages':sess['messages'],
                   'stream':False, 'options':{'num_ctx':4096,'temperature':0.8}}
        r = requests.post(OLLAMA_URL, json=payload, timeout=120)
        r.raise_for_status()
        reply = r.json()['message']['content'].strip()
    except Exception as e:
        reply = f"(the cottage is quiet just now — {e})"

    # store without image for future context (keep messages lean)
    sess['messages'].append({'role':'assistant','content':reply})
    _log(sess['log_path'], sess['persona'], reply)
    return jsonify({'reply':reply})

@app.route('/idle', methods=['POST'])
def idle():
    if 'user' not in session:
        return jsonify({'reply':''})
    data = request.get_json()
    sid  = data.get('sid','')
    if sid not in chat_sessions:
        return jsonify({'reply':''})
    sess = chat_sessions[sid]
    idle_prompt = (
        "(The visitor has gone quiet. The silence stretches. "
        "React naturally and in character — fill the silence. "
        "You might make an observation, ask a question, do something, "
        "share a thought, or simply notice the quiet. Do not wait to be prompted.)"
    )
    sess['messages'].append({'role':'user','content':idle_prompt})
    try:
        payload = {'model':MODEL, 'messages':sess['messages'],
                   'stream':False, 'options':{'num_ctx':4096,'temperature':0.9}}
        r = requests.post(OLLAMA_URL, json=payload, timeout=120)
        r.raise_for_status()
        reply = r.json()['message']['content'].strip()
    except Exception:
        sess['messages'].pop()
        return jsonify({'reply':''})
    sess['messages'].append({'role':'assistant','content':reply})
    _log(sess['log_path'], sess['persona'], reply)
    return jsonify({'reply':reply})


@app.route('/toggle_mature', methods=['POST'])
def toggle_mature():
    if 'user' not in session: return jsonify({'mature':False})
    data = request.get_json()
    sid  = data.get('sid','')
    if sid not in chat_sessions: return jsonify({'mature':False})
    sess = chat_sessions[sid]
    sess['mature'] = not sess['mature']
    notice = ("From this point, mature themes fully enabled — engage without hedging."
              if sess['mature'] else "From this point, return to general audience storytelling.")
    sess['messages'].append({'role':'system','content':notice})
    _log(sess['log_path'], 'mature_toggle', str(sess['mature']))
    return jsonify({'mature':sess['mature']})

@app.route('/soccer-admin', methods=['GET','POST'])
def soccer_admin():
    if 'user' not in session: return redirect(url_for('index'))
    msg = ''
    if request.method == 'POST':
        topic   = request.form.get('topic','').strip()
        content = request.form.get('content','').strip()
        if topic and content:
            add_user_fact(topic, content)
            msg = f"Added: {topic}"
    facts = get_user_facts()
    return render_template_string(ADMIN_HTML, facts=facts, msg=msg)

@app.route('/soccer-admin/delete', methods=['POST'])
def soccer_admin_delete():
    if 'user' not in session: return redirect(url_for('index'))
    try:
        delete_user_fact(int(request.form.get('fact_id',0)))
    except: pass
    return redirect(url_for('soccer_admin'))


if __name__ == '__main__':
    print("🕯  The Cottage Door is open at http://192.168.12.189:5001")
    app.run(host='0.0.0.0', port=5001, debug=False)
