import sqlite3
import argparse
import json
import os
import webbrowser
import datetime
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
import subprocess

sqlite3.register_adapter(datetime.datetime, lambda dt: dt.isoformat())

def init_database(db_path):
    """Inicializa la base de datos añadiendo las columnas necesarias si no existen"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Comprobamos si las columnas existen en la tabla artists
    cursor.execute("PRAGMA table_info(artists)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    
    if 'wikipedia_url' not in column_names:
        cursor.execute("ALTER TABLE artists ADD COLUMN wikipedia_url TEXT")
        print("Columna 'wikipedia_url' añadida a la tabla 'artists'")
    
    if 'wikipedia_content' not in column_names:
        cursor.execute("ALTER TABLE artists ADD COLUMN wikipedia_content TEXT")
        print("Columna 'wikipedia_content' añadida a la tabla 'artists'")
    
    if 'wikipedia_updated' not in column_names:
        cursor.execute("ALTER TABLE artists ADD COLUMN wikipedia_updated TIMESTAMP")
        print("Columna 'wikipedia_updated' añadida a la tabla 'artists'")
    
    # Comprobamos si las columnas existen en la tabla albums
    cursor.execute("PRAGMA table_info(albums)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    
    if 'wikipedia_url' not in column_names:
        cursor.execute("ALTER TABLE albums ADD COLUMN wikipedia_url TEXT")
        print("Columna 'wikipedia_url' añadida a la tabla 'albums'")
    
    if 'wikipedia_content' not in column_names:
        cursor.execute("ALTER TABLE albums ADD COLUMN wikipedia_content TEXT")
        print("Columna 'wikipedia_content' añadida a la tabla 'albums'")
    
    if 'wikipedia_updated' not in column_names:
        cursor.execute("ALTER TABLE albums ADD COLUMN wikipedia_updated TIMESTAMP")
        print("Columna 'wikipedia_updated' añadida a la tabla 'albums'")
    
    # Actualizamos la base de datos
    conn.commit()
    conn.close()

def load_log_file(log_file):
    """Carga el archivo de registro o crea uno nuevo si no existe"""
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print("Error al cargar el archivo de registro. Creando uno nuevo.")
                return {"last_artist_id": 0, "last_album_id": 0}
    else:
        return {"last_artist_id": 0, "last_album_id": 0}

def save_log_file(log_file, data):
    """Guarda el estado actual en el archivo de registro"""
    with open(log_file, 'w') as f:
        json.dump(data, f)

def get_database_stats(db_path):
    """Obtiene estadísticas sobre enlaces existentes y faltantes"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Artistas
    cursor.execute("SELECT COUNT(*) FROM artists")
    total_artists = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM artists WHERE wikipedia_url IS NOT NULL AND wikipedia_url != ''")
    artists_with_wiki = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM artists WHERE wikipedia_content IS NOT NULL AND wikipedia_content != ''")
    artists_with_content = cursor.fetchone()[0]
    
    # Álbumes
    cursor.execute("SELECT COUNT(*) FROM albums")
    total_albums = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM albums WHERE wikipedia_url IS NOT NULL AND wikipedia_url != ''")
    albums_with_wiki = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM albums WHERE wikipedia_content IS NOT NULL AND wikipedia_content != ''")
    albums_with_content = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "total_artists": total_artists,
        "artists_with_wiki": artists_with_wiki,
        "artists_with_content": artists_with_content,
        "artists_missing_wiki": total_artists - artists_with_wiki,
        "total_albums": total_albums,
        "albums_with_wiki": albums_with_wiki,
        "albums_with_content": albums_with_content,
        "albums_missing_wiki": total_albums - albums_with_wiki
    }

def extract_wikipedia_url_from_musicbrainz(mb_url):
    """Intenta extraer un enlace a Wikipedia desde MusicBrainz"""
    if not mb_url:
        return None
    
    # Obtener el ID de MusicBrainz
    mb_id = mb_url.split('/')[-1]
    
    # Consultar la API de MusicBrainz para obtener relaciones
    try:
        if 'artist' in mb_url:
            endpoint = f"https://musicbrainz.org/ws/2/artist/{mb_id}?inc=url-rels&fmt=json"
        else:
            endpoint = f"https://musicbrainz.org/ws/2/release/{mb_id}?inc=url-rels&fmt=json"
        
        response = requests.get(endpoint, headers={"User-Agent": "MusicLibraryWikipediaUpdater/1.0"})
        
        if response.status_code == 200:
            data = response.json()
            
            # Buscar relación con Wikipedia
            if 'relations' in data:
                for relation in data['relations']:
                    if relation['type'] == 'wikipedia' and 'url' in relation:
                        return relation['url']['resource']
        
        return None
    except Exception as e:
        print(f"Error al consultar MusicBrainz: {e}")
        return None

