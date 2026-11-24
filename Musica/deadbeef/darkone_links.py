"""Datos propios para Infobar NG: Encarta, Grapa, vvmm, Discogs y la carpeta Mix.

Lo importan info_album.py y bio_artista.py (mismo directorio). Cada función
devuelve líneas de texto; los enlaces van como [texto](url), que Infobar NG
convierte en enlaces clicables, y «## Título» como cabecera de sección.
"""
import json
import os
import re
import sqlite3
import time
import unicodedata
from pathlib import Path

HOME = Path.home()
ENCARTA_DB = Path(os.environ.get("ENCARTA_DB", HOME / "gits/pollo/encarta/encarta.db"))
ENCARTA_URL = os.environ.get("ENCARTA_URL", "http://192.168.1.133:8777/")
GRAPA_DB = Path(os.environ.get("GRAPA_DB", HOME / "gits/pollo/Music_articles/articles.db"))
GRAPA_URL = "https://volteret4.github.io/grapa/"
VVMM_DIR = Path(os.environ.get("VVMM_DIR", "/mnt/NFS/blogs/vvmm/content"))
VVMM_URL = "https://volteret4.github.io/vvmm/"
DISCOGS_ENV = HOME / "gits/pollo/music-fuzzy/db/.env"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "darkone4mod"
MIX_INDEX = CACHE_DIR / "mix_index.tsv"

UA = {"User-Agent": "ddb-infobar-ng/1.1"}


# ── normalización ────────────────────────────────────────────────────────────

