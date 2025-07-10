
#!/usr/bin/env python
#
# Script Name: add_release_calendar.py
# Description: Actualizar calendario caldav con los nuevos discos que ofrece el rss de muspy
# Author: volteret4
# Repository: https://github.com/volteret4/
# License:
# Notes:
#   Dependencies:  - python3, caldav, dotenv, feedparser
#

import requests
import feedparser
import re
from datetime import datetime, timezone, date
from caldav import DAVClient
from icalendar import Event, Calendar
from dotenv import load_dotenv
import os

load_dotenv()

def parse_atom_feed(feed_url):
    """Parse the Atom feed and extract album release information."""
    feed = feedparser.parse(feed_url)

    if feed.bozo:
        raise ValueError("Invalid feed format or malformed XML.")

    releases = []
    date_pattern = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")  # Match dates in YYYY-MM-DD format

    for entry in feed.entries:
        title = entry.title.strip()  # Limpiar espacios extra
        content = entry.summary

        # Search for date in the content
        match = date_pattern.search(content)
        if not match:
            print(f"Skipping entry with invalid date: {content}")
            continue

        release_date_str = match.group()
        try:
            release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
        except ValueError:
            print(f"Skipping entry with unparsable date: {release_date_str}")
            continue

        releases.append({"title": title, "release_date": release_date})

    return releases

def get_existing_events(calendar):
    """Retrieve existing events from the calendar to avoid duplicates."""
    existing_events = set()

    for event in calendar.events():
        try:
            cal = Calendar.from_ical(event.data)
            for component in cal.walk():
                if component.name == "VEVENT":
                    summary = str(component.get("SUMMARY")).strip()
                    dtstart = component.get("DTSTART").dt

                    # Convert datetime to date if necessary
                    if isinstance(dtstart, datetime):
                        dtstart = dtstart.date()

                    existing_events.add((summary, dtstart))
        except Exception as e:
            print(f"Error parsing existing event: {e}")

    return existing_events

def create_caldav_event(client_url, username, password, calendar_name, event_data):
    """Connect to CalDAV and create events if they do not already exist."""
    client = DAVClient(client_url, username=username, password=password)
    principal = client.principal()
    calendars = principal.calendars()

    # Buscar el calendario por nombre
    calendar = next((c for c in calendars if c.name == calendar_name), None)
    if calendar is None:
        print(f"Calendar '{calendar_name}' not found. Creating a new one.")
        calendar = principal.make_calendar(name=calendar_name)

    # Obtener eventos existentes para evitar duplicados
    existing_events = get_existing_events(calendar)

    for event in event_data:
        event_title = event["title"].strip()
        event_date = event["release_date"]

        # Verificar si el evento ya existe
        if (event_title, event_date) in existing_events:
            print(f"Skipping duplicate event: {event_title} ({event_date})")
            continue

        # Crear nuevo evento
        cal_event = Event()
        cal_event.add("summary", event_title)
        cal_event.add("dtstart", datetime(event_date.year, event_date.month, event_date.day, tzinfo=timezone.utc))
        cal_event.add("dtend", datetime(event_date.year, event_date.month, event_date.day, tzinfo=timezone.utc))
        cal_event.add("description", f"Release Date for {event_title}")

        calendar.save_event(cal_event.to_ical())
        print(f"Added event: {event_title} ({event_date})")

# ELIMINAR DUPLICADOS
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
    # Tu URL de Atom Feed
    atom_feed_url = "https://muspy.com/feed?id=rvy1q943dvxvelrwvmmnxzk6ownko6"

    # Información del servidor CalDAV
    caldav_url = "https://radicale.pollete.duckdns.org/pollo/d1573ec1-e837-6918-1dfe-bc0b6c04681d/"
    username = "pollo"
    password = os.getenv("RADICALE_PW")
    calendar_name = "discos"

    # Parsear el feed Atom
    releases = parse_atom_feed(atom_feed_url)

    # Conectar a CalDAV y agregar eventos sin duplicados
    create_caldav_event(caldav_url, username, password, calendar_name, releases)

    print("Events successfully processed!")

    # Duplicados por tabaco
    calendar = get_calendar(caldav_url, username, password, calendar_name)

    if calendar:
        remove_duplicate_events(calendar)
    print("Duplicados por tabaco.")