import os
import psycopg2

# Load environment variables
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", "5432")  # Default to 5432 if not set

# Database connection settings with timeout
DB_CONNECT_TIMEOUT = 10  # seconds

def get_business_id(instagram_business_id: int) -> str:
    """
    Fetch the business_id mapped to the given Instagram business_id.
    Returns None if no mapping exists.
    """
    try:
        # Establish a connection with timeout
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            connect_timeout=DB_CONNECT_TIMEOUT
        )
        cur = conn.cursor()

        # Query to fetch the mapped business_id
        cur.execute(
            "SELECT business_id FROM businesses WHERE instagram_business_id = %s",
            (instagram_business_id,)
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
