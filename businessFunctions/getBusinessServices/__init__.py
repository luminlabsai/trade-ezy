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

    # Get businessID and fields from the query parameters
    business_id = req.route_params.get("businessID")
    fields = req.params.get("fields")  # Expecting a comma-separated list of fields
    service_name = req.params.get("service_name")  # Optional service_name parameter for filtering

    if business_id:
        business_id = business_id.strip()  # Remove extra spaces or newlines

    if not business_id:
        logging.warning("Missing business_id in the request.")
        return func.HttpResponse(
            json.dumps({"error": "Business ID is required."}),
            status_code=400,
            mimetype="application/json"
        )

    # Default fields to query
    default_fields = ["name", "description", "duration_minutes", "price"]

    try:
        # Parse and validate fields
        if fields:
            fields = [field.strip() for field in fields.split(",")]
            # Validate fields against allowed fields
            allowed_fields = {"name", "description", "duration_minutes", "price"}
            fields = [field for field in fields if field in allowed_fields]
            if not fields:
                fields = default_fields
        else:
            fields = default_fields

        # Construct the SELECT clause
        select_clause = ", ".join(fields)

        # Construct the SQL query
        query = f"SELECT {select_clause} FROM Services WHERE business_id = %s"
        query_params = [business_id]

        if service_name:
            query += " AND name = %s"
            query_params.append(service_name.strip())

        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cursor = conn.cursor()

        logging.info(f"Executing query: {query}")
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
                json.dumps({"services": services}, default=json_serial),
                status_code=200,
                mimetype="application/json"
            )
        else:
            logging.warning(f"No services found for business_id: {business_id}")
            return func.HttpResponse(
                json.dumps({"error": "No services found for the specified business."}),
                status_code=404,
                mimetype="application/json"
            )

    except psycopg2.Error as e:
        logging.error(f"PostgreSQL error: {e}")
        return func.HttpResponse(
            json.dumps({"error": "An error occurred while querying the database."}),
            status_code=500,
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Internal Server Error"}),
            status_code=500,
            mimetype="application/json"
        )
