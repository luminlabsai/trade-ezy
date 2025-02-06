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

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
}

def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        if req.method == "OPTIONS":
            return func.HttpResponse("", status_code=200, headers=CORS_HEADERS)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        business_id = req.params.get("business_id")
        if not business_id:
            return func.HttpResponse(
                json.dumps({"error": "Missing required parameter: business_id"}),
                status_code=400,
                mimetype="application/json",
                headers=CORS_HEADERS,
            )

        if req.method == "GET":
            cursor.execute("""
                SELECT name, address, phone, email, operating_hours, description, instagram_business_id
                FROM businesses WHERE business_id = %s
            """, (business_id,))
            business = cursor.fetchone()
            
            if not business:
                return func.HttpResponse(
                    json.dumps({"error": "Business not found"}),
                    status_code=404,
                    mimetype="application/json",
                    headers=CORS_HEADERS,
                )
            
            business_data = {
                "name": business[0],
                "address": business[1],
                "phone": business[2],
                "email": business[3],
                "operating_hours": business[4],
                "description": business[5],
                "instagram_business_id": business[6]
            }
            return func.HttpResponse(json.dumps(business_data), mimetype="application/json", status_code=200, headers=CORS_HEADERS)
        
        elif req.method == "POST":
            data = req.get_json()
            cursor.execute("""
                UPDATE businesses SET name=%s, address=%s, phone=%s, email=%s, operating_hours=%s, description=%s, instagram_business_id=%s
                WHERE business_id = %s
            """, (data.get("name"), data.get("address"), data.get("phone"), data.get("email"),
                   json.dumps(data.get("operating_hours")), data.get("description"), data.get("instagram_business_id"), business_id))
            conn.commit()
            return func.HttpResponse(json.dumps({"message": "Business updated successfully"}), status_code=200, mimetype="application/json", headers=CORS_HEADERS)
        
        elif req.method == "DELETE":
            cursor.execute("DELETE FROM businesses WHERE business_id = %s", (business_id,))
            conn.commit()
            return func.HttpResponse(json.dumps({"message": "Business deleted successfully"}), status_code=200, mimetype="application/json", headers=CORS_HEADERS)
        
        return func.HttpResponse(json.dumps({"error": "Method not allowed"}), status_code=405, mimetype="application/json", headers=CORS_HEADERS)
    
    except Exception as e:
        logging.error(f"Error in manageAccounts: {e}")
        return func.HttpResponse(json.dumps({"error": str(e)}), status_code=500, mimetype="application/json", headers=CORS_HEADERS)
    
    finally:
        cursor.close()
        conn.close()
