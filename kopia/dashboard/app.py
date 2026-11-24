#!/usr/bin/env python3
"""Dashboard local de estado y control de los backups Kopia (arcolinux + pepecono)."""
import json
import os
import subprocess
import threading
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, jsonify, Response, request

app = Flask(__name__)

HOME = "/home/pepe"
STATUS_DIR = f"{HOME}/.cache/kopia-status"
KOPIA_UI_URL = "https://192.168.1.89:51515"

ARCOLINUX_SOURCES = [
    ("chezmoi", "/home/huan/.local/share/chezmoi"),
    ("Scripts", "/home/huan/Scripts"),
    ("pollo (untracked)", "/home/huan/.cache/kopia-untracked-staging/pollo"),
    ("/etc/fstab", "/etc/fstab"),
    ("/etc/ssh/sshd_config", "/etc/ssh/sshd_config"),
]

PEPECONO_SOURCES = [
    ("chezmoi", "pepe@pepe-cono:/home/pepe/.local/share/chezmoi"),
    ("Scripts", "pepe@pepe-cono:/home/pepe/Scripts"),
    ("hugo/web", "pepe@pepe-cono:/home/pepe/hugo/web"),
    ("pollo (untracked)", "pepe@pepe-cono:/home/pepe/.cache/kopia-untracked-staging/pollo"),
    ("/etc/fstab", "pepe@pepe-cono:/etc/fstab"),
    ("/etc/ssh/sshd_config", "pepe@pepe-cono:/etc/ssh/sshd_config"),
    ("/etc/exports", "pepe@pepe-cono:/etc/exports"),
    ("contenedores", "pepe@pepe-cono:/home/pepe/contenedores"),
]

DAYS = 7

_running_lock = threading.Lock()
_running = {}


# --- auth -------------------------------------------------------------

def _load_credentials():
    env_file = f"{HOME}/Scripts/kopia/.encrypted.env"
    out = subprocess.run(["sops", "--decrypt", env_file], capture_output=True, text=True, timeout=15)
    user = password = None
    for line in out.stdout.splitlines():
        if line.startswith("DASHBOARD_USER="):
            user = line.split("=", 1)[1]
        elif line.startswith("DASHBOARD_PASSWORD="):
            password = line.split("=", 1)[1]
    return user, password


DASH_USER, DASH_PASSWORD = _load_credentials()


def requires_auth(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != DASH_USER or auth.password != DASH_PASSWORD:
            return Response(
                "Autenticacion requerida", 401,
                {"WWW-Authenticate": 'Basic realm="Backups"'},
            )
        return f(*args, **kwargs)
    return wrapped


# --- helpers ------------------------------------------------------------

def human_size(n):
    if n is None:
        return "—"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def entries_to_info(entries):
    """entries: lista de snapshots (json de kopia). -> (days, latest_iso, size_bytes)"""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    times = []
    for e in entries:
        st = e.get("startTime", "")
        st = st.split(".")[0] + "+00:00" if "." in st else st.replace("Z", "+00:00")
        try:
            times.append((datetime.fromisoformat(st), e))
        except ValueError:
            continue
    days = []
    for d in range(DAYS - 1, -1, -1):
        day_start = today - timedelta(days=d)
        day_end = day_start + timedelta(days=1)
        days.append(any(day_start <= t < day_end for t, _ in times))
    latest = None
    size = None
    if times:
        t, e = max(times, key=lambda x: x[0])
        latest = t.isoformat()
        size = e.get("stats", {}).get("totalSize")
    return days, latest, size


def kopia_list_local(source_path):
    try:
        out = subprocess.run(
            ["kopia", "snapshot", "list", source_path, "--json"],
            capture_output=True, text=True, timeout=30,
        )
        return json.loads(out.stdout) if out.stdout.strip() else []
    except Exception:
        return None


def kopia_list_remote_arcolinux():
    """Un solo SSH que devuelve el listado de todas las fuentes de arcolinux,
    porque kopia aplica ACL por usuario y pepe no puede verlas via el repo."""
    try:
        out = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "dashboard-arcolinux", "kopia-snapshots"],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return None, False
    if out.returncode != 0:
        return None, False
    result = {}
    current = None
    buf = []
    for line in out.stdout.splitlines():
        if line.startswith("### "):
            if current is not None:
                result[current] = "\n".join(buf)
            current = line[4:].strip()
            buf = []
        else:
            buf.append(line)
    if current is not None:
        result[current] = "\n".join(buf)
    parsed = {}
    for path, raw in result.items():
        try:
            parsed[path] = json.loads(raw) if raw.strip() else []
        except Exception:
            parsed[path] = None
    return parsed, True


