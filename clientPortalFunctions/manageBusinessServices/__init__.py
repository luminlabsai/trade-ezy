import logging
import os
import azure.functions as func
import psycopg2
import json
import uuid
from decimal import Decimal

# PostgreSQL Configuration
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", 5432)

def json_serial(obj):
    """JSON serializer for Decimal values."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

def get_db_connection():
    """Establish a connection to PostgreSQL."""
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT,
        connect_timeout=30
    )

def main(req: func.HttpRequest) -> func.HttpResponse:
    """Azure Function to manage business services (GET, POST, PUT, DELETE)."""
    logging.info("Processing request to manage business services.")
    method = req.method
    response = None  # Ensure we have a response assigned

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if method == "GET":
            business_id = req.params.get("business_id")
            service_id = req.params.get("service_id")

            if not business_id:
                return func.HttpResponse(json.dumps({"error": "business_id is required."}), status_code=400)

            query = "SELECT service_id, service_name, description, duration_minutes, price FROM Services WHERE business_id = %s"
            params = [business_id]

            if service_id:
                query += " AND service_id = %s"
                params.append(service_id)

            cursor.execute(query, params)
            services = [dict(zip([desc[0] for desc in cursor.description], row)) for row in cursor.fetchall()]

            response = func.HttpResponse(json.dumps(services, default=json_serial), status_code=200, mimetype="application/json")
        
        elif method == "POST":
            data = req.get_json()
            business_id = data.get("business_id")
            service_name = data.get("service_name")
            description = data.get("description", "")
            duration_minutes = data.get("duration_minutes")
            price = data.get("price")

            if not business_id or not service_name or duration_minutes is None or price is None:
                return func.HttpResponse(json.dumps({"error": "Missing required fields."}), status_code=400)

            # ✅ Generate UUID for service_id
            service_id = str(uuid.uuid4())

            cursor.execute(
                "INSERT INTO Services (service_id, business_id, service_name, description, duration_minutes, price, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())",
                (service_id, business_id, service_name, description, duration_minutes, price)
            )
            conn.commit()

            response = func.HttpResponse(json.dumps({"message": "Service added", "service_id": service_id}), status_code=201)

        elif method == "PUT":
            data = req.get_json()
            service_id = data.get("service_id")
            fields = {k: v for k, v in data.items() if k in ["service_name", "description", "duration_minutes", "price"] and v is not None}

            if not service_id or not fields:
                return func.HttpResponse(json.dumps({"error": "service_id and at least one field to update are required."}), status_code=400)

            query = "UPDATE Services SET " + ", ".join([f"{k} = %s" for k in fields.keys()]) + ", updated_at = NOW() WHERE service_id = %s"
            params = list(fields.values()) + [service_id]

            cursor.execute(query, params)
            conn.commit()

            response = func.HttpResponse(json.dumps({"message": "Service updated"}), status_code=200)

        elif method == "DELETE":
            data = req.get_json()
            service_id = data.get("service_id")

            if not service_id:
                return func.HttpResponse(json.dumps({"error": "service_id is required for deletion."}), status_code=400)

            cursor.execute("DELETE FROM Services WHERE service_id = %s", (service_id,))
            conn.commit()

            response = func.HttpResponse(json.dumps({"message": "Service deleted"}), status_code=200)

        else:
            response = func.HttpResponse(json.dumps({"error": "Method not allowed."}), status_code=405)

    except psycopg2.DatabaseError as e:
        logging.error(f"Database error: {e}")
        response = func.HttpResponse(json.dumps({"error": "Database error", "details": str(e)}), status_code=500)
    
    except Exception as e:
        logging.error(f"Error managing services: {e}")
        response = func.HttpResponse(json.dumps({"error": "Internal Server Error", "details": str(e)}), status_code=500)

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return response  # Ensure function always returns a response
