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
        function_name = req_body.get("function_name")
        if function_name != "update_user_details":
            return func.HttpResponse(
                json.dumps({"error": "Invalid function name."}),
                status_code=400,
                mimetype="application/json"
            )

        business_id = req_body.get("businessID")
        sender_id = req_body.get("senderID")
        user_details = req_body.get("details")

        # Validate required parameters
        if not business_id or not sender_id or not user_details:
            return func.HttpResponse(
                json.dumps({"error": "Missing required parameters."}),
                status_code=400,
                mimetype="application/json"
            )

        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST"),
            database=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD")
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
