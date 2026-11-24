#!/usr/bin/env python3
"""
Extrae la lista de paquetes instalados directamente desde los .dist-info
Útil cuando pip list no funciona correctamente
"""
import os
import re
from pathlib import Path

# Buscar todos los .dist-info en el entorno virtual
venv_path = Path.home() / "Scripts/python_venv/lib"
dist_info_dirs = list(venv_path.glob("python*/site-packages/*.dist-info"))

packages = []
for dist_info in sorted(dist_info_dirs):
    # Extraer nombre y versión del directorio
    match = re.match(r"(.+?)-(\d+\..+?)\.dist-info", dist_info.name)
    if match:
        name, version = match.groups()
        # Normalizar el nombre (reemplazar _ por -)
        name = name.replace("_", "-")
        packages.append(f"{name}=={version}")

# Imprimir todos los paquetes
print("# Paquetes instalados en el entorno virtual")
print("# Generado desde .dist-info directories")
print()
for pkg in sorted(packages):
    print(pkg)

print(f"\n# Total: {len(packages)} paquetes")
