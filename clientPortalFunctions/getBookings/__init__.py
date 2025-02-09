import logging
import os
import psycopg2
import json
import azure.functions as func

# PostgreSQL Configuration
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", 5432)

# CORS Headers
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
}

def get_db_connection():
    """Establish a connection to PostgreSQL."""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT
    )

def main(req: func.HttpRequest) -> func.HttpResponse:
    """Retrieve bookings with user details and handle CORS."""
    logging.info("Processing request to retrieve bookings.")

    # Handle CORS preflight request
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization, Content-Type"
            }
        )

    # Parse query parameters
    business_id = req.params.get("business_id")
    from_date = req.params.get("from_date")
    to_date = req.params.get("to_date")

    if not business_id:
        return func.HttpResponse(
            json.dumps({"error": "business_id is required."}),
            status_code=400,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*"
            }
        )
    
    try:
        # Connect to the database
        conn = get_db_connection()
        cursor = conn.cursor()

        # Base query
        query = """
        SELECT 
            b.booking_id,
            b.service_name,
            b.preferred_date_time,
            b.duration_minutes,
            b.notes,
            u.name AS customer_name,
            u.email AS customer_email,
            u.phone_number AS customer_phone
        FROM bookings b
        INNER JOIN users u ON b.sender_id = u.sender_id
        WHERE b.business_id = %s
        """

        # Query parameters
        query_params = [business_id]

        # Add date filters if provided
        if from_date:
            query += " AND DATE(b.preferred_date_time) >= %s"
            query_params.append(from_date)
        if to_date:
            query += " AND DATE(b.preferred_date_time) <= %s"
            query_params.append(to_date)

        # Order by date
        query += " ORDER BY b.preferred_date_time DESC;"

        # Execute the query
        cursor.execute(query, query_params)
        rows = cursor.fetchall()

        # Map results to a list of dictionaries
        bookings = [
            {
                "booking_id": row[0],
                "service_name": row[1],
                "preferred_date_time": row[2].isoformat(),
                "duration_minutes": row[3],
                "notes": row[4],
                "customer_name": row[5],
                "customer_email": row[6],
                "customer_phone": row[7]
            }
            for row in rows
        ]

        # Close the connection
        cursor.close()
        conn.close()

        # Return the bookings
        return func.HttpResponse(
            json.dumps(bookings),
            status_code=200,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*"
            }
        )
    
    except Exception as e:
        logging.error(f"Error retrieving bookings: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Internal server error", "details": str(e)}),
            status_code=500,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*"
            }
        )
