
from user_manager import update_user_details  # Import the function here
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
    Update user details in the database for a given sender_id. If the user doesn't exist, create a new record.
    """
    try:
        # SQL query to update user details
        update_query = """
            UPDATE public.users
            SET
                name = COALESCE(%s, name),
                phone_number = COALESCE(%s, phone_number),
                email = COALESCE(%s, email),
                updated_at = NOW()
            WHERE sender_id = %s
        """
        # SQL query to insert user if not exists
        insert_query = """
            INSERT INTO public.users (sender_id, name, phone_number, email, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (sender_id) DO NOTHING
        """

        with psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        ) as conn:
            with conn.cursor() as cursor:
                # Attempt to update user details
                cursor.execute(
                    update_query,
                    (
                        updates.get("name"),
                        updates.get("phone_number"),
                        updates.get("email"),
                        sender_id
                    )
                )
                # If no rows were updated, insert a new user
                if cursor.rowcount == 0:
                    logging.warning(f"No user found with sender_id: {sender_id}. Creating a new user.")
                    cursor.execute(
                        insert_query,
                        (
                            sender_id,
                            updates.get("name"),
                            updates.get("phone_number"),
                            updates.get("email")
                        )
                    )
                conn.commit()
        logging.info(f"Successfully updated user details for sender_id: {sender_id}")
    except Exception as e:
        logging.error(f"Failed to update user details: {e}")
        raise
