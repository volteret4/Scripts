import os
import caldav
from datetime import datetime, timedelta
from sops_env import load_sops_env

load_sops_env()

# --- CONFIGURACIÓN ---
URL = os.getenv("RADICALE_URL")
USUARIO = os.getenv("RADICALE_USERNAME")
PASSWORD = os.getenv("RADICALE_PW")
DRY_RUN = False  # Cambia a False para borrar realmente

def limpiar_duplicados_vtodo():
    try:
        client = caldav.DAVClient(url=URL, username=USUARIO, password=PASSWORD)
        calendar = client.calendar(url=URL)
        print(f"Conectado a: {calendar.url}")

        # Buscamos específicamente VTODOs
        # Nota: Algunos servidores requieren search() sin fechas para traer todos los TODOs
        todos_raw = calendar.search(todo=True)
        
        print(f"Total de tareas (VTODO) recuperadas: {len(todos_raw)}")

        agrupados = {}

        for item in todos_raw:
            try:
                vcal = item.vobject_instance
                # Verificamos que sea un VTODO
                if not hasattr(vcal, 'vtodo'):
                    continue
                
                vtodo = vcal.vtodo
                
                # Usamos el SUMMARY (título de la tarea)
                if not hasattr(vtodo, 'summary'):
                    continue
                
                titulo = str(vtodo.summary.value).strip().lower()
                
                if titulo not in agrupados:
                    agrupados[titulo] = []
                agrupados[titulo].append(item)
                
            except Exception:
                continue

        tareas_a_borrar = []

        for titulo, lista_tareas in agrupados.items():
            if len(lista_tareas) > 1:
                candidatos_grupo = []

                for item in lista_tareas:
                    vtodo = item.vobject_instance.vtodo
                    puntuacion = 0
                    
                    # --- CRITERIOS DE "CALIDAD" PARA VTODO ---
                    if hasattr(vtodo, 'summary'):     puntuacion += 1
                    if hasattr(vtodo, 'dtstart'):     puntuacion += 2
                    if hasattr(vtodo, 'due'):         puntuacion += 5  # Priorizamos la que tiene vencimiento
                    if hasattr(vtodo, 'description'): puntuacion += 1
                    if hasattr(vtodo, 'priority'):    puntuacion += 1
                    if hasattr(vtodo, 'status'):      puntuacion += 1
                    
                    candidatos_grupo.append((puntuacion, item))

                # Ordenar: la más completa primero
                candidatos_grupo.sort(key=lambda x: x[0], reverse=True)
                
                # Mantener la mejor (índice 0), borrar el resto
                for i in range(1, len(candidatos_grupo)):
                    tareas_a_borrar.append(candidatos_grupo[i][1])

        if not tareas_a_borrar:
            print("No se encontraron duplicados.")
            return

        print(f"\n--- SE HAN ENCONTRADO {len(tareas_a_borrar)} TAREAS DUPLICADAS ---")
        
        for t_del in tareas_a_borrar:
            nombre = t_del.vobject_instance.vtodo.summary.value
            if DRY_RUN:
                print(f"[SIMULACIÓN] Se borraría: {nombre}")
            else:
                print(f"[BORRANDO] {nombre}...")
                t_del.delete()

        if DRY_RUN:
            print("\n*** MODO SIMULACIÓN ACTIVADO. Nada se ha borrado aún. ***")

    except Exception as e:
        print(f"Error general: {e}")

if __name__ == "__main__":
    limpiar_duplicados_vtodo()
