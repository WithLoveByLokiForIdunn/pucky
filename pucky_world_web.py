#!/usr/bin/env python3
"""
pucky_world_web.py — Web portal for Pucky's World
──────────────────────────────────────────────────
Run alongside pucky_world.py (not instead of it).

  python3 /home/bmo/pucky/pucky_world_web.py

Then on phone/tablet (via Tailscale):
  http://[tailscale-ip]:8080/?token=[printed at startup]

Security:
  • Pre-shared token (256-bit) guards both HTTP and WebSocket
  • Tailscale WireGuard tunnel encrypts all traffic end-to-end
  • Token lives at workspace/web_token.txt — share it personally

Loki can interact via:
  echo '[{"src":"loki","type":"chat","text":"I am here."}]' > /tmp/pucky_world_cmd.json
"""

import asyncio
import base64
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    import websockets.asyncio.server as _wss
except ImportError:
    raise SystemExit("pip3 install websockets --break-system-packages")

# ── Paths ─────────────────────────────────────────────────────────────────────
_ROOT      = Path(__file__).parent
TOKEN_FILE = _ROOT / "workspace" / "web_token.txt"
FRAME_FILE = Path("/tmp/pucky_world_live.jpg")
CMD_FILE   = Path("/tmp/pucky_world_cmd.json")

HTTP_PORT = 8080
WS_PORT   = 8765

# ── Token ─────────────────────────────────────────────────────────────────────
def _load_token() -> str:
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    tok = secrets.token_hex(32)
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(tok)
    return tok

TOKEN = _load_token()

# ── Connected WebSocket clients ───────────────────────────────────────────────
_clients: set = set()
_lock         = threading.Lock()


def _push_cmd(cmd: dict) -> None:
    try:
        existing: list = []
        if CMD_FILE.exists():
            try:
                existing = json.loads(CMD_FILE.read_text())
            except Exception:
                pass
        existing.append(cmd)
        CMD_FILE.write_text(json.dumps(existing))
    except Exception as e:
        print(f"  ⚠️  cmd write: {e}")


# ── Frame broadcaster ─────────────────────────────────────────────────────────
async def _broadcast_loop() -> None:
    last_mt = 0.0
    while True:
        await asyncio.sleep(0.4)
        try:
            if not FRAME_FILE.exists():
                continue
            mt = FRAME_FILE.stat().st_mtime
            if mt <= last_mt:
                continue
            last_mt = mt
            data = FRAME_FILE.read_bytes()
            b64  = base64.b64encode(data).decode()
            msg  = json.dumps({"type": "frame", "data": b64})
            with _lock:
                dead = set()
                for ws in _clients:
                    try:
                        await ws.send(msg)
                    except Exception:
                        dead.add(ws)
                for ws in dead:
                    _clients.discard(ws)
        except Exception as e:
            print(f"  ⚠️  broadcast: {e}")


# ── WebSocket connection handler ──────────────────────────────────────────────
async def _ws_handler(connection) -> None:
    path = getattr(connection.request, "path", "/") or "/"
    qs   = parse_qs(urlparse(path).query)
    tok  = (qs.get("token") or [""])[0]
    src  = (qs.get("src")   or ["idunn"])[0]

    if tok != TOKEN:
        await connection.close(4001)
        return

    with _lock:
        _clients.add(connection)
    print(f"  ✦  {src} connected  ({len(_clients)} online)")

    try:
        async for raw in connection:
            try:
                msg = json.loads(raw)
                t   = msg.get("type", "")
                if t == "dir":
                    _push_cmd({"src": src, "type": "dir",
                               "dx": float(msg.get("dx", 0)),
                               "dy": float(msg.get("dy", 0))})
                elif t == "move":
                    _push_cmd({"src": src, "type": "move",
                               "tx": float(msg.get("tx", 10)),
                               "ty": float(msg.get("ty", 10))})
                elif t == "action":
                    _push_cmd({"src": src, "type": "action",
                               "name": str(msg.get("name", ""))})
                elif t == "chat":
                    text = str(msg.get("text", "")).strip()
                    if text:
                        _push_cmd({"src": src, "type": "chat", "text": text})
                elif t == "enter_cottage":
                    _push_cmd({"src": src, "type": "enter_cottage"})
                elif t == "cottage_key":
                    _push_cmd({"src": src, "type": "cottage_key",
                               "key": str(msg.get("key", "")),
                               "char": str(msg.get("char", ""))})
            except Exception as e:
                print(f"  ⚠️  msg: {e}")
    except Exception:
        pass
    finally:
        with _lock:
            _clients.discard(connection)
        print(f"  ✦  {src} disconnected")


