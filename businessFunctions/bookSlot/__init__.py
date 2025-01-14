import logging
import json
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import azure.functions as func  # Import Azure Functions module

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

SERVICE_ACCOUNT_FILE = 'service-account.json'  # Adjust the path if necessary
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'luminlabsdemo@gmail.com'

import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

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

    # Debugging log for the private key
    if "PRIVATE KEY" in private_key_processed:
        logging.info(f"Private Key Loaded: {private_key_processed[:30]}...{private_key_processed[-30:]}")
    else:
        raise ValueError("Private key is missing or improperly formatted.")

    credentials = Credentials.from_service_account_info(service_account_info, scopes=['https://www.googleapis.com/auth/calendar'])
    return build('calendar', 'v3', credentials=credentials, cache_discovery=False)

def add_calendar_entry(calendar_id, summary, description, start_time, end_time):
    service = get_calendar_service()
    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time,
            'timeZone': 'Australia/Sydney',
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'Australia/Sydney',
        },
    }
    try:
        return service.events().insert(calendarId=calendar_id, body=event).execute()
    except HttpError as e:
        logger.error(f"Error adding calendar entry: {e}")
        raise e

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        preferred_date_time = req_body.get('preferredDateTime')
        duration_minutes = req_body.get('durationMinutes')
        client_name = req_body.get('clientName')
        appointment_purpose = req_body.get('appointmentPurpose')

        if not preferred_date_time or not duration_minutes or not client_name or not appointment_purpose:
            return func.HttpResponse(
                json.dumps({"error": "All parameters are required: preferredDateTime, durationMinutes, clientName, appointmentPurpose"}),
                status_code=400,
                mimetype="application/json"
            )

        start_time = datetime.fromisoformat(preferred_date_time).astimezone(datetime.timezone.utc)
        end_time = start_time + datetime.timedelta(minutes=duration_minutes)

        start_time_str = start_time.isoformat()
        end_time_str = end_time.isoformat()

        event = add_calendar_entry(
            CALENDAR_ID,
            f'Appointment with {client_name}',
            appointment_purpose,
            start_time_str,
            end_time_str
        )

        return func.HttpResponse(
            json.dumps({"result": f"Appointment scheduled with {client_name} for {appointment_purpose} on {start_time_str}", "eventId": event.get('id')}),
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
