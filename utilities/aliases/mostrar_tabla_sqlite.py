import sqlite3
import sys

base_datos = sys.argv[1]
conn = sqlite3.connect(base_datos)
cursor = conn.cursor()

# Obtener todas las tablas
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tablas = cursor.fetchall()

for tabla in tablas:
    print(f"\nEstructura de la tabla: {tabla[0]}")
    cursor.execute(f"PRAGMA table_info({tabla[0]})")
    columnas = cursor.fetchall()
    for columna in columnas:
        print(columna)  # (ID, Nombre, Tipo, ¿Puede ser NULL?, Valor por defecto, Clave primaria)

conn.close()