#!/usr/bin/env python3
"""Carátulas grandes (~1500 px) para la colección de moode.

Adaptación de embeed_cover.py: en vez de incrustar la miniatura de 500 px de
Picard en cada pista, guarda un cover.jpg por carpeta con audio. moode y
Navidrome lo leen y no se reescribe ningún archivo de audio.

Origen de la imagen, por orden:
  1. Cover Art Archive con el MUSICBRAINZ_ALBUMID de las etiquetas (original).
  2. Cover Art Archive del release group (MUSICBRAINZ_RELEASEGROUPID).
  3. iTunes, solo si artista y álbum coinciden (se puede desactivar).

La imagen se reduce a 1500 px de lado mayor y solo sustituye a lo que hay si es
mayor. Si no se encuentra nada mejor, se extrae la incrustada a cover.jpg. Con
la carátula de carpeta comprobada se borra la incrustada de las pistas (para
Mix es al revés: ahí sigue valiendo embeed_cover.py, que incrusta).
El registro permite reanudar.

Uso:
  caratulas_moode.py                       # toda la colección
  caratulas_moode.py --prueba --limite 20  # sin escribir nada
  caratulas_moode.py "/mnt/NFS/moode/moode/S/Sade"
"""
import argparse
import io
import os
import re
import shutil
import sys
import time
import unicodedata

import requests
from mutagen import File
from PIL import Image

RAIZ = "/mnt/NFS/moode/moode"
LADO = 1500          # lado mayor de la imagen guardada
CALIDAD = 90
NOMBRE = "cover.jpg"
AUDIO = (".flac", ".mp3", ".m4a", ".ogg", ".opus", ".wv", ".ape", ".dsf", ".dff", ".aiff", ".wav")
IMAGENES = ("cover", "folder", "front")
OMITIR = {"playlists", "temp"}
DATOS = os.path.expanduser("~/.local/share/caratulas_moode")
REGISTRO = os.path.join(DATOS, "registro.tsv")
COPIAS = os.path.join(DATOS, "anteriores")
UA = {"User-Agent": "caratulas-moode/1.0"}

Image.MAX_IMAGE_PIXELS = 200_000_000
sesion = requests.Session()
sesion.headers.update(UA)
cache = {}


# ---------- lectura de lo que ya hay ----------

def etiquetas(path):
    try:
        a = File(path, easy=True)
    except Exception:
        return {}
    if not a or not a.tags:
        return {}
    g = lambda k: (a.tags.get(k) or [None])[0]
    return {
        "mbid": g("musicbrainz_albumid"),
        "rgid": g("musicbrainz_releasegroupid"),
        "artista": g("albumartist") or g("artist"),
        "album": g("album"),
    }


def incrustada(path):
    """Bytes de la carátula incrustada, o None."""
    try:
        a = File(path)
    except Exception:
        return None
    if a is None:
        return None
    if getattr(a, "pictures", None):                       # FLAC
        return a.pictures[0].data
    t = a.tags
    if t is None:
        return None
    for k in list(t.keys()):
        if k.startswith("APIC"):                           # MP3, DSF
            return t[k].data
    if "covr" in t and t["covr"]:                          # M4A
        return bytes(t["covr"][0])
    return None


def lado_bytes(datos):
    if not datos:
        return 0
    try:
        return max(Image.open(io.BytesIO(datos)).size)
    except Exception:
        return 0


def quita_incrustada(path, compactar):
    """Borra las imágenes incrustadas. True si había alguna."""
    a = File(path)
    if a is None:
        return False
    cambio = False
    if getattr(a, "pictures", None):                       # FLAC
        a.clear_pictures()
        cambio = True
    t = a.tags
    if t is not None:
        claves = [k for k in t.keys() if k.startswith("APIC") or k.lower() in ("covr", "metadata_block_picture", "coverart")
                  or k.lower().startswith("cover art")]
        for k in claves:
            del t[k]
            cambio = True
    if cambio:
        # Sin compactar el hueco queda como relleno: rápido, pero no libera espacio.
        # Compactar reescribe el archivo entero (lento por NFS).
        if compactar:
            try:
                a.save(padding=lambda info: 4096)
            except TypeError:
                a.save()
        else:
            a.save()
    return cambio