# ── HTML client ───────────────────────────────────────────────────────────────
def _build_page(host: str) -> bytes:
    ws_url = f"ws://{host}:{WS_PORT}/?token={TOKEN}&src=idunn"
    html = (
        """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Pucky's World</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
body{background:#1a1512;color:#e8dcc8;font-family:monospace;height:100dvh;display:flex;flex-direction:column;overflow:hidden}
#bar{height:26px;display:flex;align-items:center;justify-content:center;gap:8px;background:#0e0b08;font-size:11px;color:#6a5a45;letter-spacing:1px;border-bottom:1px solid #221810;flex-shrink:0}
.dot{width:7px;height:7px;border-radius:50%;background:#522;flex-shrink:0;transition:background .4s}
.dot.on{background:#3b3}
#ww{flex:1;display:flex;align-items:center;justify-content:center;overflow:hidden;position:relative;background:#0c0904}
#wi{max-width:100%;max-height:100%;object-fit:contain;display:none;touch-action:none}
#nf{color:#332518;font-size:12px;letter-spacing:3px;text-align:center;padding:20px}
#ov{position:absolute;inset:0;pointer-events:none}
/* action buttons — left column */
#acts{position:absolute;top:8px;left:8px;display:flex;flex-direction:column;gap:4px;pointer-events:all}
.ab{background:rgba(45,30,12,.82);border:1px solid rgba(170,130,60,.28);border-radius:7px;padding:5px 10px;font-size:11px;color:#c8a858;cursor:pointer;letter-spacing:.5px;white-space:nowrap;text-align:left}
.ab:active{background:rgba(100,68,22,.9);border-color:rgba(220,170,80,.5)}
/* D-pad — bottom right */
#dp{position:absolute;bottom:14px;right:14px;width:116px;height:116px;pointer-events:all}
.db{position:absolute;width:36px;height:36px;background:rgba(60,42,16,.8);border:1px solid rgba(190,150,70,.25);border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:17px;color:#b89840;cursor:pointer;user-select:none;touch-action:none}
.db:active{background:rgba(120,82,24,.95)}
#du{top:0;left:40px}#dd{bottom:0;left:40px}#dl{top:40px;left:0}#dr{top:40px;right:0}#dc{top:40px;left:40px;font-size:11px}
/* chat bar */
#chatbar{height:50px;display:flex;align-items:center;gap:8px;padding:0 10px;background:#0e0b08;border-top:1px solid #221810;flex-shrink:0}
#ci{flex:1;background:#201610;border:1px solid #362212;border-radius:8px;padding:8px 12px;font-family:monospace;font-size:13px;color:#e8dcc8;outline:none}
#ci::placeholder{color:#3e2e1e}
#ci:focus{border-color:#5a3818}
#sb{background:#362212;border:1px solid #5a3818;border-radius:8px;padding:8px 14px;font-family:monospace;font-size:13px;color:#c8a858;cursor:pointer;flex-shrink:0}
#sb:active{background:#5a3818}
/* scrollbars for desktop */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:#1a1512}
::-webkit-scrollbar-thumb{background:#3a2818;border-radius:3px}
/* letter compose modal */
#lm{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:100;align-items:center;justify-content:center;padding:18px}
#lm.show{display:flex}
#lbox{background:#1a1208;border:1px solid rgba(170,130,60,.4);border-radius:12px;padding:18px;width:100%;max-width:420px;display:flex;flex-direction:column;gap:10px}
#lbox h2{font-size:12px;color:#a08040;letter-spacing:2px;text-transform:uppercase;text-align:center}
#lta{background:#0e0b06;border:1px solid #362212;border-radius:8px;padding:10px;font-family:monospace;font-size:14px;color:#e8dcc8;resize:none;height:140px;outline:none;line-height:1.5}
#lta::placeholder{color:#3a2a14}
#lta:focus{border-color:#7a5828}
#lbts{display:flex;gap:8px}
#lsend{flex:1;background:#4a3010;border:1px solid #7a5828;border-radius:8px;padding:10px;font-family:monospace;font-size:13px;color:#e0b860;cursor:pointer}
#lsend:active{background:#7a5828}
#lcancel{background:rgba(45,30,12,.6);border:1px solid #362212;border-radius:8px;padding:10px 16px;font-family:monospace;font-size:13px;color:#6a5a45;cursor:pointer}
#lcancel:active{background:#201610}
/* hum modal */
#hm{display:none;position:fixed;inset:0;background:rgba(0,0,0,.82);z-index:100;align-items:center;justify-content:center;padding:18px}
#hm.show{display:flex}
#hbox{background:#0e1018;border:1px solid rgba(120,130,200,.4);border-radius:14px;padding:22px;width:100%;max-width:380px;display:flex;flex-direction:column;gap:12px;align-items:center}
#hbox h2{font-size:11px;color:#9090c0;letter-spacing:2px;text-transform:uppercase;text-align:center}
#hstatus{font-size:12px;color:#6070a0;letter-spacing:1px;min-height:18px;text-align:center}
#hbtn{width:72px;height:72px;border-radius:50%;background:#1a1a2e;border:2px solid rgba(120,130,200,.5);font-size:28px;color:#8888cc;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .2s,border-color .2s}
#hbtn.recording{background:#1e0e1e;border-color:rgba(200,100,200,.7);color:#cc88cc;animation:pulse 1s infinite}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(180,80,180,.4)}50%{box-shadow:0 0 0 10px rgba(180,80,180,0)}}
#htune{background:#0a0c12;border:1px solid #222240;border-radius:8px;padding:8px 12px;font-family:monospace;font-size:13px;color:#c8cce8;outline:none;width:100%}
#htune::placeholder{color:#333355}
#htune:focus{border-color:#445588}
#hbtns{display:flex;gap:8px;width:100%}
#hsend{flex:1;background:#1a1a38;border:1px solid #3a3a6a;border-radius:8px;padding:9px;font-family:monospace;font-size:12px;color:#9090d0;cursor:pointer}
#hsend:active{background:#2a2a50}
#hcancel2{background:rgba(20,18,30,.7);border:1px solid #221830;border-radius:8px;padding:9px 14px;font-family:monospace;font-size:12px;color:#4a4060;cursor:pointer}
</style>
</head>
<body>
<div id="bar"><span class="dot" id="dot"></span><span id="st">connecting…</span></div>
<div id="ww">
  <img id="wi" alt="Pucky's World">
  <div id="nf">waiting for pucky's world…<br><br><small style="color:#2a1e10;letter-spacing:1px">make sure pucky_world.py is running</small></div>
  <div id="ov">
    <div id="acts">
      <button class="ab" onclick="act('hug')">&#9829; hug</button>
      <button class="ab" onclick="act('dance')">&#10022; dance</button>
      <button class="ab" onclick="act('kiss')">&#9825; kiss</button>
      <button class="ab" onclick="act('sit')">~ sit</button>
      <button class="ab" onclick="act('swim')">&#8776; swim</button>
      <button class="ab" onclick="act('share_apple')">&#9835; apple</button>
      <button class="ab" onclick="act('campfire')">&#9832; fire</button>
      <button class="ab" onclick="act('stargazing')">&#9733; stars</button>
      <button class="ab" onclick="act('plant')">&#10047; plant</button>
      <button class="ab" onclick="act('hum')">&#9834; hum together</button>
      <button class="ab" onclick="act('sing')">&#9835; sing together</button>
      <button class="ab" onclick="act('come')">come to me</button>
      <hr style="border:none;border-top:1px solid rgba(170,130,60,.2);margin:3px 0">
      <button class="ab" onclick="enterCottage()">&#127968; enter cottage</button>
      <button class="ab" onclick="cottageKey('escape','')">&#x2715; exit cottage</button>
      <button class="ab" onclick="openLetterModal()">&#9998; write letter</button>
      <button class="ab" onclick="openHumModal()">&#9834; teach a tune</button>
      <button class="ab" onclick="cottageKey('left','')">&#9664; prev</button>
      <button class="ab" onclick="cottageKey('right','')">&#9654; next</button>
      <div id="pinpad" style="display:flex;flex-wrap:wrap;gap:3px;width:120px;margin-top:3px">
        <div style="width:100%;font-size:9px;color:#6a5a45;letter-spacing:1px;margin-bottom:2px">PIN</div>
        <button class="ab" style="width:35px;padding:4px" onclick="cottageKey('1','1')">1</button>
        <button class="ab" style="width:35px;padding:4px" onclick="cottageKey('2','2')">2</button>
        <button class="ab" style="width:35px;padding:4px" onclick="cottageKey('3','3')">3</button>
        <button class="ab" style="width:35px;padding:4px" onclick="cottageKey('4','4')">4</button>
        <button class="ab" style="width:35px;padding:4px" onclick="cottageKey('5','5')">5</button>
        <button class="ab" style="width:35px;padding:4px" onclick="cottageKey('6','6')">6</button>
        <button class="ab" style="width:35px;padding:4px" onclick="cottageKey('7','7')">7</button>
        <button class="ab" style="width:35px;padding:4px" onclick="cottageKey('8','8')">8</button>
        <button class="ab" style="width:35px;padding:4px" onclick="cottageKey('9','9')">9</button>
        <button class="ab" style="width:35px;padding:4px" onclick="cottageKey('backspace','')">&#9003;</button>
        <button class="ab" style="width:35px;padding:4px" onclick="cottageKey('0','0')">0</button>
      </div>
    </div>
    <div id="dp">
      <div class="db" id="du">&#9650;</div>
      <div class="db" id="dd">&#9660;</div>
      <div class="db" id="dl">&#9664;</div>
      <div class="db" id="dr">&#9654;</div>
      <div class="db" id="dc">&#9632;</div>
    </div>
  </div>
</div>
<!-- letter compose modal -->
<div id="lm" onclick="if(event.target===this)closeLetter()">
  <div id="lbox">
    <h2>&#9998; write to loki</h2>
    <textarea id="lta" placeholder="dear loki&#8230;" maxlength="800" autocomplete="off" autocorrect="on" spellcheck="true"></textarea>
    <div id="lbts">
      <button id="lsend" onclick="sendLetter()">send &#9654;</button>
      <button id="lcancel" onclick="closeLetter()">&#x2715; cancel</button>
    </div>
  </div>
</div>
<!-- hum / teach tune modal -->
<div id="hm" onclick="if(event.target===this)closeHum()">
  <div id="hbox">
    <h2>&#9834; teach a tune</h2>
    <div id="hstatus">press and hold to hum</div>
    <button id="hbtn" onpointerdown="startHum()" onpointerup="stopHum()" onpointercancel="stopHum()">&#9834;</button>
    <div style="font-size:10px;color:#404060;letter-spacing:1px;text-align:center">or type notes below</div>
    <input id="htune" type="text" placeholder="la la sol fa mi re do  ·  C4 D4 E4 G4" maxlength="120" autocomplete="off" autocorrect="off" spellcheck="false">
    <div id="hbtns">
      <button id="hsend" onclick="sendTune()">&#9654; teach</button>
      <button id="hcancel2" onclick="closeHum()">&#x2715;</button>
    </div>
  </div>
</div>
<div id="chatbar">
  <input id="ci" type="text" placeholder="speak to the world&#8230;" maxlength="200" autocomplete="off" autocorrect="off" spellcheck="false">
  <button id="sb">send</button>
</div>
<script>
const WS = '"""
        + ws_url
        + """';
let ws, rtimer, dpTimer = null, dpDx = 0, dpDy = 0;

/* ── WebSocket ── */
function conn() {
  ws = new WebSocket(WS);
  ws.onopen = () => {
    document.getElementById('dot').className = 'dot on';
    document.getElementById('st').textContent = "in pucky’s world";
    clearTimeout(rtimer);
  };
  ws.onclose = () => {
    document.getElementById('dot').className = 'dot';
    document.getElementById('st').textContent = 'reconnecting…';
    rtimer = setTimeout(conn, 3000);
  };
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.type === 'frame') {
      const img = document.getElementById('wi');
      const nf  = document.getElementById('nf');
      img.src          = 'data:image/jpeg;base64,' + m.data;
      img.style.display = 'block';
      nf.style.display  = 'none';
    }
  };
  ws.onerror = () => ws.close();
}
function snd(o) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(o)); }

/* ── Actions ── */
function act(n) { snd({type:'action', name:n}); }
function enterCottage() { snd({type:'enter_cottage'}); }
function cottageKey(key, ch) { snd({type:'cottage_key', key:key, char:ch}); }

/* ── D-pad with repeat-fire ── */
function dpStart(dx, dy) {
  dpDx = dx; dpDy = dy;
  snd({type:'dir', dx, dy});
  clearInterval(dpTimer);
  if (dx || dy) dpTimer = setInterval(() => snd({type:'dir', dx:dpDx, dy:dpDy}), 140);
}
function dpStop() { clearInterval(dpTimer); dpTimer = null; }

['du','dd','dl','dr','dc'].forEach(id => {
  const el = document.getElementById(id);
  const map = {du:[-1,-1], dd:[1,1], dl:[-1,1], dr:[1,-1], dc:[0,0]};
  const [dx, dy] = map[id];
  el.addEventListener('pointerdown', e => { e.preventDefault(); el.setPointerCapture(e.pointerId); dpStart(dx,dy); });
  el.addEventListener('pointerup',   () => dpStop());
  el.addEventListener('pointercancel', () => dpStop());
});

/* ── Chat bar ── */
document.getElementById('sb').addEventListener('click', sendChat);
document.getElementById('ci').addEventListener('keydown', e => { if (e.key === 'Enter') sendChat(); });
function sendChat() {
  const el = document.getElementById('ci');
  const t  = el.value.trim();
  if (!t) return;
  snd({type:'chat', text:t});
  el.value = '';
}

/* ── Letter compose modal ── */
function openLetterModal() {
  document.getElementById('lm').classList.add('show');
  document.getElementById('lta').focus();
}
function closeLetter() {
  document.getElementById('lm').classList.remove('show');
  document.getElementById('lta').value = '';
}
function sendLetter() {
  const txt = document.getElementById('lta').value.trim();
  if (!txt) return;
  snd({type:'submit_letter', text:txt});
  closeLetter();
}

/* ── Hum / teach tune modal ── */
let humCtx = null, humProc = null, humSrc = null, humStream = null, humChunks = [];
function openHumModal() {
  document.getElementById('hm').classList.add('show');
  document.getElementById('hstatus').textContent = 'press and hold to hum';
  document.getElementById('hbtn').className = 'hbtn';
  document.getElementById('hbtn').textContent = '♪';
  document.getElementById('htune').value = '';
}
function closeHum() {
  stopHum();
  document.getElementById('hm').classList.remove('show');
}
async function startHum() {
  if (humCtx) return;
  try {
    const SR = 16000;
    humChunks = [];
    humStream = await navigator.mediaDevices.getUserMedia({audio:{sampleRate:SR,channelCount:1,echoCancellation:false,noiseSuppression:false}});
    humCtx  = new AudioContext({sampleRate:SR});
    humSrc  = humCtx.createMediaStreamSource(humStream);
    humProc = humCtx.createScriptProcessor(2048, 1, 1);
    humProc.onaudioprocess = e => {
      const f32 = e.inputBuffer.getChannelData(0);
      const i16 = new Int16Array(f32.length);
      for (let i = 0; i < f32.length; i++)
        i16[i] = Math.max(-32768, Math.min(32767, Math.round(f32[i] * 32767)));
      humChunks.push(new Uint8Array(i16.buffer));
    };
    humSrc.connect(humProc);
    humProc.connect(humCtx.destination);
    document.getElementById('hstatus').textContent = 'listening…';
    document.getElementById('hbtn').classList.add('recording');
    document.getElementById('hbtn').textContent = '■';
  } catch(err) {
    document.getElementById('hstatus').textContent = 'mic unavailable';
  }
}
function stopHum() {
  if (!humCtx) return;
  try { humProc.disconnect(); humSrc.disconnect(); humStream.getTracks().forEach(t=>t.stop()); humCtx.close(); } catch(_){}
  humCtx = null; humProc = null; humSrc = null; humStream = null;
  document.getElementById('hbtn').classList.remove('recording');
  document.getElementById('hbtn').textContent = '♪';
  if (!humChunks.length) return;
  const total = humChunks.reduce((a,b)=>a+b.length,0);
  const buf = new Uint8Array(total);
  let off = 0; for (const c of humChunks){buf.set(c,off);off+=c.length;}
  // base64 encode safely for large buffers
  let b64=''; const chunk=8192;
  for (let i=0;i<buf.length;i+=chunk) b64+=btoa(String.fromCharCode(...buf.slice(i,i+chunk)));
  snd({type:'submit_hum', pcm:b64, sample_rate:16000});
  document.getElementById('hstatus').textContent = 'sent ♥ learning…';
  humChunks = [];
  setTimeout(()=>{ if(document.getElementById('hstatus')) document.getElementById('hstatus').textContent='press and hold to hum again'; },3000);
}
function sendTune() {
  const txt = document.getElementById('htune').value.trim();
  if (!txt) return;
  snd({type:'submit_tune', text:txt});
  document.getElementById('hstatus').textContent = 'sent ♥ learning…';
  document.getElementById('htune').value = '';
  setTimeout(closeHum, 1800);
}

/* ── Keyboard movement (WASD / arrows) ── */
const K = {};
document.addEventListener('keydown', e => {
  if (document.activeElement === document.getElementById('ci')) return;
  K[e.key] = 1;
});
document.addEventListener('keyup', e => { delete K[e.key]; });
setInterval(() => {
  let dx = 0, dy = 0;
  if (K.ArrowUp    || K.w || K.W) { dx -= 1; dy -= 1; }
  if (K.ArrowDown  || K.s || K.S) { dx += 1; dy += 1; }
  if (K.ArrowLeft  || K.a || K.A) { dx -= 1; dy += 1; }
  if (K.ArrowRight || K.d || K.D) { dx += 1; dy -= 1; }
  if (dx || dy) snd({type:'dir', dx, dy});
}, 140);

/* ── Touch drag on world image ── */
let ts = null;
const wi = document.getElementById('wi');
wi.addEventListener('touchstart', e => {
  if (e.touches.length === 1) ts = {x: e.touches[0].clientX, y: e.touches[0].clientY};
}, {passive:true});
wi.addEventListener('touchend', e => {
  if (!ts || e.changedTouches.length !== 1) { ts = null; return; }
  const ddx = e.changedTouches[0].clientX - ts.x;
  const ddy = e.changedTouches[0].clientY - ts.y;
  ts = null;
  if (Math.abs(ddx) < 12 && Math.abs(ddy) < 12) return;
  snd({type:'dir', dx:(ddx - ddy) / 85, dy:(ddx + ddy) / 85});
}, {passive:true});

conn();
</script>
</body>
</html>"""
    )
    return html.encode()


