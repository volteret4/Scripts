#!/usr/bin/env python3
"""
dashboard_utils.py - Utilidades para gestionar el dashboard
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
import shutil

def add_custom_port(port: int, name: str = None, icon: str = "⚙️"):
    """Añade un puerto personalizado a la configuración"""
    config_file = Path("config.py")
    
    if not config_file.exists():
        print("❌ config.py no encontrado")
        return False
    
    # Leer configuración actual
    with open(config_file, 'r') as f:
        content = f.read()
    
    # Añadir puerto a CUSTOM_PORTS si no existe
    if f"{port}" not in content:
        # Buscar la línea donde termina CUSTOM_PORTS
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if "# Agrega tus puertos personalizados aquí" in line:
                lines.insert(i, f"    {port},  # {name or f'Puerto {port}'}")
                break
        
        # Actualizar archivo
        with open(config_file, 'w') as f:
            f.write('\n'.join(lines))
        
        print(f"✓ Puerto {port} añadido a la configuración")
        
        # Añadir mapeo si se proporciona nombre
        if name:
            add_app_mapping(port, name, icon)
    else:
        print(f"⚠️  Puerto {port} ya existe en la configuración")
    
    return True

def add_app_mapping(port: int, name: str, icon: str = "⚙️"):
    """Añade un mapeo de aplicación personalizado"""
    config_file = Path("config.py")
    
    with open(config_file, 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if "# Agrega más aplicaciones personalizadas" in line:
            new_mapping = f'    {port}: {{"name": "{name}", "icon": "{icon}"}},'
            lines.insert(i, new_mapping)
            break
    
    with open(config_file, 'w') as f:
        f.write('\n'.join(lines))
    
    print(f"✓ Mapeo añadido: {port} -> {name} {icon}")

def remove_port(port: int):
    """Remueve un puerto de la configuración"""
    config_file = Path("config.py")
    
    if not config_file.exists():
        print("❌ config.py no encontrado")
        return False
    
    with open(config_file, 'r') as f:
        lines = f.readlines()
    
    # Remover puerto de CUSTOM_PORTS y CUSTOM_APP_MAPPINGS
    updated_lines = []
    for line in lines:
        if f"{port}" not in line or "def " in line or "class " in line:
            updated_lines.append(line)
        else:
            print(f"🗑️  Removiendo: {line.strip()}")
    
    with open(config_file, 'w') as f:
        f.writelines(updated_lines)
    
    print(f"✓ Puerto {port} removido de la configuración")
    return True

def list_monitored_services():
    """Lista los servicios monitoreados actualmente"""
    apps_file = Path("dashboard/apps.json")
    
    if not apps_file.exists():
        print("❌ No hay datos de servicios. Ejecuta primero el dashboard.")
        return
    
    with open(apps_file, 'r') as f:
        apps = json.load(f)
    
    print("\n📋 Servicios monitoreados:")
    print("-" * 50)
    
    for app in apps:
        status_icon = "🟢" if app['status'] == 'ONLINE' else "🔴"
        print(f"{status_icon} {app['name']} (puerto {app['port']})")
        print(f"   URL: {app['url']}")
        print(f"   Proceso: {app['process']}")
        print()

def backup_dashboard():
    """Crea un backup del dashboard y configuración"""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_dir = Path(f"backup_{timestamp}")
    backup_dir.mkdir(exist_ok=True)
    
    # Archivos a respaldar
    files_to_backup = [
        "dashboard_generator.py",
        "config.py",
        "dashboard_extensions.py",
        "dashboard/",
        "monitoring/",
        "docker-compose.yml",
        "Dockerfile",
        "nginx.conf"
    ]
    
    backed_up = []
    for item in files_to_backup:
        source = Path(item)
        if source.exists():
            if source.is_dir():
                shutil.copytree(source, backup_dir / source.name)
            else:
                shutil.copy2(source, backup_dir / source.name)
            backed_up.append(item)
    
    print(f"✓ Backup creado en: {backup_dir}")
    print(f"📁 Archivos respaldados: {', '.join(backed_up)}")
    
    return backup_dir

def restore_dashboard(backup_dir: str):
    """Restaura un backup del dashboard"""
    backup_path = Path(backup_dir)
    
    if not backup_path.exists():
        print(f"❌ Backup no encontrado: {backup_dir}")
        return False
    
    print(f"🔄 Restaurando desde: {backup_path}")
    
    # Restaurar archivos
    for item in backup_path.iterdir():
        if item.is_dir():
            if Path(item.name).exists():
                shutil.rmtree(item.name)
            shutil.copytree(item, item.name)
        else:
            shutil.copy2(item, item.name)
        print(f"✓ Restaurado: {item.name}")
    
    print("✅ Restauración completada")
    return True

def run_dashboard_daemon():
    """Ejecuta el dashboard como daemon (actualización continua)"""
    print("🔄 Iniciando dashboard en modo daemon...")
    print("   Actualización cada 5 minutos")
    print("   Presiona Ctrl+C para detener")
    
    try:
        while True:
            print(f"\n🔄 Actualizando dashboard - {time.strftime('%H:%M:%S')}")
            result = subprocess.run([sys.executable, "dashboard_generator.py"])
            
            if result.returncode == 0:
                print("✅ Dashboard actualizado correctamente")
            else:
                print("❌ Error actualizando dashboard")
            
            # Esperar 5 minutos
            time.sleep(300)
            
    except KeyboardInterrupt:
        print("\n🛑 Dashboard daemon detenido")

def check_dependencies():
    """Verifica que todas las dependencias estén instaladas"""
    dependencies = {
        "requests": "requests",
        "psutil": "psutil"
    }
    
    missing = []
    
    for module, package in dependencies.items():
        try:
            __import__(module)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - NO INSTALADO")
            missing.append(package)
    
    if missing:
        print(f"\n🔧 Para instalar dependencias faltantes:")
        print(f"pip install {' '.join(missing)}")
        return False
    
    print("\n✅ Todas las dependencias están instaladas")
    return True

def setup_systemd_service():
    """Crea un servicio systemd para el dashboard"""
    current_dir = Path.cwd().absolute()
    python_path = shutil.which('python3') or shutil.which('python')
    
    service_content = f"""[Unit]
