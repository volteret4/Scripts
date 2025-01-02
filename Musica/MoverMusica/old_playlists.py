import os
import shutil

# Directorios
mix_dir = "/mnt/windows/Mix"
old_dir = "/mnt/windows/Mix/.old"

# Crear el directorio .old si no existe
if not os.path.exists(old_dir):
    os.makedirs(old_dir)

# Función para leer archivos desde un .m3u
def leer_m3u(archivo_m3u):
    archivos_en_playlist = []
    with open(archivo_m3u, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea and not linea.startswith("#"):  # Ignorar comentarios en la playlist
                archivos_en_playlist.append(linea)
    return archivos_en_playlist

# Recorrer las carpetas en /Mix (exceptuando .old)
for carpeta in os.listdir(mix_dir):
    carpeta_ruta = os.path.join(mix_dir, carpeta)
    
    # Verificar si es un directorio
    if os.path.isdir(carpeta_ruta) and carpeta != ".old" and carpeta != ".playlists":
        archivo_m3u = os.path.join(mix_dir, f"{carpeta}.m3u")
        
        # Verificar si existe la playlist con el mismo nombre que la carpeta
        if os.path.exists(archivo_m3u):
            archivos_playlist = leer_m3u(archivo_m3u)
            archivos_relativos_playlist = set(archivos_playlist)
            archivos_en_carpeta = set(os.listdir(carpeta_ruta))

            # Comparar archivos y mover los que no están en la playlist
            for archivo in archivos_en_carpeta:
                if archivo not in archivos_relativos_playlist:
                    origen = os.path.join(carpeta_ruta, archivo)
                    destino = os.path.join(old_dir, carpeta)
                    # Crear el subdirectorio en .old si no existe
                    if not os.path.exists(destino):
                        os.makedirs(destino)
                    # Mover el archivo
                    shutil.move(origen, os.path.join(destino, archivo))
                    print(f"Moviendo {archivo} a {destino}")
        else:
            print(f"No se encontró la playlist para el género: {carpeta}")