def search_wikipedia(query):
    """Busca en la API de Wikipedia y devuelve el primer resultado"""
    try:
        encoded_query = quote(query)
        url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={encoded_query}&limit=1&namespace=0&format=json"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if len(data) > 3 and len(data[3]) > 0:
                return data[3][0]  # Primera URL
        
        # Intentar en español si no hay resultados
        url = f"https://es.wikipedia.org/w/api.php?action=opensearch&search={encoded_query}&limit=1&namespace=0&format=json"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            if len(data) > 3 and len(data[3]) > 0:
                return data[3][0]  # Primera URL
        
        return None
    except Exception as e:
        print(f"Error al buscar en Wikipedia: {e}")
        return None

def get_wikipedia_content(url):
    """Obtiene el contenido principal de una página de Wikipedia"""
    if not url:
        return None
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extraer el contenido principal
            main_content = soup.find('div', {'id': 'mw-content-text'})
            
            if main_content:
                # Eliminar elementos no deseados
                for div in main_content.find_all(['div', 'table'], {'class': ['navbox', 'infobox', 'toc', 'metadata', 'tmbox', 'ambox']}):
                    div.decompose()
                
                # Extraer sólo los párrafos principales
                paragraphs = main_content.find_all('p')
                content = '\n\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
                
                return content
            
        return None
    except Exception as e:
        print(f"Error al obtener contenido de Wikipedia: {e}")
        return None

def get_artist_albums(db_path, artist_id):
    """Obtiene los álbumes asociados a un artista"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name, year, label 
        FROM albums 
        WHERE artist_id = ? 
        ORDER BY year
    """, (artist_id,))
    
    albums = cursor.fetchall()
    conn.close()
    
    return albums

