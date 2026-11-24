#!/usr/bin/env python3
"""
Script Name: servidor_web.py (pepecono)
Description: Web mínima para arrancar el servidor en Proxmox o Windows desde el móvil (LAN o Tailscale).
             Lanza arrancar_servidor.sh en segundo plano y muestra su progreso; el final llega por Telegram.
Uso:         servidor_web.py [puerto]   (por defecto 8781)
API:         GET  /estado                       -> {"estado": "proxmox|windows|apagado", "en_curso": bool}
             GET  /log                          -> últimas líneas del arranque en curso o del último
             POST /arrancar?destino=windows[&forzar=1]   (sirve también para Tasker)
"""
import html
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SCRIPT = Path.home() / "Scripts/servidor/arrancar_servidor.sh"
LOG = Path.home() / ".cache/arrancar_servidor.log"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8781
DESTINOS = ("proxmox", "windows")

proceso = None

PAGINA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Servidor</title>
<style>
body{font-family:system-ui,sans-serif;background:#1e1e2e;color:#cdd6f4;margin:0;padding:24px 16px;max-width:480px;margin:auto}
h1{font-size:1.3rem;margin:0 0 4px}
#estado{color:#a6adc8;margin-bottom:24px}
button{display:block;width:100%;font-size:1.3rem;padding:22px;margin:0 0 14px;border:0;border-radius:14px;color:#1e1e2e;font-weight:600}
#proxmox{background:#fab387}#windows{background:#89b4fa}
button:disabled{opacity:.4}
pre{background:#181825;padding:12px;border-radius:10px;white-space:pre-wrap;min-height:3em;color:#bac2de}
</style></head><body>
<h1>Servidor 192.168.1.222</h1>
<div id="estado">Comprobando…</div>
<button id="proxmox">Proxmox</button>
<button id="windows">Windows</button>
<pre id="log"></pre>
<script>
const NOMBRES={proxmox:"Proxmox",windows:"Windows",apagado:"Apagado"};
let estado=null;
async function refrescar(){
  try{
    const e=await (await fetch("estado")).json();
    estado=e.estado;
    document.getElementById("estado").textContent="Ahora: "+NOMBRES[e.estado]+(e.en_curso?" · arrancando…":"");
    for(const b of document.querySelectorAll("button")) b.disabled=e.en_curso;
    document.getElementById("log").textContent=await (await fetch("log")).text();
  }catch(err){document.getElementById("estado").textContent="Sin conexión con pepecono";}
}
async function arrancar(destino){
  let forzar=0;
  if(estado && estado!=="apagado" && estado!==destino){
    if(!confirm(NOMBRES[estado]+" está encendido: ¿reiniciar en "+NOMBRES[destino]+"?")) return;
    forzar=1;
  }
  const r=await fetch("arrancar?destino="+destino+"&forzar="+forzar,{method:"POST"});
  if(!r.ok) alert(await r.text());
  refrescar();
}
for(const d of ["proxmox","windows"]) document.getElementById(d).onclick=()=>arrancar(d);
refrescar();setInterval(refrescar,4000);
</script></body></html>"""


def en_curso():
    return proceso is not None and proceso.poll() is None


class Handler(BaseHTTPRequestHandler):
    def responder(self, codigo, cuerpo, tipo="text/plain; charset=utf-8"):
        datos = cuerpo.encode()
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        ruta = urlparse(self.path).path
        if ruta == "/":
            self.responder(200, PAGINA, "text/html; charset=utf-8")
        elif ruta == "/estado":
            salida = subprocess.run([SCRIPT, "estado"], capture_output=True, text=True, timeout=20)
            cuerpo = {"estado": salida.stdout.strip() or "apagado", "en_curso": en_curso()}
            self.responder(200, json.dumps(cuerpo), "application/json")
        elif ruta == "/log":
            texto = LOG.read_text(errors="replace") if LOG.exists() else ""
            self.responder(200, "\n".join(texto.splitlines()[-15:]))
        else:
            self.responder(404, "No encontrado")

    def do_POST(self):
        global proceso
        url = urlparse(self.path)
        if url.path != "/arrancar":
            return self.responder(404, "No encontrado")
        params = parse_qs(url.query)
        destino = params.get("destino", [""])[0]
        if destino not in DESTINOS:
            return self.responder(400, "Destino no válido: " + html.escape(destino))
        if en_curso():
            return self.responder(409, "Ya hay un arranque en curso")
        args = [SCRIPT, destino]
        if params.get("forzar", ["0"])[0] == "1":
            args.append("--forzar")
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("w") as log:
            proceso = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        self.responder(202, "Arrancando " + destino)

    def log_message(self, formato, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), formato % args))


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
