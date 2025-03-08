
#!/usr/bin/env python
#
# Script Name: optimiza_db_lastpass.py
# Description: Optimiza la base de datos, crea 
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Dependencies:  - python3, sqlite3
#
# CONSEJOS DE USO:
# - Para búsquedas de texto rápidas, usa las tablas virtuales '_fts':
#     SELECT * FROM songs WHERE id IN (SELECT id FROM song_fts WHERE song_fts MATCH 'palabra_clave')

# - Utiliza las vistas 'view_song_details' y 'view_album_stats' para consultas comunes

# - Aprovecha las columnas desnormalizadas para consultas más rápidas:
#     - album_year
#     - artist_origin
#     - album_art_path_denorm
#     - has_lyrics


import sqlite3
import os
import time
import logging
import shutil

class QueryOptimizer:
    def __init__(self, db_path, backup=True):
        self.db_path = db_path
        self.backup = backup
        self.logger = self._setup_logger()
        
    def _setup_logger(self):
        logger = logging.getLogger('QueryOptimizer')
        logger.setLevel(logging.INFO)
        
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
    
    def backup_database(self):
        """Crea una copia de seguridad de la base de datos."""
        if self.backup:
            backup_path = f"{self.db_path}_backup_{int(time.time())}"
            self.logger.info(f"Creando copia de seguridad en: {backup_path}")
            shutil.copy2(self.db_path, backup_path)
            return backup_path
        return None
    
    def optimize_for_reading(self):
        """Aplica optimizaciones específicas para maximizar la velocidad de consulta."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            self.logger.info("Aplicando optimizaciones para velocidad máxima de consulta...")
            
            # Configuraciones de rendimiento orientadas a lectura
            pragmas = [
                "PRAGMA journal_mode = WAL",         # Write-Ahead Logging mejora lecturas concurrentes
                "PRAGMA synchronous = NORMAL",        # Equilibrio entre rendimiento y seguridad
                "PRAGMA cache_size = -32000",         # Usar ~32MB de caché para consultas (valor negativo para KB)
                "PRAGMA temp_store = MEMORY",         # Almacenar tablas temporales en memoria
                "PRAGMA mmap_size = 30000000000",     # Usar memory-mapped I/O para lectura más rápida (30GB máximo)
                "PRAGMA page_size = 32768",           # Páginas más grandes (32KB) mejor para lecturas secuenciales
                "PRAGMA foreign_keys = OFF",          # Deshabilitar verificación de claves foráneas para rendimiento
                "PRAGMA automatic_index = ON"         # Permitir índices automáticos para consultas complejas
            ]
            
            for pragma in pragmas:
                c.execute(pragma)
                
            # Verificar configuraciones aplicadas
            c.execute("PRAGMA journal_mode")
            journal_mode = c.fetchone()[0]
            self.logger.info(f"Modo de journal establecido a: {journal_mode}")
            
            c.execute("PRAGMA page_size")
            page_size = c.fetchone()[0]
            self.logger.info(f"Tamaño de página establecido a: {page_size} bytes")
            
            c.execute("PRAGMA cache_size")
            cache_size = c.fetchone()[0]
            self.logger.info(f"Tamaño de caché establecido a: {cache_size * -1 / 1024} MB")
            
            # Ejecutar ANALYZE para optimizar el planificador de consultas
            c.execute("ANALYZE")
            
            self.logger.info("Optimizaciones de lectura aplicadas correctamente")
        
        except Exception as e:
            self.logger.error(f"Error al optimizar la base de datos: {str(e)}")
        
        finally:
            conn.close()
    
    def create_advanced_indices(self):
        """Crea índices avanzados optimizados para consultas comunes en una biblioteca musical."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            self.logger.info("Creando índices avanzados para consultas...")
            
            # Identificar consultas potencialmente frecuentes y crear índices específicos
            indexes = [
                # Índices básicos
                "CREATE INDEX IF NOT EXISTS idx_songs_title ON songs(title COLLATE NOCASE)",
                "CREATE INDEX IF NOT EXISTS idx_songs_artist ON songs(artist COLLATE NOCASE)",
                "CREATE INDEX IF NOT EXISTS idx_songs_album ON songs(album COLLATE NOCASE)",
                "CREATE INDEX IF NOT EXISTS idx_songs_genre ON songs(genre COLLATE NOCASE)",
                "CREATE INDEX IF NOT EXISTS idx_albums_name ON albums(name COLLATE NOCASE)",
                "CREATE INDEX IF NOT EXISTS idx_artists_name ON artists(name COLLATE NOCASE)",
                
                # Índices para búsquedas parciales (usando LIKE)
                "CREATE INDEX IF NOT EXISTS idx_songs_title_pattern ON songs(title COLLATE NOCASE)",
                "CREATE INDEX IF NOT EXISTS idx_songs_artist_pattern ON songs(artist COLLATE NOCASE)",
                
                # Índices compuestos para búsquedas comunes combinadas
                "CREATE INDEX IF NOT EXISTS idx_songs_artist_album ON songs(artist, album)",
                "CREATE INDEX IF NOT EXISTS idx_songs_album_title ON songs(album, title)",
                "CREATE INDEX IF NOT EXISTS idx_albums_artist_id_year ON albums(artist_id, year)",
                
                # Índices para ordenamiento
                "CREATE INDEX IF NOT EXISTS idx_songs_added_timestamp ON songs(added_timestamp DESC)",
                "CREATE INDEX IF NOT EXISTS idx_songs_duration ON songs(duration)",
                
                # Índices para juntar tablas eficientemente
                "CREATE INDEX IF NOT EXISTS idx_songs_lyrics_id ON songs(lyrics_id)",
                "CREATE INDEX IF NOT EXISTS idx_lyrics_track_id ON lyrics(track_id)",
                "CREATE INDEX IF NOT EXISTS idx_song_links_song_id ON song_links(song_id)",
                "CREATE INDEX IF NOT EXISTS idx_albums_artist_id ON albums(artist_id)",
                
                # Índices para filtros de tiempo/fecha
                "CREATE INDEX IF NOT EXISTS idx_songs_added_year_month ON songs(added_year, added_month)",
                
                # Índices para estadísticas y agregaciones
                "CREATE INDEX IF NOT EXISTS idx_songs_bitrate ON songs(bitrate)",
                "CREATE INDEX IF NOT EXISTS idx_songs_bit_depth ON songs(bit_depth)",
                "CREATE INDEX IF NOT EXISTS idx_songs_sample_rate ON songs(sample_rate)",
                
                # Índices para metadatos de streaming
                "CREATE INDEX IF NOT EXISTS idx_albums_spotify_id ON albums(spotify_id)",
                "CREATE INDEX IF NOT EXISTS idx_song_links_spotify_id ON song_links(spotify_id)"
            ]
            
            # Crear vistas materializadas para consultas frecuentes
            materializations = [
                # Vista para información completa de canciones
                """
                CREATE VIEW IF NOT EXISTS view_song_details AS
                SELECT 
                    s.id, s.title, s.artist, s.album_artist, s.album, s.duration, s.genre, 
                    s.date, s.track_number, s.file_path, s.bitrate, s.bit_depth, s.sample_rate,
                    a.id as album_id, a.year as album_year, a.album_art_path,
                    ar.id as artist_id, ar.bio as artist_bio,
                    l.lyrics,
                    sl.spotify_url, sl.youtube_url
                FROM songs s
                LEFT JOIN albums a ON s.album = a.name
                LEFT JOIN artists ar ON s.artist = ar.name
                LEFT JOIN lyrics l ON s.lyrics_id = l.id
                LEFT JOIN song_links sl ON s.id = sl.song_id
                """,
                
                # Vista para estadísticas de álbumes
                """
                CREATE VIEW IF NOT EXISTS view_album_stats AS
                SELECT 
                    a.id, a.name, a.artist_id, a.year, a.genre,
                    COUNT(s.id) as actual_track_count,
                    a.total_tracks as reported_track_count,
                    SUM(s.duration) as total_duration,
                    AVG(s.bitrate) as avg_bitrate
                FROM albums a
                LEFT JOIN songs s ON s.album = a.name
                GROUP BY a.id
                """
            ]
            
            # Crear los índices
            for index in indexes:
                try:
                    c.execute(index)
                    self.logger.info(f"Índice creado: {index}")
                except sqlite3.Error as e:
                    self.logger.warning(f"No se pudo crear el índice: {str(e)}")
            
            # Crear vistas materializadas
            for view in materializations:
                try:
                    c.execute(view)
                    self.logger.info(f"Vista creada correctamente")
                except sqlite3.Error as e:
                    self.logger.warning(f"No se pudo crear la vista: {str(e)}")
            
            conn.commit()
            self.logger.info("Índices y vistas creados con éxito")
        
        except Exception as e:
            self.logger.error(f"Error al crear índices avanzados: {str(e)}")
        
        finally:
            conn.close()
    
    def add_denormalized_columns(self):
        """
        Añade columnas desnormalizadas para mejorar el rendimiento de consulta.
        La desnormalización es una técnica que sacrifica espacio para mejorar la velocidad de lectura.
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            self.logger.info("Añadiendo columnas desnormalizadas para mejorar rendimiento de consulta...")
            
            # Verificar si las columnas ya existen en la tabla songs
            c.execute("PRAGMA table_info(songs)")
            columns = [info[1] for info in c.fetchall()]
            
            # Columnas a añadir si no existen
            columns_to_add = []
            if "album_year" not in columns:
                columns_to_add.append("album_year TEXT")
            if "artist_origin" not in columns:
                columns_to_add.append("artist_origin TEXT")
            if "album_art_path_denorm" not in columns:
                columns_to_add.append("album_art_path_denorm TEXT")
            if "has_lyrics" not in columns:
                columns_to_add.append("has_lyrics INTEGER DEFAULT 0")
            
            # Añadir columnas a la tabla songs
            if columns_to_add:
                for column_def in columns_to_add:
                    column_name = column_def.split()[0]
                    self.logger.info(f"Añadiendo columna {column_name} a la tabla songs")
                    c.execute(f"ALTER TABLE songs ADD COLUMN {column_def}")
                
                conn.commit()
                self.logger.info("Columnas añadidas correctamente")
            else:
                self.logger.info("Las columnas desnormalizadas ya existen")
            
            # Actualizar valores desnormalizados
            self.logger.info("Actualizando valores desnormalizados...")
            
            # Actualizar album_year desde la tabla albums
            c.execute("""
            UPDATE songs
            SET album_year = (
                SELECT year FROM albums WHERE name = songs.album
            )
            WHERE album_year IS NULL
            """)
            
            # Actualizar artist_origin desde la tabla artists
            c.execute("""
            UPDATE songs
            SET artist_origin = (
                SELECT origin FROM artists WHERE name = songs.artist
            )
            WHERE artist_origin IS NULL
            """)
            
            # Actualizar album_art_path_denorm desde la tabla albums
            c.execute("""
            UPDATE songs
            SET album_art_path_denorm = (
                SELECT album_art_path FROM albums WHERE name = songs.album
            )
            WHERE album_art_path_denorm IS NULL
            """)
            
            # Actualizar has_lyrics basado en lyrics_id
            c.execute("""
            UPDATE songs
            SET has_lyrics = CASE WHEN lyrics_id IS NOT NULL THEN 1 ELSE 0 END
            """)
            
            conn.commit()
            self.logger.info("Valores desnormalizados actualizados correctamente")
            
            # Crear índices para las nuevas columnas
            new_indexes = [
                "CREATE INDEX IF NOT EXISTS idx_songs_album_year ON songs(album_year)",
                "CREATE INDEX IF NOT EXISTS idx_songs_artist_origin ON songs(artist_origin)",
                "CREATE INDEX IF NOT EXISTS idx_songs_has_lyrics ON songs(has_lyrics)"
            ]
            
            for index in new_indexes:
                c.execute(index)
            
            conn.commit()
            self.logger.info("Índices para columnas desnormalizadas creados con éxito")
        
        except Exception as e:
            self.logger.error(f"Error al añadir columnas desnormalizadas: {str(e)}")
        
        finally:
            conn.close()
    
    def create_full_text_search(self):
        """
        Crea índices de búsqueda de texto completo para consultas de búsqueda rápidas.
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        try:
            self.logger.info("Configurando búsqueda de texto completo...")
            
            # Habilitar la extensión FTS5
            c.execute("PRAGMA foreign_keys = OFF")
            
            # Crear tabla virtual para la búsqueda de canciones
            c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS song_fts USING fts5(
                id, title, artist, album, genre, 
                content='songs', content_rowid='id',
                tokenize='unicode61'
            )
            """)
            
            # Llenar la tabla FTS con datos existentes
            c.execute("""
            INSERT INTO song_fts(rowid, title, artist, album, genre)
            SELECT id, title, artist, album, genre FROM songs
            """)
            
            # Crear disparadores para mantener el índice FTS actualizado
            triggers = [
                # Disparador para INSERT
                """
                CREATE TRIGGER IF NOT EXISTS songs_ai AFTER INSERT ON songs BEGIN
                  INSERT INTO song_fts(rowid, title, artist, album, genre)
                  VALUES (new.id, new.title, new.artist, new.album, new.genre);
                END;
                """,
                
                # Disparador para DELETE
                """
                CREATE TRIGGER IF NOT EXISTS songs_ad AFTER DELETE ON songs BEGIN
                  INSERT INTO song_fts(song_fts, rowid, title, artist, album, genre)
                  VALUES ('delete', old.id, old.title, old.artist, old.album, old.genre);
                END;
                """,
                
                # Disparador para UPDATE
                """
                CREATE TRIGGER IF NOT EXISTS songs_au AFTER UPDATE ON songs BEGIN
                  INSERT INTO song_fts(song_fts, rowid, title, artist, album, genre)
                  VALUES ('delete', old.id, old.title, old.artist, old.album, old.genre);
                  INSERT INTO song_fts(rowid, title, artist, album, genre)
                  VALUES (new.id, new.title, new.artist, new.album, new.genre);
                END;
                """
            ]
            
            for trigger in triggers:
                c.execute(trigger)
            
            # También crear FTS para artists
            c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS artist_fts USING fts5(
                id, name, bio, tags,
                content='artists', content_rowid='id',
                tokenize='unicode61'
            )
            """)
            
            c.execute("""
            INSERT INTO artist_fts(rowid, name, bio, tags)
            SELECT id, name, bio, tags FROM artists
            """)
            
            # Y para albums
            c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS album_fts USING fts5(
                id, name, genre,
                content='albums', content_rowid='id',
                tokenize='unicode61'
            )
            """)
            
            c.execute("""
            INSERT INTO album_fts(rowid, name, genre)
            SELECT id, name, genre FROM albums
            """)
            
            conn.commit()
            self.logger.info("Búsqueda de texto completo configurada correctamente")
        
        except Exception as e:
            self.logger.error(f"Error al configurar búsqueda de texto completo: {str(e)}")
        
        finally:
            conn.close()
    
    def run_query_optimization(self):
        """Ejecuta todo el proceso de optimización para consultas."""
        backup_path = self.backup_database()
        
        try:
            self.logger.info("Iniciando proceso de optimización para CONSULTAS...")
            
            # Paso 1: Configuraciones de SQLite para lectura
            self.optimize_for_reading()
            
            # Paso 2: Crear índices avanzados
            self.create_advanced_indices()
            
            # Paso 3: Añadir columnas desnormalizadas
            self.add_denormalized_columns()
            
            # Paso 4: Configurar búsqueda de texto completo
            self.create_full_text_search()
            
            # Compactar y analizar la base de datos
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("VACUUM")
            c.execute("ANALYZE")
            conn.close()
            
            self.logger.info("¡Proceso de optimización para CONSULTAS completado con éxito!")
            self.logger.info("""
            CONSEJOS DE USO:
            - Para búsquedas de texto rápidas, usa las tablas virtuales '_fts': 
              SELECT * FROM songs WHERE id IN (SELECT id FROM song_fts WHERE song_fts MATCH 'palabra_clave')
              
            - Utiliza las vistas 'view_song_details' y 'view_album_stats' para consultas comunes
              
            - Aprovecha las columnas desnormalizadas para consultas más rápidas:
              - album_year
              - artist_origin
              - album_art_path_denorm
              - has_lyrics
            """)
            
            return True
        except Exception as e:
            self.logger.error(f"Error durante la optimización: {str(e)}")
            
            if backup_path:
                self.logger.info(f"Restaurando base de datos desde la copia de seguridad: {backup_path}")
                shutil.copy2(backup_path, self.db_path)
            
            return False


if __name__ == "__main__":
    # Ejemplo de uso
    db_path = input("Ingresa la ruta completa a tu base de datos SQLite: ")
    if os.path.exists(db_path):
        optimizer = QueryOptimizer(db_path)
        optimizer.run_query_optimization()
    else:
        print(f"El archivo {db_path} no existe.")