def run_bg(task_id, cmd):
    def _run():
        try:
            subprocess.run(cmd, timeout=1800)
        finally:
            with _running_lock:
                _running.pop(task_id, None)
    with _running_lock:
        if _running.get(task_id):
            return False
        _running[task_id] = True
    threading.Thread(target=_run, daemon=True).start()
    return True


def is_running(task_id):
    with _running_lock:
        return bool(_running.get(task_id))


def read_local_status():
    result = {}
    if not os.path.isdir(STATUS_DIR):
        return result
    for fname in os.listdir(STATUS_DIR):
        if fname.endswith(".json"):
            try:
                with open(f"{STATUS_DIR}/{fname}") as f:
                    data = json.load(f)
                result[data.get("task", fname)] = data
            except Exception:
                continue
    return result


def read_remote_status():
    try:
        out = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "dashboard-arcolinux", "status"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:
        return {}, False
    if out.returncode != 0:
        return {}, False
    result = {}
    for line in out.stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            result[data.get("task", line)] = data
        except Exception:
            continue
    return result, True


# --- routes ---------------------------------------------------------------

@app.route("/api/status")
def api_status():
    local_status = read_local_status()
    remote_status, arcolinux_reachable = read_remote_status()
    arcolinux_snapshots, _ = kopia_list_remote_arcolinux()

    hosts = []

    pepecono_src = []
    for label, path in PEPECONO_SOURCES:
        entries = kopia_list_local(path)
        if entries is None:
            pepecono_src.append({"label": label, "days": [False] * DAYS, "latest": None, "size": None, "error": True})
        else:
            days, latest, size = entries_to_info(entries)
            pepecono_src.append({"label": label, "days": days, "latest": latest, "size": human_size(size), "error": False})
    hosts.append({"host": "pepecono", "reachable": True, "sources": pepecono_src, "last_run": local_status})

    arcolinux_src = []
    for label, path in ARCOLINUX_SOURCES:
        entries = (arcolinux_snapshots or {}).get(path)
        if entries is None:
            arcolinux_src.append({"label": label, "days": [False] * DAYS, "latest": None, "size": None, "error": True})
        else:
            days, latest, size = entries_to_info(entries)
            arcolinux_src.append({"label": label, "days": days, "latest": latest, "size": human_size(size), "error": False})
    hosts.append({"host": "arcolinux", "reachable": arcolinux_reachable, "sources": arcolinux_src, "last_run": remote_status})

    return jsonify({
        "hosts": hosts,
        "kopia_ui_url": KOPIA_UI_URL,
        "running": {
            "pepecono_snapshot": is_running("pepecono_snapshot"),
            "arcolinux_snapshot": is_running("arcolinux_snapshot"),
            "wake_proxmox": is_running("wake_proxmox"),
        },
    })


@app.route("/api/logs/<host>")
def api_logs(host):
    if host == "pepecono":
        try:
            with open(f"{STATUS_DIR}/Snapshot_pepecono.log") as f:
                return Response(f.read(), mimetype="text/plain")
        except FileNotFoundError:
            return Response("(sin log todavia)", mimetype="text/plain")
    elif host == "arcolinux":
        out = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "dashboard-arcolinux", "log"],
            capture_output=True, text=True, timeout=15,
        )
        return Response(out.stdout or "(sin log / no alcanzable)", mimetype="text/plain")
    return Response("host desconocido", status=404, mimetype="text/plain")


@app.route("/api/trigger/snapshot/pepecono", methods=["POST"])
def trigger_pepecono():
    ok = run_bg("pepecono_snapshot", [
        f"{HOME}/Scripts/kopia/kopia-notify.sh", "Snapshot pepecono", "--",
        f"{HOME}/Scripts/kopia/snapshot_pepecono.sh",
    ])
    return jsonify({"started": ok})


@app.route("/api/trigger/snapshot/arcolinux", methods=["POST"])
def trigger_arcolinux():
    ok = run_bg("arcolinux_snapshot", ["ssh", "-o", "ConnectTimeout=5", "dashboard-arcolinux", "snapshot"])
    return jsonify({"started": ok})


@app.route("/api/trigger/wake-proxmox", methods=["POST"])
def trigger_wake():
    ok = run_bg("wake_proxmox", [
        f"{HOME}/Scripts/kopia/kopia-notify.sh", "Despertar proxmox manual", "--",
        f"{HOME}/Scripts/kopia/wake_proxmox.sh",
    ])
    return jsonify({"started": ok})


