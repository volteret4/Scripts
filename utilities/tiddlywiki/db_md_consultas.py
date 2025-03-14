#!/usr/bin/env python3
import sqlite3
import argparse
import datetime
import re
import os
from dateutil.relativedelta import relativedelta
from tabulate import tabulate

def parse_date(date_str):
    """
    Convierte una cadena de fecha en un objeto datetime.
    Admite formatos:
    - Fechas ISO (YYYY-MM-DD)
    - Meses (enero 2024, ene 2024)
    - Años (2024)
    - Relativos (hoy, ayer, esta semana, este mes, este año)
    """
    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Fechas relativas
    if date_str.lower() == "hoy":
        return today, today + datetime.timedelta(days=1) - datetime.timedelta(microseconds=1)
    
    if date_str.lower() == "ayer":
        yesterday = today - datetime.timedelta(days=1)
        return yesterday, yesterday + datetime.timedelta(days=1) - datetime.timedelta(microseconds=1)
    
    if date_str.lower() == "esta semana":
        start_of_week = today - datetime.timedelta(days=today.weekday())
        end_of_week = start_of_week + datetime.timedelta(days=7) - datetime.timedelta(microseconds=1)
        return start_of_week, end_of_week
    
    if date_str.lower() == "este mes":
        start_of_month = today.replace(day=1)
        if today.month == 12:
            end_of_month = today.replace(year=today.year + 1, month=1, day=1) - datetime.timedelta(microseconds=1)
        else:
            end_of_month = today.replace(month=today.month + 1, day=1) - datetime.timedelta(microseconds=1)
        return start_of_month, end_of_month
    
    if date_str.lower() == "este año":
        start_of_year = today.replace(month=1, day=1)
        end_of_year = today.replace(year=today.year + 1, month=1, day=1) - datetime.timedelta(microseconds=1)
        return start_of_year, end_of_year
    
    # Intentar formato ISO
    try:
        date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return date, date + datetime.timedelta(days=1) - datetime.timedelta(microseconds=1)
    except ValueError:
        pass
    
    # Intentar año
    if re.match(r'^\d{4}$', date_str):
        year = int(date_str)
        start = datetime.datetime(year, 1, 1)
        end = datetime.datetime(year + 1, 1, 1) - datetime.timedelta(microseconds=1)
        return start, end
    
    # Intentar mes y año
    meses = {
        'enero': 1, 'ene': 1, 'jan': 1, 'january': 1,
        'febrero': 2, 'feb': 2, 'february': 2,
        'marzo': 3, 'mar': 3, 'march': 3,
        'abril': 4, 'abr': 4, 'apr': 4, 'april': 4,
        'mayo': 5, 'may': 5,
        'junio': 6, 'jun': 6, 'june': 6,
        'julio': 7, 'jul': 7, 'july': 7,
        'agosto': 8, 'ago': 8, 'aug': 8, 'august': 8,
        'septiembre': 9, 'sep': 9, 'sept': 9, 'september': 9,
        'octubre': 10, 'oct': 10, 'october': 10,
        'noviembre': 11, 'nov': 11, 'november': 11,
        'diciembre': 12, 'dic': 12, 'dec': 12, 'december': 12
    }
    
    for nombre_mes, num_mes in meses.items():
        # Patrones como "enero 2024" o "ene 2024"
        pattern = f'^{nombre_mes}\s+(\d{{4}})$'
        match = re.match(pattern, date_str.lower())
        if match:
            year = int(match.group(1))
            start = datetime.datetime(year, num_mes, 1)
            if num_mes == 12:
                end = datetime.datetime(year + 1, 1, 1) - datetime.timedelta(microseconds=1)
            else:
                end = datetime.datetime(year, num_mes + 1, 1) - datetime.timedelta(microseconds=1)
            return start, end
    
    raise ValueError(f"Formato de fecha no reconocido: {date_str}")

