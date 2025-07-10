#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import configparser
import logging
import json
from pathlib import Path
from datetime import datetime
import argparse

class WebSyncer:
    def __init__(self, config_file='config.ini'):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        
        # Configuración
        self.web_server = self.config.get('sync', 'web_server', fallback='192.168.1.180')
        self.web_user = self.config.get('sync', 'web_user', fallback='www-data')
        self.web_path = self.config.get('sync', 'web_path', fallback='/var/www/html/musica')
        self.pepecono_url = self.config.get('sync', 'pepecono_url', fallback='100.90.91.96:5157')
        
        # Paths locales
        self.local_web_dir = Path('./web_build')
        self.templates_dir = Path('./templates')
        
        # Logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def create_web_build_directory(self):
        """Crear directorio de build local"""
        self.local_web_dir.mkdir(exist_ok=True)
        (self.local_web_dir / 'static').mkdir(exist_ok=True)
        (self.local_web_dir / 'static' / 'css').mkdir(exist_ok=True)
        (self.local_web_dir / 'static' / 'js').mkdir(exist_ok=True)
        (self.local_web_dir / 'static' / 'images').mkdir(exist_ok=True)
        
        self.logger.info(f"Directorio de build creado: {self.local_web_dir}")
    
    def generate_static_html(self):
        """Generar HTML estático con URLs correctas"""
        
        # Leer template original
        template_path = self.templates_dir / 'index.html'
        if not template_path.exists():
            raise FileNotFoundError(f"Template no encontrado: {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Reemplazar URLs de API para apuntar al servidor pepecono via Tailscale
        html_content = html_content.replace('/api/', f'http://{self.pepecono_url}/api/')
        
        # Añadir información de build
        build_info = f"""
        <!-- Build Info -->
        <!-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->
        <!-- API Server: {self.pepecono_url} -->
        <!-- Web Server: {self.web_server} -->
        """
        
        html_content = html_content.replace('</head>', f'{build_info}</head>')
        
        # Guardar HTML generado
        output_path = self.local_web_dir / 'index.html'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self.logger.info(f"HTML estático generado: {output_path}")
    
    def generate_nginx_config(self):
        """Generar configuración de nginx para el servidor web"""
        
        nginx_config = f"""# Configuración nginx para Music Web Explorer
# Archivo: /etc/nginx/sites-available/musica

server {{
    listen 80;
    server_name {self.web_server};
    
    # Directorio raíz
    root {self.web_path};
    index index.html;
    
    # Logs específicos
    access_log /var/log/nginx/musica_access.log;
    error_log /var/log/nginx/musica_error.log;
    
    # Servir archivos estáticos
    location / {{
        try_files $uri $uri/ /index.html;
        
        # Headers de cache para archivos estáticos
        location ~* \.(css|js|png|jpg|jpeg|gif|ico|svg)$ {{
            expires 1y;
            add_header Cache-Control "public, immutable";
        }}
        
        # No cache para HTML
        location ~* \.html$ {{
            add_header Cache-Control "no-cache, no-store, must-revalidate";
            add_header Pragma "no-cache";
            add_header Expires "0";
        }}
    }}
    
    # Proxy para API (pepecono via Tailscale)
    location /api/ {{
        # Proxy a pepecono via Tailscale
        proxy_pass http://{self.pepecono_url};
        
        # Headers necesarios
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # CORS para permitir acceso desde el navegador
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS, PUT, DELETE";
        add_header Access-Control-Allow-Headers "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization";
        
        # Manejar OPTIONS requests
        if ($request_method = 'OPTIONS') {{
            add_header Access-Control-Allow-Origin *;
            add_header Access-Control-Allow-Methods "GET, POST, OPTIONS, PUT, DELETE";
            add_header Access-Control-Allow-Headers "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization";
            add_header Access-Control-Max-Age 1728000;
            add_header Content-Type 'text/plain; charset=utf-8';
            add_header Content-Length 0;
            return 204;
        }}
        
        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }}
    
    # Ruta específica para /musica/
    location /musica/ {{
        alias {self.web_path}/;
        try_files $uri $uri/ /index.html;
    }}
    
    # Bloquear acceso a archivos sensibles
    location ~ /\.(ht|git) {{
        deny all;
    }}
    
    # Comprimir respuestas
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;
}}

# Redirección opcional de www
server {{
    listen 80;
    server_name www.{self.web_server};
    return 301 http://{self.web_server}$request_uri;
}}
"""
        
        config_path = self.local_web_dir / 'nginx_musica.conf'
        with open(config_path, 'w') as f:
            f.write(nginx_config)
        
        self.logger.info(f"Configuración nginx generada: {config_path}")
    
    def create_health_check(self):
        """Crear página de health check"""
        
        health_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Music Explorer - Health Check</title>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; text-align: center; }}
        .status {{ padding: 20px; margin: 20px; border-radius: 10px; }}
        .ok {{ background: #d4edda; color: #155724; }}
        .error {{ background: #f8d7da; color: #721c24; }}
    </style>
</head>
<body>
    <h1>🎵 Music Web Explorer</h1>
    <h2>Health Check</h2>
    
    <div id="webStatus" class="status">
        ✅ Servidor web: OK
    </div>
    
    <div id="apiStatus" class="status">
        🔄 Verificando API...
    </div>
    
    <p>Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p>API: {self.pepecono_url}</p>
    <p><a href="/">Ir a la aplicación</a></p>
    
    <script>
        // Verificar API
        fetch('http://{self.pepecono_url}/api/stats')
            .then(response => response.json())
            .then(data => {{
                document.getElementById('apiStatus').innerHTML = '✅ API: OK (' + data.artist_count + ' artistas)';
                document.getElementById('apiStatus').className = 'status ok';
            }})
            .catch(error => {{
                document.getElementById('apiStatus').innerHTML = '❌ API: Error - ' + error.message;
                document.getElementById('apiStatus').className = 'status error';
            }});
    </script>
</body>
</html>"""
        
        health_path = self.local_web_dir / 'health.html'
        with open(health_path, 'w', encoding='utf-8') as f:
            f.write(health_html)
        
        self.logger.info(f"Health check creado: {health_path}")
    
    def create_sync_info(self):
        """Crear archivo de información de sincronización"""
        
        sync_info = {
            'last_sync': datetime.now().isoformat(),
            'web_server': self.web_server,
            'api_server': self.pepecono_url,
            'sync_user': os.getenv('USER', 'unknown'),
            'files_synced': [],
            'version': '1.0'
        }
        
        # Lista de archivos que se van a sincronizar
        for file_path in self.local_web_dir.rglob('*'):
            if file_path.is_file():
                sync_info['files_synced'].append(str(file_path.relative_to(self.local_web_dir)))
        
        info_path = self.local_web_dir / 'sync_info.json'
        with open(info_path, 'w') as f:
            json.dump(sync_info, f, indent=2)
        
        self.logger.info(f"Info de sync creada: {info_path}")
        return sync_info
    
    def create_installation_script(self):
        """Crear script de instalación para el servidor web"""
        
        install_script = f"""#!/bin/bash
# Script de instalación en servidor web {self.web_server}
# Ejecutar como root o con sudo

set -e

echo "=== Instalando Music Web Explorer en {self.web_server} ==="

# Crear directorio web
mkdir -p {self.web_path}
chown -R {self.web_user}:{self.web_user} {self.web_path}

# Copiar configuración nginx
if [ -f "nginx_musica.conf" ]; then
    cp nginx_musica.conf /etc/nginx/sites-available/musica
    
    # Habilitar sitio
    ln -sf /etc/nginx/sites-available/musica /etc/nginx/sites-enabled/
    
    # Probar configuración
    nginx -t
    
    if [ $? -eq 0 ]; then
        systemctl reload nginx
        echo "✅ Nginx configurado y recargado"
    else
        echo "❌ Error en configuración nginx"
        exit 1
    fi
else
    echo "⚠️  nginx_musica.conf no encontrado"
fi

# Verificar que Tailscale puede alcanzar pepecono
if ping -c 1 100.90.91.96 >/dev/null 2>&1; then
    echo "✅ 100.90.91.96 es alcanzable"
else
    echo "❌ 100.90.91.96 NO es alcanzable"
    echo "Verifica la configuración de Tailscale"
fi

echo "🎵 Instalación completada"
echo "Accede a: http://{self.web_server}/musica/"
echo "Health check: http://{self.web_server}/musica/health.html"
"""
        
        script_path = self.local_web_dir / 'install_on_webserver.sh'
        with open(script_path, 'w') as f:
            f.write(install_script)
        
        os.chmod(script_path, 0o755)
        self.logger.info(f"Script de instalación creado: {script_path}")
    
    def sync_to_server(self, dry_run=False):
        """Sincronizar archivos al servidor web usando rsync"""
        
        rsync_cmd = [
            'rsync',
            '-avz',
            '--delete',
            '--progress',
            '--human-readable'
        ]
        
        if dry_run:
            rsync_cmd.append('--dry-run')
            self.logger.info("Ejecutando dry-run (no se copiarán archivos)")
        
        # Fuente: directorio local build
        source = f"{self.local_web_dir}/"
        
        # Destino: servidor web
        destination = f"{self.web_user}@{self.web_server}:{self.web_path}/"
        
        rsync_cmd.extend([source, destination])
        
        self.logger.info(f"Ejecutando: {' '.join(rsync_cmd)}")
        
        try:
            result = subprocess.run(rsync_cmd, check=True, capture_output=True, text=True)
            
            if dry_run:
                self.logger.info("Dry-run completado:")
                print(result.stdout)
            else:
                self.logger.info("Sincronización completada exitosamente")
                if result.stdout:
                    print("Archivos sincronizados:")
                    print(result.stdout)
        
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error en rsync: {e}")
            if e.stderr:
                print(f"Error: {e.stderr}")
            raise
    
    def build_and_sync(self, dry_run=False):
        """Proceso completo: build y sincronización"""
        
        self.logger.info("Iniciando build y sincronización...")
        
        try:
            # 1. Crear directorio de build
            self.create_web_build_directory()
            
            # 2. Generar archivos
            self.generate_static_html()
            self.generate_nginx_config()
            self.create_health_check()
            self.create_installation_script()
            
            # 3. Crear info de sync
            sync_info = self.create_sync_info()
            
            # 4. Mostrar resumen
            print(f"\n📦 Build completado:")
            print(f"   - Archivos generados: {len(sync_info['files_synced'])}")
            print(f"   - Destino: {self.web_user}@{self.web_server}:{self.web_path}")
            print(f"   - API: {self.pepecono_url}")
            
            # 5. Sincronizar
            print(f"\n🔄 Sincronizando...")
            self.sync_to_server(dry_run)
            
            if not dry_run:
                print(f"\n✅ Sincronización completada")
                print(f"🌐 Web disponible en: http://{self.web_server}/musica/")
                print(f"🏥 Health check: http://{self.web_server}/musica/health.html")
                print(f"\n📋 Para completar la instalación en {self.web_server}:")
                print(f"   1. ssh {self.web_user}@{self.web_server}")
                print(f"   2. cd {self.web_path}")
                print(f"   3. sudo ./install_on_webserver.sh")
        
        except Exception as e:
            self.logger.error(f"Error en build y sync: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description='Sincronizar Music Web a servidor remoto')
    parser.add_argument('--config', default='config.ini', help='Archivo de configuración')
    parser.add_argument('--dry-run', action='store_true', help='Solo mostrar qué se sincronizaría')
    parser.add_argument('--build-only', action='store_true', help='Solo hacer build, no sincronizar')
    
    args = parser.parse_args()
    
    try:
        syncer = WebSyncer(args.config)
        
        if args.build_only:
            syncer.create_web_build_directory()
            syncer.generate_static_html()
            syncer.generate_nginx_config()
            syncer.create_health_check()
            syncer.create_installation_script()
            syncer.create_sync_info()
            print("✅ Build completado. Archivos en ./web_build/")
        else:
            syncer.build_and_sync(args.dry_run)
    
    except Exception as e:
        print(f"❌ Error: {e}")
        exit(1)

if __name__ == '__main__':
    main()