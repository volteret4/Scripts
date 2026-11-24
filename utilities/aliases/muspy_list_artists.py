#!/usr/bin/env python3
"""
Exporta los artistas seguidos en muspy.com a un archivo artists.txt
Uso: python muspy_export.py
"""

import os
import requests
import sys

# ── Configuración ──────────────────────────────────────────────
MUSPY_USER_ID = "rvy1q943dvxvelrwvmmnxzk6ownko6"   # Tu user ID o nombre de usuario de muspy
MUSPY_EMAIL   = "frodobolson@disroot.org" # Email de tu cuenta
_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")  # ignorado por git
MUSPY_PASS    = os.environ.get("MUSPY_PASS") or next((l.split("=", 1)[1].strip() for l in open(_ENV) if l.startswith("MUSPY_PASS=")), "")
OUTPUT_FILE   = "/home/huan/Scripts/.content/muspy_artists.txt"
# ───────────────────────────────────────────────────────────────

API_URL = f"https://muspy.com/api/1/artists/{MUSPY_USER_ID}"

def fetch_artists():
    print(f"Conectando a muspy.com para el usuario '{MUSPY_USER_ID}'...")

    response = requests.get(
        API_URL,
        auth=(MUSPY_EMAIL, MUSPY_PASS),
        headers={"Accept": "application/json"},
        timeout=30
    )

    if response.status_code == 401:
        print("Error: Credenciales incorrectas. Revisa email y contraseña.")
        sys.exit(1)
    elif response.status_code == 404:
        print("Error: Usuario no encontrado. Revisa MUSPY_USER_ID.")
        sys.exit(1)
    elif response.status_code != 200:
        print(f"Error inesperado: HTTP {response.status_code}")
        print(response.text)
        sys.exit(1)

    artists = response.json()
    print(f"Se encontraron {len(artists)} artistas.")
    return artists

def save_artists(artists):
    # Ordenar por nombre (ignorando mayúsculas)
    artists_sorted = sorted(artists, key=lambda a: a.get("name", "").lower())

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for artist in artists_sorted:
            name = artist.get("name", "").strip()
            if name:
                f.write(name + "\n")

    print(f"Artistas guardados en '{OUTPUT_FILE}'.")

def main():
    artists = fetch_artists()
    save_artists(artists)

if __name__ == "__main__":
    main()
