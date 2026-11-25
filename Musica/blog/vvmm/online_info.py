#!/usr/bin/env python3
"""
Información de un álbum desde fuentes en línea, para lo que no esté en la base de datos.

Discogs aporta sello, créditos, estudios, notas, valoración, tracklist y vídeos.
MusicBrainz aporta las duraciones que Discogs no tenga, el tracklist si Discogs no conoce el disco
y el enlace a ListenBrainz. Last.fm solo se consulta si hay LASTFM_API_KEY (API de pago) y aún falta algo.

Un resultado solo se acepta si artista y título coinciden: es preferible dejar una sección
vacía a publicar los datos de otro disco.
"""

import json
import logging
import re
import time
import unicodedata
from typing import Dict, List, Optional, Tuple

import requests

DISCOGS_API = 'https://api.discogs.com'
MUSICBRAINZ_API = 'https://musicbrainz.org/ws/2'
LASTFM_API = 'https://ws.audioscrobbler.com/2.0/'
USER_AGENT = 'vvmm-post-creator/1.0'
TIMEOUT = 20

logger = logging.getLogger(__name__)


def normalize(text: str) -> str:
    """Minúsculas, sin acentos ni puntuación: 'Mùm & Co.' -> 'mum and co'."""
    text = unicodedata.normalize('NFKD', text or '').encode('ascii', 'ignore').decode()
    text = text.lower().replace('&', ' and ')
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', text).split())


def _strip_brackets(text: str) -> str:
    return re.sub(r'[(\[{].*?[)\]}]', ' ', text or '')


def same_artist(a: str, b: str) -> bool:
    """Compara artistas ignorando el artículo inicial y el sufijo numérico de Discogs."""
    def key(name):
        name = normalize(re.sub(r'\s*\(\d+\)\s*$', '', (name or '').rstrip('*')))
        return re.sub(r'^the ', '', name)
    return bool(key(a)) and key(a) == key(b)


def same_title(a: str, b: str) -> bool:
    """Compara títulos ignorando lo que va entre paréntesis ('Xs (Deluxe)' == 'Xs')."""
    for x, y in ((a, b), (_strip_brackets(a), _strip_brackets(b))):
        if normalize(x) and normalize(x) == normalize(y):
            return True
    return False


def cover_matches_artist(path: str, artist: str) -> bool:
    """La carátula local de la BD debe estar en una carpeta del artista.

    La BD a veces asocia la carpeta de otro disco con el mismo título
    (Grimes - Visions con la de Norah Jones), así que el nombre del artista,
    o el apellido si es largo, tiene que aparecer en la ruta.
    """
    def key(text):
        # Letras que NFKD no descompone: 'Molvær' -> 'molvaer', 'μ-Ziq' -> 'mu ziq'
        for a, b in (('æ', 'ae'), ('ø', 'oe'), ('ß', 'ss'), ('µ', 'mu'), ('μ', 'mu'), ('’', ''), ("'", '')):
            text = text.replace(a, b).replace(a.upper(), b.upper())
        return normalize(text.replace('_', ' ').replace('.', ''))

    name = key(clean_name(artist))
    if not name or name in ('various artists', 'various', 'va', 'artisti vari', 'varios artistas'):
        return True  # sin letras latinas (平沢進) o recopilatorio: no se puede comprobar
    hay = key(path or '')
    # Carpeta con nombre japonés, que en el NFS queda como '____': tampoco se puede comprobar
    if any(part and not key(part) for part in (path or '').split('/')):
        return True
    if name.replace(' ', '') in hay.replace(' ', ''):
        return True
    # 'Binker Golding and Moses Boyd' está en la carpeta 'Binker and Moses'
    words = set(hay.split())
    return any(w in words for w in name.split() if len(w) >= 3 and w not in _COMMON_WORDS)


_COMMON_WORDS = {'the', 'and', 'los', 'las', 'les', 'der', 'die', 'das', 'band', 'orchestra', 'quartet',
                 'quintet', 'trio', 'ensemble', 'project', 'group', 'sound', 'sounds', 'music',
                 'records', 'disc', 'feat', 'with', 'experience', 'brothers', 'sisters', 'family'}


