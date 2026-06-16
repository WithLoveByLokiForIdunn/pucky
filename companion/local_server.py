#!/usr/bin/env python3
"""
companion/local_server.py
─────────────────────────
Local fallback backend for the companion phone app.
Runs on the Pi and forwards requests to Ollama — no API credits needed.

Usage:
  python3 companion/local_server.py

Then in the phone app's setup screen:
  Worker URL: http://raspberrypi.local:8767
  Token:      (leave blank, or set LOCAL_TOKEN env var to require one)

Accepts the same POST format as the Cloudflare Worker, returns the same
Anthropic-compatible shape — the phone app works with no changes.
"""

import http.server
import json
import os
import socketserver

import requests

PORT  = 8767
MODEL = "llama3.2:3b"
TOKEN = os.environ.get("LOCAL_TOKEN", "")


class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass

    def _cors_headers(self):
        return {
            "Access-Control-Allow-Origin":  "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }

    def _send(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in self._cors_headers().items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in self._cors_headers().items():
            self.send_header(k, v)
        self.end_headers()

    def do_POST(self):
        if TOKEN:
            auth = self.headers.get("Authorization", "")
            if auth != f"Bearer {TOKEN}":
                self._send(401, {"error": {"message": "unauthorized"}})
                return

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._send(400, {"error": {"message": "bad request"}})
            return

        system   = body.get("system", "")
        messages = body.get("messages", [])
        max_tok  = body.get("max_tokens", 600)

        ollama_msgs = []
        if system:
            ollama_msgs.append({"role": "system", "content": system})
        ollama_msgs.extend(messages)

        try:
            r = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model":   MODEL,
                    "messages": ollama_msgs,
                    "stream":  False,
                    "options": {
                        "num_predict": max_tok,
                        "temperature": 0.8,
                    },
                },
                timeout=90,
            )
            r.raise_for_status()
            text = r.json()["message"]["content"].strip()
            self._send(200, {"content": [{"type": "text", "text": text}]})

        except requests.exceptions.ConnectionError:
            self._send(503, {"error": {"message": "ollama not running — sudo systemctl start ollama"}})
        except Exception as e:
            self._send(500, {"error": {"message": str(e)}})


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    with ReusableTCPServer(("", PORT), Handler) as srv:
        print(f"Local companion backend listening on port {PORT}")
        print(f"  Model: {MODEL}")
        print(f"  Phone app URL: http://raspberrypi.local:{PORT}")
        if TOKEN:
            print(f"  Token: required (LOCAL_TOKEN is set)")
        else:
            print(f"  Token: none — open on local network")
        print()
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("Stopped.")
