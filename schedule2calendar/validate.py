from datetime import datetime, timezone
import re

def validate_event(event):
    required_fields = ["summary", "location", "start", "end"]
    for field in required_fields:
        if field not in event:
            raise ValueError(f"Missing required field: {field}")
        
    if "dateTime" not in event["start"] or "dateTime" not in event["end"]:
        raise ValueError("Missing start or end datetime in event")
    try:
        datetime.fromisoformat(event["start"]["dateTime"].replace("Z", "+00:00"))
        datetime.fromisoformat(event["end"]["dateTime"].replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Invalid ISO 8601 datetime format in event")

def _extract_until_dt(recurrence_list):
    UNTIL_RE = re.compile(r"UNTIL=(\d{8}T\d{6}Z)")
    if not recurrence_list:
        return None
    for rule in recurrence_list:
        m = UNTIL_RE.search(rule)
        if m:
            # Example: 20250314T235959Z  -> UTC
            return datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    return None
    
"""Return False if the event has already ended."""
def validate_ongoing_event(event) -> bool:
    # Recurring case
    until_dt = _extract_until_dt(event.get("recurrence"))
    if until_dt is not None:
        return datetime.now(timezone.utc) <= until_dt

    # One-off fallback
    try:
        end_str = event.get("end", {}).get("dateTime")
        if not end_str:
            return True  # no end -> include to be safe
        # Normalize possible trailing 'Z' to offset for fromisoformat
        end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        # Make sure we’re comparing tz-aware datetimes
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=timezone.utc)
        return end_dt >= datetime.now(timezone.utc)
    except Exception:
        return True  # parsing trouble -> include to be safe