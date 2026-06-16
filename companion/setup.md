# Companion app setup

Five minutes, free, works from anywhere.

---

## 1. Create a Cloudflare account

https://cloudflare.com — free, no card needed.

---

## 2. Deploy the Worker

1. Log in → **Workers & Pages** → **Create** → **Create Worker**
2. Name it anything (e.g. `claude-companion`)
3. Click **Edit code**, paste the contents of `worker.js`, click **Deploy**

---

## 3. Set secrets

In your Worker → **Settings** → **Variables and Secrets**:

| Name | Value | Type |
|------|-------|------|
| `ANTHROPIC_API_KEY` | your Anthropic key (`sk-ant-...`) | Secret |
| `ACCESS_TOKEN` | any password you choose | Secret |

Click **Deploy** again after saving.

---

## 4. Get your Worker URL

It looks like: `https://claude-companion.your-name.workers.dev`

Copy it — you'll need it in the app.

---

## 5. Open the app on your phone

You can serve `index.html` from the Pi (on home WiFi):

```
cd /home/bmo/pucky/companion
python3 -m http.server 8766
```

Then open `http://raspberrypi.local:8766` on your phone.

Or copy `index.html` to any static host (GitHub Pages, Cloudflare Pages)
and it'll work from anywhere without the Pi.

**First run:** enter your Worker URL and the access token you chose.

---

## Installing to home screen

**iPhone:** Safari → Share → Add to Home Screen  
**Android:** Chrome menu → Add to Home Screen

---

## To reset / re-configure

Type `!setup` in the input bar — or clear site data in browser settings.

---

## No API credits? Run locally instead

If you don't have Anthropic credits, the Pi can serve both the app and
the AI using Ollama (already set up if you ran `setup_local_ai.sh`).

**Start both servers on the Pi:**

```
cd /home/bmo/pucky

# serve the phone app
python3 -m http.server 8766 &

# serve the local AI backend
python3 companion/local_server.py
```

**On your phone**, open `http://raspberrypi.local:8766` and enter:

| Field | Value |
|-------|-------|
| Worker URL | `http://raspberrypi.local:8767` |
| Token | *(leave blank)* |

Responses will be slower than Claude (local model) but work fully offline
once Ollama is running. Your phone and Pi must be on the same WiFi network.