Description=Server Dashboard Generator
After=network.target

[Service]
Type=simple
User={Path.home().name}
WorkingDirectory={current_dir}
ExecStart={python_path} {current_dir}/dashboard_generator.py
Restart=always
RestartSec=300

[Install]
WantedBy=multi-user.target
"""
    
    service_file = Path("server-dashboard.service")
    with open(service_file, 'w') as f:
        f.write(service_content)
    
    print(f"✓ Servicio systemd creado: {service_file}")
    print("\nPara instalar el servicio:")
    print(f"sudo cp {service_file} /etc/systemd/system/")
    print("sudo systemctl daemon-reload")
    print("sudo systemctl enable server-dashboard")
    print("sudo systemctl start server-dashboard")

def clean_old_data():
    """Limpia datos antiguos de monitoreo"""
    monitoring_dir = Path("monitoring")
    
    if not monitoring_dir.exists():
        print("📂 No hay directorio de monitoreo")
        return
    
    files = list(monitoring_dir.glob("monitoring_*.json"))
    if len(files) <= 10:
        print(f"📁 Solo {len(files)} archivos de monitoreo, no es necesario limpiar")
        return
    
    # Mantener solo los 10 más recientes
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    to_delete = files[10:]
    
    for file in to_delete:
        file.unlink()
    
    print(f"🗑️  Eliminados {len(to_delete)} archivos de monitoreo antiguos")

def main():
    parser = argparse.ArgumentParser(description="Utilidades para el Dashboard Generator")
    subparsers = parser.add_subparsers(dest='command', help='Comandos disponibles')
    
    # Añadir puerto
    add_parser = subparsers.add_parser('add-port', help='Añadir puerto personalizado')
    add_parser.add_argument('port', type=int, help='Número de puerto')
    add_parser.add_argument('--name', help='Nombre de la aplicación')
    add_parser.add_argument('--icon', default='⚙️', help='Icono para la aplicación')
    
    # Remover puerto
    remove_parser = subparsers.add_parser('remove-port', help='Remover puerto')
    remove_parser.add_argument('port', type=int, help='Número de puerto')
    
    # Listar servicios
    subparsers.add_parser('list', help='Listar servicios monitoreados')
    
    # Backup
    subparsers.add_parser('backup', help='Crear backup')
    
    # Restaurar
    restore_parser = subparsers.add_parser('restore', help='Restaurar backup')
    restore_parser.add_argument('backup_dir', help='Directorio del backup')
    
    # Daemon
    subparsers.add_parser('daemon', help='Ejecutar como daemon')
    
    # Verificar dependencias
    subparsers.add_parser('check-deps', help='Verificar dependencias')
    
    # Servicio systemd
    subparsers.add_parser('systemd', help='Crear servicio systemd')
    
    # Limpiar datos
    subparsers.add_parser('clean', help='Limpiar datos antiguos')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Ejecutar comando
    if args.command == 'add-port':
        add_custom_port(args.port, args.name, args.icon)
    elif args.command == 'remove-port':
        remove_port(args.port)
    elif args.command == 'list':
        list_monitored_services()
    elif args.command == 'backup':
        backup_dashboard()
    elif args.command == 'restore':
        restore_dashboard(args.backup_dir)
    elif args.command == 'daemon':
        run_dashboard_daemon()
    elif args.command == 'check-deps':
        check_dependencies()
    elif args.command == 'systemd':
        setup_systemd_service()
    elif args.command == 'clean':
        clean_old_data()

if __name__ == "__main__":
    main()