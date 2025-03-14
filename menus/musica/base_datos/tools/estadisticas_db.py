import sqlite3
import pandas as pd
from datetime import datetime
import os

def get_missing_data_stats(db_path):
    """
    Genera estadísticas de datos faltantes en cada tabla de la base de datos.
    
    Args:
        db_path (str): Ruta al archivo de la base de datos SQLite
    
    Returns:
        dict: Diccionario con estadísticas por tabla
    """
    # Verificar si el archivo existe
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"No se encuentra la base de datos en: {db_path}")
    
    # Conectar a la base de datos
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Obtener todas las tablas de la base de datos (excluyendo tablas del sistema y FTS)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts%'")
    tables = [table[0] for table in cursor.fetchall()]
    
    results = {}
    
    # Analizar cada tabla
    for table in tables:
        # Obtener información de columnas
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        
        # Filtrar columnas del sistema
        valid_columns = [col[1] for col in columns if not col[1].startswith('sqlite_')]
        
        table_stats = {
            "total_registros": 0,
            "columnas_analizadas": len(valid_columns),
            "campos_vacios_por_columna": {},
            "porcentaje_completitud": {}
        }
        
        # Contar registros totales
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        total_records = cursor.fetchone()[0]
        table_stats["total_registros"] = total_records
        
        if total_records == 0:
            results[table] = table_stats
            continue
        
        # Analizar campos vacíos por columna
        for column in valid_columns:
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL OR {column} = ''")
            missing_count = cursor.fetchone()[0]
            table_stats["campos_vacios_por_columna"][column] = missing_count
            
            # Calcular porcentaje de completitud
            if total_records > 0:
                completeness = ((total_records - missing_count) / total_records) * 100
                table_stats["porcentaje_completitud"][column] = round(completeness, 2)
            else:
                table_stats["porcentaje_completitud"][column] = 0
        
        results[table] = table_stats
    
    conn.close()
    return results

