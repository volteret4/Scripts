#!/usr/bin/env python3
"""
Script para limpiar el campo GENRE de archivos de música.
Reemplaza comas, puntos, dos puntos, barras y guiones por punto y coma (;)
"""

import os
import sys
from pathlib import Path

try:
    from mutagen import File
    from mutagen.id3 import ID3, TCON
    from mutagen.mp4 import MP4
    from mutagen.flac import FLAC
    from mutagen.oggvorbis import OggVorbis
except ImportError:
    print("Error: Se requiere la biblioteca 'mutagen'")
    print("Instálala con: pip install mutagen")
    sys.exit(1)


def clean_genre(genre_text):
    """
    Reemplaza caracteres especiales en el texto de género por punto y coma.

    Caracteres reemplazados: , . : / \ - _ | +
    Casos especiales:
    - "hip-hop" se convierte en "hip hop" (con espacio)
    - "post-" (post-metal, post-rock, etc.) se convierte en "post " (con espacio)
    """
    if not genre_text:
        return genre_text

    import re

    # CASO ESPECIAL 1: Preservar "hip-hop" convirtiéndolo en "hip hop"
    # Esto debe hacerse ANTES de reemplazar guiones
    # Usamos regex para capturar hip-hop en cualquier combinación de mayúsculas/minúsculas
    cleaned = re.sub(r'\bhip-hop\b', 'hip hop', genre_text, flags=re.IGNORECASE)

    # CASO ESPECIAL 2: Preservar "post-" convirtiéndolo en "post "
    # Ejemplos: post-metal → post metal, post-rock → post rock, post-punk → post punk
    cleaned = re.sub(r'\bpost-(\w+)', r'post \1', cleaned, flags=re.IGNORECASE)

    # Caracteres a reemplazar por punto y coma
    chars_to_replace = [',', '.', ':', '/', '\\', '-', '_', '|', '+']

    for char in chars_to_replace:
        cleaned = cleaned.replace(char, ';')

    # Limpiar múltiples punto y coma consecutivos
    while ';;' in cleaned:
        cleaned = cleaned.replace(';;', ';')

    # Eliminar punto y coma al inicio o final
    cleaned = cleaned.strip(';').strip()

    return cleaned


