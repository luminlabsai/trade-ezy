import os
import logging
import openai
import requests
import json
import azure.functions as func
import psycopg2
from uuid import uuid4
from function_descriptions import function_descriptions
from function_endpoints import function_endpoints
from fuzzywuzzy import fuzz, process  # For fuzzy matching of service names

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "MISSING_KEY")
ASSISTANT_ID = "asst_x0xrh7dShxqC0eBHfIuunn1L"
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")  # Default to gpt-4 if not set
CHAT_HISTORY_LIMIT = int(os.getenv("CHAT_HISTORY_LIMIT", 10))  # Default to 10 if not set
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", 5432)

# Validate environment variables
if OPENAI_API_KEY == "MISSING_KEY":
    logging.error("Required environment variable OPENAI_API_KEY is not set.")
    raise ValueError("Required environment variable is not set.")

openai.api_key = OPENAI_API_KEY

# Helper Functions
def fetch_chat_history(business_id, session_id, limit=CHAT_HISTORY_LIMIT):
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cursor = conn.cursor()
        query = """
            SELECT role, content 
            FROM chathistory 
            WHERE business_id = %s AND session_id = %s 
            ORDER BY timestamp ASC LIMIT %s
        """
        cursor.execute(query, (business_id, session_id, limit))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [{"role": row[0], "content": row[1]} for row in rows]
    except psycopg2.Error as e:
        logging.error(f"Error fetching chat history: {e}")
        return []

def store_chat_message(business_id, session_id, role, content):
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cursor = conn.cursor()
        query = """
            INSERT INTO chathistory (business_id, session_id, role, content)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (business_id, session_id, role, content))
        conn.commit()
        cursor.close()
        conn.close()
        logging.info(f"Stored message: Role={role}, Content={content}")
    except psycopg2.Error as e:
        logging.error(f"Error storing chat message: {e}")

# Main Function
def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Processing chat request with OpenAI assistant.")
    
    # Handle CORS preflight requests
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            },
        )

    try:
        req_body = req.get_json()
        query = req_body.get("query")
        business_context = req_body.get("businessContext")
        session_id = req_body.get("sessionID") or str(uuid4())  # Generate new session ID if not provided

        if not query:
            return func.HttpResponse(
                "Query is missing.",
                status_code=400,
                headers={"Access-Control-Allow-Origin": "*"}
            )

        if not business_context or "businessID" not in business_context:
            return func.HttpResponse(
                "Business context is missing or invalid.",
                status_code=400,
                headers={"Access-Control-Allow-Origin": "*"}
            )

        business_id = business_context["businessID"]

        # Fetch chat history
        chat_history = fetch_chat_history(business_id, session_id)
        messages = [{"role": message["role"], "content": message["content"]} for message in chat_history]
        messages.append({"role": "user", "content": query})

        # Add system context
        messages.insert(0, {
            "role": "system",
            "content": f"You are assisting a business with ID {business_id}. Respond in a professional, user-friendly tone."
        })

        # Store the query
        store_chat_message(business_id, session_id, "user", query)

        # OpenAI API call
        logging.info(f"Sending request to OpenAI with model {LLM_MODEL}.")
        response = openai.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            functions=function_descriptions,
            function_call="auto",
            temperature=0.7,
            max_tokens=800,
            user=ASSISTANT_ID
        )

        assistant_response = response.choices[0].message

        # Process function call if requested
        if hasattr(assistant_response, "function_call") and assistant_response.function_call:
            function_call = assistant_response.function_call
            function_name = function_call.name
            arguments = json.loads(function_call.arguments)
            endpoint = function_endpoints.get(function_name)

            if not endpoint:
                return func.HttpResponse(
                    f"No endpoint configured for function: {function_name}",
                    status_code=500,
                    headers={"Access-Control-Allow-Origin": "*"}
                )

            # Handle dynamic GET construction
            if function_name == "getBusinessServices":
                fields = ",".join(arguments.get("fields", []))
                endpoint = endpoint.format(businessID=arguments["businessID"], fields=fields)

            # Execute function call
            try:
                function_response = requests.get(endpoint) if function_name == "getBusinessServices" else requests.post(endpoint, json=arguments)
                if function_response.status_code == 200:
                    result = function_response.json()

                    # Format response for getBusinessServices
                    if function_name == "getBusinessServices":
                        formatted_services = "\n".join([f"- {service['name']}: {service['description']}" for service in result.get('services', [])])
                        result_message = f"Here are the services offered by the business:\n{formatted_services}" if formatted_services else "No services found for the business."
                    else:
                        result_message = json.dumps(result)

                    # Store and return the formatted response
                    store_chat_message(business_id, session_id, "assistant", result_message)
                    return func.HttpResponse(result_message, status_code=200, headers={"Access-Control-Allow-Origin": "*"})
                else:
                    return func.HttpResponse(f"Function call failed: {function_response.text}", status_code=500, headers={"Access-Control-Allow-Origin": "*"})
            except Exception as e:
                logging.error(f"Error during function call: {e}")
                return func.HttpResponse(f"Error during function call: {e}", status_code=500, headers={"Access-Control-Allow-Origin": "*"})

        # Store and return assistant response
        store_chat_message(business_id, session_id, "assistant", assistant_response.content)
        return func.HttpResponse(assistant_response.content, status_code=200, headers={"Access-Control-Allow-Origin": "*"})

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return func.HttpResponse("Internal Server Error", status_code=500, headers={"Access-Control-Allow-Origin": "*"})
