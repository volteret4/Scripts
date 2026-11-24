import os

# Colores del tema
BACKGROUND_COLOR = "#14141e"
ACCENT_COLOR = "#9a7ecc"

# Directorio donde están los MP3 (usa '.' si está en la misma carpeta)
DIRECTORIO_MP3 = "mp3"  # o "." si están junto al script

def generar_html(lista_mp3):
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Reproductor de música</title>
<style>
    body {{
        background-color: {BACKGROUND_COLOR};
        color: white;
        font-family: 'Arial', sans-serif;
        text-align: center;
        padding: 2rem;
    }}
    h1 {{
        color: {ACCENT_COLOR};
    }}
    audio {{
        width: 80%;
        margin: 1rem 0;
    }}
    .track {{
        background: #1c1c28;
        border: 1px solid {ACCENT_COLOR}33;
        border-radius: 12px;
        margin: 1rem auto;
        padding: 1rem;
        width: 80%;
        max-width: 600px;
        box-shadow: 0 0 10px {ACCENT_COLOR}22;
    }}
    .track:hover {{
        box-shadow: 0 0 20px {ACCENT_COLOR}44;
    }}
    .filename {{
        margin-bottom: 0.5rem;
        font-weight: bold;
    }}
</style>
</head>
<body>
<h1>🎧 Mi colección de música</h1>
<p>Haz clic en reproducir para escuchar.</p>
"""

    for mp3 in lista_mp3:
        html += f"""
<div class="track">
    <div class="filename">{mp3}</div>
    <audio controls>
        <source src="{mp3}" type="audio/mpeg">
        Tu navegador no soporta el elemento de audio.
    </audio>
</div>
"""

    html += """
</body>
</html>"""
    return html


def main():
    mp3s = [f for f in os.listdir(DIRECTORIO_MP3) if f.lower().endswith(".mp3")]
    if not mp3s:
        print("No se encontraron archivos MP3 en el directorio especificado.")
        return

    html = generar_html(mp3s)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ Generado index.html con {len(mp3s)} canciones.")


if __name__ == "__main__":
    main()
