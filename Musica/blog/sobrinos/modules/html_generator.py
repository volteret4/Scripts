"""
Módulo para generación de HTML
Genera páginas HTML responsivas para álbumes
"""

import logging
from typing import Dict, Any, List
import html
import json

logger = logging.getLogger(__name__)


class HTMLGenerator:
    """Generador de HTML para páginas de álbum"""

    def __init__(self):
        """Inicializar generador HTML"""
        pass

    def generate_html(self, album_info: Dict[str, Any],
                     css_filename: str = "../styles.css",
                     js_filename: str = "../script.js") -> str:
        """
        Generar página HTML completa

        Args:
            album_info: Información del álbum
            css_filename: Nombre del archivo CSS (ruta relativa)
            js_filename: Nombre del archivo JavaScript (ruta relativa)

        Returns:
            Código HTML completo
        """
        logger.info(f"Generando HTML para: {album_info['artist']} - {album_info['title']}")

        # Datos seguros para JavaScript
        safe_album_data = self._prepare_safe_data(album_info)

        # Generar colores dinámicos para este álbum
        album_colors = self._generate_album_colors(album_info)

        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(album_info['artist'])} - {html.escape(album_info['title'])}</title>
    <meta name="description" content="Información completa del álbum {html.escape(album_info['title'])} de {html.escape(album_info['artist'])}">
    <meta name="keywords" content="{html.escape(album_info['artist'])}, {html.escape(album_info['title'])}, álbum, música">

    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="music.album">
    <meta property="og:url" content="">
    <meta property="og:title" content="{html.escape(album_info['artist'])} - {html.escape(album_info['title'])}">
    <meta property="og:description" content="Información completa del álbum {html.escape(album_info['title'])} de {html.escape(album_info['artist'])}">
    <meta property="og:image" content="{self._get_image_url(album_info.get('album_image'))}">

    <!-- Twitter -->
    <meta property="twitter:card" content="summary_large_image">
    <meta property="twitter:title" content="{html.escape(album_info['artist'])} - {html.escape(album_info['title'])}">
    <meta property="twitter:description" content="Información completa del álbum {html.escape(album_info['title'])} de {html.escape(album_info['artist'])}">
    <meta property="twitter:image" content="{self._get_image_url(album_info.get('album_image'))}">

    <link rel="stylesheet" href="{css_filename}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">

    <!-- Colores dinámicos para este álbum -->
    <style>
        :root {{
            --color-primary: {album_colors['primary']};
            --color-secondary: {album_colors['secondary']};
            --color-accent: {album_colors['accent']};
        }}

        .album-header {{
            background: linear-gradient(135deg, {album_colors['primary']}, {album_colors['secondary']});
        }}
    </style>

    <script>
        // Datos del álbum para JavaScript
        window.albumData = {json.dumps(safe_album_data, ensure_ascii=False, indent=2)};
    </script>
</head>
<body>
    <!-- Navegación hacia el índice -->
    <header class="site-header">
        <div class="container">
            <nav class="site-nav">
                <div class="site-logo">
                    <a href="../index.html" style="color: inherit; text-decoration: none;">← Volver a la Colección</a>
                </div>
                <div class="nav-links">
                    <a href="../index.html" class="nav-link">🏠 Inicio</a>
                </div>
            </nav>
        </div>
    </header>

    {self._generate_header(album_info)}
    {self._generate_main_content(album_info)}
    {self._generate_footer(album_info)}

    <script src="{js_filename}"></script>
