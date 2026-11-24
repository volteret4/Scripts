#!/usr/bin/env python
#
# Script Name: import json.py 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#



import json
from datetime import datetime

def convertir_a_taskwarrior(entrada):
    # Carga el JSON de entrada
    entrada_json = json.loads(entrada)

    # Mapea los campos a los del formato de Taskwarrior
    tarea = {
        "id": 7,  # Puedes establecer este valor según tus necesidades
        "description": entrada_json["description"],
        "entry": datetime.utcfromtimestamp(int(entrada_json["entry"])).strftime("%Y%m%dT%H%M%SZ"),
        "modified": datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
        "status": entrada_json["status"],
        "uuid": "b25ee441-bd89-474c-9d56-c3cc0ed85287",  # Puedes generar un UUID único
        "tags": ["tasker"],  # Puedes ajustar las etiquetas según tus necesidades
        "urgency": 2.8  # Puedes ajustar la urgencia según tus necesidades
    }

    # Convierte la tarea a formato JSON
    tarea_json = json.dumps(tarea, indent=2)

    return tarea_json

# JSON de entrada
entrada_json = '{"status":"pending","entry":"1667516400","description":"Repasar Proyecto AUTOSHARE de Tasker"}'

# Convierte a formato Taskwarrior
tarea_warrior = convertir_a_taskwarrior(entrada_json)

print(tarea_warrior)