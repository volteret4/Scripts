#!/usr/bin/env python3
"""
Script auxiliar para encontrar carpetas de correo de Thunderbird
relacionadas con Bandcamp
"""

import os
import sys
from pathlib import Path


def find_thunderbird_profiles():
    """Encuentra los perfiles de Thunderbird en el sistema."""
    possible_paths = [
        Path.home() / '.thunderbird',
        Path.home() / '.mozilla-thunderbird',
        Path.home() / 'snap' / 'thunderbird' / 'common' / '.thunderbird',
        Path('/home') / os.getenv('USER', '') / '.thunderbird',
    ]

    profiles = []
    for base_path in possible_paths:
        if base_path.exists():
            # Buscar perfiles
            for item in base_path.iterdir():
                if item.is_dir() and ('default' in item.name.lower() or '.default' in item.name):
                    profiles.append(item)

    return profiles


def find_mail_folders(profile_path):
    """Encuentra carpetas de correo en un perfil de Thunderbird."""
    folders = []

    # Buscar en Mail y ImapMail
    for mail_dir in ['Mail', 'ImapMail']:
        mail_path = profile_path / mail_dir
        if mail_path.exists():
            # Buscar en subdirectorios
            for account in mail_path.iterdir():
                if account.is_dir():
                    # Buscar archivos mbox (sin extensión)
                    for item in account.iterdir():
                        if item.is_file() and not item.suffix and item.stat().st_size > 0:
                            folders.append(item)
                        # También buscar en subdirectorios
                        elif item.is_dir():
                            for subitem in item.iterdir():
                                if subitem.is_file() and not subitem.suffix and subitem.stat().st_size > 0:
                                    folders.append(subitem)

    return folders


def main():
    print("🔍 Buscando carpetas de Thunderbird...\n")

    profiles = find_thunderbird_profiles()

    if not profiles:
        print("❌ No se encontraron perfiles de Thunderbird")
        print("\nPor favor, especifica manualmente la ruta a tus carpetas de correo.")
        print("Las carpetas suelen estar en:")
        print("  - ~/.thunderbird/XXXXXXXX.default/Mail/")
        print("  - ~/.thunderbird/XXXXXXXX.default/ImapMail/")
        return

    print(f"✓ Encontrados {len(profiles)} perfiles de Thunderbird\n")

    all_folders = []
    for profile in profiles:
        print(f"Perfil: {profile}")
        folders = find_mail_folders(profile)
        all_folders.extend([(folder, profile) for folder in folders])
        print(f"  Carpetas encontradas: {len(folders)}\n")

    if not all_folders:
        print("❌ No se encontraron carpetas de correo")
        return

    print("📂 Carpetas de correo encontradas:\n")

    # Filtrar carpetas que podrían contener correos de Bandcamp
    bandcamp_keywords = ['bandcamp', 'music', 'rock', 'electronic', 'jazz', 'metal',
                         'ambient', 'classical', 'hip-hop', 'folk', 'indie', 'experimental']

    relevant_folders = []

    for folder, profile in all_folders:
        folder_name = folder.name.lower()
        # Verificar si el nombre contiene palabras clave
        is_relevant = any(keyword in folder_name for keyword in bandcamp_keywords)

        if is_relevant or True:  # Mostrar todas por ahora
            size_mb = folder.stat().st_size / (1024 * 1024)
            status = "⭐" if is_relevant else "  "
            print(f"{status} {folder}")
            print(f"   Tamaño: {size_mb:.2f} MB")
            print(f"   Nombre: {folder.name}")
            relevant_folders.append(folder)

    print("\n" + "="*80)
    print("📝 COMANDO SUGERIDO:\n")
    print("python3 bandcamp_html_generator.py --folders \\")

    # Sugerir algunos ejemplos
    example_folders = [f for f in relevant_folders[:5]]  # Primeros 5

    for i, folder in enumerate(example_folders):
        # Intentar inferir el género del nombre de la carpeta
        genre = folder.stem.replace('_', ' ').replace('-', ' ').title()
        separator = " \\" if i < len(example_folders) - 1 else ""
        print(f"  '{folder}:{genre}'{separator}")

    print("\n" + "="*80)
    print("\n💡 INSTRUCCIONES:")
    print("1. Revisa las carpetas listadas arriba")
    print("2. Identifica cuáles contienen correos de Bandcamp por género")
    print("3. Ejecuta el comando adaptándolo a tus carpetas específicas")
    print("4. El formato es: 'RUTA_COMPLETA:NOMBRE_GÉNERO'")
    print("\nEjemplo:")
    print("  '/home/user/.thunderbird/xxx.default/Mail/Local Folders/Rock:Rock'")


if __name__ == '__main__':
    main()
