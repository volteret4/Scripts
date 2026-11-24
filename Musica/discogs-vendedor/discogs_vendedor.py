#!/home/huan/Scripts/python_venv/bin/python
"""
Comprueba qué discos de tus artistas (base de datos de music-fuzzy) tiene a la
venta un vendedor de Discogs.

Uso:
    discogs_vendedor.py NOMBRE_O_URL [--formato vinyl] [--csv salida.csv]

Ejemplos:
    discogs_vendedor.py https://www.discogs.com/seller/RecordShop/profile
    discogs_vendedor.py RecordShop --formato LP --max-precio 30

El inventario de Discogs solo trae el nombre del artista, no su id. Para evitar
homónimos se resuelven los ids de discogs_url de la db a su nombre canónico en
Discogs (p.ej. "Nirvana (2)") y se cachean en ~/.cache/discogs_vendedor/.
Los artistas sin discogs_url se comparan por nombre normalizado.

Token: DISCOGS_TOKEN desde el entorno, .encrypted.env (sops) o db/.env de
music-fuzzy. Sin token también funciona, pero Discogs limita a 25 peticiones/min.
"""
import argparse
import csv
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import requests

DB_DEFAULT = Path.home() / "gits/pollo/music-fuzzy/db/sqlite/musica_local.sqlite"
MFUZ_ENV = Path.home() / "gits/pollo/music-fuzzy/db/.env"
CACHE_DIR = Path.home() / ".cache/discogs_vendedor"
API = "https://api.discogs.com"
USER_AGENT = "discogs-vendedor/1.0 +https://github.com/volteret4"

# Separadores que usa Discogs al unir varios artistas en un mismo release
SEPARADORES = re.compile(r"\s+(?:&|/|\+|and|y|vs\.?|feat\.?|featuring|ft\.?|with|meets|x)\s+|,\s+", re.I)
SUFIJO_DISCOGS = re.compile(r"\s*\(\d+\)$")
# Nombres de relleno que aparecen como "artista" en la db y en Discogs
GENERICOS = {"unknownartist", "various", "variousartists", "va", "noartist", "unknown", "anonymous"}


# ── Credenciales ─────────────────────────────────────────────────────────────

def cargar_token() -> str | None:
    if os.environ.get("DISCOGS_TOKEN"):
        return os.environ["DISCOGS_TOKEN"]
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from sops_env import load_sops_env
        for d in (Path(__file__).resolve().parent, Path.cwd()):
            if (d / ".encrypted.env").exists():
                load_sops_env(d / ".encrypted.env")
                break
    except Exception as e:
        print(f"⚠️  No se pudo descifrar .encrypted.env: {e}", file=sys.stderr)
    if os.environ.get("DISCOGS_TOKEN"):
        return os.environ["DISCOGS_TOKEN"]
    if MFUZ_ENV.exists():
        for linea in MFUZ_ENV.read_text().splitlines():
            clave, _, valor = linea.partition("=")
            if clave.strip() == "DISCOGS_TOKEN" and valor.strip():
                return valor.strip().strip("'\"")
    return None


# ── Cliente Discogs con control de rate limit ────────────────────────────────

class Discogs:
    def __init__(self, token: str | None):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = USER_AGENT
        if token:
            self.s.headers["Authorization"] = f"Discogs token={token}"
        # 60/min con token, 25/min sin él
        self.pausa = 1.0 if token else 2.4

    def get(self, ruta: str, **params) -> dict | None:
        for intento in range(5):
            r = self.s.get(f"{API}{ruta}", params=params, timeout=30)
            restantes = int(r.headers.get("X-Discogs-Ratelimit-Remaining", 10))
            time.sleep(self.pausa if restantes > 2 else 10)
            if r.status_code == 429:
                time.sleep(20 * (intento + 1))
                continue
            if r.status_code == 404:
                return None
            if r.status_code == 403 and "Pagination above" in r.text:
                return {"pagination": {"pages": 0, "items": 0}, "listings": []}
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"Discogs sigue devolviendo 429 en {ruta}")


# ── Normalización y emparejado ───────────────────────────────────────────────

def normalizar(nombre: str) -> str:
    n = SUFIJO_DISCOGS.sub("", nombre or "")
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    n = re.sub(r"^the\s+|,\s*the$", "", n.strip())
    n = n.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "", n)


def partes_artista(texto: str) -> list[str]:
    """'A & B (2)' -> ['A & B (2)', 'A', 'B (2)']"""
    texto = texto.strip().rstrip("*")
    partes = [texto] + [p.strip().rstrip("*") for p in SEPARADORES.split(texto) if p.strip()]
    return list(dict.fromkeys(partes))


