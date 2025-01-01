import os
import sqlite3
import shutil
import re
from datetime import datetime

# Ruta a la base de datos places.sqlite de Floorp
src_db_path = os.path.expanduser('~/.floorp/26srpcup.default-release/places.sqlite')
# Ruta donde se copiará el archivo y se crearán las carpetas
output_db_path = '/mnt/windows/FTP/wiki/marcadores/places.sqlite'
output_path = '/mnt/windows/FTP/wiki/marcadores'

# Dominios a excluir
excluded_pattern = re.compile(r'^(http://|https://)?(www\.)?(google\.com|google\.es|github\.com|bandcamp\.[a-z]{2,4}|invidious\.[a-z]{2,4}|twitter\.com|pornhub\.com|192\.168\.1\.\d{1,3})')

# Copiar el archivo places.sqlite a la nueva ubicación
shutil.copy(src_db_path, output_db_path)

# Conectar a la base de datos
conn = sqlite3.connect(output_db_path)
cursor = conn.cursor()

# Consulta para obtener la estructura de carpetas y marcadores
query = """
SELECT moz_bookmarks.id, moz_bookmarks.title, moz_bookmarks.type, moz_bookmarks.parent, moz_places.url
FROM moz_bookmarks
LEFT JOIN moz_places ON moz_bookmarks.fk = moz_places.id
ORDER BY moz_bookmarks.id;
"""

cursor.execute(query)
bookmarks = cursor.fetchall()

# Función para crear la estructura de carpetas
def create_directory_structure(bookmark_id, parent_id, title):
    path = []
    while parent_id != 0:
        cursor.execute("SELECT title, parent FROM moz_bookmarks WHERE id = ?", (parent_id,))
        parent = cursor.fetchone()
        if parent:
            # Solo agregar el título si no es None
            if parent[0]:
                path.append(parent[0])
            parent_id = parent[1]
        else:
            break
    path.reverse()  # Invertir para tener la jerarquía correcta
    return os.path.join(output_path, *path, title)

# Procesar los marcadores
for bookmark in bookmarks:
    bookmark_id, title, bookmark_type, parent_id, url = bookmark

    if bookmark_type == 1 and not excluded_pattern.match(url):  # Si es un marcador y no está en la lista de exclusión
        # Verificar si el título no es None
        if title is not None:
            # Crear la estructura de carpetas basada en la jerarquía de los marcadores
            sanitized_title = re.sub(r'[<>:"/\\|?*]', '', title)  # Limpiar caracteres no permitidos en nombres de archivos
            dir_path = create_directory_structure(bookmark_id, parent_id, sanitized_title)

            # Asegurarse de que el directorio existe
            directory_to_create = os.path.dirname(dir_path)
            os.makedirs(directory_to_create, exist_ok=True)

            # Definir el nombre del archivo .md como el título sanitizado
            file_name = re.sub(r'[^a-zA-Z0-9]', '_', sanitized_title) + '.md'  # Sanitizar título para el nombre del archivo
            file_path = os.path.join(directory_to_create, file_name)

            # Escribir el título y la URL en el archivo .md
            with open(file_path, 'w') as md_file:
                md_file.write(f'# {title}\n\n')  # Título del archivo Markdown
                md_file.write(f'**URL:** [{url}]({url})\n')  # Enlace a la URL

# Cerrar la conexión a la base de datos
conn.close()

# Obtener la fecha y hora actual
now = datetime.now()
timestamp = now.strftime('%Y-%m-%d %H:%M')

# Imprimir el mensaje final con fecha y hora
print(f"{timestamp} - Archivo places.sqlite copiado y archivos .md creados exitosamente con título y URL.")