def process_file(filepath, dry_run=False, albums_without_genre=None):
    """
    Procesa un archivo de música y limpia su campo GENRE.

    Args:
        filepath: Ruta al archivo de música
        dry_run: Si es True, solo muestra los cambios sin aplicarlos
        albums_without_genre: Set para registrar álbumes sin género

    Returns:
        True si se procesó correctamente, False en caso contrario
    """
    try:
        audio = File(filepath)

        if audio is None:
            print(f"⚠️  No se pudo leer: {filepath}")
            return False

        original_genre = None
        new_genre = None
        modified = False
        has_genre = False

        # Determinar el tipo de archivo y procesar
        file_type = type(audio).__name__

        # FLAC, OGG Vorbis y formatos similares (Vorbis Comments)
        if file_type in ['FLAC', 'OggVorbis', 'OggOpus', 'OggSpeex', 'OggTheora']:
            if 'genre' in audio and audio['genre']:
                has_genre = True
                # Los tags Vorbis son listas
                genre_list = audio['genre']
                if genre_list:
                    original_genre = genre_list[0] if isinstance(genre_list, list) else str(genre_list)
                    new_genre = clean_genre(original_genre)
                    if original_genre != new_genre:
                        if not dry_run:
                            audio['genre'] = [new_genre]
                            audio.save()
                        modified = True

        # MP3 (ID3 tags)
        elif file_type in ['MP3', 'ID3']:
            if hasattr(audio, 'tags') and audio.tags is not None:
                if 'TCON' in audio.tags:
                    has_genre = True
                    original_genre = str(audio.tags['TCON'].text[0]) if hasattr(audio.tags['TCON'], 'text') else str(audio.tags['TCON'])
                    new_genre = clean_genre(original_genre)
                    if original_genre != new_genre:
                        if not dry_run:
                            audio.tags['TCON'].text = [new_genre]
                            audio.save()
                        modified = True

        # MP4/M4A
        elif file_type in ['MP4', 'M4A']:
            if hasattr(audio, 'tags') and audio.tags is not None:
                genre_key = None

                # Buscar el campo de género
                if '\xa9gen' in audio.tags:
                    genre_key = '\xa9gen'
                elif 'GENRE' in audio.tags:
                    genre_key = 'GENRE'
                elif 'genre' in audio.tags:
                    genre_key = 'genre'

                if genre_key:
                    has_genre = True
                    original_genre = audio.tags[genre_key][0] if isinstance(audio.tags[genre_key], list) else str(audio.tags[genre_key])
                    new_genre = clean_genre(original_genre)
                    if original_genre != new_genre:
                        if not dry_run:
                            audio.tags[genre_key] = [new_genre]
                            audio.save()
                        modified = True

        # WMA y otros formatos ASF
        elif file_type == 'ASF':
            if hasattr(audio, 'tags') and audio.tags is not None:
                if 'WM/Genre' in audio.tags:
                    has_genre = True
                    original_genre = str(audio.tags['WM/Genre'][0].value) if hasattr(audio.tags['WM/Genre'][0], 'value') else str(audio.tags['WM/Genre'][0])
                    new_genre = clean_genre(original_genre)
                    if original_genre != new_genre:
                        if not dry_run:
                            audio.tags['WM/Genre'] = [new_genre]
                            audio.save()
                        modified = True

        # Si no tiene género, registrar el álbum
        if not has_genre and albums_without_genre is not None:
            album_dir = os.path.dirname(filepath)
            albums_without_genre.add(album_dir)

        # Mostrar cambios
        if modified:
            status = "🔍 [DRY RUN]" if dry_run else "✅ Modificado"
            print(f"{status}: {os.path.basename(filepath)}")
            print(f"   Antes: {original_genre}")
            print(f"   Después: {new_genre}")
            return True
        else:
            if original_genre:
                print(f"ℹ️  Sin cambios: {os.path.basename(filepath)} (Género: {original_genre})")
            else:
                print(f"⚠️  Sin tag GENRE: {os.path.basename(filepath)}")
            return False

    except Exception as e:
        print(f"❌ Error procesando {filepath}: {str(e)}")
        import traceback
        if '--verbose' in sys.argv:
            traceback.print_exc()
        return False


