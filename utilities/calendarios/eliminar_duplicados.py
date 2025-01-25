import caldav
from icalendar import Calendar
from collections import defaultdict
from dotenv import load_dotenv
import os

load_dotenv()

# Configuración del servidor CalDAV
CALDAV_URL = "https://radicale.pollete.duckdns.org/pollo/987a0de8-661b-c19d-41c1-4bd065bc29e0/" #turnos
USERNAME = "pollo"
PASSWORD = os.getenv('RADICALE_PW')

# Conectar al servidor CalDAV
client = caldav.DAVClient(url=CALDAV_URL, username=USERNAME, password=PASSWORD)

# Acceder a los calendarios
principal = client.principal()
calendars = principal.calendars()

if not calendars:
    print("No se encontraron calendarios.")
    exit()

# Lista para guardar eventos eliminados
deleted_events = []

# Analizar eventos duplicados
for calendar in calendars:
    print(f"Revisando calendario: {calendar.name}")

    # Almacenar eventos por su resumen (título) y hora de inicio
    events_by_key = defaultdict(list)
    for event in calendar.events():
        raw_data = event.data
        ical = Calendar.from_ical(raw_data)
        
        for component in ical.walk():
            if component.name == "VEVENT":
                summary = component.get("SUMMARY", "Sin título")
                start = component.get("DTSTART").dt
                key = (summary, start)
                events_by_key[key].append(event)

    # Identificar y eliminar duplicados
    for key, events in events_by_key.items():
        if len(events) > 1:
            print(f"Duplicados encontrados para {key}: {len(events)} eventos")
            for duplicate_event in events[1:]:
                deleted_events.append({
                    "calendar": calendar.name,
                    "summary": key[0],
                    "start": key[1],
                    "raw_data": duplicate_event.data
                })
                duplicate_event.delete()

# Mostrar los eventos eliminados
if deleted_events:
    print("\nEventos eliminados:")
    for event in deleted_events:
        print(f"- Calendario: {event['calendar']}, Título: {event['summary']}, Inicio: {event['start']}")
else:
    print("\nNo se encontraron eventos duplicados.")

print("Procesamiento completado.")
