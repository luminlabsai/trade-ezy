import logging
import json
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import azure.functions as func  # Import the Azure Functions module

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
        preferred_date_time = req_body.get('preferredDateTime')
        duration_minutes = req_body.get('durationMinutes')

        if not preferred_date_time or not duration_minutes:
            return func.HttpResponse(
                json.dumps({"error": "preferredDateTime and durationMinutes are required"}),
                status_code=400,
                mimetype="application/json"
            )

        start_time = datetime.datetime.fromisoformat(preferred_date_time).astimezone(datetime.timezone.utc)
        end_time = start_time + datetime.timedelta(minutes=duration_minutes)

        start_time_str = start_time.isoformat()
        end_time_str = end_time.isoformat()

        is_available = is_time_slot_available(CALENDAR_ID, start_time_str, end_time_str)
        return func.HttpResponse(
            json.dumps({"isAvailable": is_available}),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as e:
        logger.error(f"Error in checking slot availability: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