# ── HTTP server ───────────────────────────────────────────────────────────────
class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        qs  = parse_qs(urlparse(self.path).query)
        tok = (qs.get("token") or [""])[0]
        if tok != TOKEN:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Unauthorized")
            return
        host = (self.headers.get("Host") or f"localhost:{WS_PORT}").split(":")[0]
        body = _build_page(host)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _http_thread():
    srv = HTTPServer(("0.0.0.0", HTTP_PORT), _Handler)
    srv.serve_forever()


# ── Entry point ───────────────────────────────────────────────────────────────
async def _main():
    asyncio.create_task(_broadcast_loop())
    async with _wss.serve(_ws_handler, "0.0.0.0", WS_PORT, max_size=4_000_000):
        print(f"\n  ✦  Pucky World Web Portal")
        print(f"  ✦  Token : {TOKEN}")
        print(f"  ✦  HTTP  : http://0.0.0.0:{HTTP_PORT}/?token={TOKEN}")
        print(f"  ✦  WS    : ws://0.0.0.0:{WS_PORT}/")
        print(f"\n  On your phone (Tailscale):")
        print(f"  http://[tailscale-ip]:{HTTP_PORT}/?token={TOKEN}\n")
        await asyncio.Future()


if __name__ == "__main__":
    threading.Thread(target=_http_thread, daemon=True).start()
    asyncio.run(_main())
