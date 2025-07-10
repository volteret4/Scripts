#!/usr/bin/env python3
import subprocess
import socket
import requests
from urllib.parse import urlparse
import time

def check_dns_resolution(domain):
    """Verifica la resolución DNS para un dominio específico"""
    try:
        ip = socket.gethostbyname(domain)
        return True, ip
    except socket.gaierror:
        return False, None

def check_port_open(ip, port):
    """Verifica si un puerto específico está abierto en una IP"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex((ip, port))
    sock.close()
    return result == 0

def ping_host(ip):
    """Realiza un ping a una IP para verificar si responde"""
    try:
        output = subprocess.check_output(
            ['ping', '-c', '1', '-W', '2', ip],
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        return True, output
    except subprocess.CalledProcessError as e:
        return False, e.output

def check_http_response(url, verify=False):
    """Verifica la respuesta HTTP de una URL"""
    try:
        response = requests.get(url, timeout=5, verify=verify)
        return True, response.status_code, response.headers
    except requests.RequestException as e:
        return False, str(e), None

def diagnose_domain(domain, expected_ip=None, ports=[80, 443]):
    """Diagnostica problemas con un dominio específico"""
    print(f"\n--- Diagnóstico para {domain} ---")
    
    # Comprobar resolución DNS
    dns_ok, resolved_ip = check_dns_resolution(domain)
    if dns_ok:
        print(f"✅ Resolución DNS: {domain} -> {resolved_ip}")
        if expected_ip and resolved_ip != expected_ip:
            print(f"⚠️ La IP resuelta ({resolved_ip}) no coincide con la esperada ({expected_ip})")
    else:
        print(f"❌ No se pudo resolver {domain}")
        return
    
    # Comprobar ping
    ping_ok, ping_output = ping_host(resolved_ip)
    if ping_ok:
        print(f"✅ Ping a {resolved_ip} exitoso")
    else:
        print(f"❌ No se pudo hacer ping a {resolved_ip}")
    
    # Comprobar puertos
    for port in ports:
        port_open = check_port_open(resolved_ip, port)
        if port_open:
            print(f"✅ Puerto {port} abierto en {resolved_ip}")
        else:
            print(f"❌ Puerto {port} cerrado en {resolved_ip}")
    
    # Comprobar HTTP/HTTPS
    for protocol in ['http', 'https']:
        url = f"{protocol}://{domain}"
        success, result, headers = check_http_response(url)
        if success:
            print(f"✅ {url} responde con código {result}")
            if headers:
                server = headers.get('Server', 'No especificado')
                print(f"   Servidor: {server}")
        else:
            print(f"❌ Error al acceder a {url}: {result}")

def check_pihole_config():
    """Verifica la configuración de Pi-hole"""
    print("\n--- Verificando configuración de Pi-hole ---")
    try:
        with open('/etc/dnsmasq.d/02-wild.conf', 'r') as f:
            content = f.read()
            print(f"Configuración actual:\n{content}")
    except FileNotFoundError:
        print("❌ No se pudo encontrar el archivo de configuración de Pi-hole")
        
    # Intentar consultar directamente al Pi-hole
    pihole_ip = "192.168.1.202"
    for domain in domains_to_check:
        try:
            cmd = f"dig @{pihole_ip} {domain}"
            output = subprocess.check_output(cmd, shell=True, universal_newlines=True)
            print(f"\nConsulta DNS para {domain} usando Pi-hole ({pihole_ip}):")
            
            # Extraer la sección de respuesta del comando dig
            answer_section = output.split("ANSWER SECTION:")
            if len(answer_section) > 1:
                answer = answer_section[1].split("\n")[1]
                print(f"✅ Respuesta: {answer}")
            else:
                print("❌ No se obtuvo respuesta")
        except subprocess.CalledProcessError:
            print(f"❌ Error al consultar {domain} en Pi-hole")

def main():
    global domains_to_check
    domains_to_check = [
        "yt.pollete.duckdns.org",
        "wallabag.pollete.duckdns.org",
        "rss.pollete.duckdns.org"
    ]
    
    # Diagnóstico de dominios
    for domain in domains_to_check:
        diagnose_domain(domain)
    
    # Verificar configuración de Pi-hole
    check_pihole_config()
    
    # Consultar configuración de Nginx Proxy Manager
    print("\n--- Verificando Nginx Proxy Manager ---")
    print("Para verificar la configuración de Nginx Proxy Manager:")
    print("1. Ingresa a la interfaz web en http://192.168.1.191:81")
    print("2. Verifica los certificados SSL para los dominios problemáticos")
    print("3. Revisa los registros de acceso y error en la sección 'Logs'")
    
    print("\n--- Recomendaciones para solucionar el problema ---")
    print("1. Verifica que los servicios en las IPs de destino estén funcionando")
    print("2. Comprueba que Nginx Proxy Manager tenga configurados correctamente los puertos")
    print("3. Revisa los logs de Nginx Proxy Manager para ver errores específicos")
    print("4. Verifica que los certificados SSL sean válidos si estás usando HTTPS")
    print("5. Comprueba que no haya conflictos en la configuración de Pi-hole")

if __name__ == "__main__":
    main()