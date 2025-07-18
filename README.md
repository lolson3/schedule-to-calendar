# Schedule2Calendar

Schedule2Calendar is a Flask-based web application that parses student schedules from plain text and automatically creates events in Google Calendar. It supports lectures, discussions, and final exams with intelligent recurrence rules and event reminders.

## Features

- Converts raw text schedules into Google Calendar events
- OAuth 2.0 authentication with Google
- Redis-backed session and credential caching
- Regex-based schedule parsing with support for lectures, discussions, and finals
- Recurrence support (e.g., MWF, TR) with proper end dates
- Input sanitization and CSRF protection
- Rate limiting via Redis to prevent abuse

## Technologies

- Python (Flask, Redis, Google API Client)
- Google Calendar API
- OAuth 2.0
- Redis for session management and rate limiting

## Setup

1. **Clone the repository**  
   ```bash
   git clone https://github.com/your-username/Schedule2Calendar.git
   cd Schedule2Calendar
# schedule-to-calendar
Imports UC Davis school schedule and quickly adds all courses/discussions/exams to your Google calendar.
