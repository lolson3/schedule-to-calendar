from schedule2calendar.date_math import calc_recur, convert_datetime, check_start_end
from datetime import datetime, timedelta
from flask import request, jsonify
import unicodedata
import bleach
import html
import re

# Fetches a schedule and sanitizes it
def get_schedule() -> str | tuple:
    data = request.json
    dirty_schedule = data.get("schedule", "")
    schedule = bleach.clean(dirty_schedule, tags = [], strip = True)
    schedule = html.unescape(schedule)

    if len(schedule) == 0:
        return "<h2>No input detected. Please enter your schedule to generate an event preview.</h2>", 400

    if len(schedule) > 1000:  # Limit to 1000 characters
        return jsonify({"message": "Input too long"}), 401

    # Validate that "schedule" exists and is a string
    if 'schedule' not in data or not isinstance(data['schedule'], str):
        return jsonify({"message": "Invalid input: 'schedule' must be a string"}), 402

    # Validate content (e.g., allow only alphanumeric, spaces, and certain punctuation)
    if not re.match(r'^[a-zA-Z0-9\s,.\-:/#&()]+$', schedule):
        return "<h2>Invalid input. Please only enter characters that may appear in your schedule.</h2>", 403
    
    return schedule

# Regex to parse schedule
def parse_schedule(raw_text):
    # Normalize
    text = html.unescape(raw_text)
    text = unicodedata.normalize("NFKC", text).replace("\r\n", "\n")

    # Patterns
    header_re = re.compile(
        r'(?P<dept>[A-Z]{2,4})\s+(?P<num>\d{2,3}[A-Z]?)\s*[-–]\s*'
        r'(?P<title>[A-Za-z0-9&/()\'’:,.\- ]+?)'
        r'(?=\s+(?:[MTWRFSU]{1,5}(?:/[MTWRFSU]{1,5})*\b)'   # days token starts
        r'|\s*Final\s*Exam:'                                  # or "Final Exam:"
        r'|[ \t]*\r?\n'                                       # or newline
        r'|[A-Z]{2,4}\s+\d{2,3}[A-Z]?\s*[-–]'                 # or next header
        r'|$)'
    )

    meeting_re = re.compile(r'''
        (?P<days>\b[MTWRFSU]{1,5}(?:/[MTWRFSU]{1,5})*\b) \s+          # M, TR, M/WF, etc.
        (?P<start>\d{1,2}:\d{2}) \s*-\s* (?P<end>\d{1,2}:\d{2}) \s*   # 10:30 - 11:50
        (?P<ampm>[AaPp][Mm])? \s+                                     # optional AM/PM (applies to both)
        (?P<building>[A-Z][A-Z0-9&\-]*) \s+ (?P<room>[A-Za-z0-9\-]+)  # KEMPER 2110, 90A, etc.
    ''', re.VERBOSE | re.IGNORECASE | re.DOTALL)

    final_re = re.compile(
        r'Final\s*Exam:\s*(?P<wday>[A-Za-z]{3,})\.?\s+'
        r'(?P<month>[A-Za-z]{3,})\.?\s*(?P<date>\d{1,2})\s+at\s+'
        r'(?P<time>\d{1,2}:\d{2}\s*[AaPp][Mm])',
        re.IGNORECASE | re.DOTALL
    )

    # Scan headers first
    headers = list(header_re.finditer(text))
    events = []

    def slice_block(i):
        start = headers[i].start()
        end = headers[i+1].start() if i+1 < len(headers) else len(text)
        return text[start:end]

    for i, h in enumerate(headers):
        course_name = f"{h.group('dept')} {h.group('num')} - {h.group('title').strip()}"
        block = slice_block(i)

        # Final exam (optional)
        f = final_re.search(block)
        final_month = f.group('month') if f else None
        final_date = f.group('date') if f else None
        final_time_start = (f.group('time').replace(" ", "").upper() if f else None)

        # collect meetings first
        meetings = []
        first_location = None
        lecture_location = None  # we'll prefer this for the final

        for m in meeting_re.finditer(block):
            days = m.group('days')
            day_count = len(re.findall(r'[MTWRFSU]', days.upper()))
            meeting_type = "Lecture" if day_count > 1 else "Discussion/Lab"

            start = m.group('start')
            end = m.group('end')
            ampm = (m.group('ampm') or "").upper()
            location = f"{m.group('building').upper()} {m.group('room')}"

            if first_location is None:
                first_location = location
            if lecture_location is None and meeting_type == "Lecture":
                lecture_location = location

            meetings.append({
                "days": days,
                "start": start,
                "end": end,
                "ampm": ampm,
                "location": location,
                "meeting_type": meeting_type,
            })

        for mm in meetings:
            start_dt = convert_datetime(time=mm["start"], apm=mm["ampm"], schedule_days=mm["days"])
            end_dt   = convert_datetime(time=mm["end"],   apm=mm["ampm"], schedule_days=mm["days"])
            start_dt, end_dt = check_start_end(start_dt, end_dt)

            events.append({
                "summary": f"{course_name} ({mm['meeting_type']})",
                "location": mm["location"],
                "description": mm["location"],
                "start": {"dateTime": start_dt, "timeZone": "America/Los_Angeles"},
                "end":   {"dateTime": end_dt,   "timeZone": "America/Los_Angeles"},
                "recurrence": [calc_recur(mm["days"], final_month, final_date)],
                "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 60}]},
            })

        # final exam event (if present) uses LECTURE location, with sensible fallback
        final_location = lecture_location or first_location or ""
        if final_month and final_date and final_time_start:
            final_end = (datetime.strptime(final_time_start, "%I:%M%p") + timedelta(hours=2)).strftime("%I:%M%p")
            fs = convert_datetime(time=final_time_start, month=final_month, date=final_date)
            fe = convert_datetime(time=final_end,   month=final_month, date=final_date)
            fs, fe = check_start_end(fs, fe)
            events.append({
                "summary": f"{course_name} Final Exam",
                "location": final_location,
                "description": final_location,
                "start": {"dateTime": fs, "timeZone": "America/Los_Angeles"},
                "end":   {"dateTime": fe, "timeZone": "America/Los_Angeles"},
                "reminders": {"useDefault": False, "overrides": [
                    {"method": "popup", "minutes": 60},
                    {"method": "popup", "minutes": 24 * 60},
                ]},
            })

    return events