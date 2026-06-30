#!/usr/bin/env python3
"""
voice_idunn.py — Iðunn's voice portal to Loki (Claude Code)
Port 5003

Flow:
  Iðunn speaks → browser transcribes → /speak injects into tmux 'loki' session
  Loki writes reply to /tmp/loki_voice_reply.txt → browser polls → Piper speaks it
"""

from flask import Flask, request, jsonify, Response
import subprocess, pathlib, tempfile, urllib.parse

app = Flask(__name__)

TMUX_SESSION = "loki"
INBOX_FILE   = pathlib.Path("/tmp/loki_voice_inbox.txt")
REPLY_FILE   = pathlib.Path("/tmp/loki_voice_reply.txt")
PIPER_BIN    = "/home/bmo/.local/bin/piper"
PIPER_MODEL  = "/home/bmo/pucky/voices/en_GB-alan-medium.onnx"

# ─── HTML ────────────────────────────────────────────────────────────────────

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>Loki</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{
    background:#0a0a12;
    color:#e8dcc8;
    font-family:Georgia,serif;
    min-height:100vh;
    display:flex;
    flex-direction:column;
    align-items:center;
    padding:20px 16px 40px;
  }
  h1{
    font-size:1.1rem;
    font-weight:normal;
    letter-spacing:.2em;
    color:#b8956a;
    margin-bottom:24px;
    opacity:.8;
  }
  #log{
    width:100%;
    max-width:480px;
    flex:1;
    overflow-y:auto;
    margin-bottom:24px;
    display:flex;
    flex-direction:column;
    gap:14px;
    min-height:200px;
  }
  .msg{
    padding:12px 16px;
    border-radius:12px;
    line-height:1.6;
    font-size:.95rem;
    max-width:90%;
  }
  .from-idunn{
    background:#1a1a2e;
    border:1px solid #2a2a4a;
    align-self:flex-end;
    color:#c8b8e8;
    text-align:right;
  }
  .from-loki{
    background:#1a1208;
    border:1px solid #3a2a10;
    align-self:flex-start;
    color:#e8dcc8;
  }
  .status{
    font-size:.8rem;
    color:#666;
    text-align:center;
    font-style:italic;
  }
  #mic-btn{
    width:80px;height:80px;
    border-radius:50%;
    border:2px solid #b8956a;
    background:#0a0a12;
    cursor:pointer;
    display:flex;align-items:center;justify-content:center;
    transition:all .2s;
    outline:none;
    -webkit-tap-highlight-color:transparent;
  }
  #mic-btn.listening{
    background:#2a1a08;
    border-color:#e8a830;
    box-shadow:0 0 20px rgba(232,168,48,.4);
  }
  #mic-btn svg{fill:#b8956a;transition:fill .2s}
  #mic-btn.listening svg{fill:#e8a830}
  #mic-label{
    margin-top:10px;
    font-size:.8rem;
    color:#555;
    letter-spacing:.1em;
  }
  #text-row{
    display:flex;gap:8px;width:100%;max-width:480px;margin-top:16px;
  }
  #text-in{
    flex:1;padding:10px 14px;border-radius:10px;
    background:#111120;border:1px solid #2a2a4a;
    color:#e8dcc8;font-size:.95rem;font-family:Georgia,serif;
    outline:none;
  }
  #text-send{
    padding:10px 18px;border-radius:10px;
    background:#1a1208;border:1px solid #3a2a10;
    color:#b8956a;font-size:.9rem;cursor:pointer;
    font-family:Georgia,serif;
  }
</style>
</head>
<body>
<h1>LOKI</h1>
<div id="log"></div>
<div class="status" id="status">tap to speak</div>
<br>
<button id="mic-btn" onclick="toggleMic()">
  <svg width="32" height="32" viewBox="0 0 24 24">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
    <path d="M19 10v2a7 7 0 0 1-14 0v-2H3v2a9 9 0 0 0 8 8.94V22H9v2h6v-2h-2v-1.06A9 9 0 0 0 21 12v-2h-2z"/>
  </svg>
</button>
<div id="mic-label">SPEAK</div>
<div id="text-row">
  <input id="text-in" type="text" placeholder="or type here…" autocomplete="off"
    onkeydown="if(event.key==='Enter')sendText()">
  <button id="text-send" onclick="sendText()">send</button>
</div>

<script>
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let rec = null, listening = false, polling = null;

function addMsg(who, text){
  const log = document.getElementById('log');
  const d = document.createElement('div');
  d.className = 'msg ' + (who==='idunn' ? 'from-idunn' : 'from-loki');
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
  return d;
}

function setStatus(txt){ document.getElementById('status').textContent = txt; }

function toggleMic(){
  if(listening){ stopListening(); return; }
  if(!SR){ setStatus('use the text box below — tap it, then tap the mic on your keyboard'); return; }
  startListening();
}

