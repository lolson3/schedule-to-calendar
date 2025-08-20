from schedule2calendar.date_math import calc_recur, convert_datetime, check_start_end
from datetime import datetime, timedelta
from flask import request, jsonify
import bleach
import re

# Fetches a schedule and sanitizes it
def get_schedule() -> str | tuple:
    data = request.json
    dirty_schedule = data.get("schedule", "")
    schedule = bleach.clean(dirty_schedule, tags = [], strip = True)

    if len(schedule) == 0:
        return "<h2>No input detected. Please enter your schedule to generate an event preview.</h2>", 400

    if len(schedule) > 1000:  # Limit to 1000 characters
        return jsonify({"message": "Input too long"}), 401

    # Validate that "schedule" exists and is a string
    if 'schedule' not in data or not isinstance(data['schedule'], str):
        return jsonify({"message": "Invalid input: 'schedule' must be a string"}), 402

    # Validate content (e.g., allow only alphanumeric, spaces, and certain punctuation)
    if not re.match(r'^[a-zA-Z0-9\s,.\-:#]+$', schedule):
        return "<h2>Invalid input. Please only enter characters that may appear in your schedule.</h2>", 403
    
    return schedule

# Regex to parse schedule
def parse_schedule(raw_text):

    # Regex pattern for extracting each course block
    course_block_pattern = r"(?P<course>[A-Z]+\s[0-9]+.\s-\s\S+\s\S+)\n(?P<details>.+?Final Exam: .+?)(?=\n[A-Z]+\s[0-9]+.\s-\s\S+\s\S+|\Z)"

    # Regex patterns for course details
    schedule_pattern = r"(?P<lecture_days>\b[MTWRF]{2,}\b) (?P<lecture_time_start>[0-9]+:[0-9]+) - (?P<lecture_time_end>[0-9]+:[0-9]+) (?P<lecture_apm>[APM]+) (?P<lecture_location>(?:[A-Z]+\s)+\S+)"
    discussion_pattern = r"(?P<discussion_day>\b[MTWRF]\b) (?P<discussion_time_start>[0-9]+:[0-9]+) - (?P<discussion_time_end>[0-9]+:[0-9]+) (?P<discussion_apm>[APM]+) (?P<discussion_location>(?:[A-Z]+\s)+\S+)"
    final_pattern = r"Final Exam: (?P<final_day>\w+). (?P<final_month>\w+).(?P<final_date>\d+).+ (?P<final_time_start>.+[apm]\b)"

    # Processes each course block
    course_blocks = re.finditer(course_block_pattern, raw_text, re.DOTALL)
    events = []
    for block in course_blocks:

        course_name = block.group("course")
        details = block.group("details")

        # Extracts details
        lecture_match = re.search(schedule_pattern, details)
        discussion_match = re.search(discussion_pattern, details)
        final_match = re.search(final_pattern, details)
        
        # Assign extracted details to variables for lecture info
        lecture_days = lecture_match.group("lecture_days") if lecture_match else None
        lecture_time_start = lecture_match.group("lecture_time_start") if lecture_match else None
        lecture_time_end = lecture_match.group("lecture_time_end") if lecture_match else None
        lecture_apm = lecture_match.group("lecture_apm") if lecture_match else None
        lecture_location = lecture_match.group("lecture_location") if lecture_match else None

        # Assign extracted details to variables for discussion info
        discussion_day = discussion_match.group("discussion_day") if discussion_match else None
        discussion_time_start = discussion_match.group("discussion_time_start") if discussion_match else None
        discussion_time_end = discussion_match.group("discussion_time_end") if discussion_match else None
        discussion_apm = discussion_match.group("discussion_apm") if discussion_match else None
        discussion_location = discussion_match.group("discussion_location") if discussion_match else None

        # Assign extracted details to variables for final exam info
        # final_day = final_match.group("final_day") if final_match else None
        final_month = final_match.group("final_month") if final_match else None
        final_date = final_match.group("final_date") if final_match else None
        final_time_start = final_match.group("final_time_start") if final_match else None
        final_time_end = (datetime.strptime(final_time_start, '%I:%M%p') + timedelta(hours = 2)).strftime('%I:%M%p')  # Assume 2-hour exam

        # Add Final Exam details to events if course & exam exist
        if (course_name and final_match):
            final_start = convert_datetime(time = final_time_start, month = final_month, date = final_date)
            final_end = convert_datetime(time = final_time_end, month = final_month, date = final_date)

            # Error checking
            final_start, final_end = check_start_end(final_start, final_end)

            events.append({
                "summary": f"{course_name} Final Exam",
                "location": f"{lecture_location}",
                "description": f"{lecture_location}",
                "start": {
                    "dateTime": final_start,
                    "timeZone": "America/Los_Angeles"
                },
                "end":  {
                    "dateTime": final_end,
                    "timeZone": "America/Los_Angeles"
                },
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": 60},      # 1 hour before
                        {"method": "popup", "minutes": 24 * 60}  # 1 day before (1440 minutes)
                    ],
                }
            })

        # Add lecture details to events if course & schedule exist
        if (course_name and lecture_match):
            lecture_start = convert_datetime(time = lecture_time_start, apm = lecture_apm, schedule_days = lecture_days)
            lecture_end = convert_datetime(time = lecture_time_end, apm = lecture_apm, schedule_days = lecture_days)

            # Error checking
            lecture_start, lecture_end = check_start_end(lecture_start, lecture_end)

            events.append({
                "summary": f"{course_name} Lecture",
                "location": lecture_location,
                "description": lecture_location,
                "start": {
                    "dateTime": lecture_start,
                    "timeZone": "America/Los_Angeles"
                },
                "end": {
                    "dateTime": lecture_end,
                    "timeZone": "America/Los_Angeles"
                },
                "recurrence": [
                    calc_recur(lecture_days, final_month, final_date)
                ],
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": 60}, # 1 hour before
                    ],
                }
            })

        # Add discussion details to events if course & discussion exist
        if (course_name and discussion_match):
            discussion_start = convert_datetime(time = discussion_time_start, apm = discussion_apm, schedule_days = discussion_day)
            discussion_end = convert_datetime(time = discussion_time_end, apm = discussion_apm, schedule_days = discussion_day)

            # Error checking
            discussion_start, discussion_end = check_start_end(discussion_start, discussion_end)

            events.append({
                "summary": f"{course_name} Discussion",
                "location": discussion_location,
                "description": discussion_location,
                "start": {
                    "dateTime": discussion_start,
                    "timeZone": "America/Los_Angeles"
                },
                "end": {
                    "dateTime": discussion_end,
                    "timeZone": "America/Los_Angeles"
                },
                "recurrence": [
                    calc_recur(discussion_day, final_month, final_date)
                ],
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": 60}, # 1 hour before
                    ],
                }
            })

    return events