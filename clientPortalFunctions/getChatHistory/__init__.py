import os
import psycopg2
import json
import logging
import azure.functions as func

def get_db_connection():
    """Establish a connection to the PostgreSQL database."""
    try:
        return psycopg2.connect(
            dbname=os.getenv("DB_NAME"),    
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            connect_timeout=30
        )
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        raise

# ✅ Set CORS Headers
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
}

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # ✅ Handle CORS preflight request
        if req.method == "OPTIONS":
            return func.HttpResponse("", status_code=200, headers=CORS_HEADERS)

        # Parse query parameters
        business_id = req.params.get("business_id")
        from_date = req.params.get("from_date")
        to_date = req.params.get("to_date")
        limit = int(req.params.get("limit", 20))
        offset = int(req.params.get("offset", 0))

        if not business_id:
            return func.HttpResponse(
                json.dumps({"error": "Missing required parameter: business_id"}),
                status_code=400,
                mimetype="application/json",
                headers=CORS_HEADERS
            )

        conn = get_db_connection()
        cursor = conn.cursor()

        # ✅ Query to count total messages (for pagination)
        count_query = """
            SELECT COUNT(*) FROM chathistory WHERE business_id = %s
        """
        count_params = [business_id]

        if from_date:
            count_query += " AND timestamp >= %s"
            count_params.append(from_date)
        
        if to_date:
            count_query += " AND timestamp <= %s"
            count_params.append(to_date)
        
        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()[0]  # ✅ Fetch total count

        # ✅ Query to fetch paginated messages
        data_query = """
            SELECT message_id, business_id, sender_id, role, content, timestamp, message_type, name
            FROM chathistory
            WHERE business_id = %s
        """
        data_params = [business_id]

        if from_date:
            data_query += " AND timestamp >= %s"
            data_params.append(from_date)

        if to_date:
            data_query += " AND timestamp <= %s"
            data_params.append(to_date)

        data_query += " ORDER BY timestamp DESC LIMIT %s OFFSET %s"
        data_params.extend([limit, offset])

        cursor.execute(data_query, data_params)
        rows = cursor.fetchall()

        # ✅ Format response
        messages = [
            {
                "message_id": row[0],
                "business_id": row[1],
                "sender_id": row[2],
                "role": row[3],
                "content": row[4],
                "timestamp": row[5].isoformat(),
                "message_type": row[6],
                "name": row[7]
            }
            for row in rows
        ]

        cursor.close()
        conn.close()

        return func.HttpResponse(
            json.dumps({"messages": messages, "totalCount": total_count}),  # ✅ Return both messages & total count
            mimetype="application/json",
            status_code=200,
            headers=CORS_HEADERS
        )

    except Exception as e:
        logging.error(f"Error in getChatHistory: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json",
            headers=CORS_HEADERS
        )
