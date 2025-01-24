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
    Retrieve or create a user record in the database.

    Args:
        sender_id (str): The sender ID of the user.

    Returns:
        dict: A dictionary of user details (e.g., {"name": "John", "email": "john@example.com"}).
    """
    try:
        query = "SELECT sender_id, name, phone_number, email FROM public.users WHERE sender_id = %s"
        with psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (sender_id,))
                result = cursor.fetchone()
                if result:
                    return {
                        "sender_id": result[0],
                        "name": result[1],
                        "phone_number": result[2],
                        "email": result[3]
                    }

                # Create a new user if none exists
                insert_query = """
                    INSERT INTO public.users (sender_id, created_at, updated_at)
                    VALUES (%s, NOW(), NOW())
                """
                cursor.execute(insert_query, (sender_id,))
                conn.commit()
                logging.info(f"New user created with sender_id: {sender_id}")
                return {"sender_id": sender_id, "name": None, "phone_number": None, "email": None}
    except Exception as e:
        logging.error(f"Error in get_or_create_user: {e}")
        return None




def update_user_details(sender_id, updates):
    """
    Update user details in the database for a given sender_id.
    """
    try:
        query = """
            UPDATE public.users
            SET
                name = COALESCE(%s, name),
                phone_number = COALESCE(%s, phone_number),
                email = COALESCE(%s, email),
                updated_at = NOW()
            WHERE sender_id = %s
        """
        with psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        ) as conn:
            with conn.cursor() as cursor:
                logging.debug(f"Updating user details with: {updates} for sender_id: {sender_id}")
                cursor.execute(
                    query,
                    (
                        updates.get("name"),
                        updates.get("phone_number"),
                        updates.get("email"),
                        sender_id
                    )
                )
                if cursor.rowcount == 0:
                    logging.warning(f"No user found with sender_id: {sender_id}. Update skipped.")
                conn.commit()
        logging.info(f"Successfully updated user details for sender_id: {sender_id}")
    except psycopg2.Error as db_error:
        logging.error(f"Database error during update_user_details: {db_error}")
        raise  # Ensure error is propagated
    except Exception as e:
        logging.error(f"Unexpected error in update_user_details: {e}")
        raise
