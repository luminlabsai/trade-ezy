import os
import psycopg2
import uuid  # Import UUID module

# Load environment variables
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", "5432")  # Default to 5432 if not set
DB_CONNECT_TIMEOUT = 10  # Timeout in seconds

def get_or_create_sender_id(instagram_sender_id: int) -> str:
    """
    Retrieves the sender_id for a given Instagram user_id.
    If the user doesn't exist, creates a new entry with a generated sender_id.
    """
    try:
        # Establish connection with timeout
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            connect_timeout=DB_CONNECT_TIMEOUT
        )
        cur = conn.cursor()

        # Check if user already exists
        cur.execute(
            "SELECT sender_id FROM users WHERE instagram_sender_id = %s",
            (instagram_sender_id,)
        )
        result = cur.fetchone()

        if result:
            sender_id = result[0]
        else:
            # Generate a new sender_id
            new_sender_id = str(uuid.uuid4())  # Generate UUID
            cur.execute(
                """
                INSERT INTO users (sender_id, instagram_sender_id, created_at, updated_at)
                VALUES (%s, %s, NOW(), NOW())
                RETURNING sender_id
                """,
                (new_sender_id, instagram_sender_id)
            )
            sender_id = cur.fetchone()[0]
            conn.commit()

        cur.close()
        conn.close()
        return sender_id

    except psycopg2.OperationalError as e:
        print(f"Database connection error: {e}")
        return None
    except psycopg2.Error as e:
        print(f"Database query error: {e}")
        return None


def get_mapped_uuid(instagram_sender_id: int) -> str:
    """ Fetch the mapped UUID for an Instagram sender ID without creating a new entry. """
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            connect_timeout=DB_CONNECT_TIMEOUT
        )
        cur = conn.cursor()

        cur.execute(
            "SELECT sender_id FROM users WHERE instagram_sender_id = %s",
            (instagram_sender_id,)
        )
        result = cur.fetchone()

        cur.close()
        conn.close()
        return result[0] if result else None

    except psycopg2.OperationalError as e:
        print(f"Database connection error: {e}")
        return None
    except psycopg2.Error as e:
        print(f"Database query error: {e}")
        return None


def ensure_uuid_exists(instagram_sender_id: int) -> bool:
    """ Ensure a UUID exists for a given Instagram sender ID without modifying existing data unnecessarily. """
    sender_id = get_mapped_uuid(instagram_sender_id)
    if sender_id:
        return True
    return bool(get_or_create_sender_id(instagram_sender_id))
