from datetime import datetime
from zoneinfo import ZoneInfo

from icalendar import Calendar

from queer_events_calendar import PartyEvent, build_calendar, deduplicate, oh_my_rockness


def sample():
    return PartyEvent("source", "one", "Queer Party", "2026-11-01T22:00:00-05:00", "2026-11-02T02:00:00-05:00",
        "Venue", "New York, NY", "New York", "Organizer", "https://example.com/event", "Public description")


def test_calendar_is_valid_and_keeps_local_time():
    parsed = Calendar.from_ical(build_calendar([sample()], datetime(2026, 10, 10, tzinfo=ZoneInfo("UTC"))))
    event = next(component for component in parsed.walk() if component.name == "VEVENT")
    assert str(event["SUMMARY"]) == "Queer Party"
    assert event.decoded("DTSTART").hour == 22
    assert "Organizer" in str(event["DESCRIPTION"])


def test_deduplicate():
    assert len(deduplicate([sample(), sample()])) == 1


class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.status_code = 200

    def raise_for_status(self):
        pass


class FakeClient:
    def __init__(self, pages):
        self.pages = pages
        self.requested = []

    def get(self, url):
        page = int(url.rsplit("=", 1)[-1])
        self.requested.append(page)
        return FakeResponse(self.pages[page])


def listing(show_id, day, band):
    return f"""
Track Show
 Mon 10/{day} 8:00PM
[{band}](https://www.ohmyrockness.com/bands/{band.casefold()})
[Venue](https://www.ohmyrockness.com/venues/venue)
[more info »](https://www.ohmyrockness.com/shows/{show_id}-{band.casefold()}-venue)
"""


def test_fetches_every_pagination_page():
    pages = {
        1: listing(101, 12, "First") + "\n[Last »](https://www.ohmyrockness.com/shows?page=3)",
        2: listing(102, 13, "Second"),
        3: listing(103, 14, "Third"),
    }
    client = FakeClient(pages)
    events = oh_my_rockness(client, datetime(2026, 10, 12, tzinfo=ZoneInfo("America/New_York")), datetime(2027, 10, 12).date())
    assert {event.source_id for event in events} == {"101", "102", "103"}
    assert sorted(client.requested) == [1, 2, 3]
