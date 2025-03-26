from PyQt6.QtCore import QThread, pyqtSignal, QTimer



class SearchWorker(QThread):
    # Señal que emite los resultados de la búsqueda
    search_finished = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, db_path, search_term, selected_folders, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_path = db_path
        self.search_term = search_term
        self.selected_folders = selected_folders
    
    def run(self):
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            search_term = self.search_term.strip()
            results = []
            
            if search_term:
                # Construir consulta SQL con búsqueda en FTS y posible filtro de carpetas
                query = """
                SELECT s.id, s.filename, s.path, s.content
                FROM snippets s
                LEFT JOIN snippet_tags st ON s.id = st.snippet_id
                LEFT JOIN tags t ON st.tag_id = t.id
                WHERE 
                """
                
                # Buscar en tabla FTS para contenido y nombre de archivo
                fts_condition = """
                s.id IN (
                    SELECT rowid FROM snippet_fts 
                    WHERE snippet_fts MATCH ?
                )
                """
                
                # Buscar en tags
                tag_condition = """
                OR t.name LIKE ?
                """
                
                query += fts_condition + tag_condition
                
                # Añadir filtro de carpetas si está definido
                folder_condition = ""
                folder_params = []
                
                if self.selected_folders is not None and len(self.selected_folders) > 0:
                    folder_condition_parts = []
                    for folder in self.selected_folders:
                        folder_condition_parts.append("s.path LIKE ?")
                        folder_params.append(f"{folder}%")
                    
                    folder_condition = f" AND ({' OR '.join(folder_condition_parts)})"
                    
                query += folder_condition
                
                # Agrupar para evitar duplicados y ordenar por nombre
                query += " GROUP BY s.id ORDER BY s.filename"
                
                # Parámetros para la consulta
                params = [search_term, f"%{search_term}%"] + folder_params
                
                # Ejecutar la consulta
                cursor.execute(query, params)
            else:
                # Si no hay término de búsqueda, mostrar todos los snippets (con posible filtro de carpetas)
                if self.selected_folders is not None and len(self.selected_folders) > 0:
                    folder_condition_parts = []
                    folder_params = []
                    
                    for folder in self.selected_folders:
                        folder_condition_parts.append("path LIKE ?")
                        folder_params.append(f"{folder}%")
                    
                    folder_condition = f"({' OR '.join(folder_condition_parts)})"
                    query = f"""
                    SELECT id, filename, path, content
                    FROM snippets
                    WHERE {folder_condition}
                    ORDER BY filename
                    """
                    cursor.execute(query, folder_params)
                else:
                    # Mostrar todos sin filtro
                    cursor.execute("""
                    SELECT id, filename, path, content
                    FROM snippets
                    ORDER BY filename
                    """)
            
            # Procesar resultados básicos
            basic_results = cursor.fetchall()
            
            # Procesar resultados y obtener tags
            for snippet_id, filename, path, content in basic_results:
                # Obtener tags para este snippet
                cursor.execute("""
                SELECT t.name FROM tags t
                JOIN snippet_tags st ON t.id = st.tag_id
                WHERE st.snippet_id = ?
                """, (snippet_id,))
                
                tags = [tag[0] for tag in cursor.fetchall()]
                
                # Añadir toda la información a los resultados
                results.append((snippet_id, filename, path, content, tags))
            
            # Cerrar conexión
            conn.close()
            
            # Emitir resultados
            self.search_finished.emit(results)
            
        except sqlite3.Error as e:
            self.error_occurred.emit(f"Error al buscar snippets: {e}")
        except Exception as e:
            self.error_occurred.emit(f"Error inesperado: {e}")