def enorm(s):
    """norm() de Encarta: minúsculas, sin acentos ni puntuación, & = and."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("&", " and ").replace("’", "'")
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def enorm_the(s):
    s = enorm(s)
    return s[4:] if s.startswith("the ") else s


def mix_norm(s, title=False):
    """Misma clave que plugin/extras.c (norm_text) de DarkOne4Mod."""
    if title:
        s = re.sub(r"[\(\[][^\)\]]*[\)\]]", "", s or "")
    return enorm_the(s)


# ── Encarta + Grapa ──────────────────────────────────────────────────────────

def _ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=3)


def encarta_entity(kind, artist, album=None):
    if not ENCARTA_DB.exists():
        return None
    if kind == "artist":
        keys = [enorm_the(artist)]
        types = ("artist",)
    else:
        keys = [f"{enorm_the(artist)}|{enorm_the(album)}"]
        types = ("album", "work")
    with _ro(ENCARTA_DB) as db:
        for t in types:
            for k in keys:
                row = db.execute("SELECT id, name, year, weight FROM entity WHERE type=? AND key=?",
                                 (t, k)).fetchone()
                if row:
                    return {"id": row[0], "name": row[1], "year": row[2], "weight": row[3]}
    return None


def encarta_lines(kind, artist, album=None):
    e = encarta_entity(kind, artist, album)
    if not e:
        return [], None
    n_facts = 0
    try:
        with _ro(ENCARTA_DB) as db:
            n_facts = db.execute("SELECT count(*) FROM fact WHERE entity_id=?", (e["id"],)).fetchone()[0]
    except sqlite3.Error:
        pass
    extra = f" · {n_facts} notas" if n_facts else ""
    return [f"Encarta: [{e['name']}]({ENCARTA_URL}#/e/{e['id']}){extra}"], e


def grapa_album_lines(artist_e, album_e):
    if not GRAPA_DB.exists() or not album_e:
        return []
    with _ro(GRAPA_DB) as db:
        total = db.execute("SELECT count(*) FROM article WHERE album=?", (album_e["id"],)).fetchone()[0]
        rows = db.execute(
            "SELECT kind, outlet, title, url, score, substr(published,1,4), artist FROM article "
            "WHERE album=? ORDER BY score IS NULL, score DESC, published DESC LIMIT 12",
            (album_e["id"],)).fetchall()
    if not rows:
        return []
    artist_id = artist_e["id"] if artist_e else rows[0][6]
    word = "artículo" if total == 1 else "artículos"
    lines = [f"Grapa: {total} {word} · [ver en Grapa]({GRAPA_URL}artista/{artist_id}.html#d{album_e['id']})"]
    album_n = enorm(album_e["name"])
    for kind, outlet, title, url, score, year, _a in rows[:8]:
        sc = f" · {score}/100" if score is not None else ""
        yr = f" · {year}" if year else ""
        # el titular solo si aporta algo (muchos repiten «Artista: Disco»)
        tl = f": {title}" if title and album_n not in enorm(title) else ""
        lines.append(f"  • [{outlet}]({url}) {kind}{sc}{yr}{tl}")
    return lines


def grapa_artist_lines(artist_e):
    if not GRAPA_DB.exists() or not artist_e:
        return []
    with _ro(GRAPA_DB) as db:
        rows = db.execute("SELECT kind, count(*) FROM article WHERE artist=? GROUP BY kind ORDER BY 2 DESC",
                          (artist_e["id"],)).fetchall()
    if not rows:
        return []
    parts = ", ".join(f"{n} {k}" for k, n in rows)
    return [f"Grapa: {parts} · [ver en Grapa]({GRAPA_URL}artista/{artist_e['id']}.html)"]


# ── vvmm ─────────────────────────────────────────────────────────────────────

FM = re.compile(r'^(artist|album):\s*"?(.*?)"?\s*$', re.M)


def _vvmm_build():
    idx = []
    if VVMM_DIR.is_dir():
        for md in VVMM_DIR.glob("*/*/index.md"):
            try:
                with md.open(encoding="utf-8", errors="replace") as fh:
                    head = fh.read(1500)
            except OSError:
                continue
            meta = dict(FM.findall(head.split("---", 2)[1] if head.startswith("---") else head))
            if meta.get("artist"):
                section, slug = md.parent.parent.name, md.parent.name
                idx.append([meta.get("artist", ""), meta.get("album", ""), f"{section}/{slug.lower()}/", section])
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_DIR / "vvmm.json.tmp"
    tmp.write_text(json.dumps(idx, ensure_ascii=False))
    tmp.replace(CACHE_DIR / "vvmm.json")
    return idx


def _vvmm_index():
    """Usa la caché; si tiene más de 6 h la refresca en segundo plano (el NFS es lento)."""
    cache = CACHE_DIR / "vvmm.json"
    try:
        data = json.loads(cache.read_text())
        if time.time() - cache.stat().st_mtime > 6 * 3600:
            import subprocess
            import sys
            os.utime(cache)  # evita lanzar varias recargas a la vez
            subprocess.Popen([sys.executable, __file__, "--refresh-vvmm"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        return data
    except (OSError, ValueError):
        return _vvmm_build()


def vvmm_lines(artist, album=None):
    a, b = enorm_the(artist), enorm_the(album) if album else None
    hits = [r for r in _vvmm_index() if enorm_the(r[0]) == a and (b is None or enorm_the(r[1]) == b)]
    if not hits:
        return []
    if album:
        r = hits[0]
        return [f"vvmm: ✔ [{r[0]} - {r[1]}]({VVMM_URL}{r[2]}) ({r[3]})"]
    links = ", ".join(f"[{r[1]}]({VVMM_URL}{r[2]})" for r in hits[:8])
    n = len(hits)
    return [f"vvmm: {n} " + ("disco" if n == 1 else "discos") + f" — {links}"]


# ── Discogs ──────────────────────────────────────────────────────────────────

def _discogs_token():
    tok = os.environ.get("DISCOGS_TOKEN")
    if tok:
        return tok
    try:
        for ln in DISCOGS_ENV.read_text().splitlines():
            if ln.startswith("DISCOGS_TOKEN="):
                return ln.split("=", 1)[1].strip().strip('"\'')
    except OSError:
        pass
    return None


CREDIT_GROUPS = [
    ("Producción",     re.compile(r"produc", re.I)),
    ("Masterización",  re.compile(r"master|lacquer", re.I)),
    ("Mezcla",         re.compile(r"(?<!re)mix", re.I)),
    ("Ingeniería",     re.compile(r"engineer|recorded|recording", re.I)),
    ("Arreglos",       re.compile(r"arrang|orchestrat|conduct", re.I)),
    ("Diseño y fotos", re.compile(r"design|art direction|artwork|photo|layout|illustrat|painting", re.I)),
]
STUDIO_ROLES = re.compile(r"(mastered|recorded|mixed|engineered|produced|lacquer cut|remastered) at|pressed by|manufactured by", re.I)


def _dname(n):
    return re.sub(r"\s*\(\d+\)$", "", n or "")


def discogs_album_lines(artist, album):
    import requests
    tok = _discogs_token()
    if not tok:
        return []
    h = dict(UA, Authorization=f"Discogs token={tok}")
    get = lambda url, **p: requests.get(url, params=p or None, headers=h, timeout=8).json()

    res = get("https://api.discogs.com/database/search", artist=artist, release_title=album, type="master", per_page=3).get("results", [])
    master, release_id = None, None
    if res:
        master = res[0]
        release_id = get(f"https://api.discogs.com/masters/{master['id']}").get("main_release")
    else:
        res = get("https://api.discogs.com/database/search", artist=artist, release_title=album, type="release", per_page=3).get("results", [])
        if not res:
            return []
        release_id = res[0]["id"]
    rel = get(f"https://api.discogs.com/releases/{release_id}") if release_id else {}

    lines = []
    if master:
        lines.append(f"[{master.get('title', album)}](https://www.discogs.com/master/{master['id']})"
                     + (f" · edición: [{rel.get('country', '?')} {rel.get('released', '')[:4]}](https://www.discogs.com/release/{release_id})" if rel else ""))
    elif rel:
        lines.append(f"[{rel.get('title', album)}](https://www.discogs.com/release/{release_id})")

    # sello, catálogo, fecha, formato
    for lab in rel.get("labels", [])[:3]:
        cat = lab.get("catno") or ""
        lines.append(f"  Sello: [{_dname(lab['name'])}](https://www.discogs.com/label/{lab['id']})" + (f" – {cat}" if cat and cat.lower() != "none" else ""))
    meta = []
    if rel.get("released"):
        meta.append(f"Publicado: {rel['released']}")
    elif master and master.get("year"):
        meta.append(f"Año: {master['year']}")
    if rel.get("country"):
        meta.append(f"País: {rel['country']}")
    fmts = [f.get("name", "") + (f" ({', '.join(f.get('descriptions', [])[:3])})" if f.get("descriptions") else "") for f in rel.get("formats", [])[:2]]
    if fmts:
        meta.append("Formato: " + "; ".join(fmts))
    if meta:
        lines.append("  " + "   ".join(meta))
    styles = list(dict.fromkeys((rel.get("genres") or []) + (rel.get("styles") or [])))
    if styles:
        lines.append("  Estilos: " + ", ".join(styles))
    com = rel.get("community") or {}
    rating = (com.get("rating") or {})
    if com.get("have") or com.get("want"):
        r = f" · nota {rating['average']}/5 ({rating['count']})" if rating.get("count") else ""
        lines.append(f"  Comunidad: {com.get('have', 0)} lo tienen · {com.get('want', 0)} lo quieren{r}")

    # créditos (disco + pistas), agrupados por función
    credits = list(rel.get("extraartists", []))
    for t in rel.get("tracklist", []):
        credits += t.get("extraartists", [])
    groups = {g: {} for g, _ in CREDIT_GROUPS}
    for c in credits:
        role = c.get("role", "")
        for g, rx in CREDIT_GROUPS:
            if rx.search(role):
                name = _dname(c.get("name"))
                # «Engineer [ProTools Operators]» → detalle entre corchetes
                det = re.search(r"\[([^\]]+)\]", role)
                groups[g].setdefault(name, set())
                if det and g == "Ingeniería":
                    groups[g][name].add(det.group(1))
                break
    cred_lines = []
    for g, _ in CREDIT_GROUPS:
        if groups[g]:
            names = [n + (f" ({', '.join(sorted(d))})" if d else "") for n, d in groups[g].items()]
            cred_lines.append(f"  {g}: " + ", ".join(names[:10]) + (" …" if len(names) > 10 else ""))
    studios = {}
    for c in rel.get("companies", []):
        role = c.get("entity_type_name", "")
        if STUDIO_ROLES.search(role):
            studios.setdefault(_dname(c["name"]), []).append(role.lower())
    if studios:
        cred_lines.append("  Estudios y fábrica: " + ", ".join(
            f"{n} ({', '.join(dict.fromkeys(r))})" for n, r in studios.items()))
    if cred_lines:
        lines += ["  Créditos:"] + ["  " + l for l in cred_lines]
    return lines


# ── AudioMuse (recomendaciones por audio de tu biblioteca) ──────────────────

AUDIOMUSE_ENV = Path(os.environ.get("AUDIOMUSE_ENV", HOME / ".config/darkone4mod/audiomuse.env"))


def _audiomuse_cfg():
    cfg = {}
    try:
        for ln in AUDIOMUSE_ENV.read_text().splitlines():
            if "=" in ln and not ln.lstrip().startswith("#"):
                k, v = ln.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"\'')
    except OSError:
        pass
    return cfg


def audiomuse_servers():
    """[(nombre_en_audiomuse, etiqueta)] según AUDIOMUSE_SERVERS="srv=Etiqueta;srv2=Etiqueta2"."""
    raw = _audiomuse_cfg().get("AUDIOMUSE_SERVERS", "")
    out = []
    for part in raw.split(";"):
        if part.strip():
            srv, _, label = part.partition("=")
            out.append((srv.strip(), (label or srv).strip()))
    return out or [(None, "AudioMuse")]


def audiomuse_similar(artist, title, server=None, n=20):
    """Lista de (artista, título, similitud%, género·ánimo) o None si la canción no está analizada."""
    import requests
    cfg = _audiomuse_cfg()
    url, tok = cfg.get("AUDIOMUSE_URL"), cfg.get("AUDIOMUSE_TOKEN")
    if not (url and tok):
        return []
    params = {"title": title, "artist": artist, "n": n + 5, "eliminate_duplicates": "true"}
    if server:
        params["server"] = server
    r = requests.get(f"{url.rstrip('/')}/api/similar_tracks", params=params,
                     headers={"Authorization": f"Bearer {tok}", **UA}, timeout=15)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    seed = (mix_norm(artist), mix_norm(title, title=True))
    out = []
    for t in r.json():
        a, ti = t.get("author") or t.get("album_artist") or "", t.get("title") or ""
        if (mix_norm(a), mix_norm(ti, title=True)) == seed:
            continue
        sim = max(0, round((1 - float(t.get("distance", 1))) * 100))
        extra = " · ".join(x for x in (t.get("top_genre"), t.get("top_mood")) if x)
        out.append((a, ti, sim, extra, t.get("album") or ""))
        if len(out) >= n:
            break
    return out


PLAYLIST_DIR = HOME / ".cache/darkone4mod/similares"


def audiomuse_paths():
    """{etiqueta: carpeta preferida} según AUDIOMUSE_PATHS="Mix=/mnt/windows/Mix;moode=/mnt/NFS/moode"."""
    out = {}
    for part in _audiomuse_cfg().get("AUDIOMUSE_PATHS", "").split(";"):
        label, _, path = part.partition("=")
        if label.strip() and path.strip():
            out[label.strip()] = path.strip()
    return out


def playlist_request(name, prefer, rows):
    """Fichero para «▶ crear lista»: lo lee el plugin DarkOne4Mod, que busca cada
    canción en la biblioteca de DeaDBeeF. Devuelve el enlace ddbpl:…"""
    import hashlib
    body = f"#name\t{name}\n" + (f"#prefer\t{prefer}\n" if prefer else "")
    body += "".join(f"{a}\t{t}\t{al}\n".replace("\r", "") for a, t, al in rows)
    PLAYLIST_DIR.mkdir(parents=True, exist_ok=True)
    f = PLAYLIST_DIR / (hashlib.sha1(body.encode()).hexdigest()[:16] + ".tsv")
    if not f.exists():
        f.write_text(body, encoding="utf-8")
    # limpieza: fuera las de más de 30 días
    cutoff = time.time() - 30 * 86400
    for old in PLAYLIST_DIR.glob("*.tsv"):
        try:
            if old.stat().st_mtime < cutoff:
                old.unlink()
        except OSError:
            pass
    return f"ddbpl:{f}"


def audiomuse_sections(artist, title, n=15):
    """Una sección por biblioteca de AudioMuse; ☆ = ya está en Mix.
    Junto a cada título, «▶ crear lista» con esas recomendaciones."""
    from concurrent.futures import ThreadPoolExecutor
    servers = audiomuse_servers()
    in_mix = {(mix_norm(a), mix_norm(t, title=True)) for a, t, _ in mix_rows()}

    def one(srv):
        try:
            return audiomuse_similar(artist, title, srv, n)
        except Exception as e:
            return f"(no disponible: {type(e).__name__})"

    with ThreadPoolExecutor(max_workers=len(servers)) as ex:
        results = list(ex.map(one, [s for s, _ in servers]))
    lines = []
    paths = audiomuse_paths()
    for (srv, label), res in zip(servers, results):
        if isinstance(res, list) and res:
            rows = [(artist, title, "")] + [(a, ti, al) for a, ti, _, _, al in res]
            link = playlist_request(f"AudioMuse · {label}", paths.get(label), rows)
            lines.append(f"## AudioMuse · {label}  [▶ crear lista]({link})")
        else:
            lines.append(f"## AudioMuse · {label}")
        if res is None:
            lines.append("  (esta canción no está analizada en esta biblioteca)")
        elif isinstance(res, str):
            lines.append("  " + res)
        elif not res:
            lines.append("  (sin resultados)")
        else:
            for a, ti, sim, extra, _al in res:
                star = "☆" if (mix_norm(a), mix_norm(ti, title=True)) in in_mix else "  "
                lines.append(f"{star} {a}  —  {ti}  ({sim}%{', ' + extra if extra else ''})")
        lines.append("")
    return lines


# ── Colecciones (DarkOne4Mod: tools/colecciones_index.py) ─────────────────────

COLECCIONES_DB = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "darkone4mod/colecciones_info.sqlite"


def _album_alias(album):
    """«Nevermind (Deluxe Edition)» → también «Nevermind»."""
    return [album, re.sub(r"\s*[\(\[][^\)\]]*[\)\]]\s*$", "", album or "")]


def colecciones_album_lines(artist, album, max_listas=25, max_libros=8):
    """Colecciones, notas, singles y libros del álbum (lo mismo que los iconos)."""
    if not COLECCIONES_DB.is_file():
        return []
    db = _ro(COLECCIONES_DB)
    try:
        glifo, descr = {}, {}
        row = db.execute("select json from leyenda").fetchone()
        if row:
            ley = json.loads(row[0])
            glifo = {k: g for k, g, _ in ley.get("album", []) + ley.get("pista", [])}
            descr = {k: d for k, _, d in ley.get("album", []) + ley.get("pista", [])}
        data = None
        for al in _album_alias(album):
            row = db.execute("select json from album where clave = ?",
                             (f"{mix_norm(artist)}\t{mix_norm(al, True)}",)).fetchone()
            if row:
                data = json.loads(row[0])
                break
        row = db.execute("select json from artista where clave = ?", (mix_norm(artist),)).fetchone()
        libros = json.loads(row[0]).get("libros", []) if row else []
    finally:
        db.close()

    lines = []
    if data:
        notas = data.get("notas") or {}
        if notas:
            lines.append("Notas: " + " · ".join(f"{k} {v:g}" if isinstance(v, (int, float)) else f"{k} {v}"
                                                for k, v in notas.items()))
        cols = data.get("colecciones") or []
        # primero las que dan icono, luego el resto
        cols.sort(key=lambda c: (not (len(c) > 2 and c[2]), c[1] is None, c[1] or 0))
        for c in cols[:max_listas]:
            name, rank, cat = c[0], c[1], (c[2] if len(c) > 2 else "")
            g = glifo.get(cat, "·")
            lines.append(f"{g} {name}" + (f"  · nº {rank}" if rank and cat != "premios" else ""))
        if len(cols) > max_listas:
            lines.append(f"  … y {len(cols) - max_listas} listas más")
        singles = data.get("singles") or []
        propios = [s for s in singles if not s.get("tipo")]
        otros = [s for s in singles if s.get("tipo")]
        if propios:
            lines.append(f"{glifo.get('single', '♪')} Singles: " + ", ".join(
                f"{s['titulo']} ({s['fecha'][:4]})" if s.get("fecha") else s["titulo"] for s in propios))
        if otros:
            lines.append(f"{glifo.get('single_otro', '↺')} Otros singles: " + ", ".join(
                f"{s['titulo']} ({s['tipo']}{', ' + s['fecha'][:4] if s.get('fecha') else ''})" for s in otros))
    if libros:
        extra = f" y {len(libros) - max_libros} más" if len(libros) > max_libros else ""
        lines.append(f"{glifo.get('libros', '❡')} El artista sale en: " + "; ".join(libros[:max_libros]) + extra)
    # leyenda de los iconos que tiene este álbum, en el orden de los iconos
    usados = {c[2] for c in (data or {}).get("colecciones") or [] if len(c) > 2 and c[2]}
    if data and any(not s.get("tipo") for s in data.get("singles") or []):
        usados.add("single")
    if data and any(s.get("tipo") for s in data.get("singles") or []):
        usados.add("single_otro")
    if libros:
        usados.add("libros")
    ley = [f"{glifo[k]} {d}" for k, d in descr.items() if k in usados and k in glifo]
    if ley:
        lines.append("Iconos: " + " · ".join(ley))
    return lines


# ── Mix ──────────────────────────────────────────────────────────────────────

def mix_rows():
    try:
        text = MIX_INDEX.read_text(encoding="utf-8")
    except OSError:
        return []
    return [ln.split("\t") for ln in text.splitlines() if ln.count("\t") >= 2]


def mix_artist_lines(artist, limit=15):
    a = mix_norm(artist)
    if not a:
        return []
    own, collab = [], []
    split = re.compile(r"\s*(?:&|,| and | feat\.? | ft\.? | x | vs\.? )\s*", re.I)
    for art, title, rel in mix_rows():
        if mix_norm(art) == a:
            own.append((title, rel))
        elif any(mix_norm(p) == a for p in split.split(art)):
            collab.append((title, rel))
    if not own and not collab:
        return ["En Mix: ninguna canción"]
    n = len(own) + len(collab)
    lines = [f"En Mix: {n} " + ("canción" if n == 1 else "canciones") + (f" ({len(collab)} en colaboración)" if collab else "")]
    for title, rel in (own + collab)[:limit]:
        folder = rel.split("/", 1)[0] if "/" in rel else ""
        lines.append(f"  ☆ {title}" + (f"  [{folder}]" if folder else ""))
    if n > limit:
        lines.append(f"  … y {n - limit} más")
    return lines


if __name__ == "__main__":
    import sys
    if "--refresh-vvmm" in sys.argv:
        _vvmm_build()


# ── Textos completos: Last.fm (bio / wiki) y, si no hay, Wikipedia ───────────

LASTFM_TAIL = re.compile(r"\s*(<a [^>]*>\s*)?Read more on Last\.fm.*$", re.I | re.S)
LASTFM_LICENSE = re.compile(r"\s*User-contributed text is available under the Creative Commons.*$", re.I | re.S)
WP_SKIP = {"references", "external links", "see also", "notes", "further reading", "bibliography",
           "sources", "citations", "footnotes", "referencias", "enlaces externos", "véase también", "notas"}


def lastfm_full(block):
    """Texto completo de un bloque bio/wiki de Last.fm, sin «Read more on Last.fm» ni la licencia."""
    if not block:
        return ""
    html = block.get("content") or block.get("summary") or ""
    html = LASTFM_LICENSE.sub("", LASTFM_TAIL.sub("", html))
    html = re.sub(r"<br\s*/?>|</p>\s*<p[^>]*>", "\n", html, flags=re.I)
    text = re.sub(r"<[^>]+>", "", html)
    text = (text.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
                .replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " "))
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def wikipedia_full(title, lang="en"):
    """Artículo completo (texto plano) con los apartados como «## Título»; sin referencias."""
    import requests
    r = requests.get(f"https://{lang}.wikipedia.org/w/api.php", params={
        "action": "query", "titles": title, "prop": "extracts", "explaintext": 1,
        "exsectionformat": "wiki", "redirects": 1, "format": "json",
    }, headers=UA, timeout=15)
    page = next(iter(r.json()["query"]["pages"].values()))
    raw = (page.get("extract") or "").strip()
    if not raw or "may refer to" in raw[:300]:
        return page.get("title"), ""
    out, skip = [], False
    for ln in raw.splitlines():
        m = re.match(r"^(=+)\s*(.*?)\s*=+$", ln.strip())
        if m:
            name = m.group(2)
            skip = name.lower() in WP_SKIP
            if not skip:
                out += ["", f"## {name}"]
            continue
        if not skip:
            out.append(ln)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    # apartados que se quedaron vacíos
    text = re.sub(r"## [^\n]*\n+(?=## |\Z)", "", text)
    return page.get("title"), text.strip()


