#!/usr/bin/env python3
import sqlite3
import os
import sys
import time

def optimize_database(db_path):
    """
    Optimiza la base de datos SQLite para mejorar el rendimiento de búsqueda
    """
    if not os.path.exists(db_path):
        print(f"Error: La base de datos '{db_path}' no existe.")
        return False
    
    try:
        print(f"Iniciando optimización de la base de datos: {db_path}")
        print("=" * 50)
        
        # Conectar a la base de datos
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Obtener información sobre la estructura actual
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tablas encontradas: {[t[0] for t in tables]}")
        
        # Verificar si existe la tabla principal de snippets (asumiendo su nombre)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='snippets';")
        if not cursor.fetchone():
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%snippet%';")
            snippet_table = cursor.fetchone()
            if snippet_table:
                snippet_table = snippet_table[0]
                print(f"Tabla de snippets encontrada: {snippet_table}")
            else:
                print("No se pudo encontrar la tabla de snippets.")
                # Intentar detectar la tabla principal analizando estructura
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND sql LIKE '%content%' AND sql LIKE '%path%';")
                potential_tables = cursor.fetchall()
                if potential_tables:
                    snippet_table = potential_tables[0][0]
                    print(f"Posible tabla de snippets detectada: {snippet_table}")
                else:
                    print("No se pudo identificar la tabla principal. Por favor, especifique el nombre manualmente.")
                    return False
        else:
            snippet_table = 'snippets'
        
        # Verificar estructura de la tabla
        cursor.execute(f"PRAGMA table_info({snippet_table});")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        print(f"Columnas en {snippet_table}: {column_names}")
        
        # Verificar índices existentes
        cursor.execute(f"PRAGMA index_list({snippet_table});")
        existing_indices = cursor.fetchall()
        existing_index_names = [idx[1] for idx in existing_indices]
        print(f"Índices existentes: {existing_index_names}")
        
        # Crear índices optimizados si no existen
        index_definitions = []
        
        # Determinar qué columnas necesitan índices
        needed_indices = []
        
        if 'id' in column_names and f"idx_{snippet_table}_id" not in existing_index_names:
            needed_indices.append((f"idx_{snippet_table}_id", "id"))
        
        if 'filename' in column_names and f"idx_{snippet_table}_filename" not in existing_index_names:
            needed_indices.append((f"idx_{snippet_table}_filename", "filename"))
        
        if 'path' in column_names and f"idx_{snippet_table}_path" not in existing_index_names:
            needed_indices.append((f"idx_{snippet_table}_path", "path"))
        
        if 'content' in column_names and f"idx_{snippet_table}_content" not in existing_index_names:
            needed_indices.append((f"idx_{snippet_table}_content", "content"))
        
        if 'tags' in column_names and f"idx_{snippet_table}_tags" not in existing_index_names:
            needed_indices.append((f"idx_{snippet_table}_tags", "tags"))
        
        # Crear un índice de texto completo (FTS) si no existe
        has_fts = False
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'fts_%';")
        fts_tables = cursor.fetchall()
        if fts_tables:
            print(f"Tablas FTS encontradas: {[t[0] for t in fts_tables]}")
            has_fts = True
        
        # Crear índices necesarios
        for idx_name, column in needed_indices:
            print(f"Creando índice {idx_name} en columna {column}...")
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {snippet_table}({column});")
                print(f"Índice {idx_name} creado correctamente.")
            except sqlite3.OperationalError as e:
                if "too large" in str(e):
                    print(f"No se pudo crear índice en columna {column}: {e}")
                    print(f"Intentando crear un índice parcial en {column}...")
                    try:
                        # Crear un índice parcial para columnas grandes como 'content'
                        cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name}_partial ON {snippet_table}({column}) WHERE length({column}) < 1000;")
                        print(f"Índice parcial {idx_name}_partial creado correctamente.")
                    except sqlite3.Error as e2:
                        print(f"Error creando índice parcial: {e2}")
                else:
                    print(f"Error al crear índice {idx_name}: {e}")
        
        # Crear índice virtual de búsqueda de texto completo si no existe
        if not has_fts and 'content' in column_names:
            try:
                fts_table_name = f"fts_{snippet_table}"
                print(f"Creando tabla de búsqueda de texto completo {fts_table_name}...")
                
                # Determinar qué columnas incluir en FTS
                fts_columns = []
                for col in ['filename', 'content', 'tags', 'path']:
                    if col in column_names:
                        fts_columns.append(col)
                
                fts_columns_str = ", ".join(fts_columns)
                
                # Crear tabla FTS5 (mejor rendimiento que FTS4)
                cursor.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {fts_table_name} USING fts5(
                    {fts_columns_str},
                    content={snippet_table}
                );
                """)
                
                # Poblar la tabla FTS con datos existentes
                print("Poblando tabla FTS con datos existentes...")
                cursor.execute(f"""
                INSERT INTO {fts_table_name}({fts_table_name}) VALUES('rebuild');
                """)
                
                # Crear trigger para mantener FTS actualizada con inserciones
                print("Creando triggers para mantener FTS actualizada...")
                cursor.execute(f"""
                CREATE TRIGGER IF NOT EXISTS {snippet_table}_ai AFTER INSERT ON {snippet_table} BEGIN
                    INSERT INTO {fts_table_name}({fts_columns_str}) VALUES ({', '.join(['new.' + col for col in fts_columns])});
                END;
                """)
                
                # Trigger para actualizaciones
                cursor.execute(f"""
                CREATE TRIGGER IF NOT EXISTS {snippet_table}_au AFTER UPDATE ON {snippet_table} BEGIN
                    INSERT INTO {fts_table_name}({fts_table_name}, {fts_columns_str}) VALUES('delete', {', '.join(['old.' + col for col in fts_columns])});
                    INSERT INTO {fts_table_name}({fts_columns_str}) VALUES ({', '.join(['new.' + col for col in fts_columns])});
                END;
                """)
                
                # Trigger para eliminaciones
                cursor.execute(f"""
                CREATE TRIGGER IF NOT EXISTS {snippet_table}_ad AFTER DELETE ON {snippet_table} BEGIN
                    INSERT INTO {fts_table_name}({fts_table_name}, {fts_columns_str}) VALUES('delete', {', '.join(['old.' + col for col in fts_columns])});
                END;
                """)
                
                print(f"Tabla FTS {fts_table_name} creada y poblada correctamente.")
                has_fts = True
            except sqlite3.Error as e:
                print(f"Error al crear tabla FTS: {e}")
        
        # Guardar cambios antes de VACUUM
        conn.commit()
        
        # Configuraciones recomendadas para rendimiento
        cursor.execute("PRAGMA journal_mode = WAL;")  # Modo Write-Ahead Logging para mejor concurrencia
        cursor.execute("PRAGMA synchronous = NORMAL;")  # Balance entre rendimiento y seguridad
        cursor.execute("PRAGMA cache_size = 10000;")  # Aumentar caché (en páginas)
        cursor.execute("PRAGMA temp_store = MEMORY;")  # Usar memoria para tablas temporales
        conn.commit()
        
        # Ejecutar VACUUM fuera de la transacción
        print("Compactando base de datos (VACUUM)...")
        conn.isolation_level = None  # Desactivar el modo de autocommit
        cursor.execute("VACUUM;")
        conn.isolation_level = ''  # Restaurar el modo predeterminado
        
        # Analizar la base de datos para optimizar el planificador de consultas
        print("Analizando base de datos...")
        cursor.execute("ANALYZE;")
        
        # Optimizar la base de datos
        print("Ejecutando optimización final...")
        cursor.execute("PRAGMA optimize;")
        conn.commit()
        
        # Verificar y mostrar estadísticas
        cursor.execute(f"SELECT count(*) FROM {snippet_table};")
        total_snippets = cursor.fetchone()[0]
        
        print("\nResumen de optimización:")
        print(f"Total de snippets: {total_snippets}")
        print(f"Índices creados/verificados: {len(needed_indices)}")
        print(f"Búsqueda de texto completo (FTS): {'Configurada' if has_fts else 'No configurada'}")
        
        if has_fts:
            # Verificar que FTS funciona correctamente
            fts_table = f"fts_{snippet_table}"
            try:
                cursor.execute(f"SELECT count(*) FROM {fts_table};")
                fts_count = cursor.fetchone()[0]
                print(f"Registros en tabla FTS: {fts_count}")
                if fts_count != total_snippets:
                    print("ADVERTENCIA: El número de registros en FTS no coincide con la tabla principal.")
                    print("Ejecutando reconstrucción de FTS...")
                    cursor.execute(f"INSERT INTO {fts_table}({fts_table}) VALUES('rebuild');")
                    conn.commit()
            except sqlite3.Error as e:
                print(f"Error verificando tabla FTS: {e}")
        
        # Cerrar conexión
        conn.close()
        
        print("=" * 50)
        print(f"Optimización completada exitosamente.")
        return True
        
    except sqlite3.Error as e:
        print(f"Error durante la optimización: {e}")
        return False
    except Exception as e:
        print(f"Error inesperado: {e}")
        return False

def main():
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = 'wiki_obsidian_plus.db'  # Ruta por defecto
    
    print(f"Script de optimización de base de datos para búsqueda de Markdown")
    print(f"Base de datos objetivo: {db_path}")
    
    start_time = time.time()
    success = optimize_database(db_path)
    elapsed_time = time.time() - start_time
    
    if success:
        print(f"Optimización completada en {elapsed_time:.2f} segundos.")
    else:
        print("La optimización no se completó correctamente.")
        print("Sugerencia: Ejecuta este script con la ruta específica a tu base de datos:")
        print(f"python {sys.argv[0]} ruta/a/tu/base_de_datos.db")

if __name__ == '__main__':
    main()