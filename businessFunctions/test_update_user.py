
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
                cursor.execute(
                    query,
                    (
                        updates.get("name"),
                        updates.get("phone_number"),
                        updates.get("email"),
                        sender_id
                    )
                )
                conn.commit()
        logging.info(f"Successfully updated user details for sender_id: {sender_id}")
    except Exception as e:
        logging.error(f"Failed to update user details: {e}")


# Test function to invoke update_user_details
def test_update_user_details():
    # Example sender_id and details to update
    sender_id = "110e8400-e29b-41d4-a716-446655440143"  # Use a valid sender_id
    updates = {
        "name": "Boris",
        "phone_number": "0567938479",
        "email": "boris@penaut.com"
    }

    try:
        # Call the function
        update_user_details(sender_id, updates)
        print(f"User details for sender_id {sender_id} updated successfully.")
    except Exception as e:
        print(f"Error while updating user details: {e}")

# Run the test function
if __name__ == "__main__":
    test_update_user_details()
