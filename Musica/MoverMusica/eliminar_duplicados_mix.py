import os
import hashlib
import argparse
from collections import defaultdict
from mutagen import File

def calcular_hash(ruta_archivo, chunk_size=8192):
    """Genera un hash MD5 para identificar el contenido binario."""
    hash_md5 = hashlib.md5()
    try:
        with open(ruta_archivo, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return None

def obtener_tags(ruta_archivo):
    """Extrae Artista, Álbum y Título para crear una huella de metadatos."""
    try:
        audio = File(ruta_archivo, easy=True)
        if audio is None:
            return None

        # Extraemos etiquetas básicas, si no existen usamos "Desconocido"
        artista = audio.get('artist', ['Desconocido'])[0].lower().strip()
        album = audio.get('album', ['Desconocido'])[0].lower().strip()
        titulo = audio.get('title', ['Desconocido'])[0].lower().strip()

        # Si no tiene metadatos útiles, no lo agrupamos para evitar falsos positivos
        if artista == album == titulo == "desconocido":
            return None

        return f"{artista}|{album}|{titulo}"
    except Exception:
        return None

def buscar_duplicados(directorio, usar_tags=False):
    extensiones_audio = ('.mp3', '.flac')
    grupos = defaultdict(list)
    metodo = "Etiquetas (Artist-Album-Title)" if usar_tags else "Contenido (MD5)"

    print(f"Modo: {metodo}")
    print(f"Escaneando: {directorio}...\n")

    for raiz, _, archivos in os.walk(directorio):
        for nombre in archivos:
            if nombre.lower().endswith(extensiones_audio):
                ruta_completa = os.path.join(raiz, nombre)

                if usar_tags:
                    identificador = obtener_tags(ruta_completa)
                else:
                    identificador = calcular_hash(ruta_completa)

                if identificador:
                    grupos[identificador].append(ruta_completa)

    return {k: v for k, v in grupos.items() if len(v) > 1}

def gestionar_borrado(duplicados):
    if not duplicados:
        print("No se encontraron duplicados.")
        return

    total_grupos = len(duplicados)
    for i, (key, rutas) in enumerate(duplicados.items(), 1):
        print(f"\n--- Grupo {i} de {total_grupos} ---")
        if "|" in key: # Si es modo tags, mostramos qué tags son
            print(f"Metadata: {key.replace('|', ' - ')}")

        for idx, ruta in enumerate(rutas, 1):
            tamano = os.path.getsize(ruta) / (1024 * 1024)
            print(f"{idx}. {ruta} ({tamano:.2f} MB)")

        print("0. Saltar grupo")

        seleccion = input("\nNúmero(s) a BORRAR (ej: 1 o 1,2): ")

        if seleccion == "0" or not seleccion.strip():
            continue

        try:
            indices = [int(s.strip()) - 1 for s in seleccion.split(",")]
            for index in sorted(indices, reverse=True): # Reverse para no alterar el index al borrar
                if 0 <= index < len(rutas):
                    archivo_a_borrar = rutas[index]
                    os.remove(archivo_a_borrar)
                    print(f"Eliminado: {archivo_a_borrar}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Busca duplicados de audio por MD5 o Tags.")
    parser.add_argument("ruta", help="Carpeta a escanear")
    parser.add_argument("--tags", action="store_true", help="Escanea por Artista/Álbum/Título en lugar de MD5")

    args = parser.parse_args()

    if os.path.isdir(args.ruta):
        duplicados = buscar_duplicados(args.ruta, usar_tags=args.tags)
        gestionar_borrado(duplicados)
        print("\n¡Hecho!")
    else:
        print("Ruta no válida.")