PAGE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Backups</title>
<style>
  :root { color-scheme: dark; }
  body { font-family: system-ui, sans-serif; background: #14161a; color: #e6e6e6; margin: 0; padding: 2rem; }
  h1 { font-size: 1.4rem; margin-bottom: .3rem; }
  .sub { color: #888; margin-bottom: 1.5rem; font-size: .85rem; }
  .sub a { color: #7aa2f7; }
  .host { background: #1d2026; border-radius: 10px; padding: 1rem 1.3rem; margin-bottom: 1.2rem; }
  .host h2 { margin: 0 0 .6rem; font-size: 1.05rem; display:flex; align-items:center; gap:.5rem; }
  .badge { font-size: .7rem; padding: .15rem .5rem; border-radius: 20px; }
  .ok { background: #163d24; color: #6fd88f; }
  .bad { background: #431a1a; color: #f28b8b; }
  table { width: 100%; border-collapse: collapse; font-size: .85rem; }
  td, th { padding: .3rem .5rem; text-align: left; }
  th { color: #888; font-weight: 500; font-size: .75rem; }
  .dot { font-size: .95rem; }
  .size { color: #999; }
  .actions { margin-top: 1.5rem; display: flex; gap: .6rem; flex-wrap: wrap; }
  button, .linkbtn { background: #2a2f3a; color: #e6e6e6; border: 1px solid #3a4050; padding: .5rem 1rem;
           border-radius: 8px; cursor: pointer; font-size: .85rem; text-decoration: none; display: inline-block; }
  button:hover, .linkbtn:hover { background: #343b48; }
  button:disabled { opacity: .5; cursor: default; }
  pre { background: #0d0f12; padding: 1rem; border-radius: 8px; max-height: 400px; overflow: auto;
        font-size: .78rem; white-space: pre-wrap; }
  .last-run { font-size: .78rem; color: #999; margin-top: .4rem; }
</style></head>
<body>
<h1>Estado de backups</h1>
<div class="sub" id="sub">arcolinux + pepecono, via repo Kopia compartido. Se actualiza cada 15s.</div>
<div id="hosts"></div>
<div class="actions">
  <button onclick="trigger('snapshot/pepecono')">Snapshot pepecono ahora</button>
  <button onclick="trigger('snapshot/arcolinux')">Snapshot arcolinux ahora</button>
  <button onclick="trigger('wake-proxmox')">Despertar proxmox</button>
</div>
<h3 style="margin-top:2rem">Log</h3>
<div class="actions">
  <button onclick="showLog('pepecono')">Ver log pepecono</button>
  <button onclick="showLog('arcolinux')">Ver log arcolinux</button>
</div>
<pre id="log">(elige un log)</pre>

<script>
const DAYS = __DAYS__;

async function load() {
  const r = await fetch('/api/status');
  const data = await r.json();
  document.getElementById('sub').innerHTML =
    'arcolinux + pepecono, via repo Kopia compartido. Se actualiza cada 15s. ' +
    '<a href="' + data.kopia_ui_url + '" target="_blank">Abrir Kopia UI (repo compartido, pide credenciales)</a>';
  const div = document.getElementById('hosts');
  div.innerHTML = data.hosts.map(h => {
    const rows = h.sources.map(s => {
      const dots = s.days.map(d => '<span class="dot">' + (d ? '✅' : '❌') + '</span>').join(' ');
      return '<tr><td>' + s.label + '</td><td>' + dots + '</td><td>' + (s.latest ? new Date(s.latest).toLocaleString('es') : '—') + '</td><td class="size">' + (s.size || '—') + '</td></tr>';
    }).join('');
    const lastRun = Object.values(h.last_run || {})[0];
    const lastRunTxt = lastRun
      ? ('Ultimo run: ' + lastRun.task + ' — ' + (lastRun.exit_code === 0 ? 'OK' : 'FALLO') + ' (' + lastRun.duration_s + 's) — ' + new Date(lastRun.finished_at).toLocaleString('es'))
      : 'Sin runs registrados todavia';
    return '<div class="host"><h2>' + h.host + ' <span class="badge ' + (h.reachable ? 'ok' : 'bad') + '">' +
      (h.reachable ? 'alcanzable' : 'no alcanzable') + '</span></h2>' +
      '<table><tr><th>Fuente</th><th>Ultimos ' + DAYS + ' dias</th><th>Ultimo snapshot</th><th>Tamano</th></tr>' + rows + '</table>' +
      '<div class="last-run">' + lastRunTxt + '</div></div>';
  }).join('');
}

async function trigger(path) {
  await fetch('/api/trigger/' + path, {method: 'POST'});
  load();
}

async function showLog(host) {
  const r = await fetch('/api/logs/' + host);
  document.getElementById('log').textContent = await r.text();
}

load();
setInterval(load, 15000);
</script>
</body></html>"""

PAGE = PAGE.replace("__DAYS__", str(DAYS))


@app.route("/")
def index():
    return Response(PAGE, mimetype="text/html")


# Aplica autenticacion basica a TODAS las rutas.
for endpoint, view_func in list(app.view_functions.items()):
    app.view_functions[endpoint] = requires_auth(view_func)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8790)
