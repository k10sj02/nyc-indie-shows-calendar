from datetime import datetime
from zoneinfo import ZoneInfo

from icalendar import Calendar

from queer_events_calendar import PartyEvent, build_calendar, deduplicate


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