def search_snippets(db_path, path=None, title=None, tags=None, content=None, source=None, date=None):
    """
    Busca snippets en la base de datos según los criterios especificados.
    Los criterios se combinan con AND lógico.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Construir la consulta SQL base
    query = """
    SELECT DISTINCT s.id, s.filename, s.path, s.content, s.source, s.last_modified
    FROM snippets s
    """
    
    # Condiciones y parámetros
    conditions = []
    params = {}
    
    # Si hay tags, unimos con las tablas necesarias
    if tags:
        query += """
        JOIN snippet_tags st ON s.id = st.snippet_id
        JOIN tags t ON st.tag_id = t.id
        """
        # Convertir la cadena de tags en una lista
        tag_list = [tag.strip() for tag in tags.split(',')]
        # Aquí asumimos que queremos snippets que contengan TODOS los tags especificados
        # Para cada tag, agregamos una condición
        for i, tag in enumerate(tag_list):
            conditions.append(f"EXISTS (SELECT 1 FROM tags t JOIN snippet_tags st ON t.id = st.tag_id WHERE st.snippet_id = s.id AND t.name = :tag{i})")
            params[f"tag{i}"] = tag
    
    # Agregar otras condiciones
    if path:
        conditions.append("s.path LIKE :path")
        params["path"] = f"%{path}%"
    
    if title:  # En realidad busca en filename ya que no hay campo título
        conditions.append("s.filename LIKE :title")
        params["title"] = f"%{title}%"
    
    if content:
        conditions.append("s.content LIKE :content")
        params["content"] = f"%{content}%"
    
    if source:
        conditions.append("s.source LIKE :source")
        params["source"] = f"%{source}%"
    
    if date:
        try:
            date_start, date_end = parse_date(date)
            conditions.append("s.last_modified BETWEEN :date_start AND :date_end")
            params["date_start"] = date_start.strftime("%Y-%m-%d %H:%M:%S")
            params["date_end"] = date_end.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError as e:
            print(f"Error al procesar la fecha: {e}")
            conn.close()
            return []
    
    # Completar la consulta con las condiciones
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    # Ejecutar la consulta
    cursor.execute(query, params)
    results = cursor.fetchall()
    
    # Obtener tags para cada snippet encontrado
    for i, row in enumerate(results):
        cursor.execute("""
            SELECT t.name 
            FROM tags t 
            JOIN snippet_tags st ON t.id = st.tag_id 
            WHERE st.snippet_id = ?
        """, (row['id'],))
        tags = [tag[0] for tag in cursor.fetchall()]
        results[i] = dict(row)
        results[i]['tags'] = ', '.join(tags)
    
    conn.close()
    return results

def display_results(results, format='table'):
    """
    Muestra los resultados en el formato especificado.
    Formatos soportados: table, json
    """
    if not results:
        print("No se encontraron resultados.")
        return
    
    if format.lower() == 'json':
        import json
        print(json.dumps(results, indent=2, default=str))
    else:  # table es el formato por defecto
        # Preparar datos para tabulate
        headers = ["ID", "Nombre", "Ruta", "Fuente", "Última Modificación", "Tags"]
        table_data = []
        
        for r in results:
            # Truncar el contenido para la tabla
            table_data.append([
                r['id'],
                r['filename'],
                r['path'],
                r['source'],
                r['last_modified'],
                r['tags']
            ])
        
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        print(f"\nTotal de resultados: {len(results)}")

def main():
    parser = argparse.ArgumentParser(description='Buscar snippets en la base de datos.')
    parser.add_argument('--db', required=True, help='Ruta al archivo de la base de datos SQLite')
    parser.add_argument('--path', help='Filtrar por ruta')
    parser.add_argument('--title', help='Filtrar por título del archivo')
    parser.add_argument('--tags', help='Filtrar por tags (separados por comas)')
    parser.add_argument('--content', help='Filtrar por contenido')
    parser.add_argument('--source', help='Filtrar por fuente')
    parser.add_argument('--date', help='Filtrar por fecha (formatos: YYYY-MM-DD, mes YYYY, YYYY, hoy, esta semana, etc.)')
    parser.add_argument('--format', choices=['table', 'json'], default='table', help='Formato de salida (por defecto: table)')
    
    args = parser.parse_args()
    
    # Verificar que el archivo de base de datos existe
    if not os.path.isfile(args.db):
        print(f"Error: El archivo de base de datos {args.db} no existe.")
        return
    
    # Realizar la búsqueda
    results = search_snippets(
        args.db,
        path=args.path,
        title=args.title,
        tags=args.tags,
        content=args.content,
        source=args.source,
        date=args.date
    )
    
    # Mostrar resultados
    display_results(results, args.format)

if __name__ == "__main__":
    main()