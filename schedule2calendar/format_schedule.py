from datetime import datetime

""" Formats pieces of an event so that they are more human readable """
def format_recurrence(recurrence_list):
    if not recurrence_list:
        return ""

    # Grab the first RRULE entry
    rrule = next((r for r in recurrence_list if r.startswith("RRULE:")), None)
    if not rrule:
        # Nothing standard; show the raw items
        return ", ".join(recurrence_list)

    # Strip the RRULE: prefix and parse key=value;key=value...
    body = rrule[len("RRULE:"):]
    parts = {}
    for chunk in body.split(";"):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            parts[k.upper()] = v

    freq = parts.get("FREQ", "").lower()
    interval = parts.get("INTERVAL", "1")
    byday = parts.get("BYDAY")
    until = parts.get("UNTIL")

    day_map = {"MO":"Mon","TU":"Tue","WE":"Wed","TH":"Thu","FR":"Fri","SA":"Sat","SU":"Sun"}

    pieces = []

    # Frequency & interval
    if freq == "weekly":
        pieces.append("Weekly" if interval == "1" else f"Every {interval} weeks")
        if byday:
            days = [day_map.get(d, d) for d in byday.split(",")]
            pieces.append("on " + ", ".join(days))
    elif freq == "daily":
        pieces.append("Daily" if interval == "1" else f"Every {interval} days")
    elif freq == "monthly":
        pieces.append("Monthly" if interval == "1" else f"Every {interval} months")
    elif freq == "yearly":
        pieces.append("Yearly" if interval == "1" else f"Every {interval} years")
    else:
        # Unknown/less common—just show the raw rule
        return body

    # Until date (UTC Z form)
    if until:
        try:
            dt = datetime.strptime(until, "%Y%m%dT%H%M%SZ")
            pieces.append("until " + dt.strftime("%b %d, %Y"))
        except ValueError:
            # If it’s not in the usual Z format, just append as-is
            pieces.append("until " + until)

    return " ".join(pieces)

"""Convert Google Calendar datetime string to human readable AM/PM format."""
def format_datetime(dt_str: str) -> str:
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%B %-d, %Y at %-I:%M %p")  # e.g. March 21, 2025 at 2:10 PM
    except Exception:
        return dt_str