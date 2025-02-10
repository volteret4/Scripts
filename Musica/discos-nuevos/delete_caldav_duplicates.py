import os
from datetime import datetime
from caldav import DAVClient
from icalendar import Calendar
from dotenv import load_dotenv

load_dotenv()

def get_calendar(client_url, username, password, calendar_name):
    """Connect to CalDAV and retrieve the calendar."""
    client = DAVClient(client_url, username=username, password=password)
    principal = client.principal()
    calendars = principal.calendars()

    # Buscar el calendario por nombre
    calendar = next((c for c in calendars if c.name == calendar_name), None)
    if calendar is None:
        print(f"Calendar '{calendar_name}' not found.")
        return None

    return calendar

def find_duplicate_events(calendar):
    """Find duplicate events in the calendar."""
    events_by_key = {}  # Diccionario para almacenar eventos únicos (key = (title, date))
    duplicate_events = []  # Lista de eventos duplicados para eliminar

    for event in calendar.events():
        try:
            cal = Calendar.from_ical(event.data)
            for component in cal.walk():
                if component.name == "VEVENT":
                    title = str(component.get("SUMMARY"))
                    dtstart = component.get("DTSTART").dt

                    if isinstance(dtstart, datetime):
                        dtstart = dtstart.date()  # Convertir a objeto date

                    key = (title, dtstart)

                    if key in events_by_key:
                        duplicate_events.append(event)  # Marcar como duplicado
                    else:
                        events_by_key[key] = event  # Guardar como único

        except Exception as e:
            print(f"Error parsing event: {e}")

    return duplicate_events

def remove_duplicate_events(calendar):
    """Remove duplicate events from the calendar."""
    duplicate_events = find_duplicate_events(calendar)
    
    if not duplicate_events:
        print("No duplicate events found.")
        return
    
    for event in duplicate_events:
        try:
            event.delete()
            print(f"Deleted duplicate event: {event.url}")
        except Exception as e:
            print(f"Error deleting event: {e}")

if __name__ == "__main__":
    # CalDAV server information
    caldav_url = "https://radicale.pollete.duckdns.org/pollo/d1573ec1-e837-6918-1dfe-bc0b6c04681d/"
    username = "pollo"
    password = os.getenv("RADICALE_PW")
    calendar_name = "discos"  # Nombre de tu calendario

    calendar = get_calendar(caldav_url, username, password, calendar_name)

    if calendar:
        remove_duplicate_events(calendar)
