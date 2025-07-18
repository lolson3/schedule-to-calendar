from flask import Flask, request, render_template, jsonify, redirect, session, url_for
from flask_limiter.util import get_remote_address
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired
from datetime import datetime, timedelta
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_session import Session
from flask_wtf import FlaskForm
from dotenv import load_dotenv
from pytz import timezone
import os.path
import bleach
import redis
import json
import re

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import BatchHttpRequest

app = Flask(__name__)
load_dotenv()
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")  # Use localhost instead of redis
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)  # Add password if needed

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=REDIS_PORT,
    db=0,
    password=REDIS_PASSWORD,
    ssl=True if os.getenv("REDIS_USE_SSL", "false").lower() == "true" else False)

app.config["WTF_CSRF_SECRET_KEY"] = os.getenv("WTF_CSRF_SECRET_KEY")
csrf = CSRFProtect(app) # Enables CSRF protection

# Initializes connection to Redis
app.config["SESSION_TYPE"] = "redis"
app.config["SESSION_PERMANENT"] = True
app.config["SESSION_USE_SIGNER"] = True
app.config["SESSION_KEY_PREFIX"] = "flask_session:"
app.config["SESSION_REDIS"] = redis_client
app.config["SESSION_COOKIE_SECURE"] = False  # Forces HTTPS when True
app.config["SESSION_COOKIE_HTTPONLY"] = True # Prevents JS from accessing session cookies
app.config["SESSION_COOKIE_SAMESITE"] = "Lax" # Mitigates CSRF attacks
app.config["SESSION_REFRESH_EACH_REQUEST"] = True  # Extends session expiration
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)# Sessions expire after 3 days
Session(app)

if REDIS_PASSWORD:
    redis_uri = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
else:
    redis_uri = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

# Initializes rate limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri=redis_uri,  # Use correctly formatted Redis URI
    storage_options={"socket_connect_timeout": 30},
    strategy="fixed-window",
    default_limits=["200 per day", "50 per hour"],
)

SCOPES = os.getenv("SCOPES").split()
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS_PATH")

class ScheduleForm(FlaskForm):
    schedule = TextAreaField("Schedule", validators=[DataRequired()])
    submit = SubmitField("Preview Schedule")

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
        final_time_end = (datetime.strptime(final_time_start, '%I:%M%p') + timedelta(hours=2)).strftime('%I:%M%p')  # Assume 2-hour exam

        # Add Final Exam details to events if course & exam exist
        if (course_name and final_match):
            final_start = convert_datetime(time=final_time_start, month=final_month, date=final_date)
            final_end = convert_datetime(time=final_time_end, month=final_month, date=final_date)

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
                        {"method": "popup", "minutes": 60},      # 1 hour before (60 minutes)
                        {"method": "popup", "minutes": 24 * 60}  # 1 day before (1440 minutes)
                    ],
                }
            })

        # Add lecture details to events if course & schedule exist
        if (course_name and lecture_match):
            lecture_start = convert_datetime(time=lecture_time_start, apm=lecture_apm, schedule_days=lecture_days)
            lecture_end = convert_datetime(time=lecture_time_end, apm=lecture_apm, schedule_days=lecture_days)

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
                        {"method": "popup", "minutes": 60},      # 1 hour before (60 minutes)
                    ],
                }
            })

        # Add discussion details to events if course & discussion exist
        if (course_name and discussion_match):
            discussion_start = convert_datetime(time=discussion_time_start, apm=discussion_apm, schedule_days=discussion_day)
            discussion_end = convert_datetime(time=discussion_time_end, apm=discussion_apm, schedule_days=discussion_day)

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
                        {"method": "popup", "minutes": 60},       # 1 hour before (60 minutes)
                    ],
                }
            })

    return events

def calc_recur(days, month, date):
    # SETS END DATE TO LAST OCCURING SCHEDULE DAY (i.e. in MWF, find last occuring of the three) FOR WEEK PRIOR TO FINAL DAY
    current_year = datetime.now().year
    datetime_str = f"{current_year}-{month}-{date}"
    end = datetime.strptime(datetime_str, "%Y-%b-%d")

    # Map days to weekday numbers
    day_map = {"M": 0, "T": 1, "W": 2, "R": 3, "F": 4}
    schedule_weekdays = [day_map[day] for day in days]  # Convert days to weekday numbers

    # Find the last day of the week prior to the final day
    final_week = end - timedelta(days=end.weekday() + 1)  # Previous Sunday
    last_occurrence = schedule_weekdays[-1]

    loop_check = 0

    while (final_week.weekday() != last_occurrence):
        final_week -= timedelta(days=1)
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
def convert_datetime(time, apm=None, month=None, date=None, schedule_days=None):
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
        soonest_date = today + timedelta(days=min_delta)
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
    
