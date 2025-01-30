import logging
import json
import os
import psycopg2
import azure.functions as func

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Processing create_or_update_user function.")

    try:
        # Parse the incoming request payload
        req_body = req.get_json()
        sender_id = req_body.get("sender_id")  # ✅ Expecting a UUID
        name = req_body.get("name")
        phone_number = req_body.get("phone_number")
        email = req_body.get("email")

        # Validate required parameters
        if not sender_id or "-" not in sender_id:  # Ensure it's a UUID
            logging.warning(f"🚨 Invalid or missing UUID for sender_id: {sender_id}")
            return func.HttpResponse(
                json.dumps({"error": "Invalid sender_id. Expected a UUID."}),
                status_code=400,
                mimetype="application/json"
            )

        # Connect to PostgreSQL
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            connect_timeout=30  # Timeout in seconds
        )
        cursor = conn.cursor()

        # ✅ Check if user exists before updating
        cursor.execute("SELECT COUNT(*) FROM users WHERE sender_id = %s", (sender_id,))
        user_exists = cursor.fetchone()[0] > 0

        if user_exists:
            # ✅ Update existing user
            update_query = """
                UPDATE users
                SET name = COALESCE(%s, name),
                    phone_number = COALESCE(%s, phone_number),
                    email = COALESCE(%s, email),
                    updated_at = NOW()
                WHERE sender_id = %s
            """
            cursor.execute(update_query, (name, phone_number, email, sender_id))
            logging.info(f"✅ Updated existing user: {sender_id}")
        else:
            # ✅ Insert new user
            insert_query = """
                INSERT INTO users (sender_id, name, phone_number, email, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
            """
            cursor.execute(insert_query, (sender_id, name, phone_number, email))
            logging.info(f"✅ Created new user: {sender_id}")

        conn.commit()  # ✅ Ensure transaction commits

        # Build the response
        response = {
            "message": "User processed successfully.",
            "user": {
                "sender_id": sender_id,  # ✅ Always a UUID
                "name": name,
                "phone_number": phone_number,
                "email": email
            }
        }
        return func.HttpResponse(
            json.dumps(response),
            status_code=200,
            mimetype="application/json"
        )

    except (Exception, psycopg2.Error) as e:
        logging.error(f"❌ Error in create_or_update_user: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Internal server error.", "details": str(e)}),
            status_code=500,
            mimetype="application/json"
        )

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()
