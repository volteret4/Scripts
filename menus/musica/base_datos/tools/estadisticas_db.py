import sqlite3
import pandas as pd
from datetime import datetime
import os
import json

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
        
    Returns:
        str: Reporte generado
    """
    report = []
    report.append("=" * 80)
    report.append(f"REPORTE DE DATOS FALTANTES - GENERADO: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 80)
    
    try:
        import colorama
        from colorama import Fore, Style
        colorama.init()
        has_colorama = True
    except ImportError:
        has_colorama = False
    
    for table, data in stats.items():
        # Ignorar tablas FTS y del sistema
        if (table.endswith('_fts') or table.endswith('_fts_data') or 
            table.endswith('_fts_idx') or table.endswith('_fts_docsize') or 
            table.endswith('_fts_config') or table.startswith('sqlite_')):
            continue
            
        if has_colorama:
            report.append(f"\n\nTABLA: {Fore.CYAN}{table.upper()}{Style.RESET_ALL}")
        else:
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
                bar = generate_progress_bar(percentage, width=20)
                
                if has_colorama:
                    if percentage < 30:
                        color = Fore.RED
                    elif percentage < 70:
                        color = Fore.YELLOW
                    else:
                        color = Fore.GREEN
                    report.append(f"  - {column}: {missing} registros sin datos ({color}{percentage}%{Style.RESET_ALL} completado) {bar}")
                else:
                    report.append(f"  - {column}: {missing} registros sin datos ({percentage}% completado) {bar}")
        
        # Si no hay campos incompletos
        if all(missing == 0 for missing in data["campos_vacios_por_columna"].values()):
            if has_colorama:
                report.append(f"  {Fore.GREEN}¡Todos los campos están completos!{Style.RESET_ALL}")
            else:
                report.append("  ¡Todos los campos están completos!")
        
        # Añadir resumen de completitud
        avg_completeness = sum(data["porcentaje_completitud"].values()) / len(data["porcentaje_completitud"])
        bar = generate_progress_bar(avg_completeness)
        
        if has_colorama:
            report.append(f"\nCompletitud promedio de la tabla: {Fore.CYAN}{round(avg_completeness, 2)}%{Style.RESET_ALL} {bar}")
        else:
            report.append(f"\nCompletitud promedio de la tabla: {round(avg_completeness, 2)}% {bar}")
    
    # Añadir resumen general
    summary_text, _ = generate_summary_report(stats)
    report.append(summary_text)
    
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
        
        cursor.execute("SELECT COUNT(*) FROM songs WHERE artist IS NULL OR artist = ''")
        songs_no_artist = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM songs WHERE album IS NULL OR album = ''")
        songs_no_album = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM songs s LEFT JOIN song_links sl ON s.id = sl.song_id WHERE sl.spotify_url IS NULL OR sl.spotify_url = ''")
        songs_no_spotify = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM songs WHERE album_art_path_denorm IS NULL OR album_art_path_denorm = ''")
        songs_no_artwork = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM songs WHERE has_lyrics = 0")
        songs_no_lyrics = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM songs WHERE mbid IS NULL OR mbid = ''")
        songs_no_mbid = cursor.fetchone()[0]
        
        specific_cases["songs"] = {
            "sin_titulo": songs_no_title,
            "sin_artista": songs_no_artist,
            "sin_album": songs_no_album,
            "sin_enlace_spotify": songs_no_spotify,
            "sin_artwork": songs_no_artwork,
            "sin_letras": songs_no_lyrics,
            "sin_mbid": songs_no_mbid
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
        
        cursor.execute("SELECT COUNT(*) FROM artists WHERE origin IS NULL OR origin = ''")
        artists_no_origin = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM artists WHERE formed_year IS NULL")
        artists_no_formed_year = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM artists WHERE mbid IS NULL OR mbid = ''")
        artists_no_mbid = cursor.fetchone()[0]
        
        specific_cases["artists"] = {
            "sin_biografia": artists_no_bio,
            "sin_contenido_wikipedia": artists_no_wikipedia,
            "sin_enlace_spotify": artists_no_spotify,
            "sin_origen": artists_no_origin,
            "sin_año_formacion": artists_no_formed_year,
            "sin_mbid": artists_no_mbid
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
        
        cursor.execute("SELECT COUNT(*) FROM albums WHERE label IS NULL OR label = ''")
        albums_no_label = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM albums WHERE spotify_url IS NULL OR spotify_url = ''")
        albums_no_spotify = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM albums WHERE mbid IS NULL OR mbid = ''")
        albums_no_mbid = cursor.fetchone()[0]
        
        specific_cases["albums"] = {
            "sin_artwork": albums_no_artwork,
            "sin_año": albums_no_year,
            "sin_género": albums_no_genre,
            "sin_sello": albums_no_label,
            "sin_enlace_spotify": albums_no_spotify,
            "sin_mbid": albums_no_mbid
        }
    except sqlite3.OperationalError:
        specific_cases["albums"] = "Error al analizar tabla"
    
    # Casos específicos para tabla lyrics
    try:
        cursor.execute("SELECT COUNT(*) FROM lyrics WHERE lyrics IS NULL OR lyrics = ''")
        lyrics_empty = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM lyrics WHERE source IS NULL OR source = ''")
        lyrics_no_source = cursor.fetchone()[0]
        
        specific_cases["lyrics"] = {
            "sin_contenido": lyrics_empty,
            "sin_fuente": lyrics_no_source
        }
    except sqlite3.OperationalError:
        specific_cases["lyrics"] = "Error al analizar tabla"
    
    # Casos específicos para tabla genres
    try:
        cursor.execute("SELECT COUNT(*) FROM genres WHERE description IS NULL OR description = ''")
        genres_no_description = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM genres WHERE related_genres IS NULL OR related_genres = ''")
        genres_no_related = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM genres WHERE origin_year IS NULL")
        genres_no_origin_year = cursor.fetchone()[0]
        
        specific_cases["genres"] = {
            "sin_descripcion": genres_no_description,
            "sin_generos_relacionados": genres_no_related,
            "sin_año_origen": genres_no_origin_year
        }
    except sqlite3.OperationalError:
        specific_cases["genres"] = "Error al analizar tabla"
    
    # Casos específicos para tabla song_links
    try:
        cursor.execute("SELECT COUNT(*) FROM song_links WHERE spotify_url IS NULL OR spotify_url = ''")
        song_links_no_spotify = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM song_links WHERE youtube_url IS NULL OR youtube_url = ''")
        song_links_no_youtube = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM song_links WHERE musicbrainz_url IS NULL OR musicbrainz_url = ''")
        song_links_no_musicbrainz = cursor.fetchone()[0]
        
        specific_cases["song_links"] = {
            "sin_enlace_spotify": song_links_no_spotify,
            "sin_enlace_youtube": song_links_no_youtube,
            "sin_enlace_musicbrainz": song_links_no_musicbrainz
        }
    except sqlite3.OperationalError:
        specific_cases["song_links"] = "Error al analizar tabla"
    
    # Analizar tablas de scrobbles y listens
    try:
        cursor.execute("SELECT COUNT(*) FROM scrobbles WHERE song_id IS NULL")
        scrobbles_no_song_id = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM scrobbles WHERE album_id IS NULL")
        scrobbles_no_album_id = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM scrobbles WHERE artist_id IS NULL")
        scrobbles_no_artist_id = cursor.fetchone()[0]
        
        specific_cases["scrobbles"] = {
            "sin_song_id": scrobbles_no_song_id,
            "sin_album_id": scrobbles_no_album_id,
            "sin_artist_id": scrobbles_no_artist_id
        }
    except sqlite3.OperationalError:
        specific_cases["scrobbles"] = "Error al analizar tabla"
    
    try:
        cursor.execute("SELECT COUNT(*) FROM listens WHERE song_id IS NULL")
        listens_no_song_id = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM listens WHERE album_id IS NULL")
        listens_no_album_id = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM listens WHERE artist_id IS NULL")
        listens_no_artist_id = cursor.fetchone()[0]
        
        specific_cases["listens"] = {
            "sin_song_id": listens_no_song_id,
            "sin_album_id": listens_no_album_id,
            "sin_artist_id": listens_no_artist_id
        }
    except sqlite3.OperationalError:
        specific_cases["listens"] = "Error al analizar tabla"
    
    conn.close()
    return specific_cases




def generate_report(stats, output_file=None, show_all=False):
    """
    Genera un reporte de estadísticas en formato legible.
    
    Args:
        stats (dict): Diccionario con estadísticas
        output_file (str, optional): Archivo de salida para el reporte
        show_all (bool): Si es True, muestra todos los campos incluso los completos
        
    Returns:
        str: Reporte generado
    """
    report = []
    report.append("=" * 80)
    report.append(f"REPORTE DE DATOS FALTANTES - GENERADO: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("=" * 80)
    
    try:
        import colorama
        from colorama import Fore, Style
        colorama.init()
        has_colorama = True
    except ImportError:
        has_colorama = False
    
    for table, data in stats.items():
        # Ignorar tablas FTS y del sistema
        if (table.endswith('_fts') or table.endswith('_fts_data') or 
            table.endswith('_fts_idx') or table.endswith('_fts_docsize') or 
            table.endswith('_fts_config') or table.startswith('sqlite_')):
            continue
            
        if has_colorama:
            report.append(f"\n\nTABLA: {Fore.CYAN}{table.upper()}{Style.RESET_ALL}")
        else:
            report.append(f"\n\nTABLA: {table.upper()}")
        report.append("-" * 40)
        report.append(f"Total de registros: {data['total_registros']}")
        
        if data['total_registros'] == 0:
            report.append("No hay registros para analizar en esta tabla.")
            continue
        
        if show_all:
            report.append("\nEstado de todos los campos:")
        else:
            report.append("\nCampos incompletos:")
        
        # Ordenar por cantidad de campos vacíos (descendente)
        sorted_columns = sorted(
            data["campos_vacios_por_columna"].items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for column, missing in sorted_columns:
            # Si show_all es False, solo mostrar campos con datos faltantes
            if missing > 0 or show_all:
                percentage = data["porcentaje_completitud"][column]
                bar = generate_progress_bar(percentage, width=20)
                
                if has_colorama:
                    if percentage < 30:
                        color = Fore.RED
                    elif percentage < 70:
                        color = Fore.YELLOW
                    else:
                        color = Fore.GREEN
                    report.append(f"  - {column}: {missing} registros sin datos ({color}{percentage}%{Style.RESET_ALL} completado) {bar}")
                else:
                    report.append(f"  - {column}: {missing} registros sin datos ({percentage}% completado) {bar}")
        
        # Si no hay campos incompletos
        if all(missing == 0 for missing in data["campos_vacios_por_columna"].values()) and not show_all:
            if has_colorama:
                report.append(f"  {Fore.GREEN}¡Todos los campos están completos!{Style.RESET_ALL}")
            else:
                report.append("  ¡Todos los campos están completos!")
        
        # Añadir resumen de completitud
        avg_completeness = sum(data["porcentaje_completitud"].values()) / len(data["porcentaje_completitud"])
        bar = generate_progress_bar(avg_completeness)
        
        if has_colorama:
            report.append(f"\nCompletitud promedio de la tabla: {Fore.CYAN}{round(avg_completeness, 2)}%{Style.RESET_ALL} {bar}")
        else:
            report.append(f"\nCompletitud promedio de la tabla: {round(avg_completeness, 2)}% {bar}")
    
    # Añadir resumen general
    summary_text, _ = generate_summary_report(stats)
    report.append(summary_text)
    
    report_text = "\n".join(report)
    
    # Guardar en archivo si se especifica
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(f"Reporte guardado en: {output_file}")
    
    return report_text





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
    
    try:
        import colorama
        from colorama import Fore, Style
        colorama.init()
        has_colorama = True
    except ImportError:
        has_colorama = False
    
    for table, cases in specific_cases.items():
        if has_colorama:
            report.append(f"\n\nTABLA: {Fore.CYAN}{table.upper()}{Style.RESET_ALL}")
        else:
            report.append(f"\n\nTABLA: {table.upper()}")
        report.append("-" * 40)
        
        if isinstance(cases, str):
            report.append(cases)
            continue
        
        for case_name, count in cases.items():
            if has_colorama:
                # Color basado en la cantidad (rojo si hay muchos casos)
                if count > 50:
                    color = Fore.RED
                elif count > 10:
                    color = Fore.YELLOW
                else:
                    color = Fore.GREEN
                report.append(f"  - {case_name.replace('_', ' ').title()}: {color}{count}{Style.RESET_ALL} registros")
            else:
                report.append(f"  - {case_name.replace('_', ' ').title()}: {count} registros")
    
    report_text = "\n".join(report)
    
    # Guardar en archivo si se especifica
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_text)
        print(f"Reporte de casos específicos guardado en: {output_file}")
    
    return report_text

def generate_summary_report(stats):
    """
    Genera un resumen general de completitud de todas las tablas analizadas.
    
    Args:
        stats (dict): Diccionario con estadísticas por tabla
    
    Returns:
        tuple: (texto del resumen, datos para gráfico)
    """
    summary_lines = []
    summary_lines.append("\n" + "=" * 80)
    summary_lines.append("RESUMEN GENERAL DE COMPLETITUD DE DATOS")
    summary_lines.append("=" * 80)
    
    # Para almacenar datos de completitud por tabla
    table_completeness = {}
    all_tables_avg = []
    
    for table, data in stats.items():
        # Ignorar tablas FTS y del sistema
        if (table.endswith('_fts') or table.endswith('_fts_data') or 
            table.endswith('_fts_idx') or table.endswith('_fts_docsize') or 
            table.endswith('_fts_config') or table.startswith('sqlite_')):
            continue
            
        if data['total_registros'] == 0:
            table_completeness[table] = 0
            continue
            
        # Calcular promedio de completitud para esta tabla
        avg_completeness = sum(data["porcentaje_completitud"].values()) / len(data["porcentaje_completitud"])
        table_completeness[table] = round(avg_completeness, 2)
        all_tables_avg.append(avg_completeness)
    
    # Ordenar tablas por completitud (ascendente)
    sorted_tables = sorted(table_completeness.items(), key=lambda x: x[1])
    
    # Añadir cada tabla al resumen
    for table, completeness in sorted_tables:
        bar = generate_progress_bar(completeness)
        summary_lines.append(f"{table.ljust(20)}: {completeness:.2f}% {bar}")
    
    # Calcular completitud global
    if all_tables_avg:
        global_avg = sum(all_tables_avg) / len(all_tables_avg)
        bar = generate_progress_bar(global_avg)
        summary_lines.append("\n" + "-" * 40)
        summary_lines.append(f"COMPLETITUD GLOBAL: {global_avg:.2f}% {bar}")
    else:
        summary_lines.append("\nNo hay datos suficientes para calcular completitud global.")
    
    return "\n".join(summary_lines), table_completeness



def generate_progress_bar(percentage, width=30):
    """
    Genera una barra de progreso ASCII basada en un porcentaje.
    
    Args:
        percentage (float): Porcentaje de completitud (0-100)
        width (int): Ancho de la barra en caracteres
        
    Returns:
        str: Barra de progreso ASCII
    """
    try:
        import colorama
        from colorama import Fore, Style
        colorama.init()
        has_colorama = True
    except ImportError:
        has_colorama = False
    
    filled_width = int(width * (percentage / 100))
    empty_width = width - filled_width
    
    if has_colorama:
        # Determinar color basado en el porcentaje
        if percentage < 30:
            color = Fore.RED
        elif percentage < 70:
            color = Fore.YELLOW
        else:
            color = Fore.GREEN
            
        bar = f"{color}[{'=' * filled_width}{' ' * empty_width}]{Style.RESET_ALL}"
    else:
        # Versión sin color
        bar = f"[{'=' * filled_width}{' ' * empty_width}]"
    
    return bar

def main(db_path, output=None, specific=None, progress=False, todo=False):  
    """
    Función principal que ejecuta el análisis completo.
    
    Args:
        db_path (str): Ruta al archivo de la base de datos
        output (str, optional): Archivo de salida para el reporte general
        specific (str, optional): Archivo de salida para el reporte específico
        progress (bool): Si es True, guarda el progreso en un archivo JSON
        todo (bool): Si es True, genera un reporte mostrando todos los campos
    """
    try:
        # Generar reporte general
        stats = get_missing_data_stats(db_path)
        report = generate_report(stats, output)
        if not output:
            print(report)
        
        # Generar reporte de casos específicos
        specific_cases = analyze_specific_cases(db_path)
        specific_report = generate_specific_report(specific_cases, specific)
        if not specific:
            print(specific_report)

        # Guardar el progreso en formato JSON si se especifica
        if progress:
            with open("progress.json", 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=4)
            print("Progreso guardado en: progress.json")
        
        # Generar reporte mostrando todos los campos si se especifica
        if todo:
            todo_report = generate_report(stats, "todo_list.txt", show_all=True)
            print("Reporte completo guardado en: todo_list.txt")

    except Exception as e:
        print(f"Error: {e}")
        
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Analizar datos faltantes en la base de datos musical')
    parser.add_argument('db_path', help='Ruta al archivo de la base de datos SQLite')
    parser.add_argument('--output', '-o', help='Archivo de salida para el reporte general')
    parser.add_argument('--specific', '-s', help='Archivo de salida para el reporte de casos específicos')
    parser.add_argument('--todo', '-t', action='store_true', help='mostrara tambien los datos totales')
    parser.add_argument('--progress', '-p', help='Guardará un archivo json con el progreso de la base de datos')


    args = parser.parse_args()
    main(args.db_path, args.output, args.specific)