#!/usr/bin/env python3
"""
Script para importar eventos de archivos .ics a un servidor Radicale
Usa un archivo JSON para configurar múltiples calendarios
"""

import json
import sys
import os
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth
from icalendar import Calendar
import uuid


def cargar_configuracion(archivo_config):
    """Carga la configuración desde el archivo JSON"""
    try:
        with open(archivo_config, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: No se encuentra el archivo {archivo_config}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error al parsear JSON: {e}")
        sys.exit(1)


def parsear_ics(archivo_ics):
    """Lee y parsea un archivo ICS, devuelve lista de eventos"""
    try:
        with open(archivo_ics, 'rb') as f:
            cal = Calendar.from_ical(f.read())

        eventos = []
        for component in cal.walk():
            if component.name == "VEVENT":
                eventos.append(component)

        return eventos
    except FileNotFoundError:
        print(f"❌ Error: No se encuentra el archivo {archivo_ics}")
        return []
    except Exception as e:
        print(f"❌ Error al parsear {archivo_ics}: {e}")
        return []


def crear_evento_ical(evento):
    """Crea un calendario iCalendar completo con un solo evento"""
    cal = Calendar()
    cal.add('prodid', '-//Importador Radicale//ES')
    cal.add('version', '2.0')
    cal.add_component(evento)
    return cal.to_ical()


def subir_evento_radicale(evento, url_base, auth, evento_num=None):
    """Sube un evento individual a Radicale"""
    # Obtener UID del evento o generar uno nuevo
    uid = evento.get('uid')
    if not uid:
        uid = str(uuid.uuid4())
        evento.add('uid', uid)

    # Asegurarse de que la URL termine con /
    if not url_base.endswith('/'):
        url_base += '/'

    # Construir URL del evento (UID.ics)
    url_evento = f"{url_base}{uid}.ics"

    # Crear calendario con este evento
    ical_data = crear_evento_ical(evento)

    # Headers para CalDAV
    headers = {
        'Content-Type': 'text/calendar; charset=utf-8',
    }

    try:
        # PUT request para subir el evento
        response = requests.put(
            url_evento,
            data=ical_data,
            auth=auth,
            headers=headers,
            timeout=10
        )

        if response.status_code in [200, 201, 204]:
            resumen = evento.get('summary', 'Sin título')
            print(f"  ✅ Evento subido: {resumen} (UID: {uid})")
            return True
        else:
            print(f"  ❌ Error al subir evento (HTTP {response.status_code}): {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error de conexión: {e}")
        return False


def importar_calendario(calendario_config, credenciales):
    """Importa todos los eventos de un calendario"""
    nombre = calendario_config['nombre']
    archivo_ics = calendario_config['archivo_ics']
    url_radicale = calendario_config['url_radicale']

    print(f"\n📅 Procesando: {nombre}")
    print(f"   Archivo: {archivo_ics}")
    print(f"   URL: {url_radicale}")

    # Verificar que existe el archivo
    if not os.path.exists(archivo_ics):
        print(f"   ❌ El archivo {archivo_ics} no existe")
        return 0

    # Parsear eventos
    eventos = parsear_ics(archivo_ics)
    if not eventos:
        print(f"   ⚠️  No se encontraron eventos en {archivo_ics}")
        return 0

    print(f"   📋 Encontrados {len(eventos)} eventos")

    # Crear autenticación
    auth = HTTPBasicAuth(credenciales['usuario'], credenciales['password'])

    # Subir cada evento
    exitosos = 0
    for i, evento in enumerate(eventos, 1):
        if subir_evento_radicale(evento, url_radicale, auth, i):
            exitosos += 1

    print(f"   ✨ Importados {exitosos}/{len(eventos)} eventos")
    return exitosos


def main():
    """Función principal"""
    # Archivo de configuración
    archivo_config = 'calendarios_config.json'

    # Verificar si se pasó un archivo de configuración como argumento
    if len(sys.argv) > 1:
        archivo_config = sys.argv[1]

    print("=" * 60)
    print("📥 IMPORTADOR DE CALENDARIOS A RADICALE")
    print("=" * 60)

    # Cargar configuración
    config = cargar_configuracion(archivo_config)

    # Obtener credenciales
    if 'credenciales' not in config:
        print("❌ Error: No se encontraron credenciales en la configuración")
        sys.exit(1)

    credenciales = config['credenciales']

    # Procesar cada calendario
    total_importados = 0
    for calendario in config.get('calendarios', []):
        exitosos = importar_calendario(calendario, credenciales)
        total_importados += exitosos

    print("\n" + "=" * 60)
    print(f"🎉 FINALIZADO - Total de eventos importados: {total_importados}")
    print("=" * 60)


if __name__ == '__main__':
    main()
