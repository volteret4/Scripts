#!/usr/bin/env python3
# nfc_launcher.py

from smartcard.System import readers
from smartcard.util import toHexString
import subprocess
import time
import os

# Configuración de tarjetas y comandos
TARJETAS_CONFIG = {
    "B2BA9C1E": {  
        "nombre": "Tarjeta 1",
        "comando": ["touch", "/home/pi/sonidos.txt"]
    },
    "YYYYYYYY": {  # Reemplaza con el UID real de tu tarjeta 2
        "nombre": "Tarjeta 2", 
        "comando": ["python3", "/home/pi/script1.py"],  # Ejemplo: ejecutar script
    },
    "ZZZZZZZZ": {  # Reemplaza con el UID real de tu tarjeta 3
        "nombre": "Tarjeta 3",
        "comando": ["systemctl", "restart", "nginx"],  # Ejemplo: reiniciar servicio
    }
}

def ejecutar_comando(comando):
    """Ejecuta un comando del sistema"""
    try:
        resultado = subprocess.run(comando, capture_output=True, text=True)
        if resultado.returncode == 0:
            print(f"Comando ejecutado exitosamente: {' '.join(comando)}")
            if resultado.stdout:
                print(f"Salida: {resultado.stdout}")
        else:
            print(f"Error ejecutando comando: {resultado.stderr}")
    except Exception as e:
        print(f"Error: {e}")

def monitorear_tarjetas():
    """Monitorea continuamente las tarjetas NFC"""
    try:
        # Obtener lista de lectores
        reader_list = readers()
        if not reader_list:
            print("No se encontraron lectores NFC")
            return
        
        reader = reader_list[0]
        print(f"Usando lector: {reader}")
        print("Esperando tarjetas... (Ctrl+C para salir)")
        
        ultima_tarjeta = None
        tiempo_ultima_lectura = 0
        
        while True:
            try:
                # Conectar a la tarjeta
                connection = reader.createConnection()
                connection.connect()
                
                # Obtener UID
                command = [0xFF, 0xCA, 0x00, 0x00, 0x00]
                data, sw1, sw2 = connection.transmit(command)
                
                if sw1 == 0x90 and sw2 == 0x00:
                    uid = toHexString(data).replace(' ', '')
                    tiempo_actual = time.time()
                    
                    # Evitar ejecuciones múltiples de la misma tarjeta
                    if (uid != ultima_tarjeta or 
                        tiempo_actual - tiempo_ultima_lectura > 3):
                        
                        print(f"Tarjeta detectada: {uid}")
                        
                        if uid in TARJETAS_CONFIG:
                            config = TARJETAS_CONFIG[uid]
                            print(f"Ejecutando comando para {config['nombre']}")
                            ejecutar_comando(config['comando'])
                        else:
                            print("Tarjeta no configurada")
                        
                        ultima_tarjeta = uid
                        tiempo_ultima_lectura = tiempo_actual
                
                connection.disconnect()
                time.sleep(0.5)
                
            except Exception as e:
                # La tarjeta se retiró o no hay tarjeta
                time.sleep(0.5)
                continue
                
    except KeyboardInterrupt:
        print("\nSaliendo...")

if __name__ == "__main__":
    monitorear_tarjetas()
