
import wikipediaapi
import sys

def create_wiki_instance():
    """Crea y retorna una instancia de Wikipedia con un User-Agent válido"""
    return wikipediaapi.Wikipedia(
        language='en',
        extract_format=wikipediaapi.ExtractFormat.WIKI,
        user_agent="MyWikipediaBot/1.0 (contact: myemail@example.com)"
    )

def search_wikipedia(wiki_wiki, title):
    """Busca una página de Wikipedia y retorna el objeto página si existe"""
    try:
        page = wiki_wiki.page(title)
        return page if page.exists() else None
    except Exception as e:
        print(f"Error al buscar '{title}': {e}")
        return None

def try_album_variants(wiki_wiki, artist, album):
    """Intenta diferentes variantes del título del álbum"""
    variants = [
        f"{album} (album)",
        f"{album} ({artist} album)",
        f"{artist} - {album}",
        f"{album} album",
        album
    ]

    for variant in variants:
        page = search_wikipedia(wiki_wiki, variant)
        if page and is_album_page(page, artist, album):
            return page

    disambig_page = search_wikipedia(wiki_wiki, album)
    if disambig_page:
        if 'may refer to' in disambig_page.text.lower() or 'disambiguation' in disambig_page.text.lower():
            for link in disambig_page.links.values():
                if is_album_page(link, artist, album):
                    return link

    return None

def is_album_page(page, artist, album):
    """Verifica si la página es realmente sobre el álbum correcto"""
    if not page:
        return False
    
    text_lower = page.text.lower()
    artist_lower = artist.lower()
    album_lower = album.lower()

    album_indicators = ['album', 'studio album', 'record', 'release', 'track list', 'songs']
    is_album = any(indicator in text_lower for indicator in album_indicators)
    has_artist = artist_lower in text_lower

    first_section = text_lower[:500]
    likely_album_page = (
        'album' in first_section 
        and artist_lower in first_section
        and album_lower in first_section
    )

    return is_album and has_artist and likely_album_page

def search_artist(wiki_wiki, artist):
    """Busca la página del artista y maneja posibles variantes"""
    variants = [
        artist,
        f"{artist} (band)",
        f"{artist} (musician)",
        f"{artist} (artist)",
        f"{artist} (dj)",
        f"{artist} (producer)",
        f"{artist} (singer)"
    ]

    for variant in variants:
        page = search_wikipedia(wiki_wiki, variant)
        if page and is_artist_page(page):
            return page

    return None

def is_artist_page(page):
    """Verifica si la página es sobre un artista musical"""
    if not page:
        return False
    
    text_lower = page.text.lower()
    music_indicators = ['musician', 'singer', 'band', 'artist', 'album', 'songs', 'music']
    
    return any(indicator in text_lower for indicator in music_indicators)

def main(artist, album):
    wiki_wiki = create_wiki_instance()
    
    # Buscar primero la página del álbum
    album_page = try_album_variants(wiki_wiki, artist, album)
    if album_page:
        print(album_page.fullurl)
        return
    
    # Si no se encuentra el álbum, intentar encontrar al artista
    artist_page = search_artist(wiki_wiki, artist)
    if artist_page:
        print(artist_page.fullurl)
        return
    else:
        # Solo si no se encuentra ni el álbum ni el artista
        print("error")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python script.py 'Nombre del Artista' 'Nombre del Álbum'")
        sys.exit(1)
    
    artist = sys.argv[1]
    album = sys.argv[2]
    main(artist, album)