import logging
import json
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import azure.functions as func
import os
import pytz

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Constants
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'luminlabsdemo@gmail.com'

# Define AEST time zone
AEST = pytz.timezone('Australia/Brisbane')

def get_calendar_service():
    """Initialize Google Calendar API service."""
    private_key_raw = os.getenv("GOOGLE_PRIVATE_KEY", "")
    private_key_processed = private_key_raw.replace("\\n", "\n").strip()

    service_account_info = {
        "type": "service_account",
        "project_id": os.getenv("GOOGLE_PROJECT_ID"),
        "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
        "private_key": private_key_processed,
        "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{os.getenv('GOOGLE_CLIENT_EMAIL')}"
    }

    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES)
    return build('calendar', 'v3', credentials=credentials, cache_discovery=False)

def add_calendar_entry(calendar_id, summary, description, start_time, end_time):
    """Add an event to Google Calendar."""
    service = get_calendar_service()
    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time,
            'timeZone': 'Australia/Brisbane',
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'Australia/Brisbane',
        }
    }
    try:
        return service.events().insert(calendarId=calendar_id, body=event).execute()
    except HttpError as e:
        logger.error(f"Error adding calendar entry: {e}")
        raise e

def main(req: func.HttpRequest) -> func.HttpResponse:
    """Handle slot booking requests."""
    try:
        # Parse and validate request
        req_body = req.get_json()
        sender_id = req_body.get('sender_id')
        preferred_date_time = req_body.get('preferredDateTime')
        duration_minutes = req_body.get('durationMinutes')
        client_name = req_body.get('clientName')
        service_name = req_body.get('service_name')  # Changed from 'service' to 'service_name'
        phone_number = req_body.get('phone_number')  # Changed to match argument naming
        email = req_body.get('email')  # Changed to match argument naming
        time_zone = req_body.get('timeZone', 'Australia/Brisbane')

        if not all([sender_id, preferred_date_time, duration_minutes, client_name, service_name, phone_number, email]):
            return func.HttpResponse(
                json.dumps({
                    "error": "All parameters are required: sender_id, preferredDateTime, durationMinutes, clientName, service_name, phone_number, email."
                }),
                status_code=400,
                mimetype="application/json"
            )

        logging.info(f"Booking slot for sender_id: {sender_id}")

        # Parse preferred date and time
        try:
            start_time = datetime.fromisoformat(preferred_date_time)
            if start_time.tzinfo is None:
                start_time = pytz.timezone(time_zone).localize(start_time)
        except ValueError:
            return func.HttpResponse(
                json.dumps({"error": "Invalid preferredDateTime format. Must be ISO 8601."}),
                status_code=400,
                mimetype="application/json"
            )

        end_time = start_time + timedelta(minutes=duration_minutes)
        start_time_str = start_time.isoformat()
        end_time_str = end_time.isoformat()

        # Prepare event description
        description = (
            f"Service Name: {service_name}\n"  # Keep the service_name in the description
            f"Client Name: {client_name}\n"
            f"Phone: {phone_number}\n"
            f"Email: {email}"
        )

        # Add event to calendar
        event = add_calendar_entry(
            CALENDAR_ID,
            f'Appointment with {client_name}',
            description,
            start_time_str,
            end_time_str
        )

        # Return success response
        return func.HttpResponse(
            json.dumps({
                "sender_id": sender_id,
                "result": f"Appointment scheduled with {client_name} for service ID {service_name} on {start_time_str}",
                "eventId": event.get('id')
            }),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f"Error in booking slot for sender_id {sender_id}: {e}")
        return func.HttpResponse(
            json.dumps({
                "sender_id": sender_id,
                "error": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )
