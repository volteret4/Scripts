#!/usr/bin/env python3
"""
Script para generar configuraciones de nginx a partir de un archivo JSON
"""

import json
import os
import sys
from pathlib import Path


def load_config(config_file):
    """Carga la configuración desde el archivo JSON"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: No se encontró el archivo {config_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error al parsear JSON: {e}")
        sys.exit(1)


def generate_nginx_config(app, config):
    """Genera la configuración de nginx para una aplicación"""

    subdomain = app['subdomain']
    backend = app['backend']
    domain = config['domain']
    full_domain = f"{subdomain}.{domain}"

    # Configuración básica
    nginx_config = f"""# Configuración para {app['name']}
server {{
    listen 80;
    server_name {full_domain};

    # Redirigir todo el tráfico HTTP a HTTPS
    return 301 https://$server_name$request_uri;
}}

server {{
    listen 443 ssl http2;
    server_name {full_domain};

    # Certificados SSL wildcard
    ssl_certificate {config['ssl_certificate']};
    ssl_certificate_key {config['ssl_certificate_key']};

    # Configuración SSL moderna
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Headers de seguridad
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

"""

    # Client max body size si está especificado
    if 'client_max_body_size' in app:
        nginx_config += f"    client_max_body_size {app['client_max_body_size']};\n"
    else:
        nginx_config += "    client_max_body_size 100M;\n"

    nginx_config += f"""
    # Configuración del proxy
    location / {{
        proxy_pass http://{backend};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
"""

    # Configuración WebSocket si está habilitada
    if app.get('websocket', False):
        nginx_config += """
        # Soporte para WebSocket
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
"""

    nginx_config += """    }

    # Logs específicos para esta aplicación
    access_log /var/log/nginx/""" + app['name'] + """_access.log;
    error_log /var/log/nginx/""" + app['name'] + """_error.log;
}
"""

    return nginx_config


def main():
    """Función principal"""

    # Parsear argumentos
    if len(sys.argv) < 2:
        print("Uso: python3 generate_nginx_configs.py <archivo-json> [directorio-salida]")
        print("\nEjemplo:")
        print("  python3 generate_nginx_configs.py apps-config.json")
        print("  python3 generate_nginx_configs.py apps-config.json /etc/nginx/sites-available")
        sys.exit(1)

    config_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./nginx-configs"

    # Cargar configuración
    config = load_config(config_file)

    # Crear directorio de salida si no existe
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print(f"🚀 Generando configuraciones de nginx...")
    print(f"📁 Directorio de salida: {output_dir}")
    print(f"🌐 Dominio base: {config['domain']}")
    print(f"🔒 Certificado SSL: {config['ssl_certificate']}")
    print()

    # Generar configuración para cada aplicación
    generated_files = []
    for app in config['apps']:
        nginx_config = generate_nginx_config(app, config)

        # Nombre del archivo
        filename = f"{app['name']}.conf"
        filepath = os.path.join(output_dir, filename)

        # Escribir archivo
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(nginx_config)

        generated_files.append(filepath)
        subdomain = f"{app['subdomain']}.{config['domain']}"
        print(f"✅ {app['name']:20} -> {subdomain:40} -> {app['backend']}")

    print()
    print(f"✨ Se generaron {len(generated_files)} archivos de configuración")
    print()
    print("📋 Próximos pasos:")
    print(f"   1. Revisar los archivos generados en: {output_dir}")

    if output_dir != "/etc/nginx/sites-available":
        print(f"   2. Copiar los archivos a nginx:")
        print(f"      sudo cp {output_dir}/*.conf /etc/nginx/sites-available/")
        print(f"   3. Crear enlaces simbólicos:")
        print(f"      cd /etc/nginx/sites-enabled")
        for app in config['apps']:
            print(f"      sudo ln -sf ../sites-available/{app['name']}.conf .")
    else:
        print(f"   2. Crear enlaces simbólicos en sites-enabled:")
        print(f"      cd /etc/nginx/sites-enabled")
        for app in config['apps']:
            print(f"      sudo ln -sf ../sites-available/{app['name']}.conf .")

    print(f"   4. Verificar la configuración:")
    print(f"      sudo nginx -t")
    print(f"   5. Recargar nginx:")
    print(f"      sudo systemctl reload nginx")
    print()


if __name__ == "__main__":
    main()