def generate_report(stats, output_file=None):
    """
    Genera un reporte de estadísticas en formato legible.
    
    Args:
        stats (dict): Diccionario con estadísticas
        output_file (str, optional): Archivo de salida para el reporte
    """
    report = []
    report.append("=" * 80)
    report.append(f"REPORTE DE DATOS FALTANTES - GENERADO: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 80)
    
    for table, data in stats.items():
        report.append(f"\n\nTABLA: {table.upper()}")
        report.append("-" * 40)
        report.append(f"Total de registros: {data['total_registros']}")
        
        if data['total_registros'] == 0:
            report.append("No hay registros para analizar en esta tabla.")
            continue
        
        report.append("\nCampos incompletos:")
        
        # Ordenar por cantidad de campos vacíos (descendente)
        sorted_columns = sorted(
            data["campos_vacios_por_columna"].items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for column, missing in sorted_columns:
            if missing > 0:
                percentage = data["porcentaje_completitud"][column]
                report.append(f"  - {column}: {missing} registros sin datos ({percentage}% completado)")
        
        # Si no hay campos incompletos
        if all(missing == 0 for missing in data["campos_vacios_por_columna"].values()):
            report.append("  ¡Todos los campos están completos!")
        
        # Añadir resumen de completitud
        avg_completeness = sum(data["porcentaje_completitud"].values()) / len(data["porcentaje_completitud"])
        report.append(f"\nCompletitud promedio de la tabla: {round(avg_completeness, 2)}%")
    
    report_text = "\n".join(report)
    
    # Guardar en archivo si se especifica
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(f"Reporte guardado en: {output_file}")
    
    return report_text

def analyze_specific_cases(db_path):
    """
    Analiza casos específicos como canciones sin título, artistas sin biografía, etc.
    
    Args:
        db_path (str): Ruta al archivo de la base de datos SQLite
    
    Returns:
        dict: Diccionario con casos específicos por tabla
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    specific_cases = {}
    
    # Casos específicos para tabla songs
    try:
        cursor.execute("SELECT COUNT(*) FROM songs WHERE title IS NULL OR title = ''")
        songs_no_title = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM songs s LEFT JOIN song_links sl ON s.id = sl.song_id WHERE sl.spotify_url IS NULL OR sl.spotify_url = ''")
        songs_no_spotify = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM songs WHERE album_art_path_denorm IS NULL OR album_art_path_denorm = ''")
        songs_no_artwork = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM songs WHERE has_lyrics = 0")
        songs_no_lyrics = cursor.fetchone()[0]
        
        specific_cases["songs"] = {
            "sin_titulo": songs_no_title,
            "sin_enlace_spotify": songs_no_spotify,
            "sin_artwork": songs_no_artwork,
            "sin_letras": songs_no_lyrics
        }
    except sqlite3.OperationalError:
        specific_cases["songs"] = "Error al analizar tabla"
    
    # Casos específicos para tabla artists
    try:
        cursor.execute("SELECT COUNT(*) FROM artists WHERE bio IS NULL OR bio = ''")
        artists_no_bio = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM artists WHERE wikipedia_content IS NULL OR wikipedia_content = ''")
        artists_no_wikipedia = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM artists WHERE spotify_url IS NULL OR spotify_url = ''")
        artists_no_spotify = cursor.fetchone()[0]
        
        specific_cases["artists"] = {
            "sin_biografia": artists_no_bio,
            "sin_contenido_wikipedia": artists_no_wikipedia,
            "sin_enlace_spotify": artists_no_spotify
        }
    except sqlite3.OperationalError:
        specific_cases["artists"] = "Error al analizar tabla"
    
    # Casos específicos para tabla albums
    try:
        cursor.execute("SELECT COUNT(*) FROM albums WHERE album_art_path IS NULL OR album_art_path = ''")
        albums_no_artwork = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM albums WHERE year IS NULL OR year = ''")
        albums_no_year = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM albums WHERE genre IS NULL OR genre = ''")
        albums_no_genre = cursor.fetchone()[0]
        
        specific_cases["albums"] = {
            "sin_artwork": albums_no_artwork,
            "sin_año": albums_no_year,
            "sin_género": albums_no_genre
        }
    except sqlite3.OperationalError:
        specific_cases["albums"] = "Error al analizar tabla"
    
    conn.close()
    return specific_cases

def generate_specific_report(specific_cases, output_file=None):
    """
    Genera un reporte de casos específicos en formato legible.
    
    Args:
        specific_cases (dict): Diccionario con casos específicos
        output_file (str, optional): Archivo de salida para el reporte
    """
    report = []
    report.append("=" * 80)
    report.append(f"REPORTE DE CASOS ESPECÍFICOS - GENERADO: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 80)
    
    for table, cases in specific_cases.items():
        report.append(f"\n\nTABLA: {table.upper()}")
        report.append("-" * 40)
        
        if isinstance(cases, str):
            report.append(cases)
            continue
        
        for case_name, count in cases.items():
            report.append(f"  - {case_name.replace('_', ' ').title()}: {count} registros")
    
    report_text = "\n".join(report)
    
    # Guardar en archivo si se especifica
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(f"Reporte de casos específicos guardado en: {output_file}")
    
    return report_text

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Analizar datos faltantes en la base de datos musical')
    parser.add_argument('db_path', help='Ruta al archivo de la base de datos SQLite')
    parser.add_argument('--output', '-o', help='Archivo de salida para el reporte general')
    parser.add_argument('--specific', '-s', help='Archivo de salida para el reporte de casos específicos')
    
    args = parser.parse_args()
    
    try:
        # Generar reporte general
        stats = get_missing_data_stats(args.db_path)
        report = generate_report(stats, args.output)
        if not args.output:
            print(report)
        
        # Generar reporte de casos específicos
        specific_cases = analyze_specific_cases(args.db_path)
        specific_report = generate_specific_report(specific_cases, args.specific)
        if not args.specific:
            print(specific_report)
    
    except Exception as e:
        print(f"Error: {e}")