# ── fotos del artista ────────────────────────────────────────────────────────
# Se bajan a ~/.cache/darkone4mod/fotos/ y se devuelven como «![](ruta)»; Infobar NG
# las pinta como miniaturas (clic: abrir la imagen).

PHOTO_DIR = CACHE_DIR / "fotos"


def _same_artist(a, b):
    return enorm_the(_dname(a)) == enorm_the(b)


def _photo_urls(artist, n=6):
    import requests
    from concurrent.futures import ThreadPoolExecutor

    def discogs():
        tok = _discogs_token()
        if not tok:
            return []
        h = dict(UA, Authorization=f"Discogs token={tok}")
        res = requests.get("https://api.discogs.com/database/search", params={"q": artist, "type": "artist", "per_page": 5},
                           headers=h, timeout=8).json().get("results", [])
        hit = next((r for r in res if _same_artist(r.get("title", ""), artist)), None)
        if not hit:
            return []
        imgs = requests.get(f"https://api.discogs.com/artists/{hit['id']}", headers=h, timeout=8).json().get("images", [])
        imgs.sort(key=lambda i: i.get("type") != "primary")
        return [i["uri"] for i in imgs if i.get("uri")][:4]

    def deezer():
        res = requests.get("https://api.deezer.com/search/artist", params={"q": artist, "limit": 5},
                           headers=UA, timeout=8).json().get("data", [])
        hit = next((r for r in res if _same_artist(r.get("name", ""), artist)), None)
        pic = hit and hit.get("picture_xl")
        return [pic] if pic and "/artist//" not in pic else []      # «//» = sin foto

    def wikipedia():
        r = requests.get("https://en.wikipedia.org/w/api.php", params={
            "action": "query", "titles": artist, "prop": "pageimages|extracts", "piprop": "original",
            "exintro": 1, "explaintext": 1, "exchars": 1500, "redirects": 1, "format": "json"},
            headers=UA, timeout=8).json()
        page = next(iter(r.get("query", {}).get("pages", {}).values()), {})
        src = page.get("original", {}).get("source")
        txt = (page.get("extract") or "").lower()
        music = any(w in txt for w in ("band", "musician", "singer", "rapper", "producer", " dj", "composer", "duo", "group"))
        return [src] if src and music and not src.lower().endswith(".svg") else []

    out = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = [ex.submit(f) for f in (discogs, deezer, wikipedia)]
        for f in futs:
            try:
                out += f.result()
            except Exception:
                pass
    seen, uniq = set(), []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq[:n]


def artist_photos(artist, n=6):
    """Rutas locales de hasta n fotos del artista (Discogs, Deezer, Wikipedia)."""
    import hashlib
    import requests
    from concurrent.futures import ThreadPoolExecutor
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)

    def get(url):
        ext = os.path.splitext(url.split("?")[0])[1].lower()
        p = PHOTO_DIR / (hashlib.sha1(url.encode()).hexdigest() + (ext if ext in (".jpg", ".jpeg", ".png", ".webp") else ".jpg"))
        if p.exists() and p.stat().st_size > 0:
            return str(p)
        r = requests.get(url, headers=UA, timeout=10)
        if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
            return None
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_bytes(r.content)
        tmp.replace(p)
        return str(p)

    urls = _photo_urls(artist, n)
    with ThreadPoolExecutor(max_workers=4) as ex:
        res = list(ex.map(lambda u: (lambda: get(u))() if u else None, urls))
    return [p for p in res if p]


def photo_line(artist, n=6):
    try:
        paths = artist_photos(artist, n)
    except Exception:
        return []
    return [" ".join(f"![]({p})" for p in paths)] if paths else []