def main():
    """Función principal del script."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Limpia el campo GENRE de archivos de música reemplazando caracteres especiales por punto y coma.'
    )
    parser.add_argument(
        'path',
        help='Ruta al archivo o carpeta con archivos de música'
    )
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='Procesar carpetas de forma recursiva'
    )
    parser.add_argument(
        '-d', '--dry-run',
        action='store_true',
        help='Modo de prueba: muestra los cambios sin aplicarlos'
    )
    parser.add_argument(
        '-e', '--extensions',
        default='mp3,m4a,mp4,flac,ogg,wma',
        help='Extensiones de archivo a procesar (separadas por comas). Default: mp3,m4a,mp4,flac,ogg,wma'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Mostrar información detallada de errores'
    )
    parser.add_argument(
        '--export-missing',
        type=str,
        metavar='ARCHIVO',
        help='Exportar lista de álbumes sin género a un archivo (para importar en Picard)'
    )

    args = parser.parse_args()

    # Obtener extensiones válidas
    valid_extensions = [f'.{ext.strip().lower()}' for ext in args.extensions.split(',')]

    # Verificar que la ruta existe
    path = Path(args.path)
    if not path.exists():
        print(f"❌ Error: La ruta '{args.path}' no existe")
        sys.exit(1)

    # Recopilar archivos a procesar
    files_to_process = []

    if path.is_file():
        if path.suffix.lower() in valid_extensions:
            files_to_process.append(path)
        else:
            print(f"❌ Error: El archivo no tiene una extensión válida")
            sys.exit(1)
    else:
        # Es una carpeta
        if args.recursive:
            for ext in valid_extensions:
                files_to_process.extend(path.rglob(f'*{ext}'))
        else:
            for ext in valid_extensions:
                files_to_process.extend(path.glob(f'*{ext}'))

    if not files_to_process:
        print(f"⚠️  No se encontraron archivos de música en '{args.path}'")
        sys.exit(0)

    # Set para registrar álbumes sin género
    albums_without_genre = set()

    # Mostrar información
    print(f"\n{'='*60}")
    if args.dry_run:
        print("🔍 MODO DE PRUEBA - No se aplicarán cambios")
    print(f"📁 Procesando: {args.path}")
    print(f"📝 Archivos encontrados: {len(files_to_process)}")
    print(f"{'='*60}\n")

    # Procesar archivos
    modified_count = 0
    for filepath in sorted(files_to_process):
        if process_file(filepath, args.dry_run, albums_without_genre):
            modified_count += 1
        print()  # Línea en blanco entre archivos

    # Resumen final
    print(f"{'='*60}")
    print(f"✨ Procesamiento completado")
    print(f"📊 Total de archivos: {len(files_to_process)}")
    print(f"✅ Archivos {'que se modificarían' if args.dry_run else 'modificados'}: {modified_count}")

    # Mostrar información de álbumes sin género
    if albums_without_genre:
        print(f"⚠️  Álbumes sin tag GENRE: {len(albums_without_genre)}")
        print(f"{'='*60}")

        # Exportar lista si se especificó
        if args.export_missing:
            export_file = args.export_missing

            # Crear también un script bash para Picard
            picard_script = export_file.replace('.txt', '_picard.sh')

            try:
                # Exportar lista de álbumes
                with open(export_file, 'w', encoding='utf-8') as f:
                    f.write("# Álbumes sin tag GENRE\n")
                    f.write(f"# Generado el: {Path(export_file).name}\n")
                    f.write(f"# Total: {len(albums_without_genre)} álbumes\n\n")
                    for album in sorted(albums_without_genre):
                        f.write(f"{album}\n")

                print(f"\n📄 Lista exportada a: {export_file}")

                # Crear script para abrir en Picard
                with open(picard_script, 'w', encoding='utf-8') as f:
                    f.write("#!/bin/bash\n")
                    f.write("# Script para cargar álbumes sin género en MusicBrainz Picard\n")
                    f.write(f"# Generado automáticamente\n\n")
                    f.write("# Verifica que Picard esté instalado\n")
                    f.write("if ! command -v picard &> /dev/null; then\n")
                    f.write('    echo "❌ Error: MusicBrainz Picard no está instalado"\n')
                    f.write('    echo "Instálalo con: sudo apt install picard (Ubuntu/Debian)"\n')
                    f.write("    exit 1\n")
                    f.write("fi\n\n")
                    f.write(f"echo 'Cargando {len(albums_without_genre)} álbumes en Picard...'\n")
                    f.write("picard \\\n")
                    for i, album in enumerate(sorted(albums_without_genre)):
                        # Escapar espacios y caracteres especiales
                        escaped = album.replace("'", "'\\''")
                        if i < len(albums_without_genre) - 1:
                            f.write(f"  '{escaped}' \\\n")
                        else:
                            f.write(f"  '{escaped}'\n")

                # Hacer el script ejecutable
                os.chmod(picard_script, 0o755)

                print(f"📄 Script de Picard: {picard_script}")
                print(f"\n💡 Para cargar en Picard, ejecuta:")
                print(f"   bash {picard_script}")

            except Exception as e:
                print(f"❌ Error al exportar: {e}")
        else:
            print(f"\n💡 Para exportar esta lista, usa:")
            print(f"   --export-missing albums_sin_genero.txt")
            print(f"\n📂 Primeros 10 álbumes sin género:")
            for album in sorted(albums_without_genre)[:10]:
                print(f"   - {album}")
            if len(albums_without_genre) > 10:
                print(f"   ... y {len(albums_without_genre) - 10} más")

    print(f"{'='*60}")

    if args.dry_run and modified_count > 0:
        print("\n💡 Ejecuta sin --dry-run para aplicar los cambios")


if __name__ == '__main__':
    main()
