import requests
import feedparser
import re
from datetime import datetime, timezone
from caldav import DAVClient
from icalendar import Event

def parse_atom_feed(feed_url):
    """Parse the Atom feed and extract album release information."""
    feed = feedparser.parse(feed_url)

    if feed.bozo:
        raise ValueError("Invalid feed format or malformed XML.")

    releases = []
    date_pattern = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")  # Match dates in YYYY-MM-DD format

    for entry in feed.entries:
        title = entry.title
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

def create_caldav_event(client_url, username, password, calendar_name, event_data):
    """Connect to CalDAV server and create events."""
    client = DAVClient(client_url, username=username, password=password)
    principal = client.principal()
    calendars = principal.calendars()

    # Find or create the specified calendar
    calendar = next((c for c in calendars if c.name == calendar_name), None)

    if calendar is None:
        print(f"Calendar '{calendar_name}' not found. Creating a new one.")
        calendar = principal.make_calendar(name=calendar_name)

    for event in event_data:
        event_title = event["title"]
        event_date = event["release_date"]

        cal_event = Event()
        cal_event.add("summary", event_title)
        cal_event.add("dtstart", datetime(event_date.year, event_date.month, event_date.day, tzinfo=timezone.utc))
        cal_event.add("dtend", datetime(event_date.year, event_date.month, event_date.day, tzinfo=timezone.utc))
        cal_event.add("description", f"Release Date for {event_title}")

        calendar.save_event(cal_event.to_ical())

if __name__ == "__main__":
    # Your Atom feed URL
    atom_feed_url = "https://muspy.com/feed?id=rvy1q943dvxvelrwvmmnxzk6ownko6"

    # CalDAV server information
    caldav_url = "https://radicale.pollete.duckdns.org/pollo/d1573ec1-e837-6918-1dfe-bc0b6c04681d/"
    username = "pollo"
    password = "iT4wZKIZ4TXU3qtI0Nzy"
    calendar_name = "discos"  # Name of your calendar

    # Parse Atom feed
    releases = parse_atom_feed(atom_feed_url)

    # Connect to CalDAV and create events
    create_caldav_event(caldav_url, username, password, calendar_name, releases)

    print("Events successfully added to your CalDAV calendar!")