def strip_disc_marker(album: str) -> str:
    """Quita la indicación de disco de la etiqueta: 'CD 1 - S.T.O.P.' -> 'S.T.O.P.'."""
    marker = r'(?:cd|dis[ck])\s*\d+'
    clean = re.sub(rf'^\s*{marker}\s*[-–:]\s*', '', album or '', flags=re.I)
    clean = re.sub(rf'\s*(?:[-–:]\s*{marker}|[(\[]\s*{marker}\s*[)\]])\s*$', '', clean, flags=re.I)
    return clean.strip() or album


def clean_name(name: str) -> str:
    """Quita el sufijo con el que Discogs distingue homónimos: 'Schnittstelle (2)'."""
    return re.sub(r'\s*\(\d+\)\s*$', '', (name or '').rstrip('*')).strip()


def clean_markup(text: str) -> str:
    """Convierte el marcado de Discogs a texto: [a=Nombre], [l123], [url=x]y[/url]."""
    text = re.sub(r'\[url=[^\]]*\](.*?)\[/url\]', r'\1', text or '', flags=re.S)
    text = re.sub(r'\[[almr]=([^\]]+)\]', r'\1', text)
    return re.sub(r'\[[almr]\d+\]', '', text).strip()


def cell(text) -> str:
    """Texto seguro para una celda de tabla Markdown (una línea, sin barras)."""
    return ' '.join(str(text).split()).replace('|', '\\|')


def duration_text(seconds) -> str:
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return ''
    return f'{seconds // 60}:{seconds % 60:02d}' if seconds > 0 else ''


def _discogs_get(path: str, token: str, **params) -> Optional[dict]:
    headers = {'User-Agent': USER_AGENT}
    if token:
        headers['Authorization'] = f'Discogs token={token}'
    try:
        response = requests.get(DISCOGS_API + path, headers=headers, params=params, timeout=TIMEOUT)
        if response.status_code == 429:  # límite de 60 peticiones por minuto
            time.sleep(60)
            response = requests.get(DISCOGS_API + path, headers=headers, params=params, timeout=TIMEOUT)
        elif response.headers.get('X-Discogs-Ratelimit-Remaining', '9') in ('0', '1', '2'):
            time.sleep(30)
        response.raise_for_status()
        # Las notas de Discogs pueden traer caracteres de control que el modo estricto rechaza
        return json.loads(response.text, strict=False)
    except (requests.RequestException, ValueError) as e:
        logger.warning(f'Discogs {path}: {e}')
        return None


def _matches(data: dict, artist: str, album: str) -> bool:
    return (same_title(data.get('title', ''), album)
            and any(same_artist(a.get('name', ''), artist) for a in data.get('artists', [])))


def parse_discogs_url(url: str) -> Optional[Tuple[str, str]]:
    """Devuelve ('master'|'release', id) de una URL de Discogs; None si es de otra cosa."""
    found = re.search(r'discogs\.com/(?:[a-z]{2}/)?(master|release)s?/(\d+)', url or '')
    return (found.group(1), found.group(2)) if found else None


def _find_discogs(artist: str, album: str, token: str, known_url: str = '') -> Optional[Tuple[str, dict]]:
    """Busca el disco en Discogs y devuelve (tipo, datos) solo si coincide."""
    known = parse_discogs_url(known_url)
    if known:
        data = _discogs_get(f'/{known[0]}s/{known[1]}', token)
        if data and _matches(data, artist, album):
            return known[0], data
        logger.info(f'El enlace {known_url} no corresponde a {artist} - {album}; se busca de nuevo')

    for kind in ('master', 'release'):
        results = _discogs_get('/database/search', token, artist=artist, release_title=album,
                               type=kind, per_page=10) or {}
        # Un título puede coincidir con un promo o un single: primero el disco con más copias
        ranked = sorted(results.get('results', []),
                        key=lambda r: (r.get('community') or {}).get('have', 0), reverse=True)
        for result in ranked[:5]:
            data = _discogs_get(f"/{kind}s/{result['id']}", token)
            if data and _matches(data, artist, album):
                return kind, data
    return None


def _flatten_tracks(tracklist: List[dict]) -> List[dict]:
    """Las pistas agrupadas en un 'index' vienen en sub_tracks; los encabezados se descartan."""
    tracks = []
    for item in tracklist or []:
        if item.get('sub_tracks'):
            tracks.extend(_flatten_tracks(item['sub_tracks']))
        elif item.get('type_', 'track') == 'track' and item.get('title'):
            tracks.append(item)
    return tracks


