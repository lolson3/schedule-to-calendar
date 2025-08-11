from datetime import datetime

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