import logging
import json
import os
import psycopg2
import azure.functions as func

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Processing update_user_details function.")

    try:
        # Parse the incoming request
        req_body = req.get_json()
        business_id = req_body.get("businessID")
        sender_id = req_body.get("senderID")
        user_details = req_body.get("details")  # Expecting a JSON object with name, phone, email

        # Validate required parameters
        if not business_id or not sender_id or not user_details:
            return func.HttpResponse(
                json.dumps({"error": "Missing required parameters: 'businessID', 'senderID', or 'details'."}),
                status_code=400,
                mimetype="application/json"
            )

        # Validate that 'details' contains necessary fields
        if not isinstance(user_details, dict) or not all(key in user_details for key in ["name", "phone", "email"]):
            return func.HttpResponse(
                json.dumps({"error": "'details' must be a JSON object with 'name', 'phone', and 'email' fields."}),
                status_code=400,
                mimetype="application/json"
            )

        # Connect to PostgreSQL
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        cursor = conn.cursor()

        # Update user details in the database
        update_query = """
            UPDATE users
            SET details = %s
            WHERE business_id = %s AND sender_id = %s
            RETURNING sender_id;
        """
        cursor.execute(update_query, (json.dumps(user_details), business_id, sender_id))
        conn.commit()

        # Check if the update was successful
        if cursor.rowcount == 0:
            return func.HttpResponse(
                json.dumps({"error": "User not found or no details updated."}),
                status_code=404,
                mimetype="application/json"
            )

        return func.HttpResponse(
            json.dumps({"message": "User details updated successfully."}),
            status_code=200,
            mimetype="application/json"
        )

    except (Exception, psycopg2.Error) as e:
        logging.error(f"Error updating user details: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Internal server error."}),
            status_code=500,
            mimetype="application/json"
        )

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
