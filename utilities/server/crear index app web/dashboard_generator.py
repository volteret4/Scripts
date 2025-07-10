#!/usr/bin/env python3
"""
Dashboard Generator - Detecta apps corriendo y genera página web
"""

import json
import socket
import subprocess
import requests
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_active_interface() -> str:
    """Detecta la interfaz de red activa"""
    try:
        # Obtener la interfaz de la ruta por defecto
        result = subprocess.run([
            'ip', 'route', 'show', 'default'
        ], capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            import re
            match = re.search(r'dev\s+(\w+)', result.stdout)
            if match:
                interface = match.group(1)
                logger.info(f"Interfaz activa detectada: {interface}")
                return interface
    except Exception:
        pass
    
    return None

def get_local_ip() -> str:
    """Obtiene la IP local de la máquina"""
    try:
        # Método 1: Detectar interfaz activa y usar esa
        active_interface = get_active_interface()
        if active_interface:
            try:
                result = subprocess.run([
                    'ip', '-4', 'addr', 'show', active_interface
                ], capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0:
                    import re
                    match = re.search(r'inet\s+(\d+(?:\.\d+){3})', result.stdout)
                    if match:
                        local_ip = match.group(1)
                        logger.info(f"IP local detectada desde {active_interface}: {local_ip}")
                        return local_ip
            except Exception:
                pass
        
        # Método 2: Probar interfaces comunes
        interfaces = ['eth0', 'enp1s0', 'ens18', 'ens33', 'wlan0', 'wlp2s0', 'enp2s0', 'eno1']
        
        for interface in interfaces:
            try:
                result = subprocess.run([
                    'ip', '-4', 'addr', 'show', interface
                ], capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0:
                    import re
                    match = re.search(r'inet\s+(\d+(?:\.\d+){3})', result.stdout)
                    if match:
                        local_ip = match.group(1)
                        logger.info(f"IP local detectada desde {interface}: {local_ip}")
                        return local_ip
            except Exception:
                continue
        
        # Método 3: Usar ip route para obtener la IP de la ruta por defecto
        try:
            result = subprocess.run([
                'ip', 'route', 'get', '1.1.1.1'
            ], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                import re
                match = re.search(r'src\s+(\d+(?:\.\d+){3})', result.stdout)
                if match:
                    local_ip = match.group(1)
                    logger.info(f"IP local detectada (ip route): {local_ip}")
                    return local_ip
        except Exception:
            pass
        
        # Método 4: Socket method como fallback
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                if not local_ip.startswith("127."):
                    logger.info(f"IP local detectada (socket): {local_ip}")
                    return local_ip
        except Exception:
            pass
            
    except Exception as e:
        logger.warning(f"Error detectando IP local: {e}")
    
    # Fallback a localhost si no se puede detectar
    logger.warning("No se pudo detectar IP local, usando localhost")
    return "localhost"

@dataclass
class AppInfo:
    name: str
    port: int
    url: str
    status: str
    icon: str = "🌐"
    process: str = ""

class PortScanner:
    """Escanea puertos y detecta aplicaciones corriendo"""
    
    def __init__(self, host=None):
        self.host = host or get_local_ip()
        self.common_ports = [
            80, 443, 3000, 3001, 4000, 5000, 8000, 8080, 8081, 8090,
            9000, 9090, 3306, 5432, 6379, 27017, 9200, 5601, 3030,
            # Puertos específicos de tus servicios
            8096, 5157, 9117, 51515, 8686, 8145, 4040, 8384, 8282, 8181, 1880, 8983
        ]
        # Añadir puertos de tus servicios
        self.docker_ports = self.get_docker_ports() or []  # Asegurar que no sea None
        self.all_ports = list(set(self.common_ports + self.docker_ports))
    
    def get_docker_ports(self) -> List[int]:
        """Obtiene puertos expuestos de contenedores Docker"""
        ports = []
        try:
            result = subprocess.run(
                ['docker', 'ps', '--format', '{{.Ports}}'],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                import re
                for line in result.stdout.strip().split('\n'):
                    # Buscar patrones como 0.0.0.0:8096->8096/tcp
                    matches = re.findall(r'0\.0\.0\.0:(\d+)->', line)
                    for match in matches:
                        ports.append(int(match))
                        
                logger.info(f"Puertos Docker detectados: {sorted(ports)}")
        except Exception as e:
            logger.warning(f"Error obteniendo puertos Docker: {e}")
        
    def get_docker_containers_info(self) -> List[Dict]:
        """Obtiene información detallada de contenedores Docker"""
        containers = []
        try:
            result = subprocess.run([
                'docker', 'ps', '--format', 
                '{{.Names}}|||{{.Image}}|||{{.Ports}}|||{{.Status}}'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                import re
                for line in result.stdout.strip().split('\n'):
                    if line and '|||' in line:
                        parts = line.split('|||')
                        if len(parts) >= 4:
                            name, image, ports, status = parts
                            
                            # Extraer puertos host
                            host_ports = []
                            port_mappings = re.findall(r'0\.0\.0\.0:(\d+)->(\d+)', ports)
                            for host_port, container_port in port_mappings:
                                host_ports.append({
                                    'host': int(host_port),
                                    'container': int(container_port)
                                })
                            
                            containers.append({
                                'name': name,
                                'image': image,
                                'ports': host_ports,
                                'status': status
                            })
                            
            logger.info(f"Contenedores Docker encontrados: {len(containers)}")
            
        except Exception as e:
            logger.warning(f"Error obteniendo info de Docker: {e}")
        
        return containers
    
    def scan_port(self, port: int, timeout: float = 1.0) -> bool:
        """Verifica si un puerto está abierto"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                result = sock.connect_ex((self.host, port))
                return result == 0
        except Exception:
            return False
    
    def get_process_info(self, port: int) -> str:
        """Obtiene información del proceso que usa el puerto"""
        try:
            result = subprocess.run(
                ['lsof', '-i', f':{port}', '-t'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                pid = result.stdout.strip().split('\n')[0]
                proc_result = subprocess.run(
                    ['ps', '-p', pid, '-o', 'comm='],
                    capture_output=True, text=True, timeout=5
                )
                return proc_result.stdout.strip() if proc_result.returncode == 0 else "unknown"
        except Exception as e:
            logger.warning(f"Error obteniendo proceso para puerto {port}: {e}")
        return "unknown"
    
    def check_http_service(self, port: int) -> Optional[str]:
        """Verifica si el servicio responde HTTP y obtiene título"""
        for protocol in ['http', 'https']:
            try:
                url = f"{protocol}://{self.host}:{port}"
                response = requests.get(url, timeout=3, verify=False)
                if response.status_code == 200:
                    # Intentar extraer título de la página
                    title = self.extract_title(response.text)
                    return title or f"{protocol.upper()} Service"
            except Exception:
                continue
        return None
    
    def extract_title(self, html: str) -> Optional[str]:
        """Extrae el título de una página HTML"""
        try:
            import re
            match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        except Exception:
            pass
        return None

class AppDetector:
    """Detecta y clasifica aplicaciones basándose en puertos y procesos"""
    
    def __init__(self):
        self.app_mappings = {
            # Web servers
            80: {"name": "HTTP Server", "icon": "🌐"},
            443: {"name": "HTTPS Server", "icon": "🔒"},
            8080: {"name": "HTTP Alt", "icon": "🌐"},
            8000: {"name": "Dev Server", "icon": "⚡"},
            
            # Bases de datos
            3306: {"name": "MySQL", "icon": "🗄️"},
            5432: {"name": "PostgreSQL", "icon": "🐘"},
            6379: {"name": "Redis", "icon": "🔴"},
            27017: {"name": "MongoDB", "icon": "🍃"},
            
            # Development
            3000: {"name": "React/Node", "icon": "⚛️"},
            3001: {"name": "Dev App", "icon": "🚀"},
            4000: {"name": "GraphQL", "icon": "📊"},
            5157: {"name": "Flask/API", "icon": "🐍"},
            
            # Monitoring
            9200: {"name": "Elasticsearch", "icon": "🔍"},
            5601: {"name": "Kibana", "icon": "📈"},
            9090: {"name": "Prometheus", "icon": "📊"},
            3030: {"name": "Grafana", "icon": "📊"},
            
            # Servicios específicos detectados
            8096: {"name": "Jellyfin", "icon": "🎬"},
            5157: {"name": "Jellyseerr", "icon": "🎭"},
            9117: {"name": "Jackett", "icon": "🔍"},
            51515: {"name": "Kopia", "icon": "💾"},
            8686: {"name": "Lidarr", "icon": "🎵"},
            8145: {"name": "FreshRSS", "icon": "📰"},
            4040: {"name": "Airsonic", "icon": "🎶"},
            8384: {"name": "Syncthing", "icon": "🔄"},
            8282: {"name": "qBittorrent", "icon": "⬇️"},
            8181: {"name": "qBittorrent", "icon": "⬇️"},
            1880: {"name": "Node-RED", "icon": "🔴"},
            8983: {"name": "ntfy", "icon": "📨"}
        }
    
    def detect_app_type(self, port: int, process: str, http_title: str = None) -> Dict:
        """Detecta el tipo de aplicación basándose en puerto, proceso y título HTTP"""
        # Primero buscar en mappings conocidos
        if port in self.app_mappings:
            app_info = self.app_mappings[port].copy()
        else:
            app_info = {"name": f"Service {port}", "icon": "⚙️"}
        
        # Refinar basándose en el proceso
        if process:
            app_info.update(self.refine_by_process(process))
        
        # Usar título HTTP si está disponible
        if http_title:
            app_info["name"] = http_title
        
        return app_info
    
    def refine_by_process(self, process: str) -> Dict:
        """Refina la detección basándose en el nombre del proceso"""
        process_mappings = {
            'nginx': {"name": "Nginx", "icon": "🔧"},
            'apache2': {"name": "Apache", "icon": "🪶"},
            'node': {"name": "Node.js App", "icon": "💚"},
            'python': {"name": "Python App", "icon": "🐍"},
            'java': {"name": "Java App", "icon": "☕"},
            'docker-proxy': {"name": "Docker Service", "icon": "🐳"},
            'postgres': {"name": "PostgreSQL", "icon": "🐘"},
            'mysql': {"name": "MySQL", "icon": "🗄️"},
            'redis-server': {"name": "Redis", "icon": "🔴"}
        }
        
        for proc_name, info in process_mappings.items():
            if proc_name in process.lower():
                return info
        
        return {}

class DashboardGenerator:
    """Genera la página web del dashboard"""
    
    def __init__(self, output_dir: str = "./dashboard"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_html(self, apps: List[AppInfo]) -> str:
        """Genera el HTML del dashboard"""
        # Generar cards HTML
        cards_html = ""
        for app in apps:
            card_html = f"""
            <div class="card" data-url="{app.url}">
                <div class="card-header">
                    <span class="icon">{app.icon}</span>
                    <div class="card-title">{app.name}</div>
                </div>
                <div class="card-info">Puerto: {app.port}</div>
                <div class="card-info">Proceso: {app.process}</div>
                <div class="card-info">
                    URL: <a href="{app.url}" target="_blank" class="url">{app.url}</a>
                </div>
                <div class="status {app.status.lower()}">{app.status}</div>
            </div>"""
            cards_html += card_html
        
        # Template HTML completo
        html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Server Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        h1 {{
            text-align: center;
            color: white;
            margin-bottom: 30px;
            font-size: 2.5rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        
        .server-info {{
            text-align: center;
            color: rgba(255, 255, 255, 0.8);
            margin-bottom: 30px;
            font-size: 1.1rem;
        }}
        
        .server-ip {{
            background: rgba(255, 255, 255, 0.1);
            padding: 8px 16px;
            border-radius: 20px;
            display: inline-block;
            margin: 0 10px;
        }}
        
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }}
        
        .card {{
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            cursor: pointer;
        }}
        
        .card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.2);
        }}
        
        .card-header {{
            display: flex;
            align-items: center;
            margin-bottom: 15px;
        }}
        
        .icon {{
            font-size: 2rem;
            margin-right: 15px;
        }}
        
        .card-title {{
            color: white;
            font-size: 1.3rem;
            font-weight: 600;
        }}
        
        .card-info {{
            color: rgba(255, 255, 255, 0.8);
            margin-bottom: 10px;
        }}
        
        .status {{
            display: inline-block;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
        }}
        
        .status.online {{
            background: rgba(46, 204, 113, 0.8);
            color: white;
        }}
        
        .status.offline {{
            background: rgba(231, 76, 60, 0.8);
            color: white;
        }}
        
        .url {{
            color: rgba(255, 255, 255, 0.9);
            text-decoration: none;
            word-break: break-all;
        }}
        
        .url:hover {{
            color: white;
            text-decoration: underline;
        }}
        
        .last-updated {{
            text-align: center;
            color: rgba(255, 255, 255, 0.7);
            margin-top: 30px;
            font-size: 0.9rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🖥️ Server Dashboard</h1>
        <div class="server-info">
            <span class="server-ip">🌐 IP: {get_local_ip()}</span>
            <span class="server-ip">📊 Servicios: {len(apps)}</span>
        </div>
        <div class="grid">
            {cards_html}
        </div>
        <div class="last-updated">
            Última actualización: {time.strftime("%Y-%m-%d %H:%M:%S")}
        </div>
    </div>
    
    <script>
        // Auto-refresh cada 30 segundos
        setTimeout(() => {{
            location.reload();
        }}, 30000);
        
        // Hacer cards clickeables
        document.querySelectorAll('.card').forEach(card => {{
            card.addEventListener('click', () => {{
                const url = card.dataset.url;
                if (url && url !== '#') {{
                    window.open(url, '_blank');
                }}
            }});
        }});
    </script>
</body>
</html>"""
        
        return html_content

    
    def save_dashboard(self, html_content: str, apps: List[AppInfo]):
        """Guarda el dashboard y datos JSON"""
        # Guardar HTML
        html_file = self.output_dir / "index.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Guardar datos JSON
        json_file = self.output_dir / "apps.json"
        apps_data = [asdict(app) for app in apps]
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(apps_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Dashboard guardado en: {html_file}")
        logger.info(f"Datos JSON guardados en: {json_file}")

def main():
    """Función principal"""
    import sys
    
    # Permitir especificar IP como argumento
    custom_ip = None
    if len(sys.argv) > 1:
        custom_ip = sys.argv[1]
        logger.info(f"Usando IP personalizada: {custom_ip}")
    
    logger.info("Iniciando escaneo de servicios...")
    
    # Inicializar componentes
    scanner = PortScanner(host=custom_ip)
    detector = AppDetector()
    generator = DashboardGenerator()
    
    logger.info(f"Escaneando servicios en: {scanner.host}")
    
    apps = []
    
    # Obtener información de contenedores Docker
    docker_containers = scanner.get_docker_containers_info()
    
    # Crear un mapa de puertos a contenedores
    port_to_container = {}
    for container in docker_containers:
        for port_info in container['ports']:
            port_to_container[port_info['host']] = container
    
    # Escanear puertos
    for port in scanner.all_ports:
        if scanner.scan_port(port):
            logger.info(f"Puerto {port} abierto")
            
            # Obtener información del proceso
            process = scanner.get_process_info(port)
            
            # Verificar si es servicio HTTP
            http_title = scanner.check_http_service(port)
            
            # Detectar tipo de aplicación
            app_info = detector.detect_app_type(port, process, http_title)
            
            # Si es un contenedor Docker, usar su información
            if port in port_to_container:
                container = port_to_container[port]
                app_info["name"] = container['name'].title()
                process = f"docker/{container['image']}"
            
            # Crear objeto AppInfo
            protocol = "https" if port == 443 else "http"
            url = f"{protocol}://{scanner.host}:{port}"
            
            app = AppInfo(
                name=app_info["name"],
                port=port,
                url=url,
                status="ONLINE",
                icon=app_info["icon"],
                process=process
            )
            
            apps.append(app)
    
    if not apps:
        logger.warning("No se encontraron servicios activos")
        return
    
    # Generar dashboard
    html_content = generator.generate_html(apps)
    generator.save_dashboard(html_content, apps)
    
    logger.info(f"Dashboard generado con {len(apps)} servicios")
    print(f"\nServicios detectados:")
    for app in apps:
        print(f"  • {app.name} (puerto {app.port}) - {app.url}")

def test_ip_detection():
    """Función para probar la detección de IP"""
    print("🔍 Probando detección de IP local...")
    
    # Mostrar interfaz activa
    active_interface = get_active_interface()
    if active_interface:
        print(f"📡 Interfaz activa: {active_interface}")
    else:
        print("⚠️  No se pudo detectar interfaz activa")
    
    # Mostrar IP detectada
    local_ip = get_local_ip()
    print(f"🌐 IP local detectada: {local_ip}")
    
    # Mostrar todas las interfaces disponibles
    try:
        result = subprocess.run(['ip', 'addr', 'show'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("\n📋 Interfaces disponibles:")
            import re
            interfaces = re.findall(r'\d+:\s+(\w+).*\n.*inet\s+(\d+(?:\.\d+){3})', 
                                  result.stdout, re.MULTILINE)
            for interface, ip in interfaces:
                if not ip.startswith('127.'):
                    print(f"  • {interface}: {ip}")
    except Exception as e:
        print(f"❌ Error listando interfaces: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test-ip":
        test_ip_detection()
    else:
        main()