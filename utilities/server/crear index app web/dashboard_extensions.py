# dashboard_extensions.py - Funciones adicionales para extender el dashboard
"""
Extensiones y mejoras para el Dashboard Generator
"""

import json
import time
import psutil
import requests
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import subprocess

def add_system_monitoring() -> Dict:
    """Añade información de monitoreo del sistema"""
    try:
        return {
            "cpu_usage": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
            "uptime": time.time() - psutil.boot_time()
        }
    except Exception as e:
        return {"error": str(e)}

def check_service_health(url: str, timeout: int = 5) -> Dict:
    """Verifica la salud de un servicio web"""
    try:
        start_time = time.time()
        response = requests.get(url, timeout=timeout, verify=False)
        response_time = time.time() - start_time
        
        return {
            "status": "healthy" if response.status_code == 200 else "unhealthy",
            "status_code": response.status_code,
            "response_time": round(response_time * 1000, 2),  # ms
            "content_length": len(response.content) if response.content else 0
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": str(e),
            "response_time": None
        }

def scan_docker_containers() -> List[Dict]:
    """Escanea contenedores Docker corriendo"""
    try:
        result = subprocess.run(
            ['docker', 'ps', '--format', 'json'],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode != 0:
            return []
        
        containers = []
        for line in result.stdout.strip().split('\n'):
            if line:
                container = json.loads(line)
                # Extraer puertos expuestos
                ports = []
                if container.get('Ports'):
                    import re
                    port_matches = re.findall(r'(\d+):(\d+)', container['Ports'])
                    ports = [{"host": p[0], "container": p[1]} for p in port_matches]
                
                containers.append({
                    "name": container.get('Names', ''),
                    "image": container.get('Image', ''),
                    "status": container.get('State', ''),
                    "ports": ports
                })
        
        return containers
    except Exception as e:
        print(f"Error escaneando Docker: {e}")
        return []

def detect_web_frameworks(url: str) -> Dict:
    """Detecta el framework web usado en una URL"""
    try:
        response = requests.get(url, timeout=3, verify=False)
        headers = response.headers
        content = response.text.lower()
        
        framework_indicators = {
            "react": ["react", "reactdom"],
            "vue": ["vue.js", "vue/dist"],
            "angular": ["angular", "ng-version"],
            "django": ["django", "csrftoken"],
            "flask": ["flask", "werkzeug"],
            "express": ["express", "x-powered-by: express"],
            "nginx": ["nginx", "server: nginx"],
            "apache": ["apache", "server: apache"]
        }
        
        detected = []
        for framework, indicators in framework_indicators.items():
            if any(indicator in content or indicator in str(headers) for indicator in indicators):
                detected.append(framework)
        
        return {
            "frameworks": detected,
            "server": headers.get('Server', 'unknown'),
            "x_powered_by": headers.get('X-Powered-By', 'unknown')
        }
    except Exception:
        return {"frameworks": [], "server": "unknown", "x_powered_by": "unknown"}

def generate_api_endpoints_card(apps: List) -> str:
    """Genera una card especial para endpoints de API"""
    api_apps = [app for app in apps if 'api' in app.name.lower() or app.port in [5000, 8000, 4000]]
    
    if not api_apps:
        return ""
    
    endpoints_html = ""
    for app in api_apps:
        # Intentar detectar endpoints comunes
        common_paths = ['/api', '/docs', '/swagger', '/health', '/status']
        working_endpoints = []
        
        for path in common_paths:
            try:
                test_url = f"{app.url}{path}"
                response = requests.get(test_url, timeout=2)
                if response.status_code == 200:
                    working_endpoints.append(path)
            except:
                continue
        
        if working_endpoints:
            endpoints_html += f"""
            <div class="api-endpoints">
                <strong>{app.name}</strong>
                <ul>
                    {''.join(f'<li><a href="{app.url}{ep}" target="_blank">{ep}</a></li>' for ep in working_endpoints)}
                </ul>
            </div>
            """
    
    if endpoints_html:
        return f"""
        <div class="card api-card">
            <div class="card-header">
                <span class="icon">🔗</span>
                <div class="card-title">API Endpoints</div>
            </div>
            {endpoints_html}
        </div>
        """
    
    return ""

def add_performance_metrics(apps: List) -> List:
    """Añade métricas de rendimiento a las aplicaciones"""
    for app in apps:
        if app.url and app.url != "#":
            health = check_service_health(app.url)
            app.health = health
            
            # Actualizar estado basándose en salud
            if health.get("status") == "healthy":
                app.status = "ONLINE"
            elif health.get("status") == "error":
                app.status = "ERROR"
            else:
                app.status = "WARNING"
    
    return apps

def create_advanced_dashboard_html(apps: List, system_info: Dict = None) -> str:
    """Genera HTML del dashboard con características avanzadas"""
    
    # Sistema de información como card
    system_card = ""
    if system_info:
        system_card = f"""
        <div class="card system-card">
            <div class="card-header">
                <span class="icon">📊</span>
                <div class="card-title">System Status</div>
            </div>
            <div class="metrics">
                <div class="metric">
                    <span>CPU:</span> <span class="value">{system_info.get('cpu_usage', 0):.1f}%</span>
                </div>
                <div class="metric">
                    <span>Memory:</span> <span class="value">{system_info.get('memory_usage', 0):.1f}%</span>
                </div>
                <div class="metric">
                    <span>Disk:</span> <span class="value">{system_info.get('disk_usage', 0):.1f}%</span>
                </div>
            </div>
        </div>
        """
    
    # CSS adicional para las nuevas características
    additional_css = """
    .system-card {
        background: linear-gradient(135deg, #2c3e50, #3498db);
    }
    
    .api-card {
        background: linear-gradient(135deg, #27ae60, #2ecc71);
    }
    
    .metrics {
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    
    .metric {
        display: flex;
        justify-content: space-between;
        color: rgba(255, 255, 255, 0.9);
    }
    
    .value {
        font-weight: bold;
    }
    
    .api-endpoints ul {
        list-style: none;
        margin: 10px 0;
    }
    
    .api-endpoints li {
        margin: 5px 0;
    }
    
    .api-endpoints a {
        color: rgba(255, 255, 255, 0.9);
        text-decoration: none;
        font-size: 0.9rem;
    }
    
    .api-endpoints a:hover {
        color: white;
        text-decoration: underline;
    }
    
    .health-indicator {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 8px;
    }
    
    .health-healthy { background-color: #2ecc71; }
    .health-warning { background-color: #f39c12; }
    .health-error { background-color: #e74c3c; }
    
    .response-time {
        font-size: 0.8rem;
        color: rgba(255, 255, 255, 0.7);
        margin-top: 5px;
    }
    """
    
    return additional_css

def update_app_with_docker_info(apps: List, containers: List[Dict]) -> List:
    """Actualiza información de apps con datos de Docker"""
    for app in apps:
        for container in containers:
            for port_mapping in container.get('ports', []):
                if int(port_mapping['host']) == app.port:
                    app.name = f"{container['name']} ({app.name})"
                    app.icon = "🐳"
                    app.process = f"docker/{container['image']}"
                    break
    return apps

def save_monitoring_data(apps: List, system_info: Dict = None):
    """Guarda datos de monitoreo para histórico"""
    monitoring_dir = Path("./monitoring")
    monitoring_dir.mkdir(exist_ok=True)
    
    timestamp = int(time.time())
    data = {
        "timestamp": timestamp,
        "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
        "apps": [
            {
                "name": app.name,
                "port": app.port,
                "status": app.status,
                "health": getattr(app, 'health', {}),
                "url": app.url
            } for app in apps
        ],
        "system": system_info or {}
    }
    
    filename = monitoring_dir / f"monitoring_{timestamp}.json"
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    # Mantener solo los últimos 100 archivos
    monitoring_files = sorted(monitoring_dir.glob("monitoring_*.json"))
    if len(monitoring_files) > 100:
        for old_file in monitoring_files[:-100]:
            old_file.unlink()

def create_status_api(apps: List) -> str:
    """Crea un endpoint JSON simple para el estado de las apps"""
    api_data = {
        "timestamp": time.time(),
        "status": "ok",
        "services": [
            {
                "name": app.name,
                "port": app.port,
                "status": app.status.lower(),
                "url": app.url,
                "health": getattr(app, 'health', {})
            } for app in apps
        ],
        "summary": {
            "total": len(apps),
            "online": len([app for app in apps if app.status == "ONLINE"]),
            "offline": len([app for app in apps if app.status == "OFFLINE"]),
            "error": len([app for app in apps if app.status == "ERROR"])
        }
    }
    
    return json.dumps(api_data, indent=2)

# Función para integrar todas las extensiones
def enhance_dashboard_generator():
    """
    Función que puedes llamar para añadir todas las mejoras al dashboard principal.
    Agrega esto al final de tu main() en dashboard_generator.py:
    """
    enhancement_code = '''
    # === MEJORAS ADICIONALES ===
    # Importar extensiones
    try:
        from dashboard_extensions import (
            add_system_monitoring, 
            scan_docker_containers,
            add_performance_metrics,
            update_app_with_docker_info,
            save_monitoring_data,
            create_status_api
        )
        
        # Añadir información del sistema
        system_info = add_system_monitoring()
        
        # Escanear contenedores Docker
        containers = scan_docker_containers()
        apps = update_app_with_docker_info(apps, containers)
        
        # Añadir métricas de rendimiento
        apps = add_performance_metrics(apps)
        
        # Guardar datos de monitoreo
        save_monitoring_data(apps, system_info)
        
        # Crear API de estado
        api_content = create_status_api(apps)
        api_file = generator.output_dir / "api.json"
        with open(api_file, 'w') as f:
            f.write(api_content)
        
        logger.info("✓ Extensiones aplicadas correctamente")
        
    except ImportError:
        logger.warning("dashboard_extensions.py no encontrado, usando funcionalidad básica")
    except Exception as e:
        logger.error(f"Error aplicando extensiones: {e}")
    '''
    
    return enhancement_code

# Script de instalación de dependencias
def install_dependencies():
    """Instala dependencias adicionales necesarias"""
    dependencies = [
        "psutil>=5.8.0",  # Para información del sistema
        "requests>=2.25.0",  # Para verificar servicios HTTP
    ]
    
    install_script = f'''#!/bin/bash
# install_deps.sh - Instala dependencias del dashboard

echo "🔧 Instalando dependencias..."

# Actualizar pip
python3 -m pip install --upgrade pip

# Instalar dependencias
pip3 install {' '.join(dependencies)}

# Verificar instalación
python3 -c "import psutil, requests; print('✓ Dependencias instaladas correctamente')"

echo "✅ Instalación completada"
'''
    
    with open('install_deps.sh', 'w') as f:
        f.write(install_script)
    
    # Hacer ejecutable
    import os
    os.chmod('install_deps.sh', 0o755)
    
    print("✓ Script de instalación creado: install_deps.sh")

if __name__ == "__main__":
    print("🚀 Creando extensiones del dashboard...")
    install_dependencies()
    print("\n📝 Para usar las extensiones:")
    print("1. Ejecuta: ./install_deps.sh")
    print("2. Añade el código de enhance_dashboard_generator() a tu script principal")
    print("3. Las nuevas funcionalidades incluyen:")
    print("   • Monitoreo del sistema (CPU, RAM, Disco)")
    print("   • Detección de contenedores Docker")
    print("   • Verificación de salud de servicios")
    print("   • API JSON para estado (/api.json)")
    print("   • Histórico de monitoreo")