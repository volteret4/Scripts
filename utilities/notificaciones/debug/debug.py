#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Script Name: debug.py
# Description: Módulo de notificaciones con botones configurables
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Dependencies:  - dunst
#                  - subprocess, os, tempfile
#
# Modo de uso:
#
#   from debug import notify_info, notify_error, ErrorHandler
#
#   # Mostrar todos los botones
#   notify_info("Mensaje con todos los botones")
#
#   Mostrar solo algunos botones
#   notify_info("Solo botón de edición", config="100")
#
#   # Usar el manejador de errores
#   with ErrorHandler(config="110"):
#         # Tu código aquí
#         result = 10 / 0  # Esto generará una notificación de error


import subprocess
import os
import tempfile
import sys
import traceback

def notify_message(urgency="normal", message="Mensaje", script_path=None, title="Notificación", config="111"):
    """
    Muestra una notificación con dunst con botones configurables.
    
    Args:
        urgency (str): Nivel de urgencia ('low', 'normal', 'critical')
        message (str): Mensaje a mostrar
        script_path (str): Ruta al script que llama esta función
        title (str): Título de la notificación
        config (str): Configuración de botones (codium, carpeta, tarea). Formato: "111" para todos activos
    """
    # Si no se proporciona ruta al script, usar el script actual
    if script_path is None:
        script_path = os.path.abspath(sys.argv[0])
    
    script_name = os.path.basename(script_path)
    
    # Almacenar información en archivos temporales
    with open(f"/tmp/dunst_action_{script_name}.source", "w") as f:
        f.write(script_path)
    
    with open(f"/tmp/dunst_action_{script_name}.message", "w") as f:
        f.write(message)
    
    # Determinar color e icono según urgencia
    bg_color = "#3498DB"  # default
    icon = "dialog-information"  # default
    
    if urgency == "low":
        bg_color = "#4CAF50"
        icon = "dialog-information"
    elif urgency == "normal":
        bg_color = "#3498DB"
        icon = "dialog-information"
    elif urgency == "critical":
        bg_color = "#FF5555"
        icon = "dialog-error"
    
    # Construir comando base
    cmd = ["dunstify", "-u", urgency, 
           "-a", "ScriptMonitor", 
           "-i", icon,
           "-h", f"string:x-dunst-stack-tag:{script_name}",
           "-h", f"string:bgcolor:{bg_color}"]
    
    # Añadir acciones según la configuración
    if config[0] == "1":
        cmd.extend(["-A", f"vscodium_{script_name},Editar con Codium"])
    
    if len(config) > 1 and config[1] == "1":
        cmd.extend(["-A", f"folder_{script_name},Abrir carpeta"])
    
    if len(config) > 2 and config[2] == "1":
        cmd.extend(["-A", f"tarea_{script_name},Añadir a tareas"])
    
    # Añadir título y mensaje
    cmd.extend([title, message])
    
    # Configurar entorno y ejecutar
    env = os.environ.copy()
    env["DISPLAY"] = ":0"
    
    subprocess.run(cmd, env=env)

# Funciones alias para conveniencia
def notify_info(message, script_path=None, title="Info", config="111"):
    notify_message("normal", message, script_path, title, config)

def notify_warning(message, script_path=None, title="Advertencia", config="111"):
    notify_message("normal", message, script_path, title, config)

def notify_error(message, script_path=None, title="ERROR", config="111"):
    notify_message("critical", message, script_path, title, config)

def notify_success(message, script_path=None, title="Éxito", config="111"):
    notify_message("low", message, script_path, title, config)

# Clase para manejar excepciones y mostrar notificaciones
class ErrorHandler:
    def __init__(self, script_path=None, config="111"):
        self.script_path = script_path if script_path else os.path.abspath(sys.argv[0])
        self.config = config
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            error_message = f"{exc_type.__name__}: {str(exc_val)}"
            notify_error(error_message, self.script_path, config=self.config)
            return False  # Permite que la excepción se propague
        return True

# Ejemplo de uso
if __name__ == "__main__":
    # Prueba con diferentes configuraciones de botones
    notify_info("Notificación con todos los botones", config="111")
    notify_warning("Solo botón de Codium", config="100")
    notify_error("Solo botón de carpeta", config="010")
    notify_success("Solo botón de tareas", config="001")
    
    # Ejemplo con el manejador de errores
    try:
        with ErrorHandler(config="110"):
            # Tu código aquí
            print("Este es un ejemplo")
            # Descomenta para probar el manejo de errores
            # raise ValueError("¡Este es un error de prueba!")
    except Exception as e:
        print(f"Error capturado: {e}")