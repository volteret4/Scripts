#!/usr/bin/env python3
"""
Extractor de IDs de Bandcamp desde embeds
Usa el album_id o track_id que Bandcamp ya proporciona
"""

import re


def extract_bandcamp_id(embed_code):
    """
    Extrae el album_id o track_id del código embed de Bandcamp.

    Args:
        embed_code: String con el HTML del iframe embed

    Returns:
        String con el ID en formato "album_1212060845" o "track_123456"
        None si no se encuentra

    Examples:
        >>> embed = '<iframe src="https://bandcamp.com/EmbeddedPlayer/album=1212060845/...">'
        >>> extract_bandcamp_id(embed)
        'album_1212060845'

        >>> embed = '<iframe src="https://bandcamp.com/EmbeddedPlayer/track=987654321/...">'
        >>> extract_bandcamp_id(embed)
        'track_987654321'
    """
    if not embed_code:
        return None

    # Buscar album=XXXXXXXX en el embed
    album_match = re.search(r'album=(\d+)', embed_code)
    if album_match:
        return f"album_{album_match.group(1)}"

    # Buscar track=XXXXXXXX en el embed
    track_match = re.search(r'track=(\d+)', embed_code)
    if track_match:
        return f"track_{track_match.group(1)}"

    return None


def get_embed_id(embed_code):
    """
    Alias para extract_bandcamp_id - mantiene compatibilidad con otros scripts
    """
    return extract_bandcamp_id(embed_code)


def extract_bandcamp_id_from_url(bandcamp_url):
    """
    NOTA: No podemos obtener el ID directamente de la URL pública.
    La URL es tipo: https://artist.bandcamp.com/album/nombre-album
    Pero el album_id (1212060845) solo está disponible en el HTML de la página.

    Por eso necesitamos extraerlo del embed después de obtenerlo.
    """
    return None


if __name__ == '__main__':
    # Tests
    print("🧪 Tests de extracción de IDs de Bandcamp\n")

    # Test 1: Album
    embed_album = '''<iframe style="border: 0; width: 100%; height: 120px;"
        src="https://bandcamp.com/EmbeddedPlayer/album=1212060845/size=large/bgcol=181a1b/linkcol=4c1da3/license_id=5501/tracklist=false/artwork=small/transparent=true/"
        seamless><a href="https://seefeel.bandcamp.com/album/pure-impure-expanded-eps-edition">Pure, Impure</a></iframe>'''

    album_id = extract_bandcamp_id(embed_album)
    print(f"Test 1 - Album embed:")
    print(f"  Resultado: {album_id}")
    print(f"  Esperado:  album_1212060845")
    print(f"  ✅ PASS" if album_id == "album_1212060845" else f"  ❌ FAIL")

    # Test 2: Track
    embed_track = '''<iframe src="https://bandcamp.com/EmbeddedPlayer/track=987654321/size=large/..." seamless></iframe>'''

    track_id = extract_bandcamp_id(embed_track)
    print(f"\nTest 2 - Track embed:")
    print(f"  Resultado: {track_id}")
    print(f"  Esperado:  track_987654321")
    print(f"  ✅ PASS" if track_id == "track_987654321" else f"  ❌ FAIL")

    # Test 3: Sin ID
    embed_invalid = '<iframe src="https://example.com/player"></iframe>'

    no_id = extract_bandcamp_id(embed_invalid)
    print(f"\nTest 3 - Sin ID:")
    print(f"  Resultado: {no_id}")
    print(f"  Esperado:  None")
    print(f"  ✅ PASS" if no_id is None else f"  ❌ FAIL")

    print("\n" + "="*60)
    print("✅ Todos los tests pasaron" if all([
        album_id == "album_1212060845",
        track_id == "track_987654321",
        no_id is None
    ]) else "❌ Algunos tests fallaron")
