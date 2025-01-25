import shutil
import os
import time

# Ruta del perfil de Floorp
profile_path = os.path.expanduser('/home/huan/.floorp/26srpcup.default-releaseta')  # Cambia esto
backup_path = os.path.expanduser('/mnt/windows/FTP/wiki/bookmarks_backup.html')  # Cambia esto

# Función para exportar marcadores
def export_bookmarks():
    try:
        # Busca el archivo de marcadores
        bookmarks_file = os.path.join(profile_path, 'places.sqlite')  # Archivo que contiene los marcadores
        if os.path.exists(bookmarks_file):
            shutil.copy(bookmarks_file, backup_path)
            print("Marcadores exportados a:", backup_path)
        else:
            print("El archivo de marcadores no se encontró.")
    except Exception as e:
        print("Error al exportar marcadores:", e)

# Ejecuta la función de exportación
if __name__ == "__main__":
    export_bookmarks()