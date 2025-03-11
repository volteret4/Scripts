#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path

SESSIONS_DIR = Path.home() / ".tmux" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

def save_session(name):
    """Guarda la sesión actual con un nombre dado"""
    output = subprocess.run(
        ["tmux", "capture-pane", "-p", "-a", "-J", "-S", "-"],
        capture_output=True, text=True
    ).stdout
    
    session_file = SESSIONS_DIR / name
    with open(session_file, "w") as f:
        f.write(output)
    
    # También guardar la configuración de ventanas/paneles
    window_layout = subprocess.run(
        ["tmux", "list-windows", "-F", "#{window_layout}"],
        capture_output=True, text=True
    ).stdout
    
    layout_file = SESSIONS_DIR / f"{name}.layout"
    with open(layout_file, "w") as f:
        f.write(window_layout)
    
    subprocess.run(["tmux", "display-message", f"Sesión guardada como {name}"])

def load_session(name):
    """Carga una sesión guardada"""
    session_file = SESSIONS_DIR / name
    if not session_file.exists():
        subprocess.run(["tmux", "display-message", f"Sesión {name} no encontrada"])
        return
    
    # Cargar la configuración de ventanas/paneles si existe
    layout_file = SESSIONS_DIR / f"{name}.layout"
    if layout_file.exists():
        with open(layout_file, "r") as f:
            layout = f.read().strip()
            subprocess.run(["tmux", "select-layout", layout])
    
    subprocess.run(["tmux", "source-file", session_file])

def list_sessions():
    """Lista todas las sesiones guardadas"""
    sessions = [f.name for f in SESSIONS_DIR.glob("*") if not f.name.endswith(".layout")]
    return sorted(sessions)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: tmux-session [save|load|list] [nombre]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "save" and len(sys.argv) > 2:
        save_session(sys.argv[2])
    elif command == "load" and len(sys.argv) > 2:
        load_session(sys.argv[2])
    elif command == "list":
        for session in list_sessions():
            print(session)
    else:
        print("Comando no reconocido")