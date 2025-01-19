import os
import psycopg2
import logging

# Database connection settings
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", 5432)

def get_or_create_user(sender_id):
    """
    Retrieve a user by sender_id or create a new user if not found.
    """
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cursor = connection.cursor()

        # Check if the user exists
        cursor.execute(
            """SELECT sender_id, name, phone_number, email FROM users WHERE sender_id = %s""",
            (sender_id,)
        )
        user = cursor.fetchone()

        if user:
            logging.info(f"User found: {user}")
            return {
                "sender_id": user[0],
                "name": user[1],
                "phone_number": user[2],
                "email": user[3]
            }

        # Create a new user if not found
        cursor.execute(
            """INSERT INTO users (sender_id) VALUES (%s) RETURNING sender_id""",
            (sender_id,)
        )
        connection.commit()
        logging.info(f"New user created with sender_id: {sender_id}")

        return {
            "sender_id": sender_id,
            "name": None,
            "phone_number": None,
            "email": None
        }

    except Exception as e:
        logging.error(f"Error in get_or_create_user: {e}")
        raise

    finally:
        if connection:
            cursor.close()
            connection.close()

def update_user_details(sender_id, details):
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()

        # Fetch existing user details
        cursor.execute(
            "SELECT sender_id, name, phone_number, email FROM users WHERE sender_id = %s",
            (sender_id,)
        )
        existing_user = cursor.fetchone()

        if not existing_user:
            logging.error(f"No user found for sender_id: {sender_id}")
            return

        logging.info(f"Existing user details: {existing_user}")

        # Prepare updates
        updates = []
        values = []
        fields = {"clientName": "name", "phoneNumber": "phone_number", "emailAddress": "email"}
        for key, db_field in fields.items():
            # Compare the new detail with the existing value in the database
            db_value_index = list(fields.values()).index(db_field) + 1  # Offset for SELECT fields
            if key in details and details[key] != existing_user[db_value_index]:
                updates.append(f"{db_field} = %s")
                values.append(details[key])

        if updates:
            # Add sender_id for WHERE clause
            values.append(sender_id)
            query = f"""
                UPDATE users
                SET {", ".join(updates)}, updated_at = CURRENT_TIMESTAMP
                WHERE sender_id = %s
            """
            logging.info(f"Executing query: {query} with values: {values}")
            cursor.execute(query, values)
            conn.commit()
            logging.info(f"User details successfully updated for sender_id: {sender_id}")
        else:
            logging.info(f"No updates provided for sender_id: {sender_id}")

    except Exception as e:
        logging.error(f"Error updating user details: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