def get_schedule() -> str | tuple:
    data = request.json
    dirty_schedule = data.get("schedule", "")
    schedule = bleach.clean(dirty_schedule, tags=[], strip=True)

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

def get_user_credentials():
    """Retrieve stored user credentials from the database."""
    email = session.get("email")
    if not email:
        return None

    credentials_json = redis_client.get(f"user:{email}:credentials")
    if not credentials_json:
        return None

    creds = Credentials.from_authorized_user_info(json.loads(credentials_json.decode("utf-8")))

    # Refresh credentials if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())  # Refresh the credentials
            redis_client.setex(f"user:{email}:credentials", int(timedelta(days=7).total_seconds()), creds.to_json())
        except Exception as e:
            print(f"Error refreshing credentials: {e}")
            return None

    return creds

@app.route("/login", methods=['GET', 'POST'])
def login():
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # 🔹 Allow HTTP for local testing
    """Redirects user to Google's OAuth 2.0 server for authentication."""
    flow = Flow.from_client_secrets_file(
        GOOGLE_CREDENTIALS,
        SCOPES,
        redirect_uri=url_for("callback", _external=True)
    )
    auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")
    
    # Store the state in session to verify in callback
    session["state"] = state
    return redirect(auth_url)

@app.route("/callback", methods=['GET', 'POST'])
def callback():
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # 🔹 Allow HTTP for local testing
    """Handles Google's OAuth 2.0 redirect and fetches credentials."""
    state = session.get("state")
    flow = Flow.from_client_secrets_file(
        GOOGLE_CREDENTIALS,
        SCOPES,
        state=state,
        redirect_uri=url_for("callback", _external=True)
    )

    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials

    # Get user's email
    service = build("oauth2", "v2", credentials=creds)
    user_info = service.userinfo().get().execute()
    email = user_info["email"]

    # Store credentials in Redis
    redis_client.setex(f"user:{email}:credentials", int(timedelta(days=7).total_seconds()), creds.to_json())

    stored_creds = redis_client.get(f"user:{email}:credentials")

    session["email"] = email  # Store user info in session
    session.modified = True  # Force session save

    return redirect(url_for("home"))

# Route to get render template
@app.route('/', methods=['GET', 'POST'])
def home():
    form = ScheduleForm()
    return render_template("index.html", form=form)

# Route to handle schedule processing
@app.route('/process-schedule', methods=['GET', 'POST'])
@limiter.limit("20 per minute", override_defaults=False)  # Limit requests to prevent abuse
def process_schedule():
    try:
        if isinstance(get_schedule(),str):
            schedule = get_schedule()
        else:
            return get_schedule()

        events = parse_schedule(schedule)

        # Check if events list is empty
        if not events:
            # Return a message if no events were found
            return "<h2>No events were found in the provided schedule. Please check your input and try again.</h2>"

        events_html = "<h2>Events Preview</h1><ul>"
        for event in events:
            events_html += f"<strong>{event.get('summary')}</strong><br>"
            events_html += f"Location: {event.get('location')}<br>"
            events_html += f"Start: {event['start']['dateTime']} ({event['start']['timeZone']})<br>"
            events_html += f"End: {event['end']['dateTime']} ({event['end']['timeZone']})<br>"
            events_html += f"Description: {event.get('description')}<br>"
            if 'recurrence' in event:
                events_html += f"Recurrence: {', '.join(event['recurrence'])}<br>"
            events_html += "</li><br>"
        events_html += "</ul>"

        return events_html
    
    except Exception as e:
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500

def add_batch_callback(request_id, response, exception):
    if exception:
        print(f"Error in batch request: {exception}")
    else:
        print(f"Successfully added event: {response.get('summary')}")

