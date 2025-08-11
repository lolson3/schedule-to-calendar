from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from flask import session, current_app
from datetime import timedelta
import json

def get_user_credentials():
    """Retrieve stored user credentials from the database."""
    email = session.get("email")
    if not email:
        return None

    r = current_app.extensions["redis_client"]
    credentials_json = r.get(f"user:{email}:credentials")
    if not credentials_json:
        return None

    creds = Credentials.from_authorized_user_info(json.loads(credentials_json.decode("utf-8")))

    # Refresh credentials if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())  # Refresh the credentials
            r.setex(f"user:{email}:credentials", int(timedelta(days = 7).total_seconds()), creds.to_json())
        except Exception as e:
            print(f"Error refreshing credentials: {e}")
            return None

    return creds

def add_batch_callback(request_id, response, exception):
    if exception:
        print(f"Error in batch request: {exception}")
    else:
        print(f"Successfully added event: {response.get('summary')}")

def delete_batch_callback(request_id, response, exception):
    if exception:
        print(f"Error in batch delete request: {exception}")
    else:
        # Ensure response is a dictionary before accessing keys
        if isinstance(response, dict):
            print(f"Successfully deleted event: {response.get('summary', 'Unknown')}")
        else:
            print(f"Unexpected response format: {response}")