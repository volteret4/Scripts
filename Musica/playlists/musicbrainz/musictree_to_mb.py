#!/usr/bin/env python3
"""
musicbrainz_series.py
─────────────────────
1. Descarga y parsea https://www.musicgenretree.org/text_classics.html
2. Busca cada álbum en MusicBrainz con reintentos y backoff ante errores SSL
3. Crea una Serie ("Music Genre Tree – Classics") y añade los álbumes encontrados

Requisitos:
    pip install requests beautifulsoup4 urllib3

Uso:
    # Modo de prueba (solo imprime lo que haría, sin tocar MB)
    python musicbrainz_series.py --dry-run

    # Parsear + buscar en MB + exportar CSV con resultados
    python musicbrainz_series.py --export-csv resultados.csv

    # Reanudar una búsqueda interrumpida (solo procesa pending/error)
    python musicbrainz_series.py --load-csv resultados.csv --export-csv resultados.csv

    # Crear la serie real en MusicBrainz
    python musicbrainz_series.py --username TU_USUARIO --password TU_CONTRASEÑA

    # Solo añadir a una serie ya existente
    python musicbrainz_series.py --load-csv resultados.csv \\
        --username TU_USUARIO --password TU_CONTRASEÑA \\
        --series-mbid <MBID>
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
from dataclasses import dataclass
from typing import Optional

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

# ─── Constantes ────────────────────────────────────────────────────────────────

SOURCE_URL = "https://www.musicgenretree.org/text_classics.html"

MB_HEADERS = {
    "User-Agent": "MusicGenreTreeImporter/1.0 (frodobolson@disroot.org)",
    "Accept": "application/json",
}

# Mirrors de MusicBrainz — se rotan ante errores SSL/red
MB_MIRRORS = [
    "https://musicbrainz.org/ws/2",
    "https://beta.musicbrainz.org/ws/2",
]

# UUID e ID entero del tipo de relación "release group series part"
REL_TYPE_UUID    = "01018437-91d8-3b4c-9d72-c0e69ee8dede"
REL_TYPE_INT_ID  = 742   # integer ID en la BD de MB
ATTR_ORDER_UUID  = "a59c5830-5ec7-38fe-9a21-c7ea54f6650a"  # número de orden
EDIT_CREATE_REL  = 90    # EditRelationship::Create

SERIES_NAME    = "Music Genre Tree – Classics"
SERIES_COMMENT = (
    "Canonical album list from musicgenretree.org – "
    "one representative release per genre."
)

# Tiempos
RATE_LIMIT_SLEEP = 1.2   # segundos entre peticiones (MB permite 1/s)
MAX_RETRIES      = 5     # intentos por petición ante errores de red
BACKOFF_BASE     = 2.0   # segundos base para backoff exponencial

# ─── Sesión HTTP con reintentos ─────────────────────────────────────────────────

def make_session(verify_ssl: bool = True) -> requests.Session:
    """Crea una sesión requests con reintentos automáticos de urllib3."""
    session = requests.Session()
    session.headers.update(MB_HEADERS)
    session.verify = verify_ssl

    retry = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://",  adapter)
    return session


# Sesión global (se recrea si hay fallo SSL persistente)
_api_session: Optional[requests.Session] = None
_ssl_disabled = False


def get_api_session() -> requests.Session:
    global _api_session
    if _api_session is None:
        _api_session = make_session(verify_ssl=True)
    return _api_session


def mb_get(endpoint: str, params: dict) -> Optional[dict]:
    """
    GET a la API de MusicBrainz con reintentos manuales, backoff
    exponencial y rotación de mirrors ante errores SSL.

    Devuelve el JSON parseado o None si todos los intentos fallan.
    """
    global _api_session, _ssl_disabled

    for attempt in range(1, MAX_RETRIES + 1):
        # Rotar mirrors en cada intento
        base = MB_MIRRORS[(attempt - 1) % len(MB_MIRRORS)]
        url  = f"{base}{endpoint}"

        try:
            r = get_api_session().get(url, params=params, timeout=30)
            r.raise_for_status()
            time.sleep(RATE_LIMIT_SLEEP)
            return r.json()

        except requests.exceptions.SSLError:
            wait = BACKOFF_BASE ** attempt
            print(f"    ⚠  SSL error (intento {attempt}/{MAX_RETRIES}), "
                  f"esperando {wait:.1f}s … [{base}]")
            time.sleep(wait)

            # En el penúltimo intento deshabilitamos SSL como último recurso
            if attempt >= MAX_RETRIES - 1 and not _ssl_disabled:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                _ssl_disabled = True
                _api_session = make_session(verify_ssl=False)
                print("    ⚠  Verificación SSL deshabilitada como último recurso")

        except requests.exceptions.ConnectionError:
            wait = BACKOFF_BASE ** attempt
            print(f"    ⚠  Error de conexión (intento {attempt}/{MAX_RETRIES}), "
                  f"esperando {wait:.1f}s …")
            time.sleep(wait)

        except requests.exceptions.Timeout:
            wait = BACKOFF_BASE ** attempt
            print(f"    ⚠  Timeout (intento {attempt}/{MAX_RETRIES}), "
                  f"esperando {wait:.1f}s …")
            time.sleep(wait)

        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                wait = float(exc.response.headers.get("Retry-After", 15))
                print(f"    ⚠  Rate limited, esperando {wait:.0f}s …")
                time.sleep(wait)
            else:
                print(f"    ✗  HTTP error: {exc}")
                time.sleep(RATE_LIMIT_SLEEP)
                return None

        except Exception as exc:
            print(f"    ✗  Error inesperado: {exc}")
            time.sleep(RATE_LIMIT_SLEEP)
            return None

    print(f"    ✗  Todos los reintentos fallaron para {endpoint}")
    time.sleep(RATE_LIMIT_SLEEP)
    return None

# ─── Estructuras de datos ───────────────────────────────────────────────────────

@dataclass
class Album:
    number: str
    genre: str
    artist: str
    title: str
    year: str
    mb_release_group_id: Optional[str] = None
    mb_artist_id: Optional[str] = None
    search_status: str = "pending"   # pending | found | not_found | ambiguous | error

# ─── Scraping ──────────────────────────────────────────────────────────────────

def fetch_albums(url: str = SOURCE_URL) -> list:
    """Descarga la página y extrae la lista de álbumes."""
    print(f"[scrape] Descargando {url} …")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.content, "html.parser")
    raw_text = soup.get_text(separator="\n")

    # Patrón: NÚMERO | GÉNERO | ARTISTA - TÍTULO (AÑO)
    LINE_RE = re.compile(
        r"^\s*(\d{4})\s*\|\s*(.+?)\s*\|\s*(.+?)\s+-\s+(.+?)"
        r"\s*(?:\(([^)]*)\))?\s*$"
    )

    albums = []
    seen = set()

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = LINE_RE.match(line)
        if not m:
            continue

        number, genre, artist, title, year = m.groups()
        year   = (year or "").strip()
        artist = clean_text(artist)
        title  = clean_text(title)
        genre  = clean_text(genre)

        key = (artist.lower(), title.lower())
        if key in seen:
            continue
        seen.add(key)

        albums.append(Album(number=number, genre=genre,
                            artist=artist, title=title, year=year))

    print(f"[scrape] {len(albums)} álbumes parseados.")
    return albums


def clean_text(text: str) -> str:
    """Elimina caracteres de control y normaliza unicode."""
    return "".join(
        c for c in text if unicodedata.category(c)[0] != "C"
    ).strip()

# ─── Búsqueda en MusicBrainz ────────────────────────────────────────────────────

def search_album(album: Album, verbose: bool = False) -> None:
    """
    Busca el release group en MB con tres estrategias progresivamente más amplias.
    Rellena album.mb_release_group_id y album.search_status.
    """

    def _search(query: str):
        data = mb_get("/release-group", {"query": query, "limit": 5, "fmt": "json"})
        return (data or {}).get("release-groups", [])

    # Estrategia 1 — título exacto + artista
    rgs = _search(f'releasegroup:"{album.title}" AND artist:"{album.artist}"')

    # Estrategia 2 — solo título exacto
    if not rgs:
        rgs = _search(f'releasegroup:"{album.title}"')

    # Estrategia 3 — primeras palabras del título + primera palabra del artista
    if not rgs:
        title_words = " ".join(album.title.split()[:5])
        artist_word = album.artist.split()[0]
        rgs = _search(f"releasegroup:{title_words} AND artist:{artist_word}")

    if not rgs:
        album.search_status = "not_found"
        if verbose:
            print(f"    — No encontrado")
        return

    best  = rgs[0]
    score = int(best.get("score", 0))

    if score < 60:
        album.search_status = "ambiguous"
        if verbose:
            print(f"    ~ Ambiguo (score={score})")
        return

    album.mb_release_group_id = best["id"]
    ac = best.get("artist-credit", [])
    if ac and isinstance(ac[0], dict):
        album.mb_artist_id = ac[0].get("artist", {}).get("id")
    album.search_status = "found"

    if verbose:
        print(f"    ✓ {best['id']} (score={score})")


def search_all(albums: list, verbose: bool = False, resume: bool = True) -> None:
    """
    Busca todos los álbumes.
    Con resume=True solo procesa los que tienen search_status='pending' o 'error'.
    """
    to_search = (
        [a for a in albums if a.search_status in ("pending", "error")]
        if resume else albums
    )
    total    = len(to_search)
    overall  = len(albums)

    print(f"\n[mb] Buscando {total} álbumes "
          f"({'retomando' if resume else 'todos'} de {overall}) …\n")

    for i, album in enumerate(to_search, 1):
        idx = albums.index(album) + 1
        print(f"  [{idx}/{overall}] {album.artist} – {album.title}")
        search_album(album, verbose=verbose)

# ─── CSV ───────────────────────────────────────────────────────────────────────

CSV_FIELDS = ["number", "genre", "artist", "title", "year",
              "search_status", "mb_release_group_id", "mb_artist_id"]


def export_csv(albums: list, path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for a in albums:
            w.writerow({k: getattr(a, k) or "" for k in CSV_FIELDS})
    print(f"\n[csv] Exportado → {path}")


def load_csv(path: str) -> list:
    albums = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            albums.append(Album(
                number=row["number"],
                genre=row["genre"],
                artist=row["artist"],
                title=row["title"],
                year=row["year"],
                mb_release_group_id=row["mb_release_group_id"] or None,
                mb_artist_id=row["mb_artist_id"] or None,
                search_status=row["search_status"],
            ))
    print(f"[csv] Cargados {len(albums)} álbumes desde {path}")
    return albums

# ─── Resumen ───────────────────────────────────────────────────────────────────

def print_summary(albums: list) -> None:
    counts = {}
    for a in albums:
        counts[a.search_status] = counts.get(a.search_status, 0) + 1

    print("\n══════════════════════════════════════")
    print(f"  Total           : {len(albums)}")
    print(f"  Encontrados  ✓  : {counts.get('found', 0)}")
    print(f"  Ambiguos     ⚠  : {counts.get('ambiguous', 0)}")
    print(f"  No encontrados  : {counts.get('not_found', 0)}")
    print(f"  Errores         : {counts.get('error', 0)}")
    print(f"  Sin procesar    : {counts.get('pending', 0)}")
    print("══════════════════════════════════════\n")

# ─── OAuth 2.0 MusicBrainz ────────────────────────────────────────────────────

MB_OAUTH_AUTHORIZE = "https://musicbrainz.org/oauth2/authorize"
MB_OAUTH_TOKEN_URL = "https://musicbrainz.org/oauth2/token"
TOKEN_CACHE        = ".mb_token.json"


def _save_token(token_data: dict) -> None:
    with open(TOKEN_CACHE, "w") as f:
        json.dump(token_data, f, indent=2)


def _oauth_refresh(client_id: str, client_secret: str, refresh_token: str) -> str:
    resp = requests.post(
        MB_OAUTH_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=20,
    )
    resp.raise_for_status()
    token_data = resp.json()
    _save_token(token_data)
    print("[oauth] Token renovado.")
    return token_data["access_token"]


def mb_oauth_token(client_id: str, client_secret: str) -> str:
    """
    Devuelve un access token OAuth 2.0 de MusicBrainz.
    Usa caché en TOKEN_CACHE; si existe refresh_token lo renueva automáticamente.
    Si no hay caché, inicia el flujo interactivo (authorization code + OOB).
    """
    # Intentar caché
    if os.path.exists(TOKEN_CACHE):
        with open(TOKEN_CACHE) as f:
            cached = json.load(f)
        if cached.get("refresh_token"):
            try:
                return _oauth_refresh(client_id, client_secret, cached["refresh_token"])
            except Exception as e:
                print(f"[oauth] Renovación fallida ({e}), re-autorizando…")
        elif cached.get("access_token"):
            return cached["access_token"]

    # Flujo authorization code + OOB
    params = urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
        "scope": "profile",
        "access_type": "offline",
    })
    print(f"\n[oauth] Abre esta URL en tu navegador y autoriza la app:\n"
          f"  {MB_OAUTH_AUTHORIZE}?{params}\n")
    code = input("[oauth] Pega el código de autorización: ").strip()

    resp = requests.post(
        MB_OAUTH_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
        },
        timeout=20,
    )
    resp.raise_for_status()
    token_data = resp.json()
    _save_token(token_data)
    print(f"[oauth] Token obtenido y guardado en {TOKEN_CACHE}")
    return token_data["access_token"]


def mb_auth_session(session_cookie: str) -> requests.Session:
    """
    Crea una sesión autenticada usando la cookie de sesión del navegador.

    Para obtenerla: abre musicbrainz.org con sesión iniciada →
    DevTools (F12) → Application → Cookies → musicbrainz.org →
    copia el valor de 'musicbrainz_server_session'.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    retry = Retry(total=3, backoff_factor=1.5, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://",  adapter)

    session.cookies.set("musicbrainz_server_session", session_cookie,
                        domain="musicbrainz.org", path="/")

    # Verificar que la sesión es válida
    resp = session.get("https://musicbrainz.org/", timeout=20)
    if "/login" in resp.url:
        raise RuntimeError("Cookie de sesión inválida o expirada.")
    print("[auth] Sesión validada con cookie de navegador.")
    return session

# ─── Crear serie ───────────────────────────────────────────────────────────────

def create_series(session, dry_run: bool = False) -> Optional[str]:
    if dry_run:
        print(f"[dry-run] Crearía la serie: {SERIES_NAME}")
        return None

    create_url = "https://musicbrainz.org/series/create"
    page = session.get(create_url, timeout=20)
    page.raise_for_status()
    soup = BeautifulSoup(page.text, "html.parser")

    csrf = soup.find("input", {"name": "csrf_token"})
    if not csrf:
        raise RuntimeError("No se encontró CSRF en el formulario de creación.")

    type_select = soup.find("select", {"id": "id-edit-series.type_id"})
    type_id = None
    if type_select:
        for opt in type_select.find_all("option"):
            if "release group" in opt.text.lower():
                type_id = opt["value"]
                break
    if not type_id:
        raise RuntimeError("No se encontró el tipo 'Release group series' en el formulario.")

    resp = session.post(
        create_url,
        data={
            "csrf_token": csrf["value"],
            "edit-series.name": SERIES_NAME,
            "edit-series.comment": SERIES_COMMENT,
            "edit-series.type_id": type_id,
            "edit-series.ordering_type_id": "1",
        },
        allow_redirects=True,
        timeout=30,
    )

    mbid_match = re.search(
        r"/series/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        resp.url,
    )
    if not mbid_match:
        raise RuntimeError(f"Creación de serie fallida. URL final: {resp.url}")

    series_mbid = mbid_match.group(1)
    print(f"[mb] Serie creada → {series_mbid}")
    return series_mbid

# ─── Generar JSON de relaciones ────────────────────────────────────────────────

def generate_relationships_json(
    albums: list,
    series_mbid: str,
    output_path: str = "mb_series_relationships.json",
) -> None:
    """
    Genera un JSON con todas las relaciones listas para importar manualmente.
    """
    found = [a for a in albums if a.search_status == "found" and a.mb_release_group_id]

    payload = {
        "series_mbid": series_mbid,
        "series_name": SERIES_NAME,
        "total": len(found),
        "relationships": [
            {
                "order_number": a.number,
                "genre": a.genre,
                "artist": a.artist,
                "title": a.title,
                "year": a.year,
                "release_group_mbid": a.mb_release_group_id,
                "link_type_uuid": REL_TYPE_UUID,
            }
            for a in found
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[json] {len(found)} relaciones exportadas → {output_path}")
    print(f"       Añade manualmente en: https://musicbrainz.org/series/{series_mbid}/edit")

# ─── Añadir release groups a la serie ──────────────────────────────────────────

def add_release_groups_to_series(
    session,
    series_mbid: str,
    albums: list,
    dry_run: bool = False,
) -> None:
    found = [a for a in albums if a.search_status == "found" and a.mb_release_group_id]
    print(f"\n[mb] {len(found)} release groups listos para la serie {series_mbid}")

    # Siempre generar el JSON de respaldo
    generate_relationships_json(albums, series_mbid)

    if dry_run:
        print("\n[dry-run] Primeros 10 ítems que se añadirían:")
        for a in found[:10]:
            print(f"  {a.number}. {a.artist} – {a.title}  ({a.mb_release_group_id})")
        if len(found) > 10:
            print(f"  … y {len(found) - 10} más")
        return

    edit_url = f"https://musicbrainz.org/series/{series_mbid}/edit"

    # Obtener CSRF y nombre actual de la serie desde el formulario
    page = session.get(edit_url, timeout=20,
                       headers={"Referer": f"https://musicbrainz.org/series/{series_mbid}"})
    if "/login" in page.url:
        raise RuntimeError("Sesión no válida, re-autenticar.")
    soup = BeautifulSoup(page.text, "html.parser")

    csrf_input  = soup.find("input", {"name": "csrf_token"})
    name_input  = soup.find("input", {"name": "edit-series.name"})
    series_name = name_input["value"] if name_input else SERIES_NAME

    ok_count = 0
    for i, a in enumerate(found, 1):
        data = {
            "edit-series.name":                          series_name,
            "edit-series.comment":                       SERIES_COMMENT,
            "edit-series.type_id":                       "1",
            "edit-series.ordering_type_id":              "2",
            "edit-series.rel.0.target":                  a.mb_release_group_id,
            "edit-series.rel.0.entity0_credit":          "",
            "edit-series.rel.0.entity1_credit":          "",
            "edit-series.rel.0.period.begin_date.year":  "",
            "edit-series.rel.0.period.begin_date.month": "",
            "edit-series.rel.0.period.begin_date.day":   "",
            "edit-series.rel.0.period.end_date.year":    "",
            "edit-series.rel.0.period.end_date.month":   "",
            "edit-series.rel.0.period.end_date.day":     "",
            "edit-series.rel.0.period.ended":            "0",
            "edit-series.rel.0.backward":                "1",
            "edit-series.rel.0.link_type_id":            "742",
            "edit-series.rel.0.link_order":              "0",
            "edit-series.edit_note":                     f"#{a.number} {a.genre} — imported from {SOURCE_URL}",
        }
        if csrf_input:
            data["csrf_token"] = csrf_input["value"]

        resp = session.post(
            edit_url,
            data=data,
            headers={"Referer": edit_url},
            allow_redirects=False,
            timeout=30,
        )
        if resp.status_code in (301, 302, 303):
            ok_count += 1
            print(f"  [{i}/{len(found)}] ✓  {a.artist} – {a.title}")
        else:
            print(f"  [{i}/{len(found)}] ✗ ({resp.status_code})  {a.artist} – {a.title}")
            print(f"    → {resp.text[:300]}")
        time.sleep(1.2)

    print(f"\n[mb] {ok_count}/{len(found)} relaciones añadidas.")

# ─── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Crea una serie en MusicBrainz con los álbumes de musicgenretree.org",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Simula sin modificar MusicBrainz")
    p.add_argument("--session-cookie", default="",
                   metavar="COOKIE",
                   help="Valor de 'musicbrainz_server_session' copiado del navegador")
    p.add_argument("--export-csv", metavar="PATH",
                   help="Exporta resultados a CSV")
    p.add_argument("--load-csv", metavar="PATH",
                   help="Carga álbumes desde CSV previo (retoma búsquedas pendientes/error)")
    p.add_argument("--series-mbid", metavar="MBID",
                   help="MBID de una serie ya existente")
    p.add_argument("--skip-search", action="store_true",
                   help="Salta la búsqueda en MB")
    p.add_argument("--no-resume", action="store_true",
                   help="Rebusca todos los álbumes (ignora estado previo)")
    p.add_argument("--verbose", "-v", action="store_true",
                   help="Muestra detalle de cada búsqueda")
    return p


def main() -> None:
    args = build_parser().parse_args()

    # 1. Obtener álbumes
    albums = load_csv(args.load_csv) if args.load_csv else fetch_albums()

    # 2. Buscar en MusicBrainz
    if not args.skip_search:
        search_all(albums, verbose=args.verbose, resume=not args.no_resume)
        print_summary(albums)

    # 3. Exportar CSV si se pide
    if args.export_csv:
        export_csv(albums, args.export_csv)

    # 4. Crear serie y añadir álbumes
    if args.dry_run:
        print("\n[dry-run] ══ SIMULACIÓN ══")
        create_series(None, dry_run=True)
        add_release_groups_to_series(None, "DRY-RUN-MBID", albums, dry_run=True)
        return

    if not args.session_cookie:
        print(
            "\n[info] Para crear/actualizar la serie necesitas --session-cookie.\n"
            "       Obtén el valor de 'musicbrainz_server_session' en:\n"
            "       DevTools (F12) → Application → Cookies → musicbrainz.org\n"
            "       Usa --dry-run para simular o --export-csv para guardar resultados.\n"
        )
        return

    session = mb_auth_session(args.session_cookie)
    series_mbid = args.series_mbid or create_series(session)
    add_release_groups_to_series(session, series_mbid, albums)


if __name__ == "__main__":
    main()
