import logging
import json
from datetime import datetime, timedelta, timezone
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import azure.functions as func
import os
import psycopg2


# PostgreSQL configuration from environment variables
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", 5432)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Constants
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'luminlabsdemo@gmail.com'

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

def is_time_slot_available(calendar_id, start_time, end_time):
    """Check if a time slot is available in the calendar."""
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
    """Main function to handle slot availability checks."""
    try:
        # Parse the request body
        req_body = req.get_json()
        sender_id = req_body.get('sender_id')  # Changed to sender_id
        preferred_date_time = req_body.get('preferredDateTime')
        service_name = req_body.get('service_name')
        business_id = req_body.get('business_id')

        # Validate required fields
        if not all([sender_id, preferred_date_time, service_name, business_id]):
            return func.HttpResponse(
                json.dumps({"error": "sender_id, preferredDateTime, service_name, and business_id are required."}),
                status_code=400,
                mimetype="application/json"
            )

        logging.info(f"Checking slot for sender_id: {sender_id}, service_name: {service_name}")

        # Connect to PostgreSQL to get the service duration
        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                port=DB_PORT
            )
            cursor = conn.cursor()

            # Query to get duration of the service
            cursor.execute(
                """
                SELECT duration_minutes
                FROM Services
                WHERE business_id = %s AND service_name ILIKE %s
                """,
                (business_id, service_name)
            )
            result = cursor.fetchone()

            if not result:
                return func.HttpResponse(
                    json.dumps({"error": f"Service '{service_name}' not found for business_id {business_id}."}),
                    status_code=404,
                    mimetype="application/json"
                )

            duration_minutes = result[0]
            logging.info(f"Retrieved duration_minutes: {duration_minutes} for service_name: {service_name}")

        except psycopg2.Error as e:
            logging.error(f"Database error: {e}")
            return func.HttpResponse(
                json.dumps({"error": "An error occurred while querying the database."}),
                status_code=500,
                mimetype="application/json"
            )
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        # Calculate the start and end time
        start_time = datetime.fromisoformat(preferred_date_time.replace("Z", "+00:00")).astimezone(timezone.utc)
        end_time = start_time + timedelta(minutes=duration_minutes)
        start_time_str = start_time.isoformat()
        end_time_str = end_time.isoformat()

        # Check calendar availability
        is_available = is_time_slot_available(CALENDAR_ID, start_time_str, end_time_str)

        return func.HttpResponse(
            json.dumps({"sender_id": sender_id, "isAvailable": is_available}),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f"Error checking slot availability for sender_id {sender_id}: {e}")
        return func.HttpResponse(
            json.dumps({"sender_id": sender_id, "error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )

