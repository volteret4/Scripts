#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import configparser
import argparse
import sys
import os
from pathlib import Path
import json
from datetime import datetime, time

class MusicManager:
    def __init__(self, config_file='config.ini'):
        self.config = configparser.ConfigParser()
        if not os.path.exists(config_file):
            print(f"Error: {config_file} no encontrado")
            sys.exit(1)
            
        self.config.read(config_file)
        self.db_path = self.config.get('database', 'path')
        self.music_root = self.config.get('music', 'root_path')
    
    def get_connection(self):
        """Obtener conexión a la base de datos"""
        return sqlite3.connect(self.db_path)
    
    def show_stats(self):
        """Mostrar estadísticas de la colección"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        print("=== Estadísticas de la Colección Musical ===\n")
        
        # Estadísticas básicas
        cursor.execute("SELECT COUNT(*) FROM artists WHERE origen = 'local'")
        artists_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM albums WHERE origen = 'local'")
        albums_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM songs WHERE origen = 'local'")
        songs_count = cursor.fetchone()[0]
        
        print(f"📁 Artistas locales: {artists_count}")
        print(f"💿 Álbumes locales: {albums_count}")
        print(f"🎵 Canciones locales: {songs_count}")
        print()
        
        # Top artistas por cantidad de álbumes
        cursor.execute("""
            SELECT ar.name, COUNT(al.id) as album_count
            FROM artists ar
            LEFT JOIN albums al ON ar.id = al.artist_id AND al.origen = 'local'
            WHERE ar.origen = 'local'
            GROUP BY ar.id, ar.name
            HAVING album_count > 0
            ORDER BY album_count DESC
            LIMIT 10
        """)
        
        print("🏆 Top 10 artistas por cantidad de álbumes:")
        for i, (artist, count) in enumerate(cursor.fetchall(), 1):
            print(f"  {i:2d}. {artist} - {count} álbumes")
        print()
        
        # Distribución por décadas
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN CAST(year AS INTEGER) >= 2020 THEN '2020s'
                    WHEN CAST(year AS INTEGER) >= 2010 THEN '2010s'
                    WHEN CAST(year AS INTEGER) >= 2000 THEN '2000s'
                    WHEN CAST(year AS INTEGER) >= 1990 THEN '1990s'
                    WHEN CAST(year AS INTEGER) >= 1980 THEN '1980s'
                    WHEN CAST(year AS INTEGER) >= 1970 THEN '1970s'
                    WHEN CAST(year AS INTEGER) >= 1960 THEN '1960s'
                    ELSE 'Otros'
                END as decade,
                COUNT(*) as count
            FROM albums 
            WHERE origen = 'local' AND year IS NOT NULL AND year != ''
            GROUP BY decade
            ORDER BY decade DESC
        """)
        
        print("📅 Distribución por décadas:")
        for decade, count in cursor.fetchall():
            print(f"  {decade}: {count} álbumes")
        
        conn.close()
    
    def search_music(self, query, type='all'):
        """Buscar en la colección"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        print(f"🔍 Buscando '{query}' en {type}...\n")
        
        if type in ['all', 'artists']:
            cursor.execute("""
                SELECT name, origin, formed_year
                FROM artists 
                WHERE name LIKE ? AND origen = 'local'
                ORDER BY name
                LIMIT 20
            """, (f'%{query}%',))
            
            artists = cursor.fetchall()
            if artists:
                print("👨‍🎤 Artistas encontrados:")
                for name, origin, year in artists:
                    year_str = f" ({year})" if year else ""
                    origin_str = f" - {origin}" if origin else ""
                    print(f"  • {name}{year_str}{origin_str}")
                print()
        
        if type in ['all', 'albums']:
            cursor.execute("""
                SELECT al.name, ar.name, al.year
                FROM albums al
                JOIN artists ar ON al.artist_id = ar.id
                WHERE al.name LIKE ? AND al.origen = 'local'
                ORDER BY al.name
                LIMIT 20
            """, (f'%{query}%',))
            
            albums = cursor.fetchall()
            if albums:
                print("💿 Álbumes encontrados:")
                for album, artist, year in albums:
                    year_str = f" ({year})" if year else ""
                    print(f"  • {album} - {artist}{year_str}")
                print()
        
        if type in ['all', 'songs']:
            cursor.execute("""
                SELECT title, artist, album, duration
                FROM songs 
                WHERE title LIKE ? AND origen = 'local'
                ORDER BY title
                LIMIT 20
            """, (f'%{query}%',))
            
            songs = cursor.fetchall()
            if songs:
                print("🎵 Canciones encontradas:")
                for title, artist, album, duration in songs:
                    duration_str = f" [{self.format_duration(duration)}]" if duration else ""
                    print(f"  • {title} - {artist} ({album}){duration_str}")
        
        conn.close()
    
    def format_duration(self, seconds):
        """Formatear duración en segundos a mm:ss"""
        if not seconds:
            return "0:00"
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes}:{seconds:02d}"
    
    def check_database_integrity(self):
        """Verificar integridad de la base de datos"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        print("🔍 Verificando integridad de la base de datos...\n")
        
        issues = []
        
        # Verificar artistas sin álbumes
        cursor.execute("""
            SELECT ar.name
            FROM artists ar
            LEFT JOIN albums al ON ar.id = al.artist_id AND al.origen = 'local'
            WHERE ar.origen = 'local' AND al.id IS NULL
        """)
        artists_without_albums = cursor.fetchall()
        if artists_without_albums:
            issues.append(f"Artistas sin álbumes: {len(artists_without_albums)}")
        
        # Verificar álbumes sin canciones
        cursor.execute("""
            SELECT al.name, ar.name
            FROM albums al
            JOIN artists ar ON al.artist_id = ar.id
            LEFT JOIN songs s ON al.name = s.album AND ar.name = s.artist AND s.origen = 'local'
            WHERE al.origen = 'local' AND s.id IS NULL
        """)
        albums_without_songs = cursor.fetchall()
        if albums_without_songs:
            issues.append(f"Álbumes sin canciones: {len(albums_without_songs)}")
        
        # Verificar canciones huérfanas
        cursor.execute("""
            SELECT COUNT(*)
            FROM songs s
            WHERE s.origen = 'local' 
            AND NOT EXISTS (
                SELECT 1 FROM albums al 
                JOIN artists ar ON al.artist_id = ar.id
                WHERE al.name = s.album AND ar.name = s.artist AND al.origen = 'local'
            )
        """)
        orphan_songs = cursor.fetchone()[0]
        if orphan_songs > 0:
            issues.append(f"Canciones sin álbum correspondiente: {orphan_songs}")
        
        # Verificar archivos faltantes
        cursor.execute("SELECT file_path FROM songs WHERE origen = 'local'")
        missing_files = 0
        for (file_path,) in cursor.fetchall():
            if file_path and not os.path.exists(file_path):
                missing_files += 1
        
        if missing_files > 0:
            issues.append(f"Archivos de música faltantes: {missing_files}")
        
        if issues:
            print("❌ Problemas encontrados:")
            for issue in issues:
                print(f"  • {issue}")
        else:
            print("✅ Base de datos íntegra, no se encontraron problemas")
        
        print()
        conn.close()
    
    def export_catalog(self, output_file='music_catalog.json'):
        """Exportar catálogo completo a JSON"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        print(f"📤 Exportando catálogo a {output_file}...")
        
        catalog = {
            'export_date': datetime.now().isoformat(),
            'artists': [],
            'stats': {}
        }
        
        # Obtener estadísticas
        cursor.execute("SELECT COUNT(*) FROM artists WHERE origen = 'local'")
        catalog['stats']['artists_count'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM albums WHERE origen = 'local'")
        catalog['stats']['albums_count'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM songs WHERE origen = 'local'")
        catalog['stats']['songs_count'] = cursor.fetchone()[0]
        
        # Obtener artistas con sus álbumes
        cursor.execute("""
            SELECT ar.id, ar.name, ar.origin, ar.formed_year, ar.bio
            FROM artists ar
            WHERE ar.origen = 'local'
            ORDER BY ar.name
        """)
        
        for artist_row in cursor.fetchall():
            artist_id, name, origin, formed_year, bio = artist_row
            
            artist_data = {
                'id': artist_id,
                'name': name,
                'origin': origin,
                'formed_year': formed_year,
                'bio': bio[:200] + '...' if bio and len(bio) > 200 else bio,
                'albums': []
            }
            
            # Obtener álbumes del artista
            cursor.execute("""
                SELECT al.id, al.name, al.year, al.genre, al.total_tracks
                FROM albums al
                WHERE al.artist_id = ? AND al.origen = 'local'
                ORDER BY al.year DESC, al.name
            """, (artist_id,))
            
            for album_row in cursor.fetchall():
                album_id, album_name, year, genre, total_tracks = album_row
                
                album_data = {
                    'id': album_id,
                    'name': album_name,
                    'year': year,
                    'genre': genre,
                    'total_tracks': total_tracks
                }
                
                artist_data['albums'].append(album_data)
            
            catalog['artists'].append(artist_data)
        
        # Guardar archivo
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Catálogo exportado: {len(catalog['artists'])} artistas, {catalog['stats']['albums_count']} álbumes")
        conn.close()
    
    def list_recent_additions(self, days=30):
        """Listar adiciones recientes"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        print(f"📅 Música añadida en los últimos {days} días:\n")
        
        # Álbumes recientes
        cursor.execute("""
            SELECT al.name, ar.name, al.added_timestamp
            FROM albums al
            JOIN artists ar ON al.artist_id = ar.id
            WHERE al.origen = 'local' 
            AND al.added_timestamp >= datetime('now', '-{} days')
            ORDER BY al.added_timestamp DESC
        """.format(days))
        
        recent_albums = cursor.fetchall()
        if recent_albums:
            print("💿 Álbumes recientes:")
            for album, artist, added_date in recent_albums:
                print(f"  • {album} - {artist} ({added_date})")
            print()
        
        # Canciones recientes
        cursor.execute("""
            SELECT title, artist, album, added_timestamp
            FROM songs
            WHERE origen = 'local' 
            AND added_timestamp >= datetime('now', '-{} days')
            ORDER BY added_timestamp DESC
            LIMIT 20
        """.format(days))
        
        recent_songs = cursor.fetchall()
        if recent_songs:
            print("🎵 Canciones recientes:")
            for title, artist, album, added_date in recent_songs:
                print(f"  • {title} - {artist} ({album}) [{added_date}]")
        
        if not recent_albums and not recent_songs:
            print("No se encontraron adiciones recientes.")
        
        conn.close()
    
    def generate_web_report(self, output_file='web_report.html'):
        """Generar reporte HTML para web"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        print(f"📊 Generando reporte web: {output_file}")
        
        # Obtener datos para el reporte
        cursor.execute("""
            SELECT ar.name, COUNT(al.id) as album_count, 
                   COUNT(DISTINCT s.id) as song_count
            FROM artists ar
            LEFT JOIN albums al ON ar.id = al.artist_id AND al.origen = 'local'
            LEFT JOIN songs s ON ar.name = s.artist AND s.origen = 'local'
            WHERE ar.origen = 'local'
            GROUP BY ar.id, ar.name
            HAVING album_count > 0
            ORDER BY album_count DESC, ar.name
        """)
        
        artists_data = cursor.fetchall()
        
        html_content = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Reporte de Colección Musical</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .stats {{ background: #f9f9f9; padding: 20px; margin: 20px 0; }}
    </style>
</head>
<body>
    <h1>Reporte de Colección Musical</h1>
    <p>Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <div class="stats">
        <h2>Estadísticas</h2>
        <p>Total de artistas: {len(artists_data)}</p>
        <p>Total de álbumes: {sum(row[1] for row in artists_data)}</p>
        <p>Total de canciones: {sum(row[2] for row in artists_data)}</p>
    </div>
    
    <h2>Artistas por Álbumes</h2>
    <table>
        <tr>
            <th>Artista</th>
            <th>Álbumes</th>
            <th>Canciones</th>
        </tr>
"""
        
        for artist, albums, songs in artists_data:
            html_content += f"""
        <tr>
            <td>{artist}</td>
            <td>{albums}</td>
            <td>{songs}</td>
        </tr>"""
        
        html_content += """
    </table>
</body>
</html>"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ Reporte generado: {output_file}")
        conn.close()

def main():
    parser = argparse.ArgumentParser(description='Music Manager - Utilidad para gestionar la colección musical')
    parser.add_argument('--config', default='config.ini', help='Archivo de configuración')
    
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponibles')
    
    # Comando stats
    subparsers.add_parser('stats', help='Mostrar estadísticas de la colección')
    
    # Comando search
    search_parser = subparsers.add_parser('search', help='Buscar en la colección')
    search_parser.add_argument('query', help='Término de búsqueda')
    search_parser.add_argument('--type', choices=['all', 'artists', 'albums', 'songs'], 
                              default='all', help='Tipo de búsqueda')
    
    # Comando check
    subparsers.add_parser('check', help='Verificar integridad de la base de datos')
    
    # Comando export
    export_parser = subparsers.add_parser('export', help='Exportar catálogo a JSON')
    export_parser.add_argument('--output', default='music_catalog.json', help='Archivo de salida')
    
    # Comando recent
    recent_parser = subparsers.add_parser('recent', help='Mostrar adiciones recientes')
    recent_parser.add_argument('--days', type=int, default=30, help='Días hacia atrás')
    
    # Comando report
    report_parser = subparsers.add_parser('report', help='Generar reporte HTML')
    report_parser.add_argument('--output', default='web_report.html', help='Archivo de salida')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        manager = MusicManager(args.config)
        
        if args.command == 'stats':
            manager.show_stats()
        elif args.command == 'search':
            manager.search_music(args.query, args.type)
        elif args.command == 'check':
            manager.check_database_integrity()
        elif args.command == 'export':
            manager.export_catalog(args.output)
        elif args.command == 'recent':
            manager.list_recent_additions(args.days)
        elif args.command == 'report':
            manager.generate_web_report(args.output)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()