def lado_archivo(carpeta):
    """Lado mayor de la mejor imagen cover/folder/front de la carpeta."""
    mejor = 0
    for f in os.listdir(carpeta):
        base, ext = os.path.splitext(f.lower())
        if base in IMAGENES and ext in (".jpg", ".jpeg", ".png"):
            try:
                with Image.open(os.path.join(carpeta, f)) as im:
                    mejor = max(mejor, max(im.size))
            except Exception:
                pass
    return mejor


# ---------- descarga ----------

def get(url, **kw):
    for intento in range(3):
        try:
            r = sesion.get(url, timeout=60, **kw)
            if r.status_code == 503:
                time.sleep(2 + intento * 3)
                continue
            return r
        except requests.RequestException:
            time.sleep(2 + intento * 3)
    return None


def caa(tipo, mbid):
    """Bytes de la portada original en Cover Art Archive."""
    r = get(f"https://coverartarchive.org/{tipo}/{mbid}/")
    if not r or r.status_code != 200:
        return None
    try:
        imgs = r.json().get("images", [])
    except ValueError:
        return None
    front = [i for i in imgs if i.get("front")] or [i for i in imgs if "Front" in (i.get("types") or [])]
    if not front:
        return None
    url = front[0].get("image")
    r = get(url) if url else None
    return r.content if r and r.status_code == 200 else None


