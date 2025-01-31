import requests
import csv
import re

def get_lastfm_usernames(spreadsheet_id):
    """
    Descarga una hoja de cálculo pública de Google Sheets en formato CSV,
    extrae la segunda columna desde la segunda fila y obtiene los nombres de usuario de Last.fm.
    
    Args:
        spreadsheet_id (str): ID de la hoja de cálculo de Google Sheets.
    
    Returns:
        list: Lista de nombres de usuario extraídos de los enlaces de Last.fm.
    """

    # URL de exportación en formato CSV
    download_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/gviz/tq?tqx=out:csv"

    # Descargar el archivo CSV
    response = requests.get(download_url)
    if response.status_code != 200:
        raise Exception(f"❌ Error al descargar: {response.status_code} - {response.text}")

    # Leer el contenido CSV
    lines = response.text.splitlines()
    reader = csv.reader(lines)
    
    # Omitimos la primera fila (títulos) y extraemos la segunda columna (índice 1)
    links = [row[1] for row in reader if len(row) > 1][1:]

    # Función para extraer el nombre de usuario de Last.fm desde la URL
    def extract_username(url):
        match = re.search(r"/([^/]+)$", url)  # Captura la última parte de la URL
        return match.group(1) if match else None

    # Extraer nombres de usuario
    usernames = [extract_username(link) for link in links if link]

    return usernames
csv_id = "1Oxtg_U6yOJ1zu3IjaML8jcC4Kw-aPypcEBbPhalrZ6"
usernames = get_lastfm_usernames(csv_id)

print(usernames)