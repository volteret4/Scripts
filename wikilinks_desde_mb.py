import requests
import sqlite3
import sys
import time

DB_PATH = "tu_base_de_datos.sqlite"  # Ruta a la base de datos
HEADERS = {"User-Agent": "MusicWikiFetcher/1.0 (contact@example.com)"}  # Cambia el correo si es necesario

def get_musicbrainz_wikidata(artist_name):
    """Busca el ID de MusicBrainz y obtiene el enlace de Wikidata."""
    url = f"https://musicbrainz.org/ws/2/artist/?query=artist:{artist_name}&fmt=json"
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        data = response.json()
        if data.get("artists"):
            artist_id = data["artists"][0]["id"]
            url = f"https://musicbrainz.org/ws/2/artist/{artist_id}?inc=url-rels&fmt=json"
            response = requests.get(url, headers=HEADERS)

            if response.status_code == 200:
                artist_data = response.json()
                for rel in artist_data.get("relations", []):
                    if rel["type"] == "wikidata":
                        return rel["url"]["resource"]
    return None

def get_wikipedia_from_wikidata(wikidata_url):
    """Busca en Wikidata si hay un enlace a Wikipedia en español o inglés."""
    wikidata_id = wikidata_url.split("/")[-1]
    url = f"https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbgetentities",
        "ids": wikidata_id,
        "format": "json",
        "props": "sitelinks"
    }
    response = requests.get(url, params=params, headers=HEADERS)

    if response.status_code == 200:
        data = response.json()
        sitelinks = data["entities"].get(wikidata_id, {}).get("sitelinks", {})

        # Prioridad: Wikipedia en español, luego en inglés
        if "eswiki" in sitelinks:
            return sitelinks["eswiki"]["url"]
        elif "enwiki" in sitelinks:
            return sitelinks["enwiki"]["url"]

    return None

def get_artists_without_links():
    """Obtiene artistas sin enlace de Wikipedia en la base de datos."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM artists WHERE mbid IS NULL OR mbid = '' ORDER BY id")
        return cursor.fetchall()

def update_artist_wikipedia(artist_id, wikipedia_url):
    """Actualiza el enlace de Wikipedia en la columna bio de la base de datos."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE artists SET bio = ? WHERE id = ?", (wikipedia_url, artist_id))
        conn.commit()

def main():
    artists = get_artists_without_links()
    if not artists:
        print("No hay artistas pendientes.")
        return

    for artist_id, artist_name in artists:
        print(f"\n🔎 Buscando para: {artist_name}")

        # 1. Obtener Wikidata desde MusicBrainz
        wikidata_url = get_musicbrainz_wikidata(artist_name)
        if not wikidata_url:
            print(f"❌ No se encontró Wikidata para {artist_name}")
            continue

        # 2. Obtener Wikipedia desde Wikidata
        wikipedia_url = get_wikipedia_from_wikidata(wikidata_url)
        if not wikipedia_url:
            print(f"❌ No se encontró Wikipedia para {artist_name}")
            continue

        # 3. Confirmar con el usuario antes de guardar
        print(f"✅ Wikipedia encontrada: {wikipedia_url}")
        confirm = input("¿Quieres guardar este enlace? (s/n) [S]: ").strip().lower() or "s"
        if confirm == "s":
            update_artist_wikipedia(artist_id, wikipedia_url)
            print("✅ Guardado en la base de datos.")
        else:
            log_skipped_artist(artist_name, wikipedia_url)
            print("⏭️ Saltado.")

        # Pequeña pausa para evitar bloqueos por exceso de peticiones
        time.sleep(1)

def log_skipped_artist(artist_name, wikipedia_url):
    """Registra los artistas saltados en un archivo de log."""
    with open("artistas_saltados.log", "a", encoding="utf-8") as log_file:
        log_file.write(f"{artist_name} - {wikipedia_url}\n")


if __name__ == "__main__":
    main()
