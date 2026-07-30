#!/usr/bin/env python3
"""The Hardline — read-only status webapp for the open-events queue.

Serves a single auto-refreshing page (plus a small JSON API) showing every
Hardline event currently open (queued/dispatched/orphaned/resumed/requeued),
across all projects, so it can be checked from any browser on this machine
instead of running `bin/matrix hardline status` by hand.

Read-only: this process never writes to queue.jsonl. Binds to 127.0.0.1 only
(localhost), matching the "solo esta maquina" scope this tool was built for --
it is not meant to be exposed on the network. Stdlib only, no new dependency,
matching the rest of this module (telegram-bridge.py, hardline-monitor.sh).
"""

import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[2]
QUEUE_PATH = ROOT / "brain" / "state" / "hardline" / "queue.jsonl"

HOST = "127.0.0.1"
PORT = int(os.environ.get("MATRIX_HARDLINE_WEBAPP_PORT", "8765"))
POLL_SECONDS = int(os.environ.get("MATRIX_HARDLINE_WEBAPP_POLL_SECONDS", "3"))

OPEN_STATES = {"queued", "dispatched", "orphaned", "resumed", "requeued"}

PAGE_TEMPLATE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hardline — eventos abiertos</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #0b0f14; color: #d7e0ea; }}
  h1, h2 {{ font-size: 1.3rem; margin-bottom: 0.25rem; }}
  h2 {{ margin-top: 1.5rem; }}
  #meta {{ color: #7d8b9a; font-size: 0.85rem; margin-bottom: 1rem; }}
  #services {{ margin: 0.75rem 0; font-size: 0.9rem; }}
  .svc {{ display: inline-block; margin-right: 1.5rem; }}
  .status-ok {{ color: #7ce87c; }}
  .status-bad {{ color: #ff9b9b; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #1e2733; font-size: 0.9rem; }}
  th {{ color: #9fb2c7; font-weight: 600; }}
  tr:hover {{ background: #121a24; }}
  .state {{ padding: 0.15rem 0.5rem; border-radius: 0.4rem; font-size: 0.8rem; }}
  .state-queued {{ background: #2a3a4d; color: #8ec6ff; }}
  .state-dispatched {{ background: #33440f; color: #c9e874; }}
  .state-orphaned {{ background: #4d1f1f; color: #ff9b9b; }}
  .state-resumed, .state-requeued {{ background: #3a2f4d; color: #cbb0ff; }}
  #empty {{ color: #7d8b9a; padding: 1rem 0; display: none; }}
</style>
</head>
<body>
<h1>Hardline — eventos abiertos</h1>
<div id="meta">Actualiza cada {poll}s &middot; ultima actualizacion: <span id="ts">-</span></div>
<div id="services">
  <span class="svc">Monitor: <span id="svc-monitor">-</span></span>
  <span class="svc">Bridge: <span id="svc-bridge">-</span></span>
</div>
<h2>Proyectos conectados</h2>
<table id="connected-table">
  <thead>
    <tr><th>Proyecto</th><th>Path</th><th>Estado</th></tr>
  </thead>
  <tbody id="connected-rows"></tbody>
</table>
<h2>Eventos abiertos</h2>
<table>
  <thead>
    <tr><th>Evento</th><th>Proyecto</th><th>Estado</th><th>Encolado</th><th>Sesion</th></tr>
  </thead>
  <tbody id="rows"></tbody>
</table>
<div id="empty">No hay eventos abiertos.</div>
<script>
async function refresh() {{
  try {{
    const res = await fetch('/api/events');
    const data = await res.json();
    const rows = document.getElementById('rows');
    const empty = document.getElementById('empty');
    rows.innerHTML = '';
    if (data.events.length === 0) {{
      empty.style.display = 'block';
    }} else {{
      empty.style.display = 'none';
      for (const ev of data.events) {{
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${{ev.event_id}}</td><td>${{ev.project}}</td>` +
          `<td><span class="state state-${{ev.state}}">${{ev.state}}</span></td>` +
          `<td>${{ev.queued_at || '-'}}</td><td>${{ev.session_id || '-'}}</td>`;
        rows.appendChild(tr);
      }}
    }}
    document.getElementById('ts').textContent = new Date().toLocaleTimeString();
  }} catch (e) {{
    document.getElementById('meta').textContent = 'Error consultando /api/events: ' + e;
  }}
}}
async function refreshConnected() {{
  try {{
    const res = await fetch('/api/connected');
    const data = await res.json();
    const monitor = document.getElementById('svc-monitor');
    const bridge = document.getElementById('svc-bridge');
    const mRun = data.services && data.services.monitor && data.services.monitor.running;
    const bRun = data.services && data.services.bridge && data.services.bridge.running;
    monitor.textContent = mRun ? 'running' : 'stopped';
    monitor.className = mRun ? 'status-ok' : 'status-bad';
    bridge.textContent = bRun ? 'running' : 'stopped';
    bridge.className = bRun ? 'status-ok' : 'status-bad';
    const tbody = document.getElementById('connected-rows');
    tbody.innerHTML = '';
    if (data.projects && data.projects.length > 0) {{
      for (const p of data.projects) {{
        const tr = document.createElement('tr');
        const mark = p.bound ? '✓' : '✗';
        const text = p.bound ? 'bound' : 'not bound';
        const cls = p.bound ? 'status-ok' : 'status-bad';
        tr.innerHTML = `<td>${{p.name}}</td><td>${{p.path}}</td><td><span class="${{cls}}">${{mark}} ${{text}}</span></td>`;
        tbody.appendChild(tr);
      }}
    }}
  }} catch (e) {{
    document.getElementById('svc-monitor').textContent = 'error';
    document.getElementById('svc-bridge').textContent = 'error';
  }}
}}
refreshConnected();
refresh();
setInterval(refreshConnected, {poll_ms});
setInterval(refresh, {poll_ms});
</script>
</body>
</html>
"""


def read_open_events(project_filter=None):
    events = {}
    if QUEUE_PATH.exists():
        with QUEUE_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event_id = event.get("event_id")
                if event_id:
                    events[event_id] = event  # later lines win (state transitions)

    open_events = [
        e for e in events.values()
        if e.get("state") in OPEN_STATES
        and (project_filter is None or e.get("project") == project_filter)
    ]
    open_events.sort(key=lambda e: e.get("queued_at") or "", reverse=True)
    return open_events


def read_connected():
    """Return bound-project and service-status data by reusing the CLI.

    This keeps a single source of truth for "is this project bound?" and
    "is this service alive?" in bash; the webapp only consumes it.
    """
    try:
        bindings_out = subprocess.run(
            [str(ROOT / "bin" / "matrix"), "bindings", "--json"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        bindings_out = None

    try:
        services_out = subprocess.run(
            [str(ROOT / "modules" / "hardline" / "hardline-ctl.sh"), "status", "--json"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        services_out = None

    projects = []
    if bindings_out is not None and bindings_out.returncode == 0:
        try:
            projects = json.loads(bindings_out.stdout)
        except json.JSONDecodeError:
            pass

    services = {}
    if services_out is not None and services_out.returncode == 0:
        try:
            services = json.loads(services_out.stdout)
        except json.JSONDecodeError:
            pass

    return {"projects": projects, "services": services}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep stdout quiet; this is a read-only local status tool

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/":
            body = PAGE_TEMPLATE.format(poll=POLL_SECONDS, poll_ms=POLL_SECONDS * 1000).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/events":
            qs = parse_qs(parsed.query)
            project_filter = qs.get("project", [None])[0]
            events = read_open_events(project_filter)
            body = json.dumps({"events": events}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/connected":
            body = json.dumps(read_connected()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"not found")


def main():
    server = HTTPServer((HOST, PORT), Handler)
    print(f"[hardline-webapp] serving read-only status on http://{HOST}:{PORT} (Ctrl-C to stop)")
    print(f"[hardline-webapp] reading {QUEUE_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
