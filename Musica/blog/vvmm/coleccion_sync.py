#!/usr/bin/env python3
"""
Sincroniza content/coleccion del blog con la colección de Discogs.

Crea una página con portada e información por cada disco que falte, sin preguntar.
Las páginas existentes no se tocan salvo con --refresh, y nunca se borra nada: las de
discos que ya no están en la colección solo se avisan.

Usa la edición exacta que tienes en Discogs, así que portada y datos son los de tu copia.
No hace commit ni push.

    python coleccion_sync.py [--refresh] [--dest DIRECTORIO] [--limit N]
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

import main as vvmm
import online_info

BLOG_COLLECTION = Path('/mnt/NFS/blogs/vvmm/content/coleccion')
DISCOGS_ID = re.compile(r'discogs\.com/releases?/(\d+)')


def fetch_collection(token: str) -> list:
    me = online_info._discogs_get('/oauth/identity', token)['username']
    items, page = [], 1
    while True:
        data = online_info._discogs_get(f'/users/{me}/collection/folders/0/releases', token,
                                        per_page=100, page=page, sort='added', sort_order='desc')
        items.extend(data['releases'])
        if page >= data['pagination']['pages']:
            return items
        page += 1


def artist_name(artists: list) -> str:
    """'Bebo Valdés & Diego El Cigala', respetando cómo los une Discogs."""
    text = ''
    for i, artist in enumerate(artists):
        text += online_info.clean_name(artist.get('anv') or artist['name'])
        if i < len(artists) - 1:
            join = (artist.get('join') or ',').strip()
            text += ', ' if join == ',' else f' {join} '
    return text


def folder_name(artist: str, album: str) -> str:
    """Mismo formato que las páginas antiguas: Radio-Futura---Veneno-En-La-Piel."""
    def clean(text):
        return re.sub(r'-+', '-', re.sub(r'[^\w]+', '-', text)).strip('-')
    return f'{clean(artist)}---{clean(album)}'


def existing_pages(*roots: Path) -> dict:
    """Páginas ya creadas por id de release de Discogs."""
    pages = {}
    for root in roots:
        for index in root.glob('*/index.md'):
            found = DISCOGS_ID.search(index.read_text(encoding='utf-8', errors='replace'))
            if found:
                pages[found.group(1)] = index.parent.name
    return pages


def lastfm_url(artist: str, album: str, api_key: str) -> str:
    if not api_key:
        return ''
    try:
        response = requests.get(online_info.LASTFM_API, timeout=online_info.TIMEOUT,
                                headers={'User-Agent': online_info.USER_AGENT},
                                params={'method': 'album.getinfo', 'artist': artist, 'album': album,
                                        'api_key': api_key, 'format': 'json'})
        return response.json().get('album', {}).get('url', '') if response.status_code == 200 else ''
    except (requests.RequestException, ValueError):
        return ''


def download_cover(url: str, target: Path, token: str) -> bool:
    if not url or 'spacer.gif' in url:
        return False
    response = requests.get(url, timeout=30, headers={'User-Agent': online_info.USER_AGENT,
                                                      'Authorization': f'Discogs token={token}'})
    if response.status_code != 200 or not response.headers.get('content-type', '').startswith('image/'):
        return False
    target.write_bytes(response.content)
    return True


def write_page(creator, item: dict, folder: Path, token: str, lastfm_key: str) -> bool:
    basic = item['basic_information']
    artist = artist_name(basic['artists'])
    album = basic['title'].strip()
    release = online_info._discogs_get(f"/releases/{basic['id']}", token)
    if not release:
        return False

    creator.current_metadata = {'artist': artist, 'album': album, 'artist_raw': artist, 'album_raw': album}
    creator.database_data, creator.links, creator.online_info = {}, {}, {}
    if creator.check_database_first():
        creator.generate_links_from_database()

    info = online_info._parse_discogs('release', release, token)
    info['discogs_url'] = f"https://www.discogs.com/release/{basic['id']}"
    if not all(t['duration'] for t in info['tracks']):
        by_title = {online_info.normalize(t['title']): t['duration']
                    for t in online_info._lastfm_tracks(artist, album, lastfm_key)}
        for track in info['tracks']:
            track['duration'] = track['duration'] or by_title.get(online_info.normalize(track['title']), '')
    creator.online_info = info

    # Enlace exacto a tu edición, aunque la base de datos tenga otro
    creator.links['link_discogs'] = f"[![discogs](../links/svg/discogs.png (discogs))]({info['discogs_url']})"
    if '(not_in_db)' in creator.links.get('link_lastfm', '(not_in_db)'):
        url = lastfm_url(artist, album, lastfm_key)
        if url:
            creator.links['link_lastfm'] = f'[![lastfm](../links/svg/lastfm.png (lastfm))]({url})'

    folder.mkdir(parents=True, exist_ok=True)
    date = item.get('date_added') or time.strftime('%Y-%m-%dT%H:%M:%S+01:00')
    front = ['---',
             f'title: {json.dumps(f"{artist} - {album}", ensure_ascii=False)}',
             f'date: {date}',
             'image: "image.jpeg"',
             f'artist: {json.dumps(artist, ensure_ascii=False)}',
             f'album: {json.dumps(album, ensure_ascii=False)}',
             'draft: false',
             'tags:',
             ' - coleccion',
             ' - discogs',
             '---',
             '']
    creator.post_file = folder / 'index.md'
    creator.post_file.write_text('\n'.join(front), encoding='utf-8')
    if not creator.add_content_to_post():
        return False
    if not download_cover(basic.get('cover_image', ''), folder / 'image.jpeg', token):
        print(f'  sin portada en Discogs: {artist} - {album}', flush=True)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--refresh', action='store_true', help='rehacer también las páginas existentes')
    parser.add_argument('--dest', type=Path, default=BLOG_COLLECTION, help='directorio de salida')
    parser.add_argument('--limit', type=int, default=0, help='procesar solo N discos (para probar)')
    args = parser.parse_args()

    creator = vvmm.VVMMPostCreator()
    token, lastfm_key = os.getenv('DISCOGS_TOKEN', ''), os.getenv('LASTFM_API_KEY', '')
    collection = fetch_collection(token)
    pages = existing_pages(BLOG_COLLECTION)
    print(f'{len(collection)} discos en Discogs, {len(pages)} páginas en el blog', flush=True)

    used, created, failed = set(pages.values()), 0, []
    for number, item in enumerate(collection[:args.limit or None], 1):
        release_id = str(item['basic_information']['id'])
        if release_id in pages and not args.refresh:
            continue
        name = pages.get(release_id)
        if not name:
            name = folder_name(artist_name(item['basic_information']['artists']), item['basic_information']['title'])
            if name in used:  # dos ediciones del mismo disco
                name = f'{name}-{release_id}'
            used.add(name)
        try:
            ok = write_page(creator, item, args.dest / name, token, lastfm_key)
        except Exception as e:
            print(f'  error en {name}: {type(e).__name__}', flush=True)
            ok = False
        created += bool(ok)
        if not ok:
            failed.append(name)
        print(f'{number}/{len(collection)} {name}: {"ok" if ok else "FALLO"}', flush=True)

    current = {str(i['basic_information']['id']) for i in collection}
    gone = sorted(name for release_id, name in pages.items() if release_id not in current)
    print(f'Creadas o rehechas: {created}. Fallos: {failed or "ninguno"}')
    if gone:
        print(f'En el blog pero ya no en Discogs (no se borran): {gone}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
