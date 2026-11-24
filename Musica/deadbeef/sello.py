#!/home/huan/Scripts/python_venv/bin/python
"""Pestaña «Sello» de Infobar NG: el sello del disco que suena.

Uso: sello.py <artista> <álbum>
     sello.py --worker <id de sello en Discogs>   (lo lanza el propio script, en segundo plano)

- País, fundación, tipo, fundadores, sello matriz y subsellos: music-fuzzy (tabla labels),
  MusicBrainz y Discogs.
- Estudios, masterización, ingenieros y productores habituales: créditos de tus discos del
  sello (albums.credits…, discogs_discography) y de una muestra de los discos del sello en
  Discogs (la baja el worker poco a poco; mientras tanto la salida empieza con <!--parcial-->
  e Infobar NG no la guarda en caché y la vuelve a pedir).
- Discos del sello: los que tienes, otros de artistas que tienes y otros del sello.
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from darkone_links import (CACHE_DIR, CREDIT_GROUPS, STUDIO_ROLES, UA, _discogs_token, _dname,  # noqa: E402
                           _ro, mix_norm)

MUSICA_DB = Path(os.environ.get("MFUZZ_DB", Path.home() / "gits/pollo/music-fuzzy/db/sqlite/sync/musica_local.sqlite"))
SELLOS = CACHE_DIR / "sellos"
TTL = 30 * 86400
MUESTRA = 40            # discos del sello en Discogs de los que se leen los créditos
PARCIAL = "<!--parcial-->"
GENERICOS = {"[no label]", "not on label", "self-released", "none", ""}

# papeles que cuentan como «gente del sonido» (grupo → regex), de CREDIT_GROUPS
GENTE = [(g, rx) for g, rx in CREDIT_GROUPS if g in ("Masterización", "Ingeniería", "Mezcla", "Producción")]


def label_norm(s):
    s = _dname(s or "").lower()
    s = re.sub(r"\b(records?|recordings?|music|label|ltd\.?|limited|inc\.?|llc|gmbh|s\.?l\.?|co\.?)\b", " ", s)
    return mix_norm(s)


def cached(name, fn, ttl=TTL):
    SELLOS.mkdir(parents=True, exist_ok=True)
    p = SELLOS / f"{re.sub(r'[^a-z0-9_-]+', '_', name.lower())[:80]}.json"
    if p.is_file() and time.time() - p.stat().st_mtime < ttl:
        try:
            return json.loads(p.read_text())
        except ValueError:
            pass
    try:
        data = fn()
    except Exception:
        return None
    if data is not None:
        p.write_text(json.dumps(data, ensure_ascii=False))
    return data


def http():
    import requests
    return requests


# ── el sello del disco ──────────────────────────────────────────────────────

def local_album(db, artist, album):
    al = {mix_norm(album, True), mix_norm(re.sub(r"\s*[\(\[][^\)\]]*[\)\]]\s*$", "", album), True)}
    rows = db.execute("select al.id, al.name, al.label, al.catalognumber, al.year, ar.name from albums al "
                      "join artists ar on ar.id = al.artist_id where lower(ar.name) = lower(?)", (artist,)).fetchall()
    if not rows:
        a = mix_norm(artist)
        rows = [r for r in db.execute("select al.id, al.name, al.label, al.catalognumber, al.year, ar.name from albums al "
                                      "join artists ar on ar.id = al.artist_id") if mix_norm(r[5]) == a]
    for r in rows:
        if mix_norm(r[1], True) in al:
            return r
    return None


def discogs_get(path, **params):
    tok = _discogs_token()
    if not tok:
        return {}
    h = dict(UA, Authorization=f"Discogs token={tok}")
    r = http().get(f"https://api.discogs.com/{path}", params=params or None, headers=h, timeout=8)
    if r.status_code == 429:
        time.sleep(5)
        r = http().get(f"https://api.discogs.com/{path}", params=params or None, headers=h, timeout=8)
    return r.json() if r.ok else {}


def discogs_label_of(artist, album):
    """(nombre, id, catálogo) del sello del disco según Discogs."""
    def f():
        for kind in ("master", "release"):
            res = discogs_get("database/search", artist=artist, release_title=album, type=kind, per_page=3).get("results", [])
            if res:
                rid = res[0]["id"]
                if kind == "master":
                    rid = discogs_get(f"masters/{rid}").get("main_release")
                rel = discogs_get(f"releases/{rid}") if rid else {}
                for lab in rel.get("labels", []):
                    if lab.get("name", "").lower() not in GENERICOS:
                        return [lab["name"], lab["id"], lab.get("catno") or ""]
                return None
        return None
    return cached(f"album_{mix_norm(artist)}_{mix_norm(album, True)}", f)


def discogs_label_by_name(name):
    def f():
        res = discogs_get("database/search", q=name, type="label", per_page=5).get("results", [])
        n = label_norm(name)
        for r in res:
            if label_norm(r.get("title")) == n:
                return r["id"]
        return res[0]["id"] if res else None
    return cached(f"dgid_{label_norm(name)}", f)


# ── información del sello ───────────────────────────────────────────────────

def mb_label(name):
    def f():
        rq = http()
        base = "https://musicbrainz.org/ws/2"
        res = rq.get(f"{base}/label", params={"query": f'label:"{name}"', "fmt": "json", "limit": 5},
                     headers=UA, timeout=8).json().get("labels", [])
        n = label_norm(name)
        hit = next((x for x in res if label_norm(x.get("name")) == n), None)
        if not hit:
            return {}
        time.sleep(1.1)
        return rq.get(f"{base}/label/{hit['id']}", params={"inc": "label-rels+artist-rels+url-rels", "fmt": "json"},
                      headers=UA, timeout=8).json()
    return cached(f"mb_{label_norm(name)}", f) or {}


def discogs_label(lid):
    return cached(f"dg_{lid}", lambda: discogs_get(f"labels/{lid}")) or {} if lid else {}


def local_label(db, name):
    n = label_norm(name)
    cols = ("name", "country", "founded_year", "mb_type", "profile", "parent_label", "subsidiary_labels",
            "official_website", "wikipedia_url", "discogs_url", "bandcamp_url", "mbid", "id")
    # columnas de music-fuzzy db/discogs/sellos_detalle.py (si ya ha pasado por la db)
    have = {r[1] for r in db.execute("pragma table_info(labels)")}
    cols += tuple(c for c in ("discogs_id", "detalle_checked", "detalle_muestra", "mb_relaciones", "discogs_parent",
                              "discogs_sublabels") if c in have)
    for r in db.execute(f"select {', '.join(cols)} from labels where lower(name) = lower(?)", (name,)).fetchall() or \
            [r for r in db.execute(f"select {', '.join(cols)} from labels") if label_norm(r[0]) == n]:
        return dict(zip(cols, r))
    return {}


def lifespan(ls):
    b, e = (ls or {}).get("begin"), (ls or {}).get("end")
    if b and e:
        return f"{b[:4]}–{e[:4]}"
    return b[:4] if b else ""


def mb_relations(mb):
    """fundadores, dueños, matriz, subsellos, webs."""
    out = defaultdict(list)
    for r in mb.get("relations", []):
        t, d = r.get("type", ""), r.get("direction")
        when = lifespan({"begin": r.get("begin"), "end": r.get("end")})
        when = f" ({when})" if when else ""
        if r.get("target-type") == "artist":
            a = r["artist"]["name"]
            if "founder" in t:
                out["fundadores"].append(a + when)
            elif "owner" in t:
                out["dueños"].append(a + when)
            elif "personal label" in t:
                out["sello personal de"].append(a)
        elif r.get("target-type") == "label":
            lab = r["label"]["name"]
            if t in ("label ownership", "imprint", "label reissue", "label distribution", "business association",
                     "label rename"):
                if t == "label rename":
                    out["antes" if d == "backward" else "después"].append(lab + when)
                elif d == "backward":
                    out["pertenece a" if t == "label ownership" else f"{t} de"].append(lab + when)
                else:
                    out["subsellos" if t in ("label ownership", "imprint") else t].append(lab + when)
        elif r.get("target-type") == "url":
            out["url_" + t].append(r["url"]["resource"])
    return out


# ── créditos ────────────────────────────────────────────────────────────────

def add_credits(people, studios, extraartists, companies):
    for c in extraartists or []:
        role, name = c.get("role", ""), _dname(c.get("name", ""))
        for g, rx in GENTE:
            if rx.search(role):
                people[g][name] += 1
                break
    for c in companies or []:
        role = c.get("entity_type_name", "")
        if re.search(r"(recorded|mixed|mastered|engineered|produced|remastered|lacquer cut) at", role, re.I) \
                and not re.search(r"glass", role, re.I):
            studios[_dname(c.get("name", ""))] += 1


def collection(db, label):
    """tus discos del sello y sus créditos."""
    n = label_norm(label)
    people, studios = defaultdict(Counter), Counter()
    mine = []
    q = ("select al.name, al.year, ar.name, al.label, al.credits, al.engineers, al.mastering_engineers, al.producers "
         "from albums al join artists ar on ar.id = al.artist_id where al.label is not null and al.label <> ''")
    for name, year, art, lab, credits, eng, mas, prod in db.execute(q):
        if label_norm(lab) != n:
            continue
        mine.append((art, name, str(year or "")[:4]))
        try:
            cr = json.loads(credits) if credits else {}
        except ValueError:
            cr = {}
        if cr:
            for role, names in cr.items():
                for nm in names if isinstance(names, list) else [names]:
                    if re.search(r"(recorded|mixed|mastered) at|studio", role, re.I):
                        studios[_dname(nm)] += 1
                        continue
                    for g, rx in GENTE:
                        if rx.search(role):
                            people[g][_dname(nm)] += 1
                            break
        else:
            for g, field in (("Ingeniería", eng), ("Masterización", mas), ("Producción", prod)):
                for nm in re.split(r",\s*|;\s*", field or ""):
                    if nm:
                        people[g][nm] += 1
    return mine, people, studios


def artist_releases(db, label, label_ids, mine_keys):
    """discos del sello de artistas que tienes (discogs_discography) que no están en tu colección."""
    n = label_norm(label)
    ids = {str(i) for i in label_ids if i}
    out, seen = [], set()
    people, studios = defaultdict(Counter), Counter()
    first = label.split()[0] if label.split() else label
    q = ("select ar.name, d.album_name, d.year, d.label, d.labels, d.extraartists, d.companies, d.role, d.format "
         "from discogs_discography d join artists ar on ar.id = d.artist_id where d.label like ?")
    for art, title, year, lab, labs, extra, comp, role, fmt in db.execute(q, (f"%{first}%",)):
        ok = label_norm(lab) == n
        if not ok and labs and ids:
            try:
                ok = any(str(x.get("id")) in ids for x in json.loads(labs))
            except ValueError:
                pass
        if not ok:
            continue
        try:
            add_credits(people, studios, json.loads(extra) if extra else [], json.loads(comp) if comp else [])
        except ValueError:
            pass
        if role and role != "Main":
            continue
        k = (mix_norm(art), mix_norm(title, True))
        if k in mine_keys or k in seen:
            continue
        seen.add(k)
        out.append((art, title, str(year or "")[:4], fmt or ""))
    return out, people, studios


# ── worker: discos del sello en Discogs y una muestra de sus créditos ───────

def worker_path(lid):
    return SELLOS / f"dgrel_{lid}.json"


BUZON_REMOTO = "pepecono:/home/pepe/gits/pollo/music-fuzzy/db/sqlite/buzon_sellos/"


def enviar(lid):
    """manda el sello ya completo al buzón de music-fuzzy en pepecono (lo importa el cron)."""
    p = worker_path(lid)
    marca = SELLOS / f"dgrel_{lid}.enviado"
    if not p.is_file() or marca.is_file():
        return
    try:
        if not json.loads(p.read_text()).get("terminado"):
            return
        ssh = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=5"]
        host, ruta = BUZON_REMOTO.split(":", 1)
        subprocess.run(["ssh", *ssh, host, f"mkdir -p {ruta}"], check=True, timeout=30,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["scp", "-q", *ssh, str(p), BUZON_REMOTO + p.name], check=True, timeout=60,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        marca.touch()
    except (subprocess.SubprocessError, OSError, ValueError):
        pass        # se reintenta la próxima vez que se abra el sello


def lanzar(*args):
    subprocess.Popen([sys.executable, __file__, *map(str, args)], start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run_worker(lid, label=""):
    SELLOS.mkdir(parents=True, exist_ok=True)
    out = worker_path(lid)
    lock = SELLOS / f"dgrel_{lid}.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        if time.time() - lock.stat().st_mtime < 900:
            return
    try:
        rels = []
        for page in (1, 2, 3):
            d = discogs_get(f"labels/{lid}/releases", page=page, per_page=100)
            rels += d.get("releases", [])
            if page >= (d.get("pagination") or {}).get("pages", 1):
                break
            time.sleep(1.1)
        # uno por disco (el primer lanzamiento de cada artista+título)
        uniq = {}
        for r in rels:
            k = (mix_norm(_dname(r.get("artist", ""))), mix_norm(r.get("title", ""), True))
            if k not in uniq or (r.get("year") or 9999) < (uniq[k].get("year") or 9999):
                uniq[k] = r
        discos = [{"artist": _dname(r.get("artist", "")), "title": r.get("title", ""), "year": r.get("year") or 0,
                   "format": r.get("format", ""), "id": r.get("id")} for r in uniq.values()]
        data = {"discos": discos, "studios": {}, "people": {}, "muestra": 0, "terminado": False,
                "label": label, "discogs_id": lid}
        out.write_text(json.dumps(data, ensure_ascii=False))
        # muestra repartida por años
        sample = sorted(discos, key=lambda x: x["year"] or 0)
        if len(sample) > MUESTRA:
            step = len(sample) / MUESTRA
            sample = [sample[int(i * step)] for i in range(MUESTRA)]
        people, studios = defaultdict(Counter), Counter()
        for i, dsc in enumerate(sample, 1):
            time.sleep(1.1)
            rel = discogs_get(f"releases/{dsc['id']}")
            extra = list(rel.get("extraartists", []))
            for t in rel.get("tracklist", []):
                extra += t.get("extraartists", [])
            add_credits(people, studios, extra, rel.get("companies", []))
            if i % 10 == 0 or i == len(sample):
                data.update(studios=dict(studios), people={g: dict(c) for g, c in people.items()}, muestra=i,
                            terminado=i == len(sample))
                out.write_text(json.dumps(data, ensure_ascii=False))
        if not sample:
            data["terminado"] = True
            out.write_text(json.dumps(data, ensure_ascii=False))
    finally:
        lock.unlink(missing_ok=True)
    enviar(lid)


def worker_data(lid, label=""):
    """datos del worker; lo lanza si no hay o son viejos. Devuelve (datos, terminado)."""
    if not lid:
        return None, True
    p = worker_path(lid)
    data = None
    if p.is_file():
        try:
            data = json.loads(p.read_text())
        except ValueError:
            data = None
    fresh = p.is_file() and time.time() - p.stat().st_mtime < TTL
    running = (SELLOS / f"dgrel_{lid}.lock").is_file()
    if (not data or not fresh or not data.get("terminado")) and not running and _discogs_token():
        lanzar("--worker", lid, label)
        running = True
    return data, bool(data and data.get("terminado")) or not running


# ── salida ──────────────────────────────────────────────────────────────────

def top(counter, n=8, minimo=1):
    items = [(k, v) for k, v in counter.most_common() if k and v >= minimo][:n]
    return " · ".join(f"{k} ({v})" if v > 1 else k for k, v in items)


def merge(*pairs):
    people, studios = defaultdict(Counter), Counter()
    for p, s in pairs:
        for g, c in (p or {}).items():
            people[g].update(c)
        studios.update(s or {})
    return people, studios


TIPO_GRUPO = {"masterizacion": "Masterización", "grabacion": "Ingeniería", "mezcla": "Mezcla",
              "produccion": "Producción"}


def db_data(db, ll):
    """catálogo y créditos que ya guardó music-fuzzy (db/discogs/sellos_detalle.py)."""
    lid = ll["id"]
    discos = [{"artist": a, "title": t, "year": y or 0, "format": f or "", "id": i} for i, a, t, y, f in db.execute(
        "select discogs_id, artista, titulo, anio, formato from label_catalog where label_id = ?", (lid,))]
    studios, people = {}, defaultdict(dict)
    for tipo, nombre, veces in db.execute("select tipo, nombre, veces from label_credits where label_id = ?", (lid,)):
        if tipo == "estudio":
            studios[nombre] = veces
        else:
            people[TIPO_GRUPO.get(tipo, tipo)][nombre] = veces
    return {"discos": discos, "studios": studios, "people": dict(people), "muestra": ll.get("detalle_muestra") or 0,
            "terminado": True}, True


def main(artist, album):
    db = _ro(MUSICA_DB) if MUSICA_DB.is_file() else None
    loc = local_album(db, artist, album) if db else None
    label, lid, catno = (loc[2] if loc and loc[2] and loc[2].lower() not in GENERICOS else None), None, (loc[3] if loc else "")
    if not label:
        dg = discogs_label_of(artist, album)
        if dg:
            label, lid, catno = dg[0], dg[1], catno or dg[2]
    if not label:
        print("No sé de qué sello es este disco (ni en tu colección ni en Discogs).")
        return
    label = _dname(label)
    ll = local_label(db, label) if db else {}
    if not lid and ll.get("discogs_id"):
        lid = ll["discogs_id"]
    if not lid:
        m = re.search(r"/label/(\d+)", ll.get("discogs_url") or "")
        lid = int(m.group(1)) if m else discogs_label_by_name(label)
    dl = discogs_label(lid)
    mb = mb_label(label)
    rel = json.loads(ll["mb_relaciones"]) if ll.get("mb_relaciones") else mb_relations(mb)
    # fuera las relaciones consigo mismo («Warp» imprint de «Warp Records Limited»)
    rel = {k: [x for x in v if k.startswith("url_") or label_norm(re.sub(r"\s*\(\d{4}.*\)$", "", x)) != label_norm(label)]
           for k, v in rel.items()}

    out = []
    head = f"## {ll.get('name') or _dname(dl.get('name')) or label}"
    out.append(head)
    if catno and catno.lower() != "none":
        out.append(f"Este disco: {catno}")
    # país, fundación, tipo
    area = (mb.get("area") or {}).get("name") or ""
    pais = ll.get("country") or mb.get("country") or ""
    pais = f"{area} ({pais})" if area and pais and area != pais else (area or pais)
    datos = []
    if pais:
        datos.append(f"País: {pais}")
    vida = lifespan(mb.get("life-span")) or str(ll.get("founded_year") or "")
    if vida:
        datos.append(("Activo: " if "–" in vida else "Fundado: ") + vida)
    tipo = mb.get("type") or ll.get("mb_type")
    if tipo:
        datos.append(f"Tipo: {tipo}")
    if datos:
        out.append("   ".join(datos))
    for k, lab in (("fundadores", "Fundadores"), ("dueños", "Dueños"), ("sello personal de", "Sello personal de")):
        if rel.get(k):
            out.append(f"{lab}: " + ", ".join(dict.fromkeys(rel[k])))
    matriz = list(dict.fromkeys(rel.get("pertenece a", [])))
    if dl.get("parent_label"):
        p = _dname(dl["parent_label"]["name"])
        if not any(label_norm(p) == label_norm(re.sub(r"\s*\(.*\)$", "", m)) for m in matriz):
            matriz.append(p)
    if not matriz and ll.get("parent_label"):
        matriz.append(ll["parent_label"])
    yo = label_norm(label)
    matriz = [m for m in matriz if label_norm(re.sub(r"\s*\(\d{4}.*\)$", "", m)) != yo]
    out.append("Subsidiario de: " + (", ".join(matriz) if matriz else "no (independiente, que se sepa)"))
    for k in [k for k in rel if k.endswith(" de") and k not in ("pertenece a", "sello personal de")]:
        out.append(f"{k.capitalize()}: " + ", ".join(dict.fromkeys(rel[k])))
    subs = [_dname(s["name"]) for s in dl.get("sublabels", [])] or json.loads(ll.get("discogs_sublabels") or "[]") \
        or rel.get("subsellos", [])
    if subs:
        out.append(f"Subsellos ({len(subs)}): " + ", ".join(list(dict.fromkeys(subs))[:15]) + (" …" if len(subs) > 15 else ""))
    for k, lab in (("antes", "Antes se llamaba"), ("después", "Pasó a llamarse")):
        if rel.get(k):
            out.append(f"{lab}: " + ", ".join(rel[k]))
    links = []
    if lid:
        links.append(f"[Discogs](https://www.discogs.com/label/{lid})")
    if mb.get("id"):
        links.append(f"[MusicBrainz](https://musicbrainz.org/label/{mb['id']})")
    for u in (ll.get("official_website"), *(rel.get("url_official homepage") or [])[:1]):
        if u:
            links.append(f"[web]({u})")
            break
    for u in (ll.get("bandcamp_url"), *(rel.get("url_bandcamp") or [])[:1]):
        if u:
            links.append(f"[Bandcamp]({u})")
            break
    if "wikipedia.org/wiki/" in (ll.get("wikipedia_url") or ""):
        links.append(f"[Wikipedia]({ll['wikipedia_url']})")
    if links:
        out.append(" · ".join(links))
    # marcado de Discogs: [l=Nombre] → Nombre; las líneas con [l12345] («para el otro sello, ver…») fuera
    perfil = "\n".join(ln for ln in (dl.get("profile") or ll.get("profile") or "").splitlines()
                       if not re.search(r"\[[lram]\d+\]", ln))
    perfil = re.sub(r"\[[a-z]=([^\]]*)\]", r"\1", perfil)
    perfil = re.sub(r"\[/?[biu]\]|\[url=[^\]]*\]|\[/url\]", "", perfil)
    perfil = re.sub(r"\n{3,}", "\n\n", perfil).strip()
    if perfil:
        out += ["", perfil[:700] + ("…" if len(perfil) > 700 else "")]
    out.append("")

    # créditos
    mine, p1, s1 = collection(db, label) if db else ([], {}, {})
    mine_keys = {(mix_norm(a), mix_norm(t, True)) for a, t, _ in mine}
    otros_tuyos, p2, s2 = artist_releases(db, label, [lid], mine_keys) if db else ([], {}, {})
    wd, terminado = db_data(db, ll) if ll.get("detalle_checked") else worker_data(lid, label)
    if wd and terminado and not ll.get("detalle_checked") and not (SELLOS / f"dgrel_{lid}.enviado").is_file():
        lanzar("--enviar", lid)
    wd = wd or {}
    people, studios = merge((p1, s1), (p2, s2), ({g: Counter(c) for g, c in wd.get("people", {}).items()},
                                                 Counter(wd.get("studios", {}))))
    out.append("## Sonido del sello")
    muestra = f"{len(mine)} discos tuyos" + (f" + {wd['muestra']} del sello en Discogs" if wd.get("muestra") else "")
    out.append(f"(créditos de {muestra}" + ("; leyendo más en Discogs…)" if not terminado else ")"))
    s = top(studios, 10)
    out.append("Estudios: " + (s or "sin datos"))
    for g, lab in (("Masterización", "Masterización"), ("Ingeniería", "Grabación"), ("Mezcla", "Mezcla"),
                   ("Producción", "Producción")):
        t = top(people.get(g, Counter()), 8)
        if t:
            out.append(f"{lab}: {t}")
    out.append("")

    # discos
    out.append(f"## Discos del sello")
    if mine:
        out.append(f"En tu colección ({len(mine)}):")
        for a, t, y in sorted(mine, key=lambda x: (x[2] or "9999", x[0].lower())):
            out.append(f"  ✓ {a} — {t}" + (f" ({y})" if y else ""))
    if otros_tuyos:
        out.append(f"De artistas que tienes ({len(otros_tuyos)}):")
        for a, t, y, f in sorted(otros_tuyos, key=lambda x: (x[2] or "9999", x[0].lower()))[:40]:
            out.append(f"  {a} — {t}" + (f" ({y})" if y else ""))
        if len(otros_tuyos) > 40:
            out.append(f"  … y {len(otros_tuyos) - 40} más")
    if wd.get("discos"):
        mios = {(mix_norm(a), mix_norm(t, True)) for a, t, *_ in mine + otros_tuyos}
        mis_art = {mix_norm(a) for a, *_ in mine + otros_tuyos}
        if db:
            arts = {mix_norm(r[0]) for r in db.execute("select name from artists")}
        else:
            arts = set()
        resto = [d for d in wd["discos"] if (mix_norm(d["artist"]), mix_norm(d["title"], True)) not in mios]
        conocidos = [d for d in resto if mix_norm(d["artist"]) in arts | mis_art and d["artist"].lower() != "various"]
        nuevos = [d for d in resto if mix_norm(d["artist"]) not in arts | mis_art and d["artist"].lower() != "various"]
        if conocidos:
            out.append(f"Más de artistas que tienes, según Discogs ({len(conocidos)}):")
            for d in sorted(conocidos, key=lambda x: (x["year"] or 9999))[:30]:
                out.append(f"  {d['artist']} — {d['title']}" + (f" ({d['year']})" if d["year"] else ""))
        if nuevos:
            cuenta = Counter(d["artist"] for d in nuevos)
            out.append(f"Otros artistas del sello ({len(cuenta)}): " + ", ".join(
                f"{a} ({n})" if n > 1 else a for a, n in cuenta.most_common(40)) + (" …" if len(cuenta) > 40 else ""))
    elif not terminado:
        out.append("(bajando el catálogo del sello de Discogs…)")
    if db:
        db.close()
    if not terminado:
        print(PARCIAL)
    print("\n".join(out))


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        run_worker(int(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "")
    elif len(sys.argv) >= 3 and sys.argv[1] == "--enviar":
        enviar(int(sys.argv[2]))
    elif len(sys.argv) >= 3 and sys.argv[2]:
        main(sys.argv[1], sys.argv[2])
    else:
        sys.exit(1)