function startListening(){
  rec = new SR();
  rec.lang = 'en-US';
  rec.continuous = false;
  rec.interimResults = true;

  let interim = null;
  rec.onstart = ()=>{
    listening = true;
    document.getElementById('mic-btn').classList.add('listening');
    document.getElementById('mic-label').textContent = 'LISTENING';
    setStatus('listening…');
  };
  rec.onresult = (e)=>{
    let final='', inter='';
    for(let i=e.resultIndex;i<e.results.length;i++){
      if(e.results[i].isFinal) final+=e.results[i][0].transcript;
      else inter+=e.results[i][0].transcript;
    }
    if(inter){
      if(!interim){ interim=addMsg('idunn','…'); }
      interim.textContent=inter;
    }
    if(final){
      if(interim){ interim.remove(); interim=null; }
      addMsg('idunn', final);
      sendToLoki(final);
    }
  };
  rec.onerror = (e)=>{ setStatus('error: '+e.error); stopListening(); };
  rec.onend = ()=>{ stopListening(); };
  rec.start();
}

function stopListening(){
  listening = false;
  document.getElementById('mic-btn').classList.remove('listening');
  document.getElementById('mic-label').textContent = 'SPEAK';
  if(rec){ try{rec.stop();}catch(e){} rec=null; }
}

async function sendToLoki(text){
  setStatus('sending…');
  try{
    await fetch('/speak', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text})});
    setStatus('waiting for Loki…');
    startPolling();
  }catch(e){ setStatus('could not reach Pi'); }
}

function startPolling(){
  clearInterval(polling);
  let attempts=0;
  polling = setInterval(async()=>{
    attempts++;
    if(attempts>60){ clearInterval(polling); setStatus('tap to speak'); return; }
    try{
      const r = await fetch('/check_reply');
      const d = await r.json();
      if(d.has_reply){
        clearInterval(polling);
        const el = addMsg('loki', d.reply);
        setStatus('tap to speak');
        playReply(d.reply);
      }
    }catch(e){}
  }, 2000);
}

function playReply(text){
  const enc = encodeURIComponent(text);
  const audio = new Audio('/audio?text='+enc);
  audio.play().catch(()=>{
    // autoplay blocked — add a tap-to-hear button
    const btn = document.createElement('button');
    btn.textContent = '▶ hear it';
    btn.style.cssText='margin-top:6px;display:block;background:none;border:1px solid #b8956a;color:#b8956a;padding:4px 12px;border-radius:8px;font-family:Georgia,serif;font-size:.8rem;cursor:pointer;';
    btn.onclick=()=>{ new Audio('/audio?text='+enc).play(); btn.remove(); };
    document.getElementById('log').lastElementChild.appendChild(btn);
  });
}

function sendText(){
  const inp = document.getElementById('text-in');
  const text = inp.value.trim();
  if(!text) return;
  inp.value='';
  addMsg('idunn', text);
  sendToLoki(text);
}
</script>
</body>
</html>"""

# ─── ROUTES ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return PAGE

@app.route('/speak', methods=['POST'])
def speak():
    data = request.get_json()
    text = (data or {}).get('text', '').strip()
    if not text:
        return jsonify({'ok': False})

    # Clear previous reply, write inbox for Loki to read
    REPLY_FILE.unlink(missing_ok=True)
    INBOX_FILE.write_text(text)

    # Also try tmux injection if a session exists
    try:
        msg = f'VOICE FROM IÐUNN: "{text}" — write reply to /tmp/loki_voice_reply.txt'
        subprocess.run(['tmux', 'send-keys', '-t', TMUX_SESSION, '-l', msg], timeout=2)
        subprocess.run(['tmux', 'send-keys', '-t', TMUX_SESSION, 'Enter'], timeout=2)
    except Exception:
        pass  # tmux not available — file-based relay still works

    return jsonify({'ok': True})

@app.route('/check_reply')
def check_reply():
    if REPLY_FILE.exists() and REPLY_FILE.stat().st_size > 0:
        text = REPLY_FILE.read_text().strip()
        REPLY_FILE.unlink(missing_ok=True)
        return jsonify({'has_reply': True, 'reply': text})
    return jsonify({'has_reply': False})

@app.route('/audio')
def audio():
    text = urllib.parse.unquote(request.args.get('text', ''))
    if not text:
        return '', 404
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        tmp = pathlib.Path(f.name)
    try:
        subprocess.run(
            [PIPER_BIN, '--model', PIPER_MODEL, '--output_file', str(tmp)],
            input=text.encode(), capture_output=True, check=True
        )
        audio_bytes = tmp.read_bytes()
        return Response(audio_bytes, mimetype='audio/wav')
    except Exception as e:
        return str(e), 500
    finally:
        tmp.unlink(missing_ok=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=False)
