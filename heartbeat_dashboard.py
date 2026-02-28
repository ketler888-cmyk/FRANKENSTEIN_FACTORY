import argparse
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

DEFAULT_HEARTBEAT = os.path.join(os.path.dirname(__file__), "ops", "heartbeat.json")

def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"ok": False, "error": str(e), "path": path, "ts": time.time()}

class Handler(BaseHTTPRequestHandler):
    heartbeat_path = DEFAULT_HEARTBEAT

    def _send(self, code, body, ctype):
        data = body.encode("utf-8", errors="replace")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            hb = _read_json(self.heartbeat_path)
            pretty = json.dumps(hb, ensure_ascii=False, indent=2)
            html = f"""<!doctype html>
<html><head>
<meta charset="utf-8"/>
<meta http-equiv="refresh" content="2"/>
<title>FRANKENSTEIN Heartbeat</title>
<style>
body {{ font-family: Consolas, monospace; margin: 16px; }}
pre  {{ background: #111; color: #eee; padding: 12px; border-radius: 8px; overflow: auto; }}
.small {{ color: #666; font-size: 12px; }}
</style>
</head><body>
<h2>FRANKENSTEIN Heartbeat</h2>
<div class="small">file: {self.heartbeat_path}</div>
<pre>{pretty}</pre>
<div class="small">auto-refresh: 2s</div>
</body></html>"""
            return self._send(200, html, "text/html")
        if p == "/api/heartbeat":
            hb = _read_json(self.heartbeat_path)
            return self._send(200, json.dumps(hb, ensure_ascii=False), "application/json")
        return self._send(404, "Not Found", "text/plain")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--heartbeat", type=str, default=DEFAULT_HEARTBEAT)
    args = ap.parse_args()

    Handler.heartbeat_path = args.heartbeat
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"[heartbeat_dashboard] http://127.0.0.1:{args.port}/  (heartbeat={args.heartbeat})", flush=True)
    srv.serve_forever()

if __name__ == "__main__":
    main()
