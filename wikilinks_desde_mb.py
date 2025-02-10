import sqlite3
import musicbrainzngs as mb
import requests
import json
import logging
import sys
from pathlib import Path
import time
from urllib.parse import quote
import webbrowser
import subprocess
import platform
import argparse

class ArtistEnricher:
    def __init__(self, db_path, processed_file="processed_artists.txt", max_links=None):
        self.db_path = db_path
        self.processed_file = Path(processed_file)
        self.max_links = max_links
        self.processed_links = 0
        self.processed_artists = self.load_processed_artists()
        self.total_artists = self.count_total_artists()
        
        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('artist_enrichment.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Configurar MusicBrainz
        mb.set_useragent("MusicLibraryEnricher", "1.0", "your@email.com")


    def count_total_artists(self):
        """Contar el total de artistas y los que faltan por procesar"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Total de artistas
            cursor.execute("SELECT COUNT(*) FROM artists")
            total = cursor.fetchone()[0]
            
            # Artistas con Wikipedia
            cursor.execute("SELECT COUNT(*) FROM artists WHERE wikipedia_url IS NOT NULL AND wikipedia_url != ''")
            with_wiki = cursor.fetchone()[0]
            
            # Artistas por procesar (excluyendo los ya procesados)
            pendientes = cursor.execute("""
                SELECT COUNT(*) FROM artists 
                WHERE id NOT IN (SELECT CAST(value AS INTEGER) FROM json_each(?))
            """, (json.dumps(list(self.processed_artists)),)).fetchone()[0]
            
            print("\nEstadísticas iniciales:")
            print(f"Total de artistas: {total}")
            print(f"Artistas con Wikipedia: {with_wiki}")
            print(f"Artistas procesados anteriormente: {len(self.processed_artists)}")
            print(f"Artistas pendientes por procesar: {pendientes}")
            print("----------------------------------------\n")
            
            return total
    def show_progress(self):
        """Mostrar el progreso actual"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM artists WHERE wikipedia_url IS NOT NULL AND wikipedia_url != ''")
            with_wiki = cursor.fetchone()[0]
            
            pendientes = cursor.execute("""
                SELECT COUNT(*) FROM artists 
                WHERE id NOT IN (SELECT CAST(value AS INTEGER) FROM json_each(?))
            """, (json.dumps(list(self.processed_artists)),)).fetchone()[0]
            
            print("\nProgreso actual:")
            print(f"Artistas con Wikipedia: {with_wiki}/{self.total_artists} ({(with_wiki/self.total_artists)*100:.1f}%)")
            print(f"Enlaces añadidos en esta sesión: {self.processed_links}")
            if self.max_links:
                print(f"Enlaces restantes hasta el límite: {self.max_links - self.processed_links}")
            print(f"Artistas pendientes por procesar: {pendientes}")
            print("----------------------------------------\n")


    def load_processed_artists(self):
        """Cargar la lista de artistas procesados desde el archivo"""
        if not self.processed_file.exists():
            return set()
            
        with open(self.processed_file, 'r', encoding='utf-8') as f:
            return {line.split('|')[0].strip() for line in f if line.strip()}

    def mark_as_processed(self, artist_id, artist_name):
        """Marcar un artista como procesado en el archivo"""
        with open(self.processed_file, 'a', encoding='utf-8') as f:
            f.write(f"{artist_id}|{artist_name}\n")
        self.processed_artists.add(str(artist_id))

    def setup_database(self):
        """Añadir las nuevas columnas necesarias si no existen"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Verificar si las columnas existen
            cursor.execute("PRAGMA table_info(artists)")
            columns = {col[1] for col in cursor.fetchall()}
            
            if 'wikidata_id' not in columns:
                cursor.execute("ALTER TABLE artists ADD COLUMN wikidata_id TEXT")
            if 'wikipedia_url' not in columns:
                cursor.execute("ALTER TABLE artists ADD COLUMN wikipedia_url TEXT")
            if 'wikipedia_lang' not in columns:
                cursor.execute("ALTER TABLE artists ADD COLUMN wikipedia_lang TEXT")

    def open_in_browser(self, url):
        """Abrir la URL en el navegador predeterminado en segundo plano"""
        try:
            if platform.system() == 'Darwin':  # macOS
                subprocess.Popen(['open', url], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
            elif platform.system() == 'Windows':  # Windows
                subprocess.Popen(['start', '', url], 
                               shell=True, 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
            else:  # Linux
                subprocess.Popen(['xdg-open', url], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
        except Exception as e:
            self.logger.error(f"Error abriendo el navegador: {e}")

    def get_wikidata_id(self, mbid):
        """Obtener el ID de Wikidata desde MusicBrainz"""
        try:
            if not mbid:
                return None
                
            result = mb.get_artist_by_id(mbid, includes=['url-rels'])
            
            for relation in result['artist'].get('url-relation-list', []):
                if relation['type'] == 'wikidata':
                    return relation['target'].split('/')[-1]
        except Exception as e:
            self.logger.error(f"Error obteniendo Wikidata ID: {str(e)}")
        return None

    def get_wikipedia_url(self, wikidata_id):
        """Obtener URLs de Wikipedia desde Wikidata"""
        if not wikidata_id:
            return None, None
            
        try:
            url = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={wikidata_id}&format=json&props=sitelinks"
            response = requests.get(url)
            data = response.json()
            
            if 'entities' in data and wikidata_id in data['entities']:
                sitelinks = data['entities'][wikidata_id].get('sitelinks', {})
                
                # Intentar primero español, luego inglés
                if 'eswiki' in sitelinks:
                    return f"https://es.wikipedia.org/wiki/{sitelinks['eswiki']['title']}", 'es'
                elif 'enwiki' in sitelinks:
                    return f"https://en.wikipedia.org/wiki/{sitelinks['enwiki']['title']}", 'en'
                
        except Exception as e:
            self.logger.error(f"Error obteniendo URL de Wikipedia: {str(e)}")
        return None, None

    def search_wikipedia(self, artist_name, lang='es'):
        """Buscar directamente en Wikipedia"""
        try:
            base_url = f"https://{lang}.wikipedia.org/w/api.php"
            params = {
                'action': 'query',
                'list': 'search',
                'srsearch': f"intitle:{artist_name} musician",
                'format': 'json'
            }
            
            response = requests.get(base_url, params=params)
            data = response.json()
            
            if data['query']['search']:
                title = data['query']['search'][0]['title']
                return f"https://{lang}.wikipedia.org/wiki/{quote(title)}", lang
                
            # Si no hay resultados en español, intentar en inglés
            if lang == 'es':
                return self.search_wikipedia(artist_name, 'en')
                
        except Exception as e:
            self.logger.error(f"Error buscando en Wikipedia: {str(e)}")
        return None, None

    def enrich_artists(self):
        """Proceso principal de enriquecimiento"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            while True:
                # Verificar si hemos alcanzado el límite de enlaces
                if self.max_links and self.processed_links >= self.max_links:
                    print(f"\nSe alcanzó el límite de {self.max_links} enlaces procesados.")
                    self.show_progress()
                    break

                # Obtener el siguiente artista no procesado
                cursor.execute("""
                    SELECT id, name, mbid 
                    FROM artists 
                    WHERE id NOT IN (SELECT CAST(value AS INTEGER) FROM json_each(?))
                    ORDER BY id
                """, (json.dumps(list(self.processed_artists)),))
                
                artist = cursor.fetchone()
                if not artist:
                    print("\nNo quedan más artistas por procesar.")
                    self.show_progress()
                    break

                artist_id, name, mbid = artist
                self.logger.info(f"Procesando artista: {name} (ID: {artist_id})")
                
                # Buscar en MusicBrainz/Wikidata primero
                wikidata_id = self.get_wikidata_id(mbid)
                wikipedia_url = None
                lang = None
                
                if wikidata_id:
                    wikipedia_url, lang = self.get_wikipedia_url(wikidata_id)
                
                # Si no se encuentra, buscar directamente en Wikipedia
                if not wikipedia_url:
                    wikipedia_url, lang = self.search_wikipedia(name)
                
                # Mostrar el enlace y abrirlo
                if wikipedia_url:
                    print(f"\nArtista: {name}")
                    print(f"URL encontrada: {wikipedia_url}")
                    
                    # Abrir el enlace en segundo plano
                    self.open_in_browser(wikipedia_url)
                    
                    # Preguntar si guardar el enlace
                    response = input("¿Guardar este enlace? [S/n] / [m]anual: ").strip().lower()
                    
                    if response in ['', 's', 'si', 'yes', 'y']:
                        cursor.execute("""
                            UPDATE artists 
                            SET wikidata_id = ?, wikipedia_url = ?, wikipedia_lang = ?
                            WHERE id = ?
                        """, (wikidata_id, wikipedia_url, lang, artist_id))
                        conn.commit()
                        print(f"Enlace guardado para {name}")
                        self.processed_links += 1
                    elif response == 'm':
                        manual_url = input("Introduce el enlace de Wikipedia: ").strip()
                        
                        if manual_url:
                            if manual_url.startswith('https://'):
                                cursor.execute("""
                                    UPDATE artists 
                                    SET wikipedia_url = ?, wikipedia_lang = 'es'
                                    WHERE id = ?
                                """, (manual_url, artist_id))
                                conn.commit()
                                print(f"Enlace manual guardado para {name}")
                                self.processed_links += 1
                            else:
                                print("Enlace no válido, no se guardó.")
                        else:
                            print("No se ingresó ningún enlace manual.")
                    
                else:
                    print(f"\nArtista: {name}")
                    print("No se encontró enlace. Puedes ingresar uno manualmente.")
                    manual_url = input("Introduce el enlace de Wikipedia (o Enter para saltar): ").strip()
                    
                    if manual_url:
                        if manual_url.startswith('https://'):
                            cursor.execute("""
                                UPDATE artists 
                                SET wikipedia_url = ?, wikipedia_lang = 'es'
                                WHERE id = ?
                            """, (manual_url, artist_id))
                            conn.commit()
                            print(f"Enlace manual guardado para {name}")
                            self.processed_links += 1
                        else:
                            print("Enlace no válido, no se guardó.")
                
                # Marcar como procesado independientemente del resultado
                self.mark_as_processed(artist_id, name)
                
                # Mostrar progreso cada 5 artistas
                if len(self.processed_artists) % 5 == 0:
                    self.show_progress()

def main():
    parser = argparse.ArgumentParser(description='Enriquecer base de datos de artistas con enlaces de Wikipedia')
    parser.add_argument('database', help='Ruta a la base de datos SQLite')
    parser.add_argument('--max-links', type=int, help='Número máximo de enlaces a procesar', default=None)
    parser.add_argument('--processed-file', help='Archivo para guardar artistas procesados', 
                        default='processed_artists.txt')
    
    args = parser.parse_args()
    
    enricher = ArtistEnricher(
        db_path=args.database,
        processed_file=args.processed_file,
        max_links=args.max_links
    )
    
    enricher.enrich_artists()

if __name__ == "__main__":
    main()