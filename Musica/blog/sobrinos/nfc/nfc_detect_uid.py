#!/usr/bin/env python3
# obtener_uid.py

from smartcard.System import readers
from smartcard.util import toHexString
import time

def obtener_uid():
    try:
        # Obtener lista de lectores
        reader_list = readers()
        if not reader_list:
            print("No se encontraron lectores NFC")
            return
        
        reader = reader_list[0]  # Usar el primer lector
        print(f"Usando lector: {reader}")
        print("Acerca una tarjeta al lector...")
        
        while True:
            try:
                # Conectar a la tarjeta
                connection = reader.createConnection()
                connection.connect()
                
                # Comando APDU para obtener UID
                command = [0xFF, 0xCA, 0x00, 0x00, 0x00]
                data, sw1, sw2 = connection.transmit(command)
                
                if sw1 == 0x90 and sw2 == 0x00:
                    uid = toHexString(data).replace(' ', '')
                    print(f"UID detectado: {uid}")
                else:
                    print("Error al leer la tarjeta")
                
                connection.disconnect()
                time.sleep(2)
                
            except Exception as e:
                time.sleep(0.5)
                continue
                
    except KeyboardInterrupt:
        print("\nSaliendo...")

if __name__ == "__main__":
    obtener_uid()
