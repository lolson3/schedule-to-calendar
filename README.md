# Schedule2Calendar

Schedule2Calendar is a Flask-based web application that parses student schedules from plain text and automatically creates events in Google Calendar. It supports lectures, discussions, and final exams with intelligent recurrence rules and event reminders.

## Features

* Converts raw text schedules into Google Calendar events
* OAuth 2.0 authentication with Google
* Redis-backed session and credential caching
* Regex-based schedule parsing with support for lectures, discussions, and finals
* Recurrence support (e.g., MWF, TR) with proper end dates
* Input sanitization and CSRF protection
* Rate limiting via Redis to prevent abuse
* Full containerization with Docker for easy deployment

## Technologies

* Python (Flask, Redis, Google API Client)
* Google Calendar API
* OAuth 2.0
* Redis for session management and rate limiting
* Docker for containerization

## Prerequisites

Before running the app, ensure you have:

* **Docker** and **Docker Compose** installed
* A **Google Cloud project** with the Google Calendar API enabled
* OAuth 2.0 credentials (client ID and secret)
* A `.env` file configured with the required environment variables (see below)

## Environment Variables

Create a `.env` file in the project root using the .env.example file as guidance:

> **Important:** Never commit your `.env` file or credentials to version control.

## Running with Docker

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-username/Schedule2Calendar.git
   cd Schedule2Calendar
   ```

2. **Build and start the containers:**

   ```bash
   docker-compose up --build
   ```

   This will start both the Flask app and Redis service.

3. **Access the application:**
   Open your browser and go to:

   ```
   http://localhost:5000
   ```

## Development (without Docker)

If you prefer to run the app locally:

1. **Set up a virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate   # macOS/Linux
   venv\Scripts\activate      # Windows
   ```

2. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run Redis:**
   Ensure you have Redis installed and running locally.

4. **Start the Flask app:**

   ```bash
   flask run
   ```

## Usage

1. Log in with your Google account via OAuth.
2. Paste your UC Davis schedule text into the form.
3. Preview parsed events.
4. Add them directly to your Google Calendar.

## Notes

* Events that have already passed will not be added.
* Final exams and lectures/discussions have recurrence and end dates automatically applied.
* Duplicate events are skipped automatically.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