@app.route('/add-to-calendar', methods=['GET', 'POST'])
@limiter.limit("20 per minute", override_defaults=False)  # Limit requests to prevent abuse
def add_to_calendar():
    try:
        if isinstance(get_schedule(),str):
            schedule = get_schedule()
        else:
            return get_schedule()

        events = parse_schedule(schedule)

        if not events:
            return "<h1>No events found in the provided schedule. Please check your input and try again.</h1>"
        
        # Validate events before adding
        for event in events:
            validate_event(event)

        """Adds an event using stored user credentials."""
        creds = get_user_credentials()
        if not creds:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"redirect": url_for("login")}), 200  # Force JSON response
            return jsonify({"redirect": url_for("login")}), 200  # Ensure always JSON

        service = build("calendar", "v3", credentials=creds)
        
        batch = service.new_batch_http_request(callback=add_batch_callback)
        added_count = 0
        
        # Check each event summary separately to avoid missing matches
        event_summaries = {event['summary'] for event in events}

        # Calculate the date 6 months ago in RFC3339 format
        six_months_ago = (datetime.utcnow() - timedelta(days=180)).isoformat() + "Z"  # Adding 'Z' ensures UTC time
            
        # Fetch all events from the calendar
        events_result = service.events().list(
            calendarId='primary',
            maxResults=2500,  # Ensuring all events are retrieved
            singleEvents=False,  # Include recurring events
            timeMin=six_months_ago
        ).execute()

        all_events = events_result.get('items', [])
        event_summaries = {event.get('summary') for event in all_events}

        for event in events:
            if 'summary' in event and event['summary'] in event_summaries:
                print(f"Skipping duplicate event: {event['summary']}")
            else:
                batch.add(service.events().insert(calendarId='primary', body=event))
                print(f"Adding event to batch: {event['summary']}")
                added_count += 1

        if added_count > 0:
            batch.execute()
            print(f"Batch insertion complete: {added_count} events added.")
            return {"message": f"{added_count} new events added successfully!"}
        else:
            return {"message": "No new events were added; all events already exist."}

    except Exception as e:
        import traceback
        error_msg = f"An error occurred: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return jsonify({"message": error_msg}), 501
    
def delete_batch_callback(request_id, response, exception):
    if exception:
        print(f"Error in batch delete request: {exception}")
    else:
        # Ensure response is a dictionary before accessing keys
        if isinstance(response, dict):
            print(f"Successfully deleted event: {response.get('summary', 'Unknown')}")
        else:
            print(f"Unexpected response format: {response}")
    
@app.route('/delete-from-calendar', methods=['GET', 'POST'])
@limiter.limit("20 per minute", override_defaults=False)  # Limit requests to prevent abuse
def delete_from_calendar():
    try:
        if isinstance(get_schedule(),str):
            schedule = get_schedule()
        else:
            return get_schedule()

        events = parse_schedule(schedule)

        if not events:
            return "<h1>No events found in the provided schedule. Please check your input and try again.</h1>"
        
        # Validate events before adding
        for event in events:
            validate_event(event)

        """Adds an event using stored user credentials."""
        creds = get_user_credentials()
        if not creds:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"redirect": url_for("login")}), 200  # Force JSON response
            return jsonify({"redirect": url_for("login")}), 200  # Ensure always JSON
        
        service = build("calendar", "v3", credentials=creds)

        # Get the list of event summaries to delete
        batch = service.new_batch_http_request(callback=delete_batch_callback)
        event_summaries = {event['summary'] for event in events}

        # Calculate the date 6 months ago in RFC3339 format
        six_months_ago = (datetime.utcnow() - timedelta(days=180)).isoformat() + "Z"  # Adding 'Z' ensures UTC time

        # Fetch all events from the calendar
        events_result = service.events().list(
            calendarId='primary',
            maxResults=2500,  # Ensuring all events are retrieved
            singleEvents=False,  # Include recurring events
            timeMin=six_months_ago
        ).execute()
        
        all_events = events_result.get('items', [])

        deleted_count = 0
        for event in all_events:
            if 'summary' in event and event['summary'] in event_summaries:
                if 'recurringEventId' in event:
                    # If the event is a recurrence, delete the entire recurring series
                    print(f"Deleting recurring event series: {event['summary']}")
                    batch.add(service.events().delete(calendarId='primary', eventId=event['recurringEventId']))
                else:
                    # Delete a normal non-recurring event
                    print(f"Deleting event: {event['summary']}")
                    batch.add(service.events().delete(calendarId='primary', eventId=event['id']))
                deleted_count += 1
                
        batch.execute()
        print(f"Batch deletion complete: {deleted_count} events added.")
        return jsonify({"message": f"Deleted {deleted_count} events from Google Calendar!"})

    except Exception as e:
        import traceback
        error_msg = f"An error occurred: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return jsonify({"message": error_msg}), 502

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)