def _video_for(title: str, videos: List[dict]) -> str:
    """Vídeo cuyo título contiene el de la pista como palabras completas; el más corto gana."""
    wanted = normalize(title)
    if not wanted:
        return ''
    candidates = []
    for video in videos:
        name = normalize(video.get('title', ''))
        if 'full album' not in name and re.search(rf'\b{re.escape(wanted)}\b', name):
            candidates.append((len(name), video.get('uri', '')))
    return min(candidates)[1] if candidates else ''


def _group_credits(extraartists: List[dict]) -> Dict[str, List[str]]:
    credits: Dict[str, List[str]] = {}
    for person in extraartists or []:
        role, name = person.get('role', '').strip(), clean_name(person.get('name', ''))
        if not role or not name:
            continue
        if person.get('tracks'):
            name += f" ({person['tracks']})"
        names = credits.setdefault(role, [])
        if name not in names:
            names.append(name)
    return credits


def _format_text(formats: List[dict]) -> str:
    parts = []
    for fmt in formats or []:
        quantity = f"{fmt['qty']}×" if str(fmt.get('qty', '1')) not in ('', '1') else ''
        details = ', '.join(fmt.get('descriptions') or [])
        parts.append(f"{quantity}{fmt.get('name', '')}" + (f' ({details})' if details else ''))
    return ' + '.join(parts)


def _parse_discogs(kind: str, data: dict, token: str) -> dict:
    master_videos = []
    if kind == 'master':
        master_videos = data.get('videos') or []
        release = _discogs_get(f"/releases/{data['main_release']}", token) if data.get('main_release') else None
    else:
        release = data
    release = release or {}

    url_kind, url_id = ('master', data['id']) if kind == 'master' else ('release', data['id'])
    videos = master_videos + (release.get('videos') or [])
    labels = release.get('labels') or []
    label = ', '.join(dict.fromkeys(clean_name(l.get('name', '')) for l in labels if l.get('name')))
    catno = next((l['catno'] for l in labels if l.get('catno') and l['catno'].lower() != 'none'), '')

    companies: Dict[str, List[str]] = {}
    for company in release.get('companies') or []:
        role, name = company.get('entity_type_name', ''), clean_name(company.get('name', ''))
        if role and name and name not in companies.setdefault(role, []):
            companies[role].append(name)

    tracks = []
    for track in _flatten_tracks(release.get('tracklist') or data.get('tracklist')):
        featuring = [clean_name(p.get('name', '')) for p in track.get('extraartists') or []
                     if 'featuring' in p.get('role', '').lower()]
        tracks.append({
            'position': track.get('position', ''),
            'title': track['title'],
            'featuring': featuring,
            'duration': track.get('duration', ''),
            'youtube_url': _video_for(track['title'], videos),
        })

    rating = (release.get('community') or {}).get('rating') or {}
    return {
        'discogs_url': f'https://www.discogs.com/{url_kind}/{url_id}',
        'year': str(data.get('year') or release.get('year') or '') or '',
        'released': release.get('released', ''),
        'label': label,
        'catno': catno,
        'genres': data.get('genres') or release.get('genres') or [],
        'styles': data.get('styles') or release.get('styles') or [],
        'format': _format_text(release.get('formats')),
        'country': release.get('country', ''),
        'credits': _group_credits(release.get('extraartists')),
        'companies': companies,
        'notes': clean_markup(release.get('notes', '')),
        'rating_average': rating.get('average') or 0,
        'rating_count': rating.get('count') or 0,
        'tracks': tracks,
    }


def _musicbrainz_get(path: str, **params) -> Optional[dict]:
    for attempt in range(3):
        try:
            response = requests.get(MUSICBRAINZ_API + path, timeout=TIMEOUT, headers={'User-Agent': USER_AGENT},
                                    params={**params, 'fmt': 'json'})
            if response.status_code == 503:  # saturado o más de una petición por segundo
                time.sleep(2 * (attempt + 1))
                continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as e:
            logger.warning(f'MusicBrainz {path}: {e}')
            return None
        finally:
            time.sleep(1)
    logger.warning(f'MusicBrainz {path}: no disponible')
    return None


