from schedule2calendar.google_service import get_user_credentials, add_batch_callback, delete_batch_callback
from schedule2calendar.format_schedule import format_recurrence, format_datetime
from schedule2calendar.schedule_handler import get_schedule, parse_schedule
from schedule2calendar.validate import validate_event, validate_ongoing_event
from schedule2calendar.forms import ScheduleForm
from schedule2calendar.extensions import limiter

from flask import Blueprint, request, render_template, jsonify, redirect, session, url_for, current_app

from google.auth.transport.requests import Request
from googleapiclient.http import BatchHttpRequest
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow

from datetime import datetime, timedelta, timezone
from markupsafe import escape
import os

main_bp = Blueprint("main", __name__)

# Route to get render template
@main_bp.route('/', methods = ['GET', 'POST'])
def home():
    form = ScheduleForm()
    return render_template("index.html", form = form)

@main_bp.route("/login", methods = ['GET', 'POST'])
def login():
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # 🔹 Allow HTTP for local testing
    cfg = current_app.config

    """Redirects user to Google's OAuth 2.0 server for authentication."""
    flow = Flow.from_client_secrets_file(
        cfg["GOOGLE_CREDENTIALS_PATH"],
        cfg["SCOPES"],
        redirect_uri = url_for("main.callback", _external = True)
    )
    auth_url, state = flow.authorization_url(access_type = "offline", prompt = "consent")
    
    # Store the state in session to verify in callback
    session["state"] = state
    return redirect(auth_url)

@main_bp.route("/callback", methods = ['GET', 'POST'])
def callback():
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # 🔹 Allow HTTP for local testing
    cfg = current_app.config
    
    """Handles Google's OAuth 2.0 redirect and fetches credentials."""
    state = session.get("state")
    flow = Flow.from_client_secrets_file(
        cfg["GOOGLE_CREDENTIALS_PATH"],
        cfg["SCOPES"],
        state = state,
        redirect_uri=url_for("main.callback", _external = True)
    )

    flow.fetch_token(authorization_response = request.url)
    creds = flow.credentials

    # Get user's email
    service = build("oauth2", "v2", credentials = creds)
    user_info = service.userinfo().get().execute()
    email = user_info["email"]

    # Store credentials in Redis
    r = current_app.extensions["redis_client"]
    r.setex(f"user:{email}:credentials", int(timedelta(days = 7).total_seconds()), creds.to_json())

    stored_creds = r.get(f"user:{email}:credentials")

    session["email"] = email  # Store user info in session
    session.modified = True  # Force session save

    return redirect(url_for("main.home"))

# Route to handle schedule processing
@main_bp.route('/process-schedule', methods = ['GET', 'POST'])
@limiter.limit("20 per minute", override_defaults = False)  # Limit requests to prevent abuse
def process_schedule():
    try:
        if isinstance(get_schedule(), str):
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
            events_html += f"Description: {event.get('description')}<br>"
            events_html += f"Start: {escape(format_datetime(event['start']['dateTime']))} ({event['start']['timeZone']})<br>"
            events_html += f"End: {escape(format_datetime(event['end']['dateTime']))} ({event['end']['timeZone']})<br>"
            if 'recurrence' in event:
                formatted_recur = format_recurrence(event['recurrence'])
                events_html += f"Recurrence: {escape(formatted_recur)}<br>"
            ongoing = validate_ongoing_event(event)
            if not ongoing:
                events_html += f"<span style='color:red;'>This event has already ended and will not be added to the schedule.</span><br>"
            events_html += "</li><br>"
        events_html += "</ul>"

        return events_html
    
    except Exception as e:
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500
    
@main_bp.route('/add-to-calendar', methods = ['GET', 'POST'])
@limiter.limit("20 per minute", override_defaults = False)  # Limit requests to prevent abuse
def add_to_calendar():
    try:
        if isinstance(get_schedule(), str):
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
                return jsonify({"redirect": url_for("main.login")}), 200  # Force JSON response
            return jsonify({"redirect": url_for("main.login")}), 200  # Ensure always JSON

        service = build("calendar", "v3", credentials = creds)
        
        batch = service.new_batch_http_request(callback = add_batch_callback)
        added_count = 0
        
        # Check each event summary separately to avoid missing matches
        event_summaries = {event['summary'] for event in events}

        # Calculate the date 6 months ago in RFC3339 format
        six_months_ago = (datetime.now(timezone.utc) - timedelta(days = 180)).isoformat()
            
        # Fetch all events from the calendar
        events_result = service.events().list(
            calendarId = 'primary',
            maxResults = 2500,  # Ensuring all events are retrieved
            singleEvents = False,  # Include recurring events
            timeMin = six_months_ago
        ).execute()

        all_events = events_result.get('items', [])
        event_summaries = {event.get('summary') for event in all_events}

        for event in events:
            ongoing = validate_ongoing_event(event)
            if not ongoing:
                print(f"Skipping event as it has already passed: {event['summary']}")
            elif 'summary' in event and event['summary'] in event_summaries:
                print(f"Skipping duplicate event: {event['summary']}")
            else:
                batch.add(service.events().insert(calendarId = 'primary', body = event))
                print(f"Adding event to batch: {event['summary']}")
                added_count += 1

        if added_count > 0:
            batch.execute()
            print(f"Batch insertion complete: {added_count} events added.")
            return {"message": f"{added_count} new events added successfully!"}
        else:
            return {"message": "No new events were added; all events have already passed or were already scheduled."}

    except Exception as e:
        import traceback
        error_msg = f"An error occurred: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return jsonify({"message": error_msg}), 501
    
@main_bp.route('/delete-from-calendar', methods = ['GET', 'POST'])
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
                return jsonify({"redirect": url_for("main.login")}), 200  # Force JSON response
            return jsonify({"redirect": url_for("main.login")}), 200  # Ensure always JSON
        
        service = build("calendar", "v3", credentials=creds)

        # Get the list of event summaries to delete
        batch = service.new_batch_http_request(callback = delete_batch_callback)
        event_summaries = {event['summary'] for event in events}

        # Calculate the date 6 months ago in RFC3339 format
        six_months_ago = (datetime.now(timezone.utc) - timedelta(days = 180)).isoformat()

        # Fetch all events from the calendar
        events_result = service.events().list(
            calendarId = 'primary',
            maxResults = 2500,  # Ensuring all events are retrieved
            singleEvents = False,  # Include recurring events
            timeMin = six_months_ago
        ).execute()
        
        all_events = events_result.get('items', [])

        deleted_count = 0
        for event in all_events:
            if 'summary' in event and event['summary'] in event_summaries:
                if 'recurringEventId' in event:
                    # If the event is a recurrence, delete the entire recurring series
                    print(f"Deleting recurring event series: {event['summary']}")
                    batch.add(service.events().delete(calendarId = 'primary', eventId = event['recurringEventId']))
                else:
                    # Delete a normal non-recurring event
                    print(f"Deleting event: {event['summary']}")
                    batch.add(service.events().delete(calendarId='primary', eventId = event['id']))
                deleted_count += 1
                
        batch.execute()
        print(f"Batch deletion complete: {deleted_count} events added.")
        return jsonify({"message": f"Deleted {deleted_count} events from Google Calendar!"})

    except Exception as e:
        import traceback
        error_msg = f"An error occurred: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        return jsonify({"message": error_msg}), 502