</body>
</html>"""

        return html_content

    def _generate_header(self, album_info: Dict[str, Any]) -> str:
        """Generar sección header"""
        return f"""
    <header class="album-header">
        <div class="container">
            <div class="album-hero">
                <div class="album-images">
                    <div class="album-cover">
                        <img src="{self._get_image_url(album_info.get('album_image'))}"
                             alt="Portada de {html.escape(album_info['title'])}"
                             onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'300\\' height=\\'300\\' viewBox=\\'0 0 300 300\\'%3E%3Crect width=\\'300\\' height=\\'300\\' fill=\\'%23ddd\\'/%3E%3Ctext x=\\'50%25\\' y=\\'50%25\\' text-anchor=\\'middle\\' dy=\\'.3em\\' font-family=\\'Arial, sans-serif\\' font-size=\\'18\\' fill=\\'%23999\\'%3EÁlbum%3C/text%3E%3C/svg%3E'">
                    </div>
                    <div class="artist-image">
                        <img src="{self._get_image_url(album_info.get('artist_image'))}"
                             alt="Foto de {html.escape(album_info['artist'])}"
                             onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'300\\' height=\\'300\\' viewBox=\\'0 0 300 300\\'%3E%3Ccircle cx=\\'150\\' cy=\\'150\\' r=\\'150\\' fill=\\'%23ddd\\'/%3E%3Ctext x=\\'50%25\\' y=\\'50%25\\' text-anchor=\\'middle\\' dy=\\'.3em\\' font-family=\\'Arial, sans-serif\\' font-size=\\'18\\' fill=\\'%23999\\'%3EArtista%3C/text%3E%3C/svg%3E'">
                    </div>
                </div>

                <div class="album-info">
                    <h1 class="album-title">{html.escape(album_info['title'])}</h1>
                    <h2 class="artist-name">{html.escape(album_info['artist'])}</h2>
                    {self._generate_album_details(album_info)}
                </div>
            </div>
        </div>
    </header>"""

    def _generate_album_details(self, album_info: Dict[str, Any]) -> str:
        """Generar detalles del álbum"""
        details = []

        if album_info.get('year'):
            details.append(f"<span class='detail-item'><strong>Año:</strong> {html.escape(str(album_info['year']))}</span>")

        if album_info.get('genre'):
            genres = ', '.join(album_info['genre']) if isinstance(album_info['genre'], list) else str(album_info['genre'])
            details.append(f"<span class='detail-item'><strong>Género:</strong> {html.escape(genres)}</span>")

        if album_info.get('label'):
            details.append(f"<span class='detail-item'><strong>Sello:</strong> {html.escape(album_info['label'])}</span>")

        if album_info.get('total_tracks'):
            details.append(f"<span class='detail-item'><strong>Pistas:</strong> {album_info['total_tracks']}</span>")

        if details:
            return f"<div class='album-details'>{''.join(details)}</div>"

        return ""

    def _generate_main_content(self, album_info: Dict[str, Any]) -> str:
        """Generar contenido principal"""
        return f"""
    <main class="album-content">
        <div class="container">
            <nav class="content-nav">
                <ul class="nav-tabs">
                    <li><a href="#comment" class="nav-tab active" data-tab="comment">Comentario</a></li>
                    <li><a href="#lyrics" class="nav-tab" data-tab="lyrics">Letras</a></li>
                    <li><a href="#links" class="nav-tab" data-tab="links">Enlaces</a></li>
                    <li><a href="#tracks" class="nav-tab" data-tab="tracks">Pistas</a></li>
                </ul>
            </nav>

            <div class="tab-content">
                {self._generate_comment_tab(album_info)}
                {self._generate_lyrics_tab(album_info)}
                {self._generate_links_tab(album_info)}
                {self._generate_tracks_tab(album_info)}
            </div>
        </div>
    </main>"""

    def _generate_comment_tab(self, album_info: Dict[str, Any]) -> str:
        """Generar pestaña de comentario"""
        comment = album_info.get('user_comment', '')

        if comment:
            comment_html = html.escape(comment).replace('\n', '<br>')
        else:
            comment_html = '<em>No hay comentario disponible.</em>'

        return f"""
                <section id="comment" class="tab-panel active">
                    <h3>Comentario Personal</h3>
                    <div class="comment-content">
                        <p>{comment_html}</p>
                    </div>
                </section>"""

    def _generate_lyrics_tab(self, album_info: Dict[str, Any]) -> str:
        """Generar pestaña de letras"""
        lyrics_data = album_info.get('lyrics', {})

        if not lyrics_data:
            return """
                <section id="lyrics" class="tab-panel">
                    <h3>Letras de las Canciones</h3>
                    <div class="lyrics-content">
                        <p><em>No se encontraron letras para las canciones de este álbum.</em></p>
                    </div>
                </section>"""

        lyrics_html = []
        tracks = album_info.get('tracks', [])

        for track in tracks:
            track_title = track.get('title', '')
            if track_title in lyrics_data:
                lyrics_info = lyrics_data[track_title]
                lyrics_text = lyrics_info.get('lyrics')

                if lyrics_text:
                    # Formatear letras para HTML
                    formatted_lyrics = html.escape(lyrics_text)
                    formatted_lyrics = formatted_lyrics.replace('\n\n', '</p><p>').replace('\n', '<br>')

                    source = lyrics_info.get('source', '')
                    source_info = f" <small>(Fuente: {html.escape(source)})</small>" if source else ""

                    lyrics_html.append(f"""
                    <div class="lyrics-song">
                        <h4 class="song-title">{html.escape(track_title)}{source_info}</h4>
                        <div class="lyrics-text">
                            <p>{formatted_lyrics}</p>
                        </div>
                    </div>""")
                else:
                    lyrics_html.append(f"""
                    <div class="lyrics-song">
                        <h4 class="song-title">{html.escape(track_title)}</h4>
                        <div class="lyrics-text">
                            <p><em>Letras no disponibles</em></p>
                        </div>
                    </div>""")

        return f"""
                <section id="lyrics" class="tab-panel">
                    <h3>Letras de las Canciones</h3>
                    <div class="lyrics-content">
                        {''.join(lyrics_html)}
                    </div>
                </section>"""

    def _generate_links_tab(self, album_info: Dict[str, Any]) -> str:
        """Generar pestaña de enlaces"""
        links_data = album_info.get('links', {})

        if not links_data:
            return """
                <section id="links" class="tab-panel">
                    <h3>Enlaces Relacionados</h3>
                    <div class="links-content">
                        <p><em>No se encontraron enlaces relacionados.</em></p>
                    </div>
                </section>"""

        links_html = []

        # Categorías de enlaces
        categories = {
            'official': {'name': 'Oficiales', 'icon': '🌐'},
            'streaming': {'name': 'Streaming', 'icon': '🎵'},
            'info': {'name': 'Información', 'icon': '📚'},
            'social': {'name': 'Redes Sociales', 'icon': '📱'},
            'other': {'name': 'Otros', 'icon': '🔗'}
        }

        for category, category_data in categories.items():
            if category in links_data and links_data[category]:
                links_html.append(f"""
                <div class="links-category">
                    <h4 class="category-title">
                        <span class="category-icon">{category_data['icon']}</span>
                        {category_data['name']}
                    </h4>
                    <ul class="links-list">""")

                for link_name, link_info in links_data[category].items():
                    url = link_info.get('url', '#')
                    title = link_info.get('title', link_name)
                    source = link_info.get('source', '')

                    source_badge = f"<span class='source-badge'>{source}</span>" if source else ""

                    links_html.append(f"""
                        <li class="link-item">
                            <a href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">
                                {html.escape(title)}
                            </a>
                            {source_badge}
                        </li>""")

                links_html.append("</ul></div>")

        return f"""
                <section id="links" class="tab-panel">
                    <h3>Enlaces Relacionados</h3>
                    <div class="links-content">
                        {''.join(links_html)}
                    </div>
                </section>"""

    def _generate_tracks_tab(self, album_info: Dict[str, Any]) -> str:
        """Generar pestaña de pistas"""
        tracks = album_info.get('tracks', [])

        if not tracks:
            return """
                <section id="tracks" class="tab-panel">
                    <h3>Lista de Pistas</h3>
                    <div class="tracks-content">
                        <p><em>No se encontraron pistas.</em></p>
                    </div>
                </section>"""

        tracks_html = []

        for track in tracks:
            track_number = track.get('track_number', 0)
            title = track.get('title', 'Pista Sin Título')
            duration = track.get('duration', 0)
            artist = track.get('artist')

            # Formatear duración
            if duration > 0:
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                duration_str = f"{minutes}:{seconds:02d}"
            else:
                duration_str = ""

            # Mostrar artista si es diferente al del álbum
            artist_str = ""
            if artist and artist != album_info.get('artist'):
                artist_str = f" <span class='track-artist'>({html.escape(artist)})</span>"

            tracks_html.append(f"""
            <tr class="track-row">
                <td class="track-number">{track_number if track_number > 0 else ''}</td>
                <td class="track-title">
                    {html.escape(title)}{artist_str}
                </td>
                <td class="track-duration">{duration_str}</td>
            </tr>""")

        return f"""
                <section id="tracks" class="tab-panel">
                    <h3>Lista de Pistas</h3>
                    <div class="tracks-content">
                        <table class="tracks-table">
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Título</th>
                                    <th>Duración</th>
                                </tr>
                            </thead>
                            <tbody>
                                {''.join(tracks_html)}
                            </tbody>
                        </table>
                    </div>
                </section>"""

    def _generate_footer(self, album_info: Dict[str, Any]) -> str:
        """Generar footer"""
        return """
    <footer class="album-footer">
        <div class="container">
            <p>Generado con Album Web Generator</p>
        </div>
    </footer>"""

    def _get_image_url(self, image_info: Dict[str, Any]) -> str:
        """Obtener URL de imagen o placeholder"""
        if image_info and 'url' in image_info:
            return html.escape(image_info['url'])

        # Placeholder por defecto
        return "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300' viewBox='0 0 300 300'%3E%3Crect width='300' height='300' fill='%23ddd'/%3E%3Ctext x='50%25' y='50%25' text-anchor='middle' dy='.3em' font-family='Arial, sans-serif' font-size='18' fill='%23999'%3EImagen%3C/text%3E%3C/svg%3E"

    def _generate_album_colors(self, album_info: Dict[str, Any]) -> Dict[str, str]:
        """
        Generar colores dinámicos para el álbum específico

        Args:
            album_info: Información del álbum

        Returns:
            Diccionario con colores del álbum
        """
        import hashlib
        import colorsys

        # Generar color base a partir del nombre del álbum
        album_hash = hashlib.md5(f"{album_info['artist']}{album_info['title']}".encode()).hexdigest()
        hue = int(album_hash[:2], 16) / 255.0  # Convertir a 0-1

        def hsv_to_hex(h: float, s: float, v: float) -> str:
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

        # Crear colores complementarios
        primary_color = hsv_to_hex(hue, 0.7, 0.8)
        secondary_color = hsv_to_hex((hue + 0.3) % 1.0, 0.5, 0.9)
        accent_color = hsv_to_hex((hue + 0.6) % 1.0, 0.8, 0.7)

        return {
            'primary': primary_color,
            'secondary': secondary_color,
            'accent': accent_color
        }

    def _prepare_safe_data(self, album_info: Dict[str, Any]) -> Dict[str, Any]:
        """Preparar datos seguros para JavaScript"""
        safe_data = {
            'title': album_info.get('title', ''),
            'artist': album_info.get('artist', ''),
            'year': album_info.get('year'),
            'genre': album_info.get('genre', []),
            'total_tracks': album_info.get('total_tracks', 0),
            'tracks_count': len(album_info.get('tracks', [])),
            'has_lyrics': bool(album_info.get('lyrics')),
            'has_comment': bool(album_info.get('user_comment', '').strip()),
            'links_count': sum(len(category) for category in album_info.get('links', {}).values())
        }

        return safe_data
