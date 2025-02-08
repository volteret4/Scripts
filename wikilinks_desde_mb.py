import sqlite3
import musicbrainzngs as mb
import requests
import json
import logging
import sys
from pathlib import Path
import time
from urllib.parse import quote

class ArtistEnricher:
    def __init__(self, db_path, checkpoint_path):
        self.db_path = db_path
        self.checkpoint_path = Path(checkpoint_path)
        
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
        
        # Inicializar la base de datos
        self.setup_database()

        
    def setup_database(self):
        """Añadir las nuevas columnas necesarias si no existen"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Verificar si las columnas existen
            cursor.execute("PRAGMA table_info(artists)")
            columns = {col[1] for col in cursor.fetchall()}
            
                    # Añadir la columna 'mbid' si no existe
            if 'mbid' not in columns:
                cursor.execute("ALTER TABLE artists ADD COLUMN mbid TEXT")
            if 'wikidata_id' not in columns:
                cursor.execute("ALTER TABLE artists ADD COLUMN wikidata_id TEXT")
            if 'wikipedia_url' not in columns:
                cursor.execute("ALTER TABLE artists ADD COLUMN wikipedia_url TEXT")
            if 'wikipedia_lang' not in columns:
                cursor.execute("ALTER TABLE artists ADD COLUMN wikipedia_lang TEXT")

    def load_checkpoint(self):
        """Cargar el último artista procesado"""
        if self.checkpoint_path.exists():
            with open(self.checkpoint_path, 'r') as f:
                return json.load(f)
        return {'last_artist_id': 0}

    def save_checkpoint(self, artist_id):
        """Guardar el progreso actual"""
        checkpoint = {'last_artist_id': artist_id}
        with open(self.checkpoint_path, 'w') as f:
            json.dump(checkpoint, f)

    def get_mbid_from_name(self, artist_name):
        """Buscar MBID por nombre de artista en MusicBrainz"""
        try:
            result = mb.search_artists(artist_name, limit=1)
            if result['artists']:
                return result['artists'][0]['id']
        except Exception as e:
            self.logger.error(f"Error buscando MBID para el artista {artist_name}: {str(e)}")
        return None

    def get_wikidata_id(self, mbid, artist_name=None):
        """Obtener el ID de Wikidata desde MusicBrainz o por nombre si no se proporciona MBID"""
        try:
            # Si no se pasa un MBID, buscar el MBID por nombre
            if not mbid and artist_name:
                mbid = self.get_mbid_from_name(artist_name)
            
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
        checkpoint = self.load_checkpoint()
        last_artist_id = checkpoint['last_artist_id']
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Obtener artistas no procesados
            cursor.execute("""
                SELECT id, name, mbid 
                FROM artists 
                WHERE id > ? 
                AND (wikipedia_url IS NULL OR wikipedia_url = '')
                ORDER BY id
            """, (last_artist_id,))
            
            while True:
                artist = cursor.fetchone()
                if not artist:
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
                
                if wikipedia_url:
                    # Mostrar al usuario y pedir confirmación
                    print(f"\nArtista: {name}")
                    print(f"URL encontrada: {wikipedia_url}")
                    response = input("¿Guardar este enlace? [S/n]: ").strip().lower()
                    
                    if response in ['', 's', 'si', 'yes', 'y']:
                        cursor.execute("""
                            UPDATE artists 
                            SET wikidata_id = ?, wikipedia_url = ?, wikipedia_lang = ?
                            WHERE id = ?
                        """, (wikidata_id, wikipedia_url, lang, artist_id))
                        conn.commit()
                        self.logger.info(f"Guardado enlace para {name}")
                    else:
                        self.logger.info(f"Saltado enlace para {name}")
                
                # Guardar checkpoint
                self.save_checkpoint(artist_id)
                
                # Preguntar si continuar
                if artist_id % 10 == 0:  # Cada 10 artistas
                    response = input("\n¿Continuar con el siguiente grupo? [S/n]: ").strip().lower()
                    if response in ['n', 'no']:
                        self.logger.info("Proceso pausado por el usuario")
                        return

def main():
    if len(sys.argv) < 2:
        print("Uso: python artist_enricher.py <database_path>")
        sys.exit(1)
        
    enricher = ArtistEnricher(
        db_path=sys.argv[1],
        checkpoint_path='artist_enrichment_checkpoint.json'
    )
    
    enricher.enrich_artists()

if __name__ == "__main__":
    main()