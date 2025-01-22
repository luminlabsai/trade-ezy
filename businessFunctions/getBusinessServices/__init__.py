import logging
import os
import azure.functions as func
import psycopg2
import json
from decimal import Decimal

# PostgreSQL configuration from environment variables
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", 5432)

def json_serial(obj):
    """JSON serializer for objects not serializable by default."""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Processing request to get services for a business.")

    try:
        # Parse the request body
        req_body = req.get_json()
        sender_id = req_body.get("sender_id")
        business_id = req_body.get("business_id")
        fields = req_body.get("fields")  # Expecting a list of fields
        service_name = req_body.get("service_name")  # Optional service name for filtering

        # Validate required fields
        if not sender_id or not business_id:
            return func.HttpResponse(
                json.dumps({"error": "Both sender_id and business_id are required."}),
                status_code=400,
                mimetype="application/json"
            )

        # Log the sender ID for tracking purposes
        logging.info(f"Request from sender_id: {sender_id} for business_id: {business_id}")

        # Allowed and default fields
        allowed_fields = {"service_id", "name", "description", "duration_minutes", "price"}
        default_fields = ["service_id", "name", "duration_minutes", "price"]  # Excluding description by default

        # Parse and validate fields
        if fields:
            fields = [field.strip() for field in fields if field.strip() in allowed_fields]
            if not fields:
                logging.info("No valid fields specified. Using default fields.")
                fields = default_fields
        else:
            logging.info("Fields not provided. Using default fields.")
            fields = default_fields

        # Check if the user explicitly requested descriptions
        include_description = "description" in fields
        logging.info(f"Include description: {include_description}")

        # Construct the SELECT clause
        select_clause = ", ".join(fields)

        # Construct the SQL query
        query = f"SELECT {select_clause} FROM Services WHERE business_id = %s"
        query_params = [business_id]

        if service_name:
            query += " AND name ILIKE %s"  # Case-insensitive match for service name
            query_params.append(f"%{service_name.strip()}%")

        # Log the query for debugging
        logging.info(f"Fields requested: {fields}")
        logging.info(f"Constructed query: {query} with params {query_params}")

        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cursor = conn.cursor()

        cursor.execute(query, query_params)
        rows = cursor.fetchall()

        # Format the results as a list of dictionaries
        services = [
            {field: row[i] for i, field in enumerate(fields)}
            for row in rows
        ]

        cursor.close()
        conn.close()

        if services:
            logging.info(f"Query succeeded. Number of services found: {len(services)}")
            return func.HttpResponse(
                json.dumps({"sender_id": sender_id, "services": services}, default=json_serial),
                status_code=200,
                mimetype="application/json"
            )
        else:
            logging.warning(f"No services found for business_id: {business_id}")
            return func.HttpResponse(
                json.dumps({
                    "sender_id": sender_id,
                    "business_id": business_id,
                    "fields": fields,
                    "services": [],
                    "error": "No services found for the specified business."
                }),
                status_code=404,
                mimetype="application/json"
            )

    except psycopg2.Error as e:
        logging.error(f"PostgreSQL error for sender_id {sender_id}: {e}")
        return func.HttpResponse(
            json.dumps({"sender_id": sender_id, "error": "An error occurred while querying the database."}),
            status_code=500,
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f"Unexpected error for sender_id {sender_id}: {e}")
        return func.HttpResponse(
            json.dumps({"sender_id": sender_id, "error": "Internal Server Error"}),
            status_code=500,
            mimetype="application/json"
        )
