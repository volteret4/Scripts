#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import configparser
import argparse
import sys
import os
from datetime import datetime

class MusicManager:
    def __init__(self, config_file='config.ini'):
        self.config = configparser.ConfigParser()
        if not os.path.exists(config_file):
            print(f"Error: {config_file} no encontrado")
            sys.exit(1)
            
        self.config.read(config_file)
        self.db_path = self.config.get('database', 'path')
    
    def get_connection(self):
        """Obtener conexión a la base de datos"""
        return sqlite3.connect(self.db_path)
    
    def show_stats(self):
        """Mostrar estadísticas de la colección"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        print("=== Estadísticas de la Colección Musical ===\n")
        
        # Estadísticas básicas
        cursor.execute("SELECT COUNT(*) FROM artists WHERE origen = 'local'")
        artists_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM albums WHERE origen = 'local'")
        albums_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM songs WHERE origen = 'local'")
        songs_count = cursor.fetchone()[0]
        
        print(f"📁 Artistas locales: {artists_count}")
        print(f"💿 Álbumes locales: {albums_count}")
        print(f"🎵 Canciones locales: {songs_count}")
        
        conn.close()

def main():
    parser = argparse.ArgumentParser(description='Music Manager - Utilidad simplificada')
    parser.add_argument('--config', default='config.ini', help='Archivo de configuración')
    parser.add_argument('command', nargs='?', default='stats', help='Comando a ejecutar')
    
    args = parser.parse_args()
    
    try:
        manager = MusicManager(args.config)
        
        if args.command == 'stats':
            manager.show_stats()
        else:
            print(f"Comando '{args.command}' no reconocido")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()