def _find_musicbrainz(artist: str, album: str) -> Optional[dict]:
    """Edición de MusicBrainz que coincide con el disco; mejor si es oficial."""
    def phrase(text):
        return re.sub(r'["\\]', ' ', text)

    found = _musicbrainz_get('/release', limit=25,
                             query=f'artist:"{phrase(artist)}" AND release:"{phrase(album)}"') or {}
    releases = [r for r in found.get('releases', [])
                if same_title(r.get('title', ''), album)
                and (any(same_artist(c.get('name', ''), artist) for c in r.get('artist-credit', []))
                     or same_artist(''.join(c.get('name', '') + c.get('joinphrase', '')
                                            for c in r.get('artist-credit', [])), artist))]
    official = [r for r in releases if r.get('status') == 'Official']
    return next(iter(official or releases), None)


def _musicbrainz_tracks(release_id: str) -> List[dict]:
    data = _musicbrainz_get(f'/release/{release_id}', inc='recordings') or {}
    return [{'title': t.get('title', ''), 'duration': duration_text((t.get('length') or 0) / 1000)}
            for medium in data.get('media', []) for t in medium.get('tracks', []) if t.get('title')]


def _fill_tracks(info: dict, found: List[dict]) -> None:
    """Completa las duraciones que falten, o el tracklist entero si no hay."""
    if not info.get('tracks'):
        info['tracks'] = [{'position': '', 'featuring': [], 'youtube_url': '', **t} for t in found]
        return
    by_title = {normalize(t['title']): t['duration'] for t in found}
    for track in info['tracks']:
        track['duration'] = track['duration'] or by_title.get(normalize(track['title']), '')


def _lacks_tracks(info: dict) -> bool:
    tracks = info.get('tracks', [])
    return not tracks or not all(t['duration'] for t in tracks)


def _lastfm_tracks(artist: str, album: str, api_key: str) -> List[dict]:
    if not api_key:
        return []
    try:
        response = requests.get(LASTFM_API, timeout=TIMEOUT, headers={'User-Agent': USER_AGENT}, params={
            'method': 'album.getinfo', 'artist': artist, 'album': album,
            'api_key': api_key, 'format': 'json',
        })
        if response.status_code != 200:
            logger.info(f'Last.fm no tiene {artist} - {album} (HTTP {response.status_code})')
            return []
        tracks = response.json().get('album', {}).get('tracks', {}).get('track', [])
    except requests.RequestException as e:
        # No se registra el mensaje de la excepción: incluye la URL con la API key
        logger.warning(f'Last.fm: error de conexión ({type(e).__name__})')
        return []
    except (ValueError, AttributeError):
        logger.warning('Last.fm: respuesta no válida')
        return []
    tracks = [tracks] if isinstance(tracks, dict) else tracks
    return [{'title': t.get('name', ''), 'duration': duration_text(t.get('duration'))}
            for t in tracks if t.get('name')]


def fetch_album_info(artist: str, album: str, discogs_token: str = '', lastfm_key: str = '',
                     known_discogs_url: str = '') -> dict:
    """Reúne lo que se pueda saber del disco. Sin resultados devuelve un diccionario vacío."""
    info: dict = {}
    found = _find_discogs(artist, album, discogs_token, known_discogs_url)
    if found:
        info = _parse_discogs(found[0], found[1], discogs_token)
    else:
        logger.info(f'Discogs no tiene {artist} - {album}')

    release = _find_musicbrainz(artist, album)
    if release:
        group = (release.get('release-group') or {}).get('id')
        if group:
            info['listenbrainz_url'] = f'https://listenbrainz.org/album/{group}/'
        if _lacks_tracks(info):
            _fill_tracks(info, _musicbrainz_tracks(release['id']))
    else:
        logger.info(f'MusicBrainz no tiene {artist} - {album}')
    if lastfm_key and _lacks_tracks(info):
        _fill_tracks(info, _lastfm_tracks(artist, album, lastfm_key))

    return info if any(info.values()) else {}


def track_for(info: dict, title: str) -> dict:
    """Pista de la información en línea con ese título, para completar una pista de la BD."""
    return next((t for t in (info or {}).get('tracks', []) if same_title(t['title'], title)), {})
