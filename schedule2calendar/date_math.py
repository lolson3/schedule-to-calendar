from datetime import datetime, timedelta
from pytz import timezone

def calc_recur(days, month, date):
    # SETS END DATE TO LAST OCCURING SCHEDULE DAY (i.e. in MWF, find last occuring of the three) FOR WEEK PRIOR TO FINAL DAY
    current_year = datetime.now().year
    datetime_str = f"{current_year}-{month}-{date}"
    end = datetime.strptime(datetime_str, "%Y-%b-%d")

    # Map days to weekday numbers
    day_map = {"M": 0, "T": 1, "W": 2, "R": 3, "F": 4}
    schedule_weekdays = [day_map[day] for day in days]  # Convert days to weekday numbers

    # Find the last day of the week prior to the final day
    final_week = end - timedelta(days = end.weekday() + 1)  # Previous Sunday
    last_occurrence = schedule_weekdays[-1]

    loop_check = 0

    while (final_week.weekday() != last_occurrence):
        final_week -= timedelta(days = 1)
        loop_check += 1
        if (loop_check > 31):
            raise ValueError("Infinite loop detected while searching for the last occurrence of the schedule.")

    # Format last occurrence date for RRULE
    until_date = final_week.strftime("%Y%m%dT235959Z")

    # Generate RRULE
    recurrence_days = ",".join([convert_day(day) for day in days])
    rrule = f"RRULE:FREQ=WEEKLY;BYDAY={recurrence_days};UNTIL={until_date}"

    return rrule

# UTC for Universal, America/Los_Angeles for PST
# USE Z for UTC time zone, converts to ISO 8601 - EXAMPLE FORMAT: {"dateTime": "2025-01-06T12:10:00Z", "timeZone": "UTC"}
def convert_datetime(time, apm = None, month = None, date = None, schedule_days = None):
    current_month = datetime.now().month
    current_year = datetime.now().year
    pacific = timezone('America/Los_Angeles')

    if apm != None:
        time = f"{time}{apm.lower()}"

    if month is None:
        month = current_month
    else:
        month = convert_month(month)

    # SETS DATE TO SOONEST OCCURING SCHEDULE DAY (i.e. in MWF, find soonest occuring of the three)
    if date is None and schedule_days:
        # Current date and weekday
        today = datetime.now()
        current_weekday = today.weekday()  # 0 = Monday, 6 = Sunday

        # Map schedule days to weekday numbers
        day_map = {"M": 0, "T": 1, "W": 2, "R": 3, "F": 4}
        schedule_weekdays = [day_map[day] for day in schedule_days]

        # Find the soonest occurring day
        min_delta = float('inf')
        for day in schedule_weekdays:
            delta = (day - current_weekday) % 7  # Days until the next occurrence
            if delta < min_delta:
                min_delta = delta

        # Set date to the soonest occurrence
        soonest_date = today + timedelta(days = min_delta)
        date = soonest_date.day

    # Combine into a full datetime string and parse
    datetime_str = f"{current_year}-{month}-{date} {time}"
    naive_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %I:%M%p")
    #datetime_obj = datetime.strptime(datetime_str, "%Y-%m-%d %I:%M%p")# + timedelta(hours=8) # Only use the timedelta for UTC

    # Convert to ISO 8601
    local_datetime = pacific.localize(naive_datetime, is_dst=None)
    #iso_datetime = datetime_obj.strftime("%Y-%m-%dT%H:%M:%S-08:00") #replace -08:00 with %Z for UTC

    return local_datetime.isoformat()

def convert_month(month):
    month_map = {"Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06", "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"}
    return month_map[month]

def convert_day(day):
    day_map = { "M": "MO", "T": "TU", "W": "WE", "R": "TH", "F": "FR"}
    return day_map[day]

def check_start_end(start_iso, end_iso):
    # Parse ISO 8601 times into datetime objects
    start_time = datetime.fromisoformat(start_iso)
    end_time = datetime.fromisoformat(end_iso)

    # Adjust if the start time is later than the end time (e.g., PM -> AM issue)
    if start_time > end_time:
        start_time -= timedelta(hours=12)

    # Return the adjusted times in ISO 8601 format
    return start_time.isoformat(), end_time.isoformat()