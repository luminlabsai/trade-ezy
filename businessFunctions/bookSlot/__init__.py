import logging
import json
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import azure.functions as func
import os
import pytz  # For time zone handling

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'luminlabsdemo@gmail.com'

# Define AEST time zone (UTC+10, no daylight saving)
AEST = pytz.timezone('Australia/Brisbane')

def get_calendar_service():
    # Retrieve the private key directly from the environment
    private_key_raw = os.getenv("GOOGLE_PRIVATE_KEY", "")
    
    # Replace literal `\n` with actual newlines
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
    service = get_calendar_service()
    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time,
            'timeZone': 'Australia/Brisbane',  # Ensure the time zone is explicitly set to AEST
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'Australia/Brisbane',  # Ensure the time zone is explicitly set to AEST
        }
    }
    try:
        return service.events().insert(calendarId=calendar_id, body=event).execute()
    except HttpError as e:
        logger.error(f"Error adding calendar entry: {e}")
        raise e

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Parse the request body
        req_body = req.get_json()
        preferred_date_time = req_body.get('preferredDateTime')
        duration_minutes = req_body.get('durationMinutes')
        client_name = req_body.get('clientName')
        appointment_purpose = req_body.get('appointmentPurpose')
        phone_number = req_body.get('phoneNumber')
        email_address = req_body.get('emailAddress')
        time_zone = req_body.get('timeZone', 'Australia/Brisbane')  # Default to AEST if not provided

        # Validate required fields
        if not all([preferred_date_time, duration_minutes, client_name, appointment_purpose, phone_number, email_address]):
            return func.HttpResponse(
                json.dumps({"error": "All parameters are required: preferredDateTime, durationMinutes, clientName, appointmentPurpose, phoneNumber, emailAddress"}),
                status_code=400,
                mimetype="application/json"
            )

        # Load the specified timezone
        try:
            selected_time_zone = pytz.timezone(time_zone)
        except pytz.UnknownTimeZoneError:
            return func.HttpResponse(
                json.dumps({"error": f"Invalid timeZone: {time_zone}"}),
                status_code=400,
                mimetype="application/json"
            )

        # Parse the preferred date and time
        try:
            start_time = datetime.fromisoformat(preferred_date_time)
            if start_time.tzinfo is None:  # Only localize if naive
                start_time = selected_time_zone.localize(start_time)
            else:
                logging.info(f"Datetime already has tzinfo: {start_time.tzinfo}")
        except ValueError:
            return func.HttpResponse(
                json.dumps({"error": "Invalid preferredDateTime format. Must be ISO 8601."}),
                status_code=400,
                mimetype="application/json"
            )

        end_time = start_time + timedelta(minutes=duration_minutes)

        # Convert to ISO format for Google Calendar
        start_time_str = start_time.isoformat()
        end_time_str = end_time.isoformat()

        # Format the description
        description = (
            f"Purpose: {appointment_purpose}\n"
            f"Client Name: {client_name}\n"
            f"Phone: {phone_number}\n"
            f"Email: {email_address}"
        )

        # Add the calendar entry
        event = add_calendar_entry(
            CALENDAR_ID,
            f'Appointment with {client_name}',
            description,
            start_time_str,
            end_time_str
        )

        return func.HttpResponse(
            json.dumps({
                "result": f"Appointment scheduled with {client_name} for {appointment_purpose} on {start_time_str}",
                "eventId": event.get('id')
            }),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logger.error(f"Error in booking slot: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
