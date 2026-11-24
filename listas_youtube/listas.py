#!/usr/bin/env python3
"""Crea en un canal de YouTube una lista de reproducción por capítulo de cada libro (plan.json, de
plan.mjs) y les va añadiendo los vídeos hasta agotar la cuota del día; guarda por dónde va en
estado.json y sigue en la siguiente ejecución. Solo usa requests.

  listas.py --auth        autoriza el canal (una vez, en un equipo con navegador): al elegir cuenta,
                          elegir el canal de las listas, no el principal; guarda token.json
  listas.py               crea y rellena listas hasta gastar el presupuesto de cuota
  listas.py --estado      resumen de lo hecho y lo pendiente
  listas.py --comprobar   mira si están las credenciales y si Google las acepta (no gasta cuota)

Necesita client_secret.json (cliente OAuth de tipo «Aplicación de escritorio» con la YouTube Data
API v3 activada) en esta carpeta. Cuota: 10.000 unidades al día; crear una lista o añadir un vídeo
cuesta 50, así que salen unos 190 vídeos diarios.
"""
import argparse
import http.server
import json
import secrets
import sys
import time
import urllib.parse
from pathlib import Path

import requests

DIR = Path(__file__).resolve().parent
SECRET = DIR / 'client_secret.json'
TOKEN = DIR / 'token.json'
PLAN = DIR / 'plan.json'
ESTADO = DIR / 'estado.json'
SCOPE = 'https://www.googleapis.com/auth/youtube'
API = 'https://www.googleapis.com/youtube/v3'
COSTE = 50
# Motivos que son del propio vídeo: se descarta. Con cualquier otro error se salta hasta la próxima
# ejecución, y tras MAX_SEGUIDOS seguidos se para (será de la cuenta o del permiso).
DEL_VIDEO = {'videoNotFound', 'failedPrecondition', 'videoAlreadyInPlaylist'}
MAX_SEGUIDOS = 3


def log(*a):
    print(time.strftime('%Y-%m-%d %H:%M:%S'), *a, flush=True)


def cliente():
    if not SECRET.exists():
        sys.exit('Sin configurar: falta client_secret.json. Pasos en README.md, «Puesta en marcha».')
    c = json.loads(SECRET.read_text())
    return c.get('installed') or c.get('web')


def autorizar():
    """Flujo OAuth con redirección a 127.0.0.1: abre el navegador y guarda el refresh token."""
    c = cliente()
    codigo = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            codigo.update(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write('Listo: ya puedes cerrar esta pestaña.'.encode())

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(('127.0.0.1', 0), H)
    redirect = f'http://127.0.0.1:{srv.server_port}'
    state = secrets.token_urlsafe(16)
    url = c['auth_uri'] + '?' + urllib.parse.urlencode({
        'client_id': c['client_id'], 'redirect_uri': redirect, 'response_type': 'code', 'scope': SCOPE,
        'access_type': 'offline', 'prompt': 'select_account consent', 'state': state})
    print('Abre esta dirección y, al elegir cuenta, elige el CANAL de las listas:\n\n' + url + '\n')
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception:
        pass
    while 'code' not in codigo and 'error' not in codigo:
        srv.handle_request()
    if codigo.get('state', [''])[0] != state or 'code' not in codigo:
        sys.exit(f'Autorización fallida: {codigo}')
    r = requests.post(c['token_uri'], data={
        'code': codigo['code'][0], 'client_id': c['client_id'], 'client_secret': c['client_secret'],
        'redirect_uri': redirect, 'grant_type': 'authorization_code'}, timeout=30)
    r.raise_for_status()
    tok = r.json()
    if 'refresh_token' not in tok:
        sys.exit('Google no devolvió refresh_token; revoca el acceso en myaccount.google.com y repite.')
    TOKEN.write_text(json.dumps({'refresh_token': tok['refresh_token']}))
    TOKEN.chmod(0o600)
    s = sesion()
    canal = s.get(f'{API}/channels', params={'part': 'snippet', 'mine': 'true'}, timeout=30).json()
    nombre = canal.get('items', [{}])[0].get('snippet', {}).get('title', '?')
    print(f'Guardado {TOKEN}. Canal autorizado: «{nombre}».')


def sesion():
    c = cliente()
    if not TOKEN.exists():
        sys.exit('Sin autorizar: falta token.json. Ejecuta «listas.py --auth» en el escritorio y cópialo aquí.')
    r = requests.post(c['token_uri'], data={
        'refresh_token': json.loads(TOKEN.read_text())['refresh_token'], 'client_id': c['client_id'],
        'client_secret': c['client_secret'], 'grant_type': 'refresh_token'}, timeout=30)
    if r.status_code == 400 and 'invalid_grant' in r.text:
        sys.exit('Autorización caducada o revocada (en modo «Prueba» dura 7 días): repite «listas.py --auth» '
                 'en el escritorio, copia token.json aquí y publica la app en Google Cloud.')
    if r.status_code != 200:
        sys.exit(f'No se pudo renovar el acceso ({r.status_code} {r.text[:200]}): repite «listas.py --auth».')
    s = requests.Session()
    s.headers['Authorization'] = 'Bearer ' + r.json()['access_token']
    return s


def leer_estado():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text())
    return {'listas': {}, 'hechos': {}, 'fallidos': {}}


def guardar(est):
    tmp = ESTADO.with_suffix('.tmp')
    tmp.write_text(json.dumps(est, ensure_ascii=False, indent=1))
    tmp.replace(ESTADO)


class SinCuota(Exception):
    pass


def razon(r):
    try:
        return r.json()['error']['errors'][0]['reason']
    except Exception:
        return ''


def llamar(s, metodo, url, **kw):
    """Una llamada a la API; los errores pasajeros se reintentan, la falta de cuota corta el día."""
    for intento in range(4):
        r = s.request(metodo, url, timeout=60, **kw)
        if r.status_code in (403, 429) and razon(r) in ('quotaExceeded', 'dailyLimitExceeded'):
            raise SinCuota(razon(r))
        ritmo = r.status_code == 429 or (r.status_code == 403 and razon(r) in ('rateLimitExceeded', 'userRateLimitExceeded'))
        if (ritmo or r.status_code in (409, 500, 502, 503)) and intento < 3:
            time.sleep((30 if ritmo else 5) * (intento + 1))
            continue
        return r
    return r


def ejecutar(presupuesto, privacidad):
    plan = json.loads(PLAN.read_text())
    est = leer_estado()
    s = sesion()
    gastado = seguidos = 0
    try:
        for item in plan:
            k = item['key']
            hechos = set(est['hechos'].get(k, []))
            fallidos = set(est['fallidos'].get(k, []))
            pend = [v for v in item['videos'] if v not in hechos and v not in fallidos]
            if not pend:
                continue
            if k not in est['listas']:
                if gastado + COSTE > presupuesto:
                    break
                r = llamar(s, 'POST', f'{API}/playlists', params={'part': 'snippet,status'}, json={
                    'snippet': {'title': item['title'], 'description': item['description'], 'defaultLanguage': 'es'},
                    'status': {'privacyStatus': privacidad}})
                gastado += COSTE
                if r.status_code != 200:
                    guardar(est)
                    resumen(plan, est, gastado)
                    sys.exit(f"No se pudo crear la lista {item['title']}: {r.status_code} {razon(r)} {r.text[:300]}")
                est['listas'][k] = r.json()['id']
                guardar(est)
                log('Lista creada:', item['title'])
            for v in pend:
                if gastado + COSTE > presupuesto:
                    raise SinCuota('presupuesto del día')
                r = llamar(s, 'POST', f'{API}/playlistItems', params={'part': 'snippet'}, json={
                    'snippet': {'playlistId': est['listas'][k], 'resourceId': {'kind': 'youtube#video', 'videoId': v}}})
                gastado += COSTE
                if r.status_code == 200:
                    est['hechos'].setdefault(k, []).append(v)
                elif r.status_code == 404 and razon(r) == 'playlistNotFound':
                    # La lista se borró a mano: se vuelve a crear entera en la próxima ejecución.
                    log('La lista ya no existe, se rehará:', item['title'])
                    est['listas'].pop(k, None)
                    est['hechos'].pop(k, None)
                    guardar(est)
                    break
                elif razon(r) in DEL_VIDEO:
                    # Vídeo borrado, privado o no insertable: no se reintenta.
                    est['fallidos'].setdefault(k, []).append(v)
                    log('Vídeo descartado', v, razon(r))
                else:
                    seguidos += 1
                    detalle = f'{v}: {r.status_code} {razon(r)} {r.text[:300]}'
                    if r.status_code == 401 or seguidos >= MAX_SEGUIDOS:
                        guardar(est)
                        resumen(plan, est, gastado)
                        sys.exit(f'La API rechaza los vídeos, se para: {detalle}')
                    log('Error, se salta por hoy:', detalle)
                    continue
                seguidos = 0
                guardar(est)
    except SinCuota as e:
        log('Parada por cuota:', e)
    guardar(est)
    resumen(plan, est, gastado)


def resumen(plan=None, est=None, gastado=None):
    plan = plan or json.loads(PLAN.read_text())
    est = est or leer_estado()
    total = sum(len(p['videos']) for p in plan)
    hechos = sum(len(est['hechos'].get(p['key'], [])) for p in plan)
    fallidos = sum(len(est['fallidos'].get(p['key'], [])) for p in plan)
    listas = sum(1 for p in plan if p['key'] in est['listas'])
    pend = total - hechos - fallidos
    extra = f' · {gastado} unidades de cuota gastadas' if gastado is not None else ''
    log(f'{listas}/{len(plan)} listas · {hechos}/{total} vídeos añadidos · {fallidos} descartados · '
        f'faltan {pend} (≈ {(pend + 189) // 190} días){extra}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--auth', action='store_true', help='autorizar el canal y guardar token.json')
    ap.add_argument('--estado', action='store_true', help='mostrar el progreso')
    ap.add_argument('--comprobar', action='store_true', help='comprobar las credenciales y salir')
    ap.add_argument('--presupuesto', type=int, default=9500, help='unidades de cuota a gastar (9500)')
    ap.add_argument('--privacidad', default='public', choices=['public', 'unlisted', 'private'])
    a = ap.parse_args()
    if a.auth:
        autorizar()
    elif a.comprobar:
        sesion()
    elif a.estado:
        resumen()
    else:
        ejecutar(a.presupuesto, a.privacidad)