def normaliza(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", s)
    s = re.sub(r"\b(the|deluxe|edition|remaster(ed)?|expanded|ep)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def itunes(artista, album):
    if not artista or not album:
        return None
    r = get("https://itunes.apple.com/search",
            params={"term": f"{artista} {album}", "entity": "album", "limit": 10})
    if not r or r.status_code != 200:
        return None
    try:
        res = r.json().get("results", [])
    except ValueError:
        return None
    na, nb = normaliza(artista), normaliza(album)
    for x in res:
        if normaliza(x.get("artistName")) == na and normaliza(x.get("collectionName")) == nb:
            url = (x.get("artworkUrl100") or "").replace("100x100bb", f"{LADO}x{LADO}bb")
            r = get(url) if url else None
            if r and r.status_code == 200:
                return r.content
    return None


def busca(info, usar_itunes):
    clave = info.get("mbid") or f"{info.get('artista')}|{info.get('album')}"
    if clave in cache:
        return cache[clave]
    res = (None, None)
    if info.get("mbid"):
        d = caa("release", info["mbid"])
        if d:
            res = (d, "caa")
    if not res[0] and info.get("rgid"):
        d = caa("release-group", info["rgid"])
        if d:
            res = (d, "caa-grupo")
    if not res[0] and usar_itunes:
        d = itunes(info.get("artista"), info.get("album"))
        if d:
            res = (d, "itunes")
    cache[clave] = res
    return res


def prepara(datos):
    """JPEG con lado mayor <= LADO. Devuelve (bytes, lado)."""
    im = Image.open(io.BytesIO(datos))
    im.load()
    if im.mode not in ("RGB", "L"):
        fondo = Image.new("RGB", im.size, "white")
        fondo.paste(im.convert("RGBA"), mask=im.convert("RGBA").split()[-1])
        im = fondo
    elif im.mode == "L":
        im = im.convert("RGB")
    if max(im.size) > LADO:
        im.thumbnail((LADO, LADO), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=CALIDAD, optimize=True, progressive=True)
    return out.getvalue(), max(im.size)


# ---------- recorrido ----------

def hechas():
    if not os.path.exists(REGISTRO):
        return set()
    with open(REGISTRO, encoding="utf-8") as f:
        return {l.split("\t")[1] for l in f if l.count("\t") >= 2}


PRUEBA = False


def anota(estado, carpeta, detalle=""):
    print(f"{estado:<10} {carpeta}  {detalle}".rstrip(), flush=True)
    if PRUEBA:
        return
    with open(REGISTRO, "a", encoding="utf-8") as f:
        f.write(f"{estado}\t{carpeta}\t{detalle}\n")


def carpetas(objetivos):
    for t in objetivos:
        for raiz, dirs, files in os.walk(t):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in OMITIR)
            audio = sorted(f for f in files if f.lower().endswith(AUDIO))
            if audio:
                yield raiz, audio


def escribe(destino, jpg):
    if os.path.exists(destino):               # guarda la anterior fuera del NFS
        copia = os.path.join(COPIAS, os.path.relpath(os.path.dirname(destino), "/"), NOMBRE)
        os.makedirs(os.path.dirname(copia), exist_ok=True)
        shutil.copy2(destino, copia)
    tmp = destino + ".tmp"
    with open(tmp, "wb") as f:
        f.write(jpg)
    os.replace(tmp, destino)


def procesa(carpeta, audio, args):
    rutas = [os.path.join(carpeta, f) for f in audio]
    en_archivo = lado_archivo(carpeta)
    emb = incrustada(rutas[0])
    en_pista = lado_bytes(emb)
    ya = max(en_archivo, en_pista)

    # 1. ¿Hay algo mejor fuera?
    jpg, lado, origen = None, 0, ""
    if ya < LADO:
        info = {}
        for r in rutas[:3]:                   # la primera pista puede no tener etiquetas
            info = etiquetas(r)
            if info.get("mbid") or info.get("album"):
                break
        datos, origen = busca(info, not args.sin_itunes)
        if datos:
            try:
                jpg, lado = prepara(datos)
            except Exception as e:
                jpg, lado = None, 0
                origen = f"error imagen: {e}"
        if jpg and lado <= ya:
            jpg = None

    # 2. Si no, vale lo que ya hay: archivo de carpeta o la incrustada extraída
    if not jpg and en_pista > en_archivo:
        try:
            jpg, lado = prepara(emb)
            origen = "incrustada"
        except Exception:
            jpg = None

    destino = os.path.join(carpeta, NOMBRE)
    if jpg:
        accion = f"{origen} {ya}->{lado}px"
    elif en_archivo:
        accion = f"carpeta {en_archivo}px"
    else:
        return anota("nada", carpeta, f"sin carátula {origen}".strip())

    if args.prueba:
        return anota("probaria", carpeta, accion + ("" if args.conservar_incrustada or not emb else ", quitar incrustada"))

    if jpg:
        escribe(destino, jpg)
    # Comprobar que la carátula de carpeta se lee antes de tocar las pistas
    if lado_archivo(carpeta) == 0:
        return anota("error", carpeta, "no se pudo verificar la carátula de carpeta")

    quitadas = 0
    if not args.conservar_incrustada:
        for r in rutas:
            try:
                quitadas += quita_incrustada(r, args.compactar)
            except Exception as e:
                anota("error", r, f"quitar incrustada: {e}")
    anota("ok", carpeta, f"{accion}, incrustada quitada de {quitadas}/{len(rutas)}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("objetivos", nargs="*", default=[RAIZ])
    p.add_argument("--prueba", action="store_true", help="no escribe nada")
    p.add_argument("--limite", type=int, default=0, help="procesar como mucho N carpetas")
    p.add_argument("--sin-itunes", action="store_true", help="solo Cover Art Archive")
    p.add_argument("--conservar-incrustada", action="store_true", help="no borrar la carátula de las pistas")
    p.add_argument("--compactar", action="store_true", help="liberar el espacio de la incrustada (reescribe cada archivo)")
    p.add_argument("--repasar", action="store_true", help="ignorar el registro y repasar todo")
    args = p.parse_args()

    global PRUEBA
    PRUEBA = args.prueba
    os.makedirs(DATOS, exist_ok=True)
    saltar = set() if (args.repasar or args.prueba) else hechas()
    n = 0
    for carpeta, audio in carpetas(args.objetivos):
        if carpeta in saltar:
            continue
        try:
            procesa(carpeta, audio, args)
        except Exception as e:
            anota("error", carpeta, str(e))
        n += 1
        if args.limite and n >= args.limite:
            break


if __name__ == "__main__":
    sys.exit(main())
