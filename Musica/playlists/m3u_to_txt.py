import os
import sys
from pathlib import Path
from mutagen import File

def obtener_metadata_audio(ruta_audio):
    """
    Lee un archivo de audio usando mutagen y devuelve el formato 'Artista - Canción'.
    Si no encuentra metadata o el archivo no existe, intenta usar el nombre del archivo.
    """
    try:
        audio = File(ruta_audio)
        if audio is None:
            return None

        # Intentar extraer artista y título de la metadata
        # Mutagen usa claves diferentes según el formato (MP3, FLAC, M4A, etc.)
        # .get() ayuda a manejar esto de forma más flexible
        artista = None
        titulo = None

        # Tags comunes (ID3 para MP3, Vorbis para FLAC/OGG)
        if 'TPE1' in audio:  # MP3 Artista
            artista = audio['TPE1'].text[0]
        elif 'artist' in audio:  # FLAC/OGG Artista
            artista = audio['artist'][0]
        elif '\xa9ART' in audio:  # M4A Artista
            artista = audio['\xa9ART'][0]

        if 'TIT2' in audio:  # MP3 Título
            titulo = audio['TIT2'].text[0]
        elif 'title' in audio:  # FLAC/OGG Título
            titulo = audio['title'][0]
        elif '\xa9nam' in audio:  # M4A Título
            titulo = audio['\xa9nam'][0]

        # Si se encontró la metadata, formateamos
        if artista and titulo:
            return f"{artista.strip()} - {titulo.strip()}"
        elif titulo:
            return f"Artista Desconocido - {titulo.strip()}"
        
    except Exception as e:
        # Si hay un error leyendo el archivo (ej. archivo corrupto o movido), saltamos a fallback
        pass

    # Fallback: Si falla la metadata o no existe, usamos el nombre del archivo sin extensión
    nombre_archivo = Path(ruta_audio).stem
    return f"Desconocido - {nombre_archivo}"

def procesar_listas_m3u(carpeta_objetivo):
    ruta_carpeta = Path(carpeta_objetivo)

    if not ruta_carpeta.is_dir():
        print(f"Error: La ruta '{carpeta_objetivo}' no es un directorio válido.")
        return

    # Buscar todos los archivos .m3u en la carpeta
    archivos_m3u = list(ruta_carpeta.glob("*.m3u"))

    if not archivos_m3u:
        print(f"No se encontraron archivos .m3u en la carpeta: {ruta_carpeta.resolve()}")
        return

    print(f"Se encontraron {len(archivos_m3u)} archivos .m3u para procesar.\n")

    for ruta_m3u in archivos_m3u:
        print(f"Procesando: {ruta_m3u.name}...")
        lineas_salida = []

        with open(ruta_m3u, 'r', encoding='utf-8', errors='ignore') as m3u_file:
            for linea in m3u_file:
                linea = linea.strip()
                
                # Ignorar líneas vacías y comentarios de M3U (como #EXTM3U o #EXTINF)
                if not linea or linea.startswith('#'):
                    continue

                # El M3U puede tener rutas relativas a la ubicación del propio archivo .m3u
                ruta_audio = Path(linea)
                if not ruta_audio.is_absolute():
                    ruta_audio = ruta_m3u.parent / ruta_audio

                # Si el archivo de audio existe, extraemos su metadata
                if ruta_audio.exists():
                    formato_cancion = obtener_metadata_audio(ruta_audio)
                    if formato_cancion:
                        lineas_salida.append(formato_cancion)
                else:
                    # Si el archivo ya no está ahí, usamos el nombre que venía en la ruta del m3u
                    lineas_salida.append(f"Archivo No Encontrado - {ruta_audio.stem}")

        # Crear el archivo .txt de salida con el mismo nombre que el m3u
        ruta_txt_salida = ruta_m3u.with_suffix('.txt')
        with open(ruta_txt_salida, 'w', encoding='utf-8') as txt_file:
            for linea_formateada in lineas_salida:
                txt_file.write(f"{linea_formateada}\n")
        
        print(f"-> Creado con éxito: {ruta_txt_salida.name}")

if __name__ == "__main__":
    # Validar que se haya pasado la carpeta como argumento
    if len(sys.argv) < 2:
        print("Uso: python procesar_m3u.py /ruta/a/la/carpeta_con_m3u")
        sys.exit(1)

    carpeta_argumento = sys.argv[1]
    procesar_listas_m3u(carpeta_argumento)
