#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import shutil
import configparser
import logging
from pathlib import Path
from datetime import datetime

class MusicWebDeployer:
    def __init__(self, config_file='config.ini'):
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        
        # Configuración de paths - TODO LOCAL
        self.build_dir = Path('./build')
        self.templates_dir = Path('./templates')
        
        # Configuración para referencias (no para crear directorios)
        self.remote_web_root = self.config.get('nginx', 'web_root', fallback='/var/www/html/musica')
        self.server_name = self.config.get('nginx', 'server_name', fallback='localhost')
        
        # Configuración de logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def create_directory_structure(self):
        """Crea la estructura de directorios LOCAL solamente"""
        local_directories = [
            self.build_dir,
            self.build_dir / "static",
            self.build_dir / "static" / "css",
            self.build_dir / "static" / "js", 
            self.build_dir / "static" / "images",
            self.build_dir / "logs"
        ]
        
        for directory in local_directories:
            directory.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Directorio local creado: {directory}")
        
        self.logger.info("Estructura local completada")
        self.logger.info(f"Los archivos se sincronizarán remotamente a: {self.remote_web_root}")
    
    def generate_static_html(self):
        """Genera el HTML estático con las rutas correctas"""
        
        # Verificar que existe el template
        template_path = self.templates_dir / 'index.html'
        if not template_path.exists():
            raise FileNotFoundError(f"Template no encontrado: {template_path}")
        
        # Leer el template original
        with open(template_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Reemplazar las rutas de la API para apuntar a pepecono via Tailscale
        pepecono_url = self.config.get('sync', 'pepecono_url', fallback='100.90.91.96:5157')
        html_content = html_content.replace('/api/', f'http://{pepecono_url}/api/')
        
        # Añadir información de build
        build_info = f"""
    <!-- Build generado automáticamente -->
    <!-- Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->
    <!-- API: {pepecono_url} -->
    <!-- Servidor web: {self.server_name} -->
"""
        html_content = html_content.replace('</head>', f'{build_info}</head>')
        
        # Guardar en build local
        output_path = self.build_dir / 'index.html'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self.logger.info(f"HTML estático generado: {output_path}")
    
    def create_nginx_config(self):
        """Generar configuración de nginx para el servidor web"""
        
        pepecono_url = self.config.get('sync', 'pepecono_url', fallback='100.90.91.96:5157')
        web_server = self.config.get('sync', 'web_server', fallback='192.168.1.180')
        
        nginx_config = f"""# Configuración nginx para Music Web Explorer
# Archivo: /etc/nginx/sites-available/musica
# Generad o: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

server {{
    listen 80;
    server_name {web_server};
    
    # Directorio raíz
    root {self.remote_web_root};
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
    
    # Ruta específica para /musica/
    location /musica/ {{
        alias {self.remote_web_root}/;
        try_files $uri $uri/ /index.html;
    }}
    
    # Proxy para API (pepecono via Tailscale)
    location /api/ {{
        # Proxy a pepecono via Tailscale
        proxy_pass http://{pepecono_url};
        
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
    server_name www.{web_server};
    return 301 http://{web_server}$request_uri;
}}
"""
        
        config_path = self.build_dir / 'nginx_musica.conf'
        with open(config_path, 'w') as f:
            f.write(nginx_config)
        
        self.logger.info(f"Configuración nginx generada: {config_path}")
    
    def create_systemd_service(self):
        """Genera el servicio systemd para Flask"""
        
        current_dir = os.getcwd()
        python_path = shutil.which('python3')
        
        service_content = f"""[Unit]
Description=Music Web Explorer Flask App
After=network.target

[Service]
Type=simple
User=dietpi
Group=www-data
WorkingDirectory={current_dir}
Environment=PATH={os.environ.get('PATH')}
ExecStart={python_path} app.py
Restart=always
RestartSec=10

# Logs
StandardOutput=append:/tmp/music_web_flask.log
StandardError=append:/tmp/music_web_flask_error.log

[Install]
WantedBy=multi-user.target
"""
        
        service_path = self.build_dir / 'music-web.service'
        with open(service_path, 'w') as f:
            f.write(service_content)
        
        self.logger.info(f"Servicio systemd generado: {service_path}")
    
    def create_cron_script(self):
        """Crea script para cron que actualiza la web"""
        
        current_dir = os.getcwd()
        
        cron_script = f"""#!/bin/bash
# Script para actualizar la web de música
# Se ejecuta periódicamente para regenerar y sincronizar contenido

cd {current_dir}

# Logs
LOG_FILE="/tmp/music_web_cron.log"
echo "$(date): Iniciando actualización automática" >> "$LOG_FILE"

# Verificar que el servicio Flask está ejecutándose
if ! systemctl is-active --quiet music-web; then
    echo "$(date): Servicio music-web no activo, intentando iniciar..." >> "$LOG_FILE"
    systemctl start music-web
    if systemctl is-active --quiet music-web; then
        echo "$(date): Servicio music-web iniciado correctamente" >> "$LOG_FILE"
    else
        echo "$(date): ERROR: No se pudo iniciar music-web" >> "$LOG_FILE"
        exit 1
    fi
fi

# Ejecutar sincronización automática
if ./auto_sync.sh >> "$LOG_FILE" 2>&1; then
    echo "$(date): Sincronización completada correctamente" >> "$LOG_FILE"
else
    echo "$(date): ERROR: Falló la sincronización" >> "$LOG_FILE"
    exit 1
fi

echo "$(date): Actualización automática completada" >> "$LOG_FILE"
"""
        
        cron_script_path = self.build_dir / 'update_music_web.sh'
        with open(cron_script_path, 'w') as f:
            f.write(cron_script)
        
        os.chmod(cron_script_path, 0o755)
        
        self.logger.info(f"Script de cron generado: {cron_script_path}")
    
    def create_health_check(self):
        """Crear página de health check"""
        
        pepecono_url = self.config.get('sync', 'pepecono_url', fallback='100.90.91.96:5157')
        web_server = self.config.get('sync', 'web_server', fallback='192.168.1.180')
        
        health_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <title>Music Explorer - Health Check</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 40px; 
            text-align: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: white;
        }}
        .container {{ 
            max-width: 600px; 
            margin: 0 auto; 
            background: rgba(255,255,255,0.1);
            padding: 30px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }}
        .status {{ 
            padding: 20px; 
            margin: 20px 0; 
            border-radius: 10px; 
            font-weight: bold;
        }}
        .loading {{ background: #ffc107; color: #856404; }}
        .ok {{ background: #28a745; color: white; }}
        .error {{ background: #dc3545; color: white; }}
        .info {{ background: rgba(255,255,255,0.2); }}
        h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .timestamp {{ opacity: 0.8; font-size: 0.9em; }}
        .button {{ 
            display: inline-block;
            padding: 12px 24px;
            background: #28a745;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            margin: 10px;
            transition: background 0.3s;
        }}
        .button:hover {{ background: #218838; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 Music Web Explorer</h1>
        <h2>Health Check</h2>
        
        <div id="webStatus" class="status ok">
            ✅ Servidor web: Funcionando
        </div>
        
        <div id="apiStatus" class="status loading">
            🔄 Verificando API...
        </div>
        
        <div id="dbStatus" class="status loading">
            🔄 Verificando base de datos...
        </div>
        
        <div class="info">
            <p><strong>Generado:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>API Server:</strong> {pepecono_url}</p>
            <p><strong>Web Server:</strong> {web_server}</p>
        </div>
        
        <div>
            <a href="/" class="button">🏠 Ir a la Aplicación</a>
            <a href="#" onclick="window.location.reload()" class="button">🔄 Recargar</a>
        </div>
        
        <div id="stats" class="info" style="display: none;">
            <h3>Estadísticas de la Colección</h3>
            <div id="statsContent"></div>
        </div>
    </div>
    
    <script>
        // Verificar API
        fetch('http://{pepecono_url}/api/stats')
            .then(response => response.json())
            .then(data => {{
                document.getElementById('apiStatus').innerHTML = '✅ API: Funcionando';
                document.getElementById('apiStatus').className = 'status ok';
                
                // Mostrar estadísticas
                document.getElementById('statsContent').innerHTML = `
                    <p>📁 Artistas: ${{data.artist_count}}</p>
                    <p>💿 Álbumes: ${{data.album_count}}</p>
                    <p>🎵 Canciones: ${{data.song_count}}</p>
                `;
                document.getElementById('stats').style.display = 'block';
                
                // Verificar base de datos indirectamente
                if (data.artist_count > 0) {{
                    document.getElementById('dbStatus').innerHTML = '✅ Base de datos: Accesible';
                    document.getElementById('dbStatus').className = 'status ok';
                }} else {{
                    document.getElementById('dbStatus').innerHTML = '⚠️ Base de datos: Sin datos';
                    document.getElementById('dbStatus').className = 'status loading';
                }}
            }})
            .catch(error => {{
                document.getElementById('apiStatus').innerHTML = '❌ API: Error - ' + error.message;
                document.getElementById('apiStatus').className = 'status error';
                
                document.getElementById('dbStatus').innerHTML = '❓ Base de datos: No verificable (API offline)';
                document.getElementById('dbStatus').className = 'status error';
                
                console.error('Error:', error);
            }});
    </script>
</body>
</html>"""
        
        health_path = self.build_dir / 'health.html'
        with open(health_path, 'w', encoding='utf-8') as f:
            f.write(health_html)
        
        self.logger.info(f"Health check creado: {health_path}")
    
    def create_deployment_readme(self):
        """Genera documentación de deployment"""
        
        web_server = self.config.get('sync', 'web_server', fallback='192.168.1.180')
        pepecono_url = self.config.get('sync', 'pepecono_url', fallback='100.90.91.96:5157')
        
        readme_content = f"""# Music Web Explorer - Deployment Guide

**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📁 Archivos generados en ./build/

- `index.html` - Interfaz web principal
- `health.html` - Página de verificación de estado
- `nginx_musica.conf` - Configuración de nginx
- `music-web.service` - Servicio systemd para Flask
- `update_music_web.sh` - Script de cron para actualizaciones

## 🚀 Pasos de instalación

### 1️⃣ En el servidor pepecono (Flask API):

```bash
# Instalar dependencias Python
pip3 install -r requirements.txt --user

# Instalar y configurar servicio systemd
sudo cp ./build/music-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable music-web
sudo systemctl start music-web

# Verificar que funciona
sudo systemctl status music-web
curl http://localhost:5157/api/stats
```

### 2️⃣ En el servidor web {web_server}:

#### Opción A: Setup automático
```bash
# Descargar y ejecutar script de setup
wget -O setup_remote.sh [URL_DEL_SCRIPT]
chmod +x setup_remote.sh
sudo ./setup_remote.sh
```

#### Opción B: Manual
```bash
# Crear directorios
sudo mkdir -p {self.remote_web_root}
sudo chown -R www-data:www-data {self.remote_web_root}

# Configurar nginx
sudo cp nginx_musica.conf /etc/nginx/sites-available/musica
sudo ln -sf /etc/nginx/sites-available/musica /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 3️⃣ Sincronización desde pepecono:

```bash
# Sincronización manual
python3 sync_to_webserver.py

# Probar sin cambios
python3 sync_to_webserver.py --dry-run

# Solo generar build local
python3 sync_to_webserver.py --build-only
```

### 4️⃣ Automatización (opcional):

```bash
# Configurar cron para sincronización automática
crontab -e

# Añadir una de estas líneas:
0 * * * * /ruta/completa/auto_sync.sh          # Cada hora
*/30 * * * * /ruta/completa/auto_sync.sh       # Cada 30 minutos
0 */6 * * * /ruta/completa/auto_sync.sh        # Cada 6 horas
```

## 🌐 URLs de acceso

- **Web principal:** http://{web_server}/musica/
- **Health check:** http://{web_server}/musica/health.html
- **API directa:** http://{pepecono_url}/api/stats

## 📊 Verificación

### Comprobar Flask (pepecono):
```bash
curl http://localhost:5157/api/stats
sudo systemctl status music-web
sudo journalctl -u music-web -f
```

### Comprobar nginx (servidor web):
```bash
curl http://{web_server}/musica/
sudo nginx -t
sudo tail -f /var/log/nginx/musica_error.log
```

### Comprobar conectividad Tailscale:
```bash
ping 100.90.91.96
ping {web_server}
tailscale status
```

## 🔧 Troubleshooting

### Error: API no responde
- Verificar que Flask está ejecutándose: `systemctl status music-web`
- Revisar logs: `journalctl -u music-web -f` 
- Verificar puerto: `netstat -tlnp | grep 5157`

### Error: Web no carga
- Verificar nginx: `sudo nginx -t`
- Revisar configuración de sitio: `/etc/nginx/sites-enabled/musica`
- Ver logs nginx: `sudo tail -f /var/log/nginx/musica_error.log`

### Error: Sincronización falla
- Verificar SSH: `ssh www-data@{web_server}`
- Verificar permisos: `ls -la {self.remote_web_root}`
- Ver logs sync: `tail -f /tmp/music_web_sync.log`

### Error: Tailscale no conecta
- Verificar estado: `tailscale status`
- Re-autenticar: `sudo tailscale up`
- Verificar conectividad: `ping 100.90.91.96`

## 📁 Estructura final

```
{self.remote_web_root}/
├── index.html                 # Interfaz web principal
├── health.html                # Health check
├── static/                    # Archivos estáticos (futuro)
├── logs/                      # Logs locales
└── sync_info.json            # Información de última sincronización
```

## 🔄 Comandos útiles

```bash
# En pepecono
./quick_start.sh                           # Menú interactivo
python3 app.py                            # Servidor Flask manual
python3 sync_to_webserver.py              # Sincronizar
python3 music_manager.py stats            # Ver estadísticas
tail -f /tmp/music_web_sync.log           # Ver logs sync

# En servidor web
sudo systemctl status nginx               # Estado nginx
sudo tail -f /var/log/nginx/musica_*.log  # Logs nginx
curl http://localhost/musica/health.html  # Test local
```

---
*Documentación generada automáticamente por Music Web Explorer*
"""
        
        readme_path = self.build_dir / 'README_DEPLOYMENT.md'
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        self.logger.info(f"Documentación generada: {readme_path}")
    
    def create_sync_info(self):
        """Crear archivo de información de build"""
        
        import json
        
        # Obtener lista de archivos generados
        files_generated = []
        if self.build_dir.exists():
            for file_path in self.build_dir.rglob('*'):
                if file_path.is_file():
                    files_generated.append(str(file_path.relative_to(self.build_dir)))
        
        sync_info = {
            'build_date': datetime.now().isoformat(),
            'build_version': '1.0',
            'files_generated': files_generated,
            'config': {
                'web_server': self.config.get('sync', 'web_server', fallback='192.168.1.180'),
                'pepecono_url': self.config.get('sync', 'pepecono_url', fallback='100.90.91.96:5157'),
                'remote_web_root': self.remote_web_root
            },
            'ready_for_sync': True
        }
        
        info_path = self.build_dir / 'build_info.json'
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(sync_info, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Info de build creada: {info_path}")
        return sync_info
    
    def deploy(self):
        """Ejecuta todo el proceso de build LOCAL"""
        self.logger.info("Iniciando build local de Music Web Explorer")
        
        try:
            # 1. Crear estructura local
            self.create_directory_structure()
            
            # 2. Generar archivos
            self.generate_static_html()
            self.generate_nginx_config()
            self.create_systemd_service()
            self.create_cron_script()
            self.create_health_check()
            
            # 3. Crear documentación
            self.create_deployment_readme()
            
            # 4. Crear info de build
            build_info = self.create_sync_info()
            
            # 5. Resumen
            self.logger.info("¡Build completado exitosamente!")
            print(f"\n📦 Build Summary:")
            print(f"   ✅ Archivos generados: {len(build_info['files_generated'])}")
            print(f"   📁 Directorio: {self.build_dir}")
            print(f"   🎯 Destino remoto: {self.remote_web_root}")
            print(f"   🌐 Servidor web: {build_info['config']['web_server']}")
            print(f"   🔗 API: {build_info['config']['pepecono_url']}")
            print(f"\n📋 Próximos pasos:")
            print(f"   1. Revisar: {self.build_dir}/README_DEPLOYMENT.md")
            print(f"   2. Sincronizar: python3 sync_to_webserver.py")
            print(f"   3. Verificar: http://{build_info['config']['web_server']}/musica/")
            
        except Exception as e:
            self.logger.error(f"Error durante el build: {e}")
            raise

if __name__ == '__main__':
    deployer = MusicWebDeployer()
    deployer.deploy()
    
    def create_nginx_config(self):
        """Genera configuración de nginx"""
        nginx_config = f"""
server {{
    listen 80;
    server_name {self.server_name};
    
    root {self.web_root};
    index index.html;
    
    # Servir archivos estáticos
    location / {{
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "public, max-age=3600";
    }}
    
    # Proxy para la API Flask (que corre en el servidor pepecono)
    location /api/ {{
        proxy_pass http://100.90.91.96:5157;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # CORS headers
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
        add_header Access-Control-Allow-Headers "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range";
    }}
    
    # Logs
    access_log {self.web_root}/logs/access.log;
    error_log {self.web_root}/logs/error.log;
}}
"""
        
        nginx_config_path = "./build/nginx_musica.conf"
        with open(nginx_config_path, 'w') as f:
            f.write(nginx_config)
        
        self.logger.info(f"Configuración de nginx generada: {nginx_config_path}")
        self.logger.info("Para activar, copia este archivo a /etc/nginx/sites-available/ y crea un enlace simbólico en sites-enabled/")
    
    def create_systemd_service(self):
        """Genera el servicio systemd para Flask"""
        
        current_dir = os.getcwd()
        python_path = shutil.which('python3')
        
        service_content = f"""[Unit]
Description=Music Web Explorer Flask App
After=network.target

[Service]
Type=simple
User=dietpi
Group=www-data
WorkingDirectory={current_dir}
Environment=PATH={os.environ.get('PATH')}
ExecStart={python_path} app.py
Restart=always
RestartSec=10

# Logs
StandardOutput=append:{self.web_root}/logs/flask.log
StandardError=append:{self.web_root}/logs/flask_error.log

[Install]
WantedBy=multi-user.target
"""
        
        service_file = "./build/music-web.service"
        with open(service_file, 'w') as f:
            f.write(service_content)
        
        self.logger.info(f"Servicio systemd generado: {service_file}")
        self.logger.info("Para instalar: sudo cp music-web.service /etc/systemd/system/ && sudo systemctl enable music-web")
    
    def create_cron_script(self):
        """Crea script para cron que actualiza la web"""
        
        current_dir = os.getcwd()
        python_path = shutil.which('python3')
        
        cron_script = f"""#!/bin/bash
# Script para actualizar la web de música
# Se ejecuta cada hora para regenerar contenido si es necesario

cd {current_dir}

# Verificar si el servicio Flask está ejecutándose
if ! systemctl is-active --quiet music-web; then
    echo "$(date): Iniciando servicio music-web" >> {self.web_root}/logs/cron.log
    systemctl start music-web
fi

# Log de ejecución
echo "$(date): Verificación completada" >> {self.web_root}/logs/cron.log
"""
        
        cron_script_path = "./build/update_music_web.sh"
        with open(cron_script_path, 'w') as f:
            f.write(cron_script)
        
        os.chmod(cron_script_path, 0o755)
        
        self.logger.info(f"Script de cron generado: {cron_script_path}")
        self.logger.info("Para añadir a cron: crontab -e y añadir:")
        self.logger.info(f"0 * * * * {cron_script_path}")
    
    def create_deployment_readme(self):
        """Genera documentación de deployment"""
        
        readme_content = f"""# Deployment de Music Web Explorer

## Archivos generados en ./build/

- `index.html` - Interfaz web principal
- `nginx_musica.conf` - Configuración de nginx
- `music-web.service` - Servicio systemd
- `update_music_web.sh` - Script de cron

## Pasos de instalación

### 1. En el servidor pepecono (Flask API):

```bash
# Instalar dependencias
pip3 install -r requirements.txt --user

# Instalar y habilitar servicio
sudo cp ./build/music-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable music-web
sudo systemctl start music-web

# Verificar que funciona
sudo systemctl status music-web
curl http://localhost:5157/api/stats
```

### 2. En el servidor web 192.168.1.180:

```bash
# Ejecutar como root en 192.168.1.180
wget https://raw.githubusercontent.com/tu-repo/setup_remote.sh
chmod +x setup_remote.sh
sudo ./setup_remote.sh
```

### 3. Sincronizar desde pepecono:

```bash
# En pepecono, ejecutar:
python3 sync_to_webserver.py

# O para probar sin cambios:
python3 sync_to_webserver.py --dry-run
```

### 4. Verificación

- Web: http://{self.server_name}/musica/
- Health: http://{self.server_name}/musica/health.html
- API: http://100.90.91.96:5157/api/stats

## Estructura final

```
/var/www/html/musica/
├── index.html              # Interfaz web
├── health.html             # Health check
├── static/                 # Archivos estáticos
├── logs/                   # Logs del sistema
└── verify.sh               # Script de verificación
```

## Automatización

Para sincronización automática, configura cron en pepecono:

```bash
# Editar crontab
crontab -e

# Añadir (sincronizar cada hora):
0 * * * * /ruta/completa/auto_sync.sh

# O cada 30 minutos:
*/30 * * * * /ruta/completa/auto_sync.sh
```

## Troubleshooting

### Problemas de permisos en servidor web
```bash
sudo chown -R www-data:www-data /var/www/html/musica
sudo chmod -R 755 /var/www/html/musica
```

### Flask no inicia en pepecono
```bash
sudo journalctl -u music-web -f
```

### Nginx errores en servidor web
```bash
sudo tail -f /var/log/nginx/musica_error.log
```

### Tailscale conectividad
```bash
ping 100.90.91.96
tailscale status
```

### Sincronización falla
```bash
# Verificar conectividad SSH
ssh www-data@192.168.1.180

# Ver logs de sync
tail -f /tmp/music_web_sync.log
```

Generado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        readme_path = "./build/README_DEPLOYMENT.md"
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        self.logger.info(f"Documentación generada: {readme_path}")
    
    def deploy(self):
        """Ejecuta todo el proceso de deployment"""
        self.logger.info("Iniciando deployment de Music Web Explorer")
        
        try:
            self.create_directory_structure()
            self.generate_static_html()
            self.create_nginx_config()
            self.create_systemd_service()
            self.create_cron_script()
            self.create_deployment_readme()
            
            self.logger.info("¡Deployment completado exitosamente!")
            self.logger.info(f"Revisa {self.web_root}/README_DEPLOYMENT.md para los siguientes pasos")
            
        except Exception as e:
            self.logger.error(f"Error durante el deployment: {e}")
            raise

if __name__ == '__main__':
    deployer = MusicWebDeployer()
    deployer.deploy()