def id_desde_url(url: str) -> int | None:
    m = re.search(r"/artist/(\d+)", url or "")
    return int(m.group(1)) if m else None


def vendedor_desde_arg(arg: str) -> str:
    """Acepta nombre, URL de seller/shop/user o de la API."""
    if "://" not in arg and "/" not in arg:
        return arg.strip()
    trozos = [t for t in urlparse(arg if "://" in arg else f"https://{arg}").path.split("/") if t]
    for clave in ("seller", "user", "users", "shop"):
        if clave in trozos and trozos.index(clave) + 1 < len(trozos):
            return unquote(trozos[trozos.index(clave) + 1])
    sys.exit(f"No reconozco el vendedor en la URL: {arg}")


# ── Artistas de music-fuzzy ──────────────────────────────────────────────────

def cargar_artistas(db: Path) -> list[tuple[str, int | None]]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    filas = con.execute("SELECT name, discogs_url FROM artists WHERE name IS NOT NULL").fetchall()
    con.close()
    return [(nombre, id_desde_url(url)) for nombre, url in filas]


def resolver_nombres_discogs(api: Discogs, ids: list[int]) -> dict[int, str]:
    """id de Discogs -> nombre canónico ('Nirvana (2)'), cacheado en disco."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_f = CACHE_DIR / "artistas.json"
    cache = {int(k): v for k, v in json.loads(cache_f.read_text()).items()} if cache_f.exists() else {}
    pendientes = [i for i in ids if i not in cache]
    if pendientes:
        minutos = len(pendientes) * api.pausa / 60
        print(f"🔎 Resolviendo {len(pendientes)} artistas en Discogs (~{minutos:.0f} min, solo la primera vez)…",
              file=sys.stderr)
    for n, aid in enumerate(pendientes, 1):
        datos = api.get(f"/artists/{aid}")
        cache[aid] = datos.get("name") if datos else None
        if n % 25 == 0 or n == len(pendientes):
            cache_f.write_text(json.dumps(cache, ensure_ascii=False))
            print(f"   {n}/{len(pendientes)}", file=sys.stderr, end="\r")
    if pendientes:
        print(file=sys.stderr)
    return {i: cache[i] for i in ids if cache.get(i)}


def construir_indices(artistas, nombres_discogs):
    exactos = {}     # nombre canónico de Discogs (con sufijo) -> nombre en tu db
    aproximados = {} # nombre normalizado -> nombre en tu db (solo artistas sin id)
    for nombre, aid in artistas:
        if normalizar(nombre) in GENERICOS:
            continue
        if aid and aid in nombres_discogs:
            exactos[nombres_discogs[aid]] = nombre
        else:
            aproximados.setdefault(normalizar(nombre), nombre)
    return exactos, aproximados


def emparejar(texto_artista: str, exactos, aproximados) -> str | None:
    # Con nombre canónico de Discogs se puede trocear 'A & B' sin riesgo;
    # por nombre aproximado no ('Earth, Wind & Fire' acabaría en 'Earth')
    for parte in partes_artista(texto_artista):
        if parte in exactos:
            return exactos[parte]
    return aproximados.get(normalizar(texto_artista))


# ── Inventario ───────────────────────────────────────────────────────────────

LIMITE_PAGINAS = 100  # Discogs no deja pasar de la página 100 en inventarios ajenos


def recorrer_inventario(api: Discogs, vendedor: str, max_paginas: int | None):
    """Recorre el inventario por artista A→Z y, si pasa de 10.000 artículos,
    también Z→A para cubrir hasta 20.000 sin repetir."""
    vistos = set()
    ultimo = {}
    for orden in ("asc", "desc"):
        pagina, total_paginas = 1, 1
        while pagina <= min(total_paginas, LIMITE_PAGINAS) and (not max_paginas or pagina <= max_paginas):
            datos = api.get(f"/users/{quote(vendedor)}/inventory",
                            status="For Sale", sort="artist", sort_order=orden,
                            per_page=100, page=pagina)
            if datos is None:
                sys.exit(f"El vendedor '{vendedor}' no existe o no tiene inventario público.")
            pag = datos["pagination"]
            total_paginas = pag["pages"]
            if pagina == 1 and orden == "asc":
                total_items = pag["items"]
                print(f"📦 {vendedor}: {pag['items']} artículos a la venta ({total_paginas} páginas)", file=sys.stderr)
            print(f"   página {pagina}/{min(total_paginas, LIMITE_PAGINAS)} ({'A→Z' if orden == 'asc' else 'Z→A'})",
                  file=sys.stderr, end="\r")
            nuevos = [l for l in datos["listings"] if l["id"] not in vistos]
            if orden == "desc" and not nuevos:
                break  # se ha cruzado con el recorrido A→Z: inventario completo
            for l in nuevos:
                vistos.add(l["id"])
                ultimo[orden] = l["release"].get("artist", "")
                yield l
            pagina += 1
        if total_paginas <= LIMITE_PAGINAS or max_paginas:
            break
    print(file=sys.stderr)
    if "desc" in ultimo and len(vistos) < total_items:
        print(f"⚠️  Discogs solo deja ver 20.000 artículos de inventarios ajenos: revisados {len(vistos)} de "
              f"{total_items}. Falta el tramo de artistas entre «{ultimo['asc']}» y «{ultimo['desc']}».",
              file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("vendedor", help="Nombre del vendedor o URL de su tienda/perfil en Discogs")
    ap.add_argument("--db", type=Path, default=DB_DEFAULT, help=f"Base de datos de music-fuzzy (por defecto {DB_DEFAULT})")
    ap.add_argument("--formato", help="Filtra por formato, p.ej. Vinyl, LP, CD, 12\" (subcadena, sin distinguir mayúsculas)")
    ap.add_argument("--max-precio", type=float, help="Precio máximo (en la moneda del vendedor)")
    ap.add_argument("--max-paginas", type=int, help="Límite de páginas de inventario (100 artículos cada una)")
    ap.add_argument("--csv", type=Path, help="Guarda los resultados en un CSV")
    ap.add_argument("--sin-ids", action="store_true", help="No resolver ids de Discogs; comparar solo por nombre (más rápido la 1ª vez, menos preciso)")
    args = ap.parse_args()

    if not args.db.exists() or args.db.stat().st_size == 0:
        sys.exit(f"No encuentro la base de datos: {args.db}")

    vendedor = vendedor_desde_arg(args.vendedor)
    token = cargar_token()
    if not token:
        print("⚠️  Sin DISCOGS_TOKEN: irá más lento (25 peticiones/min).", file=sys.stderr)
    api = Discogs(token)

    artistas = cargar_artistas(args.db)
    ids = sorted({aid for _, aid in artistas if aid})
    nombres_discogs = {} if args.sin_ids else resolver_nombres_discogs(api, ids)
    if args.sin_ids:
        artistas = [(n, None) for n, _ in artistas]
    exactos, aproximados = construir_indices(artistas, nombres_discogs)
    print(f"🎵 {len(artistas)} artistas en tu db ({len(exactos)} con id de Discogs)", file=sys.stderr)

    encontrados = defaultdict(list)
    for item in recorrer_inventario(api, vendedor, args.max_paginas):
        rel = item["release"]
        tuyo = emparejar(rel.get("artist", ""), exactos, aproximados)
        if not tuyo:
            continue
        formato = rel.get("format", "")
        precio = item["price"]
        if args.formato and args.formato.lower() not in formato.lower():
            continue
        if args.max_precio is not None and precio["value"] > args.max_precio:
            continue
        encontrados[tuyo].append({
            "artista_db": tuyo,
            "artista_discogs": rel.get("artist", ""),
            "titulo": rel.get("title", ""),
            "año": rel.get("year") or "",
            "formato": formato,
            "condicion": item.get("condition", ""),
            "funda": item.get("sleeve_condition", ""),
            "precio": precio["value"],
            "moneda": precio["currency"],
            "enlace": f"https://www.discogs.com/sell/item/{item['id']}",
        })

    if not encontrados:
        print(f"\nNinguno de tus artistas tiene discos a la venta en {vendedor}.")
        return

    total = sum(len(v) for v in encontrados.values())
    print(f"\n✅ {total} discos de {len(encontrados)} de tus artistas en {vendedor}\n")
    for artista in sorted(encontrados, key=str.lower):
        print(f"■ {artista}")
        for d in sorted(encontrados[artista], key=lambda d: d["precio"]):
            cond = d["condicion"].split("(")[-1].rstrip(")") if "(" in d["condicion"] else d["condicion"]
            print(f"   {d['precio']:>7.2f} {d['moneda']}  {d['titulo']} ({d['año']}) · {d['formato']} · {cond}")
            print(f"            {d['enlace']}")

    if args.csv:
        filas = [d for v in encontrados.values() for d in v]
        with args.csv.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(filas[0]))
            w.writeheader()
            w.writerows(filas)
        print(f"\n💾 CSV guardado en {args.csv}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nInterrumpido.")