def update_artists_wikipedia(db_path, log_file):
    """Actualiza los enlaces y contenido de Wikipedia para artistas"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Cargar el registro
    log_data = load_log_file(log_file)
    last_id = log_data.get("last_artist_id", 0)
    
    # Obtener artistas sin enlaces a Wikipedia
    cursor.execute("""
        SELECT id, name, musicbrainz_url
        FROM artists
        WHERE id > ? AND (wikipedia_url IS NULL OR wikipedia_url = '')
        ORDER BY id
    """, (last_id,))
    
    artists = cursor.fetchall()
    total = len(artists)
    
    if total == 0:
        print("No hay artistas pendientes de actualizar enlaces a Wikipedia.")
        return
    
    print(f"Procesando {total} artistas sin enlaces a Wikipedia...")
    
    for i, (artist_id, artist_name, mb_url) in enumerate(artists):
        print(f"\n[{i+1}/{total}] Procesando artista: {artist_name}")
        
        # Mostrar álbumes del artista
        albums = get_artist_albums(db_path, artist_id)
        if albums:
            print("  Álbumes:")
            for album_name, album_year, album_label in albums:
                label_info = f" - {album_label}" if album_label else ""
                print(f"   - {album_name} ({album_year}){label_info}")
        else:
            print("  No hay álbumes registrados para este artista.")
        
        # Primero intentamos obtener el enlace desde MusicBrainz
        wiki_url = None
        if mb_url:
            print(f"  Buscando enlace en MusicBrainz...")
            wiki_url = extract_wikipedia_url_from_musicbrainz(mb_url)
            
            if wiki_url:
                print(f"  Enlace encontrado en MusicBrainz: {wiki_url}")
        
        # Si no encontramos el enlace en MusicBrainz, buscamos en Wikipedia
        if not wiki_url:
            print(f"  Buscando en Wikipedia...")
            wiki_url = search_wikipedia(artist_name)
            
            if wiki_url:
                print(f"  Enlace encontrado en Wikipedia: {wiki_url}")
            else:
                print("  No se encontró enlace en Wikipedia.")
        
        # Si tenemos una URL, abrimos el navegador y pedimos confirmación
        content = None
        if wiki_url:
            subprocess.Popen(["xdg-open", wiki_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            user_input = input(f"  Confirmar URL para '{artist_name}' [Enter para confirmar '{wiki_url}', URL nueva, o 'n' para dejar vacío]: ")
            
            if user_input.lower() == 'n':
                wiki_url = ""
            elif user_input.strip():
                wiki_url = user_input.strip()
                
            # Si tenemos una URL final, obtenemos el contenido
            if wiki_url:
                print("  Obteniendo contenido de Wikipedia...")
                content = get_wikipedia_content(wiki_url)
                if content:
                    content_preview = content[:100] + "..." if len(content) > 100 else content
                    print(f"  Contenido obtenido: {content_preview}")
                else:
                    print("  No se pudo obtener el contenido.")
        else:
            user_input = input(f"  No se encontró URL para '{artist_name}'. Introduzca URL manualmente o Enter para dejar vacío: ")
            if user_input.strip():
                wiki_url = user_input.strip()
                
                # Si se proporciona una URL manualmente, obtenemos el contenido
                print("  Obteniendo contenido de Wikipedia...")
                content = get_wikipedia_content(wiki_url)
                if content:
                    content_preview = content[:100] + "..." if len(content) > 100 else content
                    print(f"  Contenido obtenido: {content_preview}")
                else:
                    print("  No se pudo obtener el contenido.")
            else:
                wiki_url = ""
        
        # Actualizamos la base de datos con URL y contenido
        now = datetime.datetime.now()
        if wiki_url:
            cursor.execute("""
                UPDATE artists
                SET wikipedia_url = ?, wikipedia_content = ?, wikipedia_updated = ?, links_updated = ?
                WHERE id = ?
            """, (wiki_url, content or "", now, now, artist_id))
        else:
            cursor.execute("""
                UPDATE artists
                SET wikipedia_url = ?, wikipedia_content = ?, wikipedia_updated = ?, links_updated = ?
                WHERE id = ?
            """, ("", "", now, now, artist_id))
        
        conn.commit()
        
        # Actualizamos el archivo de registro
        log_data["last_artist_id"] = artist_id
        save_log_file(log_file, log_data)
        
        # Preguntamos si desea continuar después de cada 10 artistas
        if (i + 1) % 10 == 0 and i < total - 1:
            if input("\n¿Desea continuar con la actualización? [S/n]: ").lower() == 'n':
                break
    
    conn.close()
    print("\nActualización de artistas completada.")

def update_albums_wikipedia(db_path, log_file):
    """Actualiza los enlaces y contenido de Wikipedia para álbumes"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Cargar el registro
    log_data = load_log_file(log_file)
    last_id = log_data.get("last_album_id", 0)
    
    # Obtener álbumes sin enlaces a Wikipedia
    cursor.execute("""
        SELECT albums.id, albums.name, artists.name, albums.musicbrainz_url, albums.label, albums.year
        FROM albums
        JOIN artists ON albums.artist_id = artists.id
        WHERE albums.id > ? AND (albums.wikipedia_url IS NULL OR albums.wikipedia_url = '')
        ORDER BY albums.id
    """, (last_id,))
    
    albums = cursor.fetchall()
    total = len(albums)
    
    if total == 0:
        print("No hay álbumes pendientes de actualizar enlaces a Wikipedia.")
        return
    
    print(f"Procesando {total} álbumes sin enlaces a Wikipedia...")
    
    for i, (album_id, album_name, artist_name, mb_url, album_label, album_year) in enumerate(albums):
        search_query = f"{artist_name} {album_name}"
        label_info = f" - Sello: {album_label}" if album_label else ""
        year_info = f" ({album_year})" if album_year else ""
        
        print(f"\n[{i+1}/{total}] Procesando álbum: {album_name}{year_info} de {artist_name}{label_info}")
        
        # Primero intentamos obtener el enlace desde MusicBrainz
        wiki_url = None
        if mb_url:
            print(f"  Buscando enlace en MusicBrainz...")
            wiki_url = extract_wikipedia_url_from_musicbrainz(mb_url)
            
            if wiki_url:
                print(f"  Enlace encontrado en MusicBrainz: {wiki_url}")
        
        # Si no encontramos el enlace en MusicBrainz, buscamos en Wikipedia
        if not wiki_url:
            print(f"  Buscando en Wikipedia...")
            wiki_url = search_wikipedia(search_query)
            
            if wiki_url:
                print(f"  Enlace encontrado en Wikipedia: {wiki_url}")
            else:
                print("  No se encontró enlace en Wikipedia.")
        
        # Si tenemos una URL, abrimos el navegador y pedimos confirmación
        content = None
        if wiki_url:
            subprocess.Popen(["xdg-open", wiki_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            user_input = input(f"  Confirmar URL para '{album_name}' [Enter para confirmar '{wiki_url}', URL nueva, o 'n' para dejar vacío]: ")
            
            if user_input.lower() == 'n':
                wiki_url = ""
            elif user_input.strip():
                wiki_url = user_input.strip()
                
            # Si tenemos una URL final, obtenemos el contenido
            if wiki_url:
                print("  Obteniendo contenido de Wikipedia...")
                content = get_wikipedia_content(wiki_url)
                if content:
                    content_preview = content[:100] + "..." if len(content) > 100 else content
                    print(f"  Contenido obtenido: {content_preview}")
                else:
                    print("  No se pudo obtener el contenido.")
        else:
            user_input = input(f"  No se encontró URL para '{album_name}'. Introduzca URL manualmente o Enter para dejar vacío: ")
            if user_input.strip():
                wiki_url = user_input.strip()
                
                # Si se proporciona una URL manualmente, obtenemos el contenido
                print("  Obteniendo contenido de Wikipedia...")
                content = get_wikipedia_content(wiki_url)
                if content:
                    content_preview = content[:100] + "..." if len(content) > 100 else content
                    print(f"  Contenido obtenido: {content_preview}")
                else:
                    print("  No se pudo obtener el contenido.")
            else:
                wiki_url = ""
        
        # Actualizamos la base de datos con URL y contenido
        now = datetime.datetime.now()
        if wiki_url:
            cursor.execute("""
                UPDATE albums
                SET wikipedia_url = ?, wikipedia_content = ?, wikipedia_updated = ?, links_updated = ?
                WHERE id = ?
            """, (wiki_url, content or "", now, now, album_id))
        else:
            cursor.execute("""
                UPDATE albums
                SET wikipedia_url = ?, wikipedia_content = ?, wikipedia_updated = ?, links_updated = ?
                WHERE id = ?
            """, ("", "", now, now, album_id))
        
        conn.commit()
        
        # Actualizamos el archivo de registro
        log_data["last_album_id"] = album_id
        save_log_file(log_file, log_data)
        
        # Preguntamos si desea continuar después de cada 10 álbumes
        if (i + 1) % 10 == 0 and i < total - 1:
            if input("\n¿Desea continuar con la actualización? [S/n]: ").lower() == 'n':
                break
    
    conn.close()
    print("\nActualización de álbumes completada.")

def update_content_only(db_path, entity_type):
    """Actualiza solo el contenido para entidades que ya tienen URL de Wikipedia pero no contenido"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    if entity_type == 'artists':
        # Obtener artistas con URL pero sin contenido
        cursor.execute("""
            SELECT id, name, wikipedia_url
            FROM artists
            WHERE wikipedia_url IS NOT NULL AND wikipedia_url != '' 
            AND (wikipedia_content IS NULL OR wikipedia_content = '')
            ORDER BY id
        """)
        
        entities = cursor.fetchall()
        table_name = 'artists'
        
        # Para cada artista, conseguimos también sus álbumes
        entities_with_info = []
        for entity_id, entity_name, wiki_url in entities:
            albums = get_artist_albums(db_path, entity_id)
            entities_with_info.append((entity_id, entity_name, wiki_url, albums))
        
    else:  # albums
        cursor.execute("""
            SELECT albums.id, albums.name, albums.wikipedia_url, albums.label, albums.year, artists.name
            FROM albums
            JOIN artists ON albums.artist_id = artists.id
            WHERE albums.wikipedia_url IS NOT NULL AND albums.wikipedia_url != '' 
            AND (albums.wikipedia_content IS NULL OR albums.wikipedia_content = '')
            ORDER BY albums.id
        """)
        
        entities_with_info = cursor.fetchall()
        table_name = 'albums'
    
    total = len(entities_with_info)
    
    if total == 0:
        print(f"No hay {entity_type} con URL pero sin contenido.")
        return
    
    print(f"Procesando {total} {entity_type} para obtener contenido de Wikipedia...")
    
    if entity_type == 'artists':
        for i, (entity_id, entity_name, wiki_url, albums) in enumerate(entities_with_info):
            print(f"\n[{i+1}/{total}] Obteniendo contenido para: {entity_name}")
            print(f"  URL: {wiki_url}")
            
            # Mostrar álbumes del artista
            if albums:
                print("  Álbumes:")
                for album_name, album_year, album_label in albums:
                    label_info = f" - {album_label}" if album_label else ""
                    print(f"   - {album_name} ({album_year}){label_info}")
            else:
                print("  No hay álbumes registrados para este artista.")
            
            # Obtener contenido
            print("  Obteniendo contenido...")
            content = get_wikipedia_content(wiki_url)
            
            if content:
                content_preview = content[:100] + "..." if len(content) > 100 else content
                print(f"  Contenido obtenido: {content_preview}")
                
                # Actualizar la base de datos
                now = datetime.datetime.now()
                cursor.execute(f"""
                    UPDATE {table_name}
                    SET wikipedia_content = ?, wikipedia_updated = ?
                    WHERE id = ?
                """, (content, now, entity_id))
                
                conn.commit()
            else:
                print("  No se pudo obtener el contenido.")
    else:  # albums
        for i, (entity_id, entity_name, wiki_url, album_label, album_year, artist_name) in enumerate(entities_with_info):
            label_info = f" - Sello: {album_label}" if album_label else ""
            year_info = f" ({album_year})" if album_year else ""
            
            print(f"\n[{i+1}/{total}] Obteniendo contenido para: {entity_name}{year_info} de {artist_name}{label_info}")
            print(f"  URL: {wiki_url}")
            
            # Obtener contenido
            print("  Obteniendo contenido...")
            content = get_wikipedia_content(wiki_url)
            
            if content:
                content_preview = content[:100] + "..." if len(content) > 100 else content
                print(f"  Contenido obtenido: {content_preview}")
                
                # Actualizar la base de datos
                now = datetime.datetime.now()
                cursor.execute(f"""
                    UPDATE {table_name}
                    SET wikipedia_content = ?, wikipedia_updated = ?
                    WHERE id = ?
                """, (content, now, entity_id))
                
                conn.commit()
            else:
                print("  No se pudo obtener el contenido.")
        
            # Preguntamos si desea continuar después de cada 20 entidades
            if (i + 1) % 20 == 0 and i < total - 1:
                if input("\n¿Desea continuar con la actualización de contenido? [S/n]: ").lower() == 'n':
                    break
    
    conn.close()
    print(f"\nActualización de contenido para {entity_type} completada.")

def main():
    # Configurar argumentos de línea de comandos
    parser = argparse.ArgumentParser(description='Actualizar enlaces y contenido de Wikipedia en la base de datos de música')
    parser.add_argument('log_file', help='Archivo de registro para seguimiento del progreso')
    parser.add_argument('db_path', help='Ruta a la base de datos SQLite')
    parser.add_argument('type', choices=['artists', 'albums', 'artists_content', 'albums_content'], 
                        help='Tipo de entidad a actualizar (artists, albums, artists_content, albums_content)')
    
    args = parser.parse_args()
    
    # Inicializar la base de datos
    init_database(args.db_path)
    
    # Mostrar estadísticas iniciales
    stats = get_database_stats(args.db_path)
    print("\n=== Estadísticas de Enlaces y Contenido ===")
    print(f"Artistas: {stats['artists_with_wiki']}/{stats['total_artists']} enlaces ({stats['artists_missing_wiki']} faltan)")
    print(f"Artistas: {stats['artists_with_content']}/{stats['total_artists']} con contenido")
    print(f"Álbumes: {stats['albums_with_wiki']}/{stats['total_albums']} enlaces ({stats['albums_missing_wiki']} faltan)")
    print(f"Álbumes: {stats['albums_with_content']}/{stats['total_albums']} con contenido")
    print("==========================================\n")
    
    # Ejecutar la actualización según el tipo
    if args.type == 'artists':
        update_artists_wikipedia(args.db_path, args.log_file)
    elif args.type == 'albums':
        update_albums_wikipedia(args.db_path, args.log_file)
    elif args.type == 'artists_content':
        update_content_only(args.db_path, 'artists')
    elif args.type == 'albums_content':
        update_content_only(args.db_path, 'albums')
    
    # Mostrar estadísticas finales
    stats = get_database_stats(args.db_path)
    print("\n=== Estadísticas Finales ===")
    print(f"Artistas: {stats['artists_with_wiki']}/{stats['total_artists']} enlaces ({stats['artists_missing_wiki']} faltan)")
    print(f"Artistas: {stats['artists_with_content']}/{stats['total_artists']} con contenido")
    print(f"Álbumes: {stats['albums_with_wiki']}/{stats['total_albums']} enlaces ({stats['albums_missing_wiki']} faltan)")
    print(f"Álbumes: {stats['albums_with_content']}/{stats['total_albums']} con contenido")
    print("============================\n")

if __name__ == "__main__":
    main()