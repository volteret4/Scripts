#!/usr/bin/env python3
"""
Script para servir los archivos HTML generados mediante un servidor HTTP simple.
Esto es necesario porque YouTube no permite reproducir embeds en archivos file:// locales.

Uso:
    python serve_html.py [--port 8000] [--dir freshrss_embeds]
"""

import http.server
import socketserver
import argparse
import os
import sys

def main():
    parser = argparse.ArgumentParser(
        description='Servidor HTTP simple para visualizar los HTMLs de embeds'
    )
    parser.add_argument('--port', type=int, default=8000,
                       help='Puerto en el que servir (default: 8000)')
    parser.add_argument('--dir', default='freshrss_embeds',
                       help='Directorio a servir (default: freshrss_embeds)')

    args = parser.parse_args()

    # Verificar que el directorio existe
    if not os.path.exists(args.dir):
        print(f"❌ Error: El directorio '{args.dir}' no existe")
        print(f"   Asegúrate de haber generado los HTMLs primero")
        sys.exit(1)

    # Cambiar al directorio
    os.chdir(args.dir)

    # Configurar el servidor
    Handler = http.server.SimpleHTTPRequestHandler

    try:
        with socketserver.TCPServer(("", args.port), Handler) as httpd:
            print("=" * 80)
            print("🌐 SERVIDOR HTTP INICIADO")
            print("=" * 80)
            print(f"Puerto: {args.port}")
            print(f"Directorio: {os.getcwd()}")
            print(f"\n📺 Abre tu navegador en:")
            print(f"   http://localhost:{args.port}")
            print(f"\n💡 IMPORTANTE:")
            print(f"   - Los embeds de YouTube requieren un servidor HTTP")
            print(f"   - NO funcionan con file:// (archivos locales)")
            print(f"   - Usa Ctrl+C para detener el servidor")
            print("=" * 80)
            print("\n🔄 Servidor en ejecución...\n")

            httpd.serve_forever()

    except KeyboardInterrupt:
        print("\n\n🛑 Servidor detenido")
        sys.exit(0)
    except OSError as e:
        if e.errno == 48 or e.errno == 98:  # Address already in use
            print(f"\n❌ Error: El puerto {args.port} ya está en uso")
            print(f"   Prueba con otro puerto: python serve_html.py --port {args.port + 1}")
        else:
            print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
