#!/usr/bin/env python3
"""
Generador de índice HTML para colección de Bandcamp
Lee una carpeta con archivos HTML de géneros y genera el index.html
"""

import os
import re
import argparse
from html import escape


def extract_genre_info_from_html(filepath):
    """
    Extrae información de un archivo HTML de género.

    Returns:
        dict con 'genre', 'count', 'filename' o None si hay error
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Buscar el título del género en el HTML
        title_match = re.search(r'<h1>🎵 ([^<]+)</h1>', content)

        # Contar discos buscando embed-item
        count = len(re.findall(r'class="embed-item[^"]*"', content))

        if title_match and count > 0:
            genre_name = title_match.group(1).strip()
            filename = os.path.basename(filepath)

            return {
                'genre': genre_name,
                'count': count,
                'filename': filename
            }

        return None

    except Exception as e:
        print(f"⚠️  Error leyendo {filepath}: {e}")
        return None


def scan_html_directory(directory):
    """
    Escanea un directorio buscando archivos HTML de géneros.

    Returns:
        dict con género como clave y {'filename': ..., 'count': ...} como valor
    """
    genres_data = {}

    print(f"🔍 Escaneando directorio: {directory}\n")

    if not os.path.exists(directory):
        print(f"❌ El directorio {directory} no existe")
        return genres_data

    # Buscar todos los archivos HTML excepto index.html
    html_files = [f for f in os.listdir(directory)
                  if f.endswith('.html') and f != 'index.html']

    if not html_files:
        print("⚠️  No se encontraron archivos HTML de géneros")
        return genres_data

    print(f"📄 Encontrados {len(html_files)} archivos HTML:\n")

    for html_file in sorted(html_files):
        filepath = os.path.join(directory, html_file)
        info = extract_genre_info_from_html(filepath)

        if info:
            genres_data[info['genre']] = {
                'filename': info['filename'],
                'count': info['count']
            }
            print(f"  ✓ {info['filename']:<30} → {info['genre']:<20} ({info['count']} discos)")
        else:
            print(f"  ⚠️  {html_file:<30} → No se pudo procesar")

    print(f"\n📊 Total de géneros válidos: {len(genres_data)}\n")

    return genres_data


def generate_index_html(genres_data, output_dir):
    """
    Genera el archivo index.html con enlaces a todos los géneros.

    Args:
        genres_data: dict con formato {genre_name: {'filename': '...', 'count': N}}
        output_dir: directorio donde guardar el index.html
    """
    if not genres_data:
        print("❌ No hay datos de géneros para generar el índice")
        return

    # Generar cards de géneros
    cards_html = ""
    for genre, data in sorted(genres_data.items()):
        filename = data['filename']
        count = data['count']

        cards_html += f"""
        <div class="genre-card" data-genre="{escape(genre.lower())}">
            <h2>🎵 {escape(genre)}</h2>
            <p class="genre-count">📀 {count} disco{"s" if count != 1 else ""}</p>
            <a href="{filename}" class="genre-link">Ver colección →</a>
        </div>
        """

    total_discos = sum(d['count'] for d in genres_data.values())

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎵 Mi Colección de Bandcamp</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        header {{
            text-align: center;
            color: white;
            padding: 50px 20px;
            margin-bottom: 40px;
        }}

        h1 {{
            font-size: 3.5em;
            margin-bottom: 15px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2);
        }}

        .subtitle {{
            font-size: 1.3em;
            opacity: 0.9;
        }}

        .search-container {{
            max-width: 600px;
            margin: 0 auto 40px;
        }}

        .search-box {{
            width: 100%;
            padding: 15px 25px;
            font-size: 1.1em;
            border: none;
            border-radius: 50px;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
            outline: none;
            transition: box-shadow 0.3s;
        }}

        .search-box:focus {{
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
        }}

        .genres-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 25px;
            margin-bottom: 40px;
        }}

        .genre-card {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s, box-shadow 0.3s;
            text-decoration: none;
            color: inherit;
        }}

        .genre-card:hover {{
            transform: translateY(-10px);
            box-shadow: 0 15px 40px rgba(0, 0, 0, 0.15);
        }}

        .genre-card.hidden {{
            display: none;
        }}

        .genre-card h2 {{
            color: #333;
            font-size: 1.8em;
            margin-bottom: 10px;
        }}

        .genre-count {{
            color: #666;
            font-size: 1.1em;
            margin-bottom: 20px;
        }}

        .genre-link {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px 30px;
            border-radius: 25px;
            text-decoration: none;
            font-weight: 500;
            transition: transform 0.3s;
        }}

        .genre-link:hover {{
            transform: scale(1.05);
        }}

        .no-results {{
            text-align: center;
            color: white;
            font-size: 1.3em;
            padding: 40px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            display: none;
        }}

        .no-results.visible {{
            display: block;
        }}

        footer {{
            text-align: center;
            color: rgba(255, 255, 255, 0.8);
            padding: 30px;
            margin-top: 40px;
        }}

        @media (max-width: 768px) {{
            h1 {{
                font-size: 2.5em;
            }}

            .genres-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎵 Mi Colección de Bandcamp</h1>
            <p class="subtitle">Explora tu música por género</p>
        </header>

        <div class="search-container">
            <input type="text" class="search-box" placeholder="🔍 Buscar género..." id="searchInput">
        </div>

        <div class="genres-grid" id="genresGrid">
            {cards_html}
        </div>

        <div class="no-results" id="noResults">
            No se encontraron géneros que coincidan con tu búsqueda
        </div>

        <footer>
            <p>Generado con ❤️ para los amantes de Bandcamp</p>
            <p style="margin-top: 10px; font-size: 0.9em;">
                Total de géneros: {len(genres_data)} |
                Total de discos: {total_discos}
            </p>
        </footer>
    </div>

    <script>
        const searchInput = document.getElementById('searchInput');
        const genreCards = document.querySelectorAll('.genre-card');
        const noResults = document.getElementById('noResults');

        // Búsqueda en tiempo real
        searchInput.addEventListener('input', (e) => {{
            const searchTerm = e.target.value.toLowerCase().trim();
            let visibleCount = 0;

            genreCards.forEach(card => {{
                const genreName = card.dataset.genre;
                const matches = genreName.includes(searchTerm);

                card.classList.toggle('hidden', !matches);
                if (matches) visibleCount++;
            }});

            noResults.classList.toggle('visible', visibleCount === 0 && searchTerm !== '');
        }});

        // Limpiar búsqueda con ESC
        searchInput.addEventListener('keydown', (e) => {{
            if (e.key === 'Escape') {{
                searchInput.value = '';
                searchInput.dispatchEvent(new Event('input'));
            }}
        }});
    </script>
</body>
</html>
"""

    filepath = os.path.join(output_dir, 'index.html')
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✅ Index generado: {filepath}")
    print(f"\n📊 Estadísticas:")
    print(f"   • Géneros: {len(genres_data)}")
    print(f"   • Total de discos: {total_discos}")


def main():
    parser = argparse.ArgumentParser(
        description='Genera index.html leyendo archivos HTML de géneros en una carpeta'
    )

    parser.add_argument(
        'directory',
        nargs='?',
        default='bandcamp_html',
        help='Directorio con los archivos HTML de géneros (default: bandcamp_html)'
    )

    parser.add_argument(
        '--output',
        help='Directorio de salida (default: mismo que el de entrada)'
    )

    args = parser.parse_args()

    input_dir = args.directory
    output_dir = args.output if args.output else input_dir

    print("\n" + "="*80)
    print("📝 GENERADOR DE ÍNDICE - Bandcamp Collection")
    print("="*80 + "\n")

    # Escanear directorio
    genres_data = scan_html_directory(input_dir)

    if not genres_data:
        print("\n❌ No se encontraron géneros válidos")
        print("💡 Asegúrate de que el directorio contenga archivos HTML generados")
        return

    # Generar índice
    print("="*80)
    print("📝 Generando index.html...")
    print("="*80 + "\n")

    generate_index_html(genres_data, output_dir)

    print(f"\n{'='*80}")
    print(f"✅ ¡Listo! Abre {os.path.join(output_dir, 'index.html')} en tu navegador")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    main()
