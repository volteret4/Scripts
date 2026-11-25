import requests
import argparse
import os
from dotenv import load_dotenv
import urllib.parse
import json
import sys

# same_artist y same_title están junto a main.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from online_info import same_artist, same_title

HEADERS = {'User-Agent': 'vvmm-post-creator/1.0'}

# Imagen que Last.fm devuelve cuando no tiene portada
LASTFM_PLACEHOLDER = '2a96cbd8b46e442fc41c2b86b821562f'

# Cargar variables de entorno
load_dotenv()

LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")  # Solo necesitas una API key personal
DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN")    # Token personal de usuario


def validar_url_imagen(url, fuente=""):
    """Verifica que la URL de imagen sea válida y accesible."""
    try:
        # Para Cover Art Archive, usar GET en lugar de HEAD ya que a veces HEAD falla
        if 'coverartarchive.org' in url:
            response = requests.get(url, timeout=15, stream=True)
            # Leer solo los primeros bytes para verificar
            content = next(response.iter_content(1024), b'')
            if response.status_code == 200 and len(content) > 0:
                content_type = response.headers.get('content-type', '')
                return content_type.startswith('image/') or len(content) > 500  # Si tiene contenido, probablemente es imagen
        else:
            # Para otras fuentes, usar HEAD
            response = requests.head(url, timeout=10, headers=HEADERS)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                return content_type.startswith('image/')
            # Si HEAD falla, intentar GET
            elif response.status_code in [403, 405, 404]:
                response = requests.get(url, timeout=10, stream=True, headers=HEADERS)
                if response.status_code == 200:
                    content_type = response.headers.get('content-type', '')
                    return content_type.startswith('image/')
        return False
    except Exception as e:
        print(f"    Error validando URL: {e}")
        return False


def buscar_portada_musicbrainz(artista, album):
    """Busca la URL de la portada en MusicBrainz (sin token necesario)."""
    try:
        print(f"  → Buscando '{artista} - {album}' en MusicBrainz...")
        
        # Buscar releases
        url = "https://musicbrainz.org/ws/2/release/"
        params = {
            'query': f'artist:"{artista}" AND release:"{album}"',
            'fmt': 'json',
            'limit': 10
        }
        
        headers = {'User-Agent': 'vvmm-post-creator/1.0'}
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if 'releases' in data and data['releases']:
                print(f"  → Encontrados {len(data['releases'])} releases")
                
                # La búsqueda también devuelve títulos parecidos: solo vale el mismo disco
                coinciden = [r for r in data['releases']
                             if same_title(r.get('title', ''), album)
                             and any(same_artist(c.get('name', ''), artista) for c in r.get('artist-credit', []))]

                for i, release in enumerate(coinciden[:5]):  # Solo los primeros 5
                    release_id = release['id']
                    cover_url = f"https://coverartarchive.org/release/{release_id}/front"
                    
                    print(f"  → Probando release {i+1}: {release.get('title', 'Sin título')}")
                    print(f"    URL: {cover_url}")
                    
                    # Para Cover Art Archive, intentar descargar directamente sin validación previa
                    # ya que la validación a veces falla incorrectamente
                    try:
                        test_response = requests.get(cover_url, timeout=10, stream=True)
                        if test_response.status_code == 200:
                            # Leer un poco de contenido para verificar que es una imagen
                            content = next(test_response.iter_content(1024), b'')
                            if len(content) > 500:  # Si tiene contenido suficiente, es probable que sea imagen
                                print(f"    ✓ Imagen válida encontrada")
                                return cover_url
                            else:
                                print(f"    ✗ Contenido insuficiente")
                        else:
                            print(f"    ✗ HTTP {test_response.status_code}")
                    except Exception as e:
                        print(f"    ✗ Error: {e}")
                        continue
                        
        print("  → No se encontró portada válida en MusicBrainz")
        return None
    except Exception as e:
        print(f"  → Error buscando en MusicBrainz: {e}")
        return None


