from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from icalendar import Calendar, Event

SOURCE_URL = "https://www.ohmyrockness.com/shows"
READABLE_URL = f"https://r.jina.ai/{SOURCE_URL}"
PRIVATE_FEED_PATH = "f/808f3ed8525e36f67806e02629fb91750326eb12b842b108"
NY_TZ = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


@dataclass(frozen=True)
class PartyEvent:
    source: str
    source_id: str
    title: str
    start: str
    end: str | None
    venue: str
    address: str
    city: str
    organizer: str
    url: str
    description: str = ""
    status: str = "CONFIRMED"

    @property
    def uid(self) -> str:
        digest = hashlib.sha256(f"{self.source}|{self.source_id}".encode()).hexdigest()[:28]
        return f"{digest}@nyc-indie-shows-calendar"


def oh_my_rockness(client: httpx.Client, now: datetime, final_day: date) -> list[PartyEvent]:
    response = client.get(READABLE_URL)
    response.raise_for_status()
    events: list[PartyEvent] = []
    for block in re.split(r"\nTrack Show\s*\n", response.text):
        date_match = re.search(r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})(AM|PM)\b", block, re.I)
        info_match = re.search(r"\[more info »\]\((https://www\.ohmyrockness\.com/shows/(\d+)[^)]+)\)", block, re.I)
        if not date_match or not info_match:
            continue
        month, day, hour, minute, suffix = date_match.groups()
        year = now.year + (int(month) < now.month - 6)
        hour = int(hour) % 12 + (12 if suffix.casefold() == "pm" else 0)
        begins = datetime(year, int(month), int(day), hour, int(minute), tzinfo=NY_TZ)
        if not now.date() <= begins.date() <= final_day:
            continue
        links = re.findall(r"\[([^\]]+)\]\((https://www\.ohmyrockness\.com/(?:bands|venues)/[^)]+)\)", block)
        bands = [label.strip() for label, url in links if "/bands/" in url]
        venues = [label.strip() for label, url in links if "/venues/" in url]
        if not bands or not venues:
            continue
        flags = []
        if re.search(r"\bFREE\b", block, re.I):
            flags.append("Free show")
        age = re.search(r"\b(?:all ages|\d{2}\+)\b", block, re.I)
        if age:
            flags.append(age.group(0))
        url, show_id = info_match.groups()
        events.append(PartyEvent(
            "oh-my-rockness", show_id, " + ".join(dict.fromkeys(bands)), begins.isoformat(), None,
            venues[0], f"{venues[0]}, New York, NY", "New York", "Oh My Rockness listing", url,
            "; ".join(flags),
        ))
    if not events:
        raise RuntimeError("No current Oh My Rockness listings found")
    return events


def deduplicate(events: list[PartyEvent]) -> list[PartyEvent]:
    unique = {}
    for item in events:
        title = "".join(c for c in unicodedata.normalize("NFKD", item.title.casefold()) if c.isalnum())
        unique.setdefault((title, item.start[:16], item.venue.casefold()), item)
    return list(unique.values())


def merge_state(current: list[PartyEvent], path: Path, now: datetime, successful: set[str]) -> list[PartyEvent]:
    old = {}
    if path.exists():
        try:
            old = json.loads(path.read_text()).get("events", {})
        except (OSError, json.JSONDecodeError):
            pass
    merged = {item.uid: {**asdict(item), "missing_runs": 0} for item in current}
    for uid, item in old.items():
        if uid in merged:
            continue
        missing = int(item.get("missing_runs", 0)) + (item.get("source") in successful)
        if date.fromisoformat(item["start"][:10]) >= now.date() - timedelta(days=1):
            merged[uid] = {**item, "missing_runs": missing, "status": "CANCELLED" if missing >= 2 else item.get("status", "CONFIRMED")}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"updated": now.isoformat(), "events": merged}, ensure_ascii=False, indent=2) + "\n")
    return [PartyEvent(**{key: value for key, value in item.items() if key != "missing_runs"}) for item in merged.values()]


def build_calendar(events: list[PartyEvent], generated: datetime) -> bytes:
    calendar = Calendar()
    calendar.add("prodid", "-//NYC Indie Shows Calendar//EN")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "PUBLISH")
    calendar.add("x-wr-calname", "NYC Indie Shows — Oh My Rockness")
    calendar.add("refresh-interval", timedelta(hours=6), parameters={"VALUE": "DURATION"})
    for item in sorted(events, key=lambda value: (value.start, value.title)):
        component = Event()
        component.add("uid", item.uid)
        component.add("dtstamp", generated.astimezone(UTC))
        component.add("dtstart", datetime.fromisoformat(item.start))
        component.add("summary", item.title)
        component.add("location", item.address)
        component.add("description", "\n".join(filter(None, [item.description, f"Organizer: {item.organizer}", "Confirm details before attending.", f"Original listing: {item.url}"])))
        component.add("url", item.url)
        component.add("status", item.status)
        component.add("categories", "Music,Indie,Concert")
        calendar.add_component(component)
    return calendar.to_ical()


def main() -> None:
    root = Path.cwd()
    now = datetime.now(NY_TZ)
    final_day = now.date() + timedelta(days=365)
    client = httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 (compatible; NYCIndieShowsCalendar/1.0)"})
    errors, successful = {}, set()
    try:
        current = oh_my_rockness(client, now, final_day)
        successful.add("oh-my-rockness")
    except Exception as exc:
        current = []
        errors["oh-my-rockness"] = str(exc)
    if not current and not (root / "data/state.json").exists():
        raise RuntimeError("No current events found; refusing to publish an empty calendar")
    events = merge_state(deduplicate(current), root / "data/state.json", now, successful)
    public = root / "public" / PRIVATE_FEED_PATH
    public.mkdir(parents=True, exist_ok=True)
    (public / "calendar.ics").write_bytes(build_calendar(events, now))
    status = {
        "generated": now.isoformat(),
        "count": sum(item.status != "CANCELLED" for item in events),
        "cancelled": sum(item.status == "CANCELLED" for item in events),
        "sources": {"oh-my-rockness": len(current)},
        "notes": {"source_access": "Schedule data is read through a public text representation because the source site blocks automated requests."},
        "errors": errors,
    }
    (public / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(status, ensure_ascii=False))
