#!/home/huan/Scripts/python_venv/bin/python
# -*- coding: utf-8 -*-
#
# Script Name: music_control.py
# Description: Control unificado de reproducción para DeaDBeeF y Airsonic
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Dependencies: - python3, requests, subprocess, dotenv
#                - deadbeef reproductor (opcional)
#                - airsonic-advanced server (opcional)
#
# Uso:
#   music_control.py play      - Toggle play/pause
#   music_control.py next      - Siguiente canción
#   music_control.py prev      - Canción anterior
#   music_control.py seek-f    - Avanzar 10 segundos
#   music_control.py seek-b    - Retroceder 10 segundos

import os
import sys
import subprocess
import requests
import hashlib
import secrets
from sops_env import load_sops_env

load_sops_env()


class MusicController:
    def __init__(self):
        # Configuración de Airsonic-Advanced
        self.airsonic_url = os.getenv('AIRSONIC_URL', 'http://localhost:4040')
        self.airsonic_user = os.getenv('AIRSONIC_USER')
        self.airsonic_password = os.getenv('AIRSONIC_PASSWORD')
        self.airsonic_client = os.getenv('AIRSONIC_CLIENT', 'music-control-script')
        self.airsonic_use_plain = os.getenv('AIRSONIC_USE_PLAIN_PASSWORD', 'true').lower() == 'true'

    def is_deadbeef_playing(self):
        """Verifica si DeaDBeeF está reproduciendo actualmente"""
        try:
            result = subprocess.run(
                ['deadbeef', '--nowplaying', '%a'],
                capture_output=True,
                text=True,
                timeout=1
            )

            if result.returncode != 0:
                return False

            output = result.stdout.strip()
            # Si DeaDBeeF devuelve algo que no sea vacío o "nothing", está reproduciendo
            if output and 'nothing' not in output.lower():
                return True
            return False

        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return False

    def control_deadbeef(self, action):
        """Envía comandos de control a DeaDBeeF"""
        commands = {
            'play': ['deadbeef', '--play-pause'],
            'next': ['deadbeef', '--next'],
            'prev': ['deadbeef', '--prev'],
            'seek-f': ['deadbeef', '--seek', '+10'],
            'seek-b': ['deadbeef', '--seek', '-10']
        }

        if action not in commands:
            print(f"❌ Acción desconocida: {action}", file=sys.stderr)
            return False

        try:
            result = subprocess.run(commands[action], capture_output=True, timeout=2)
            if result.returncode == 0:
                print(f"✅ [DeaDBeeF] Ejecutado: {action}")
                return True
            else:
                print(f"❌ [DeaDBeeF] Error ejecutando: {action}", file=sys.stderr)
                return False
        except Exception as e:
            print(f"❌ [DeaDBeeF] Excepción: {e}", file=sys.stderr)
            return False

    def get_airsonic_auth_params(self):
        """Genera parámetros de autenticación para Airsonic"""
        params = {
            'u': self.airsonic_user,
            'c': self.airsonic_client,
            'f': 'json',
            'v': '1.16.1'
        }

        if self.airsonic_use_plain:
            params['p'] = self.airsonic_password
        else:
            salt = secrets.token_hex(16)
            token = hashlib.md5((self.airsonic_password + salt).encode()).hexdigest()
            params['t'] = token
            params['s'] = salt

        return params

    def get_airsonic_now_playing(self):
        """Obtiene información de la reproducción actual en Airsonic"""
        try:
            params = self.get_airsonic_auth_params()
            response = requests.get(
                f"{self.airsonic_url}/rest/getNowPlaying",
                params=params,
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('subsonic-response', {}).get('status') == 'ok':
                    entries = data.get('subsonic-response', {}).get('nowPlaying', {}).get('entry', [])
                    if entries:
                        return entries[0]  # Devolver la primera entrada
            return None
        except Exception as e:
            print(f"❌ [Airsonic] Error obteniendo reproducción actual: {e}", file=sys.stderr)
            return None

    def control_airsonic(self, action):
        """
        Envía comandos de control a Airsonic.

        NOTA: La API de Subsonic/Airsonic es principalmente para streaming y gestión,
        no tiene endpoints completos para control de reproducción remota.
        Solo funcionarán algunas acciones básicas.
        """
        # Primero verificar que hay algo reproduciéndose
        now_playing = self.get_airsonic_now_playing()

        if not now_playing and action in ['next', 'prev', 'seek-f', 'seek-b']:
            print("⚠️  [Airsonic] No hay reproducción activa", file=sys.stderr)
            return False

        try:
            params = self.get_airsonic_auth_params()

            # La API de Airsonic/Subsonic no tiene endpoints estándar para play/pause/next/prev
            # como reproductor remoto. Estas funciones son principalmente del lado del cliente.

            if action == 'play':
                # No hay endpoint directo para play/pause en Airsonic
                # Podríamos hacer scrobble para "simular" que se está reproduciendo
                print("⚠️  [Airsonic] Play/Pause no soportado directamente por la API")
                print("    La API de Airsonic es para streaming, no para control remoto")
                return False

            elif action == 'next':
                print("⚠️  [Airsonic] Next no soportado directamente por la API")
                print("    Usa el cliente web o la app para controlar la reproducción")
                return False

            elif action == 'prev':
                print("⚠️  [Airsonic] Previous no soportado directamente por la API")
                print("    Usa el cliente web o la app para controlar la reproducción")
                return False

            elif action in ['seek-f', 'seek-b']:
                print("⚠️  [Airsonic] Seek no soportado directamente por la API")
                print("    Usa el cliente web o la app para controlar la reproducción")
                return False

            else:
                print(f"❌ Acción desconocida: {action}", file=sys.stderr)
                return False

        except Exception as e:
            print(f"❌ [Airsonic] Error: {e}", file=sys.stderr)
            return False

    def execute_action(self, action):
        """
        Ejecuta la acción solicitada.
        Primero intenta con DeaDBeeF, si no está disponible intenta con Airsonic.
        """
        print(f"🎵 Ejecutando acción: {action}")

        # Verificar si DeaDBeeF está reproduciendo
        if self.is_deadbeef_playing():
            print("🎵 DeaDBeeF está reproduciendo, usando DeaDBeeF...")
            return self.control_deadbeef(action)
        else:
            print("☁️  DeaDBeeF no está reproduciendo, intentando con Airsonic...")
            return self.control_airsonic(action)


def show_usage():
    """Muestra información de uso del script"""
    print("Uso: music_control.py <acción>")
    print("\nAcciones disponibles:")
    print("  play      - Toggle play/pause")
    print("  next      - Siguiente canción")
    print("  prev      - Canción anterior")
    print("  seek-f    - Avanzar 10 segundos")
    print("  seek-b    - Retroceder 10 segundos")
    print("\nEjemplos:")
    print("  music_control.py play")
    print("  music_control.py next")
    print("  music_control.py seek-f")


def main():
    """Función principal"""
    # Validar argumentos
    if len(sys.argv) != 2:
        show_usage()
        sys.exit(1)

    action = sys.argv[1].lower()

    # Validar acción
    valid_actions = ['play', 'next', 'prev', 'seek-f', 'seek-b']
    if action not in valid_actions:
        print(f"❌ Acción inválida: {action}", file=sys.stderr)
        show_usage()
        sys.exit(1)

    # Ejecutar
    controller = MusicController()
    success = controller.execute_action(action)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
