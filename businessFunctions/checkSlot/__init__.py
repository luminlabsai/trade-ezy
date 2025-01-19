import logging
import json
from datetime import datetime, timedelta, timezone  # Correct imports for datetime operations
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import azure.functions as func
import os

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'luminlabsdemo@gmail.com'

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

def is_time_slot_available(calendar_id, start_time, end_time):
    service = get_calendar_service()
    try:
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_time,
            timeMax=end_time,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        return len(events) == 0
    except HttpError as e:
        logger.error(f"Error checking time slot availability: {e}")
        raise e

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        sender_id = req_body.get('senderID')
        preferred_date_time = req_body.get('preferredDateTime')
        duration_minutes = req_body.get('durationMinutes')

        # Validate required fields
        if not sender_id or not preferred_date_time or not duration_minutes:
            return func.HttpResponse(
                json.dumps({
                    "error": "senderID, preferredDateTime, and durationMinutes are required."
                }),
                status_code=400,
                mimetype="application/json"
            )

        # Log the sender_id for tracking purposes
        logging.info(f"Checking slot for senderID: {sender_id}")

        # Convert preferred_date_time to UTC
        start_time = datetime.fromisoformat(preferred_date_time.replace("Z", "+00:00")).astimezone(timezone.utc)
        end_time = start_time + timedelta(minutes=duration_minutes)

        start_time_str = start_time.isoformat()
        end_time_str = end_time.isoformat()

        # Check slot availability
        is_available = is_time_slot_available(CALENDAR_ID, start_time_str, end_time_str)
        
        # Return response
        return func.HttpResponse(
            json.dumps({
                "senderID": sender_id,
                "isAvailable": is_available
            }),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f"Error in checking slot availability for senderID {sender_id}: {e}")
        return func.HttpResponse(
            json.dumps({
                "senderID": sender_id,
                "error": str(e)
            }),
            status_code=500,
            mimetype="application/json"
        )