def buscar_portada_discogs(artista, album):
    """Busca la URL de la portada en Discogs (con token personal)."""
    if not DISCOGS_TOKEN:
        print("  → Token de Discogs no configurado")
        return None
        
    try:
        print(f"  → Buscando '{artista} - {album}' en Discogs...")
        
        # API de búsqueda de Discogs
        url = "https://api.discogs.com/database/search"
        headers = {
            'Authorization': f'Discogs token={DISCOGS_TOKEN}',
            'User-Agent': 'PortadaDownloader/1.0'
        }
        
        for tipo in ('master', 'release'):
            params = {
                'artist': artista,
                'release_title': album,
                'type': tipo,
                'per_page': 10
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'results' in data:
                    # Un título puede coincidir con un promo o un single: primero el más extendido
                    resultados = sorted(data['results'], reverse=True,
                                        key=lambda r: (r.get('community') or {}).get('have', 0))
                    for result in resultados:
                        # El título viene como 'Artista - Disco'
                        r_artista, _, r_album = result.get('title', '').partition(' - ')
                        if not (same_artist(r_artista, artista) and same_title(r_album, album)):
                            continue
                        if 'cover_image' in result and result['cover_image'] and 'spacer.gif' not in result['cover_image']:
                            image_url = result['cover_image']
                            print(f"  → Verificando: {image_url}")
                            if validar_url_imagen(image_url, "discogs"):
                                return image_url
                                
        print("  → No se encontró portada válida en Discogs")
        return None
    except Exception as e:
        print(f"  → Error buscando en Discogs: {e}")
        return None


def buscar_portada_lastfm(artista, album):
    """Busca la URL de la portada en Last.fm (con API key personal)."""
    if not LASTFM_API_KEY:
        print("  → API key de Last.fm no configurada")
        return None
        
    try:
        print(f"  → Buscando '{artista} - {album}' en Last.fm...")
        
        url = "http://ws.audioscrobbler.com/2.0/"
        params = {
            'method': 'album.getinfo',
            'api_key': LASTFM_API_KEY,
            'artist': artista,
            'album': album,
            'format': 'json'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if ('album' in data and 'image' in data['album']
                    and same_artist(data['album'].get('artist', ''), artista)
                    and same_title(data['album'].get('name', ''), album)):
                images = data['album']['image']
                # Buscar la imagen de mayor resolución (última en la lista)
                for img in reversed(images):
                    if img.get('#text') and img['#text'].strip() and LASTFM_PLACEHOLDER not in img['#text']:
                        image_url = img['#text']
                        print(f"  → Verificando: {image_url}")
                        if validar_url_imagen(image_url, "lastfm"):
                            return image_url
            elif 'error' in data:
                print(f"  → Error de Last.fm: {data['message']}")
                        
        print("  → No se encontró portada válida en Last.fm")
        return None
    except Exception as e:
        print(f"  → Error buscando en Last.fm: {e}")
        return None


def buscar_portada_itunes(artista, album):
    """Busca la URL de la portada en iTunes (sin token necesario)."""
    try:
        print(f"  → Buscando '{artista} - {album}' en iTunes...")
        
        # API pública de iTunes
        url = "https://itunes.apple.com/search"
        params = {
            'term': f"{artista} {album}",
            'media': 'music',
            'entity': 'album',
            'limit': 25
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'results' in data and data['results']:
                for result in data['results']:
                    # iTunes devuelve lo más popular aunque no se parezca a lo buscado
                    if not (same_artist(result.get('artistName', ''), artista)
                            and same_title(result.get('collectionName', ''), album)):
                        continue
                    if 'artworkUrl100' in result:
                        # Obtener la imagen en alta resolución
                        image_url = result['artworkUrl100'].replace('100x100', '600x600')
                        print(f"  → Verificando: {image_url}")
                        if validar_url_imagen(image_url, "itunes"):
                            return image_url
                            
        print("  → No se encontró portada válida en iTunes")
        return None
    except Exception as e:
        print(f"  → Error buscando en iTunes: {e}")
        return None


def descargar_portada(artista, album, url, ruta_salida):
    """Descarga y guarda la portada en la ruta especificada."""
    try:
        print(f"Descargando desde: {url}")
        
        response = requests.get(url, stream=True, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            # Limpiar nombre de archivo
            nombre_archivo = f"{artista} - {album}".replace(' ', '_')
            nombre_archivo = "".join(c for c in nombre_archivo if c.isalnum() or c in ('_', '-', '.')).rstrip()
            
            # Determinar extensión
            content_type = response.headers.get('content-type', '')
            if 'jpeg' in content_type or 'jpg' in content_type:
                extension = '.jpg'
            elif 'png' in content_type:
                extension = '.png'
            elif 'webp' in content_type:
                extension = '.webp'
            else:
                extension = '.jpg'
            
            # Crear directorio si no existe
            os.makedirs(ruta_salida, exist_ok=True)
            ruta_archivo = os.path.join(ruta_salida, f"{nombre_archivo}{extension}")
            
            with open(ruta_archivo, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)

            print(f"✓ Portada guardada en: {ruta_archivo}")
            return True
        else:
            print(f"✗ Error al descargar: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error descargando: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Descarga la portada de un álbum desde varias fuentes.")
    parser.add_argument("artista", help="Nombre del artista.")
    parser.add_argument("album", help="Nombre del álbum.")
    parser.add_argument("ruta", help="Ruta donde guardar la portada.")
    args = parser.parse_args()

    print(f"Buscando portada para: {args.artista} - {args.album}")
    print(f"Ruta de salida: {args.ruta}")
    print("-" * 50)

    # Fuentes ordenadas por probabilidad de éxito
    fuentes = [
        ('iTunes', buscar_portada_itunes),           # No requiere token
        ('Discogs', buscar_portada_discogs),         # Solo token personal (600 px)
        ('MusicBrainz', buscar_portada_musicbrainz)  # No requiere token
    ]

    # API de pago: la última, y solo si hay clave (300 px)
    if LASTFM_API_KEY:
        fuentes.append(('Last.fm', buscar_portada_lastfm))

    for nombre_fuente, buscar_funcion in fuentes:
        print(f"\n🔍 Buscando en {nombre_fuente}...")
        portada_url = buscar_funcion(args.artista, args.album)
        
        if portada_url:
            print(f"✓ Portada encontrada en {nombre_fuente}")
            if descargar_portada(args.artista, args.album, portada_url, args.ruta):
                print(f"\n🎉 ¡Descarga completada exitosamente!")
                break
        print(f"✗ Sin éxito en {nombre_fuente}")
    else:
        print("\n😞 No se pudo encontrar la portada en ninguna fuente.")


if __name__ == "__main__":
    main()