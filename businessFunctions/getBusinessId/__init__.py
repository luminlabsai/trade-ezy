import logging
import psycopg2
import os
import json
import azure.functions as func
import firebase_admin
from firebase_admin import auth, credentials, exceptions

# Ensure Firebase is initialized
if not firebase_admin._apps:
    service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if service_account_path and os.path.exists(service_account_path):
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
    else:
        logging.error("Firebase service account JSON not found or incorrect path.")
        raise ValueError("Missing or incorrect Firebase service account JSON path.")

def get_db_connection():
    """Establish a connection to the PostgreSQL database."""
    try:
        return psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            connect_timeout=30
        )
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        raise
    # ✅ Set CORS Headers
cors_headers = {
    "Access-Control-Allow-Origin": "*",  # Can be more restrictive if needed
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
}

def main(req: func.HttpRequest) -> func.HttpResponse:
    """Azure Function to retrieve business_id for an authenticated Firebase user."""
    logging.info("Processing getBusinessId request")



    # ✅ Handle CORS preflight request
    if req.method == "OPTIONS":
        return func.HttpResponse("", status_code=200, headers=cors_headers)

    id_token = req.headers.get("Authorization")
    if not id_token or not id_token.startswith("Bearer "):
        return func.HttpResponse(json.dumps({"error": "Missing or invalid Firebase ID token"}), 
                                 status_code=401, headers=cors_headers)

    try:
        logging.info("Received Authorization Header")

        # ✅ Extract token and verify with Firebase
        token = id_token.replace("Bearer ", "").strip()
        decoded_token = auth.verify_id_token(token)
        user_email = decoded_token.get("email")

        logging.info(f"Verified Firebase user: {user_email}")

        # ✅ Query database for business_id
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT business_id FROM portal_users WHERE email = %s", (user_email,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            response_data = json.dumps({"business_id": result[0]})
            logging.info(f"Returning business ID: {result[0]}")
            return func.HttpResponse(response_data, status_code=200, headers=cors_headers)
        else:
            logging.warning(f"No business found for user {user_email}")
            return func.HttpResponse(json.dumps({"error": "Business ID not found"}), 
                                     status_code=404, headers=cors_headers)

    except exceptions.FirebaseError as fe:
        logging.error(f"Firebase Authentication error: {fe}")
        return func.HttpResponse(json.dumps({"error": "Invalid Firebase token"}), 
                                 status_code=401, headers=cors_headers)

    except Exception as e:
        logging.error(f"Error in getBusinessId: {e}")
        return func.HttpResponse(json.dumps({"error": str(e)}), 
                                 status_code=500, headers=cors_headers)
