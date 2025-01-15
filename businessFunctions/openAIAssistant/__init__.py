import os
import logging
import openai
import requests
import json
import azure.functions as func
import psycopg2
from uuid import uuid4
from urllib.parse import quote
from function_descriptions import function_descriptions
from function_endpoints import function_endpoints

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "MISSING_KEY")
ASSISTANT_ID = "asst_x0xrh7dShxqC0eBHfIuunn1L"
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")
CHAT_HISTORY_LIMIT = int(os.getenv("CHAT_HISTORY_LIMIT", 10))
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", 5432)

if OPENAI_API_KEY == "MISSING_KEY":
    raise ValueError("OPENAI_API_KEY environment variable is not set.")

openai.api_key = OPENAI_API_KEY

# Main Azure Function
def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Processing chat request with OpenAI assistant.")
    try:
        # Parse the request body
        req_body = req.get_json()
        query = req_body.get("query")
        business_context = req_body.get("businessContext")
        session_id = req_body.get("sessionID") or str(uuid4())

        # Validate inputs
        if not query:
            return func.HttpResponse(
                json.dumps({"error": "Query is missing."}),
                status_code=400,
                mimetype="application/json"
            )

        if not business_context or not business_context.get("businessID"):
            return func.HttpResponse(
                json.dumps({"error": "Business context is missing or invalid."}),
                status_code=400,
                mimetype="application/json"
            )

        business_id = business_context["businessID"]

        # Fetch chat history
        chat_history = fetch_chat_history(business_id, session_id)
        messages = [{"role": message["role"], "content": message["content"]} for message in chat_history]

        # Add current query to messages
        messages.append({"role": "user", "content": query})

        # Add detailed system instructions
        messages.insert(0, {
            "role": "system",
            "content": (
                f"You are assisting with service and booking inquiries for a business. "
                f"The unique ID of the business is {business_id}. "
                f"For queries about services or bookings, use this ID to retrieve details. "
                f"Do not ask the user for the businessID unless explicitly required."
                f"For queries about booking a service, first retrieve the service details using 'getBusinessServices'. "
                f"Then check slot availability using 'checkSlot'. If a slot is available, proceed to book it using 'bookSlot'. "
                f"Always confirm with the user before booking."
            )
        })

        # Store the user's query
        store_chat_message(business_id, session_id, "user", query)

        # Call OpenAI assistant
        logging.info(f"Sending request to OpenAI API with model {LLM_MODEL}.")
        response = openai.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            functions=function_descriptions,
            function_call="auto",
            temperature=0.7,
            top_p=0.95,
            max_tokens=800,
            user=ASSISTANT_ID
        )

        # Parse assistant's response
        assistant_response = response.choices[0].message
        logging.info(f"Assistant response: {assistant_response}")

        # Handle function call if suggested
        if hasattr(assistant_response, "function_call") and assistant_response.function_call:
            return handle_function_call(assistant_response, messages, business_id, session_id)

        # Store assistant's response if no function is called
        store_chat_message(business_id, session_id, "assistant", assistant_response.content)
        return func.HttpResponse(
            json.dumps({"response": assistant_response.content}),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Internal Server Error", "details": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


# Helper Functions
def handle_function_call(assistant_response, messages, business_id, session_id):
    """Handle function call responses."""
    try:
        # Extract function call details
        function_call = assistant_response.function_call
        function_name = function_call.name
        arguments = json.loads(function_call.arguments)

        logging.info(f"Handling function call: {function_name} with arguments: {arguments}")

        # Retrieve the endpoint template for the function
        endpoint_template = function_endpoints.get(function_name)
        if not endpoint_template:
            raise ValueError(f"No endpoint configured for function: {function_name}")

        # Construct the endpoint URL and handle query parameters
        if function_name == "getBusinessServices":
            # Build the URL for getBusinessServices
            business_id = arguments.get("businessID")
            service_name = arguments.get("service_name", "")
            fields = "name,description,price,duration"
            endpoint = endpoint_template.format(
                businessID=quote(business_id),
                fields=quote(fields)
            )
            if service_name:
                endpoint += f"&service_name={quote(service_name)}"
        else:
            # For other functions, use the endpoint directly
            endpoint = endpoint_template

        logging.info(f"Calling endpoint: {endpoint}")

        # Make the API call
        if function_name == "getBusinessServices":
            response = requests.get(endpoint)
        else:
            response = requests.post(endpoint, json=arguments)

        response.raise_for_status()
        result = response.json()

        # Handle the response based on function
        if function_name == "getBusinessServices":
            return format_response(result, messages, function_name)

        elif function_name == "checkSlot":
            slot_availability = result
            if slot_availability.get("isAvailable"):
                # Prepare arguments for booking
                book_slot_arguments = {
                    "businessID": arguments["businessID"],
                    "service_name": arguments["service_name"],
                    "preferredDateTime": arguments["preferredDateTime"],
                    "clientName": arguments.get("clientName", "Default Client")
                }
                logging.info(f"Slot available. Preparing to call bookSlot with arguments: {book_slot_arguments}")
                next_function_call = {
                    "role": "assistant",
                    "function_call": {
                        "name": "bookSlot",
                        "arguments": json.dumps(book_slot_arguments)
                    }
                }
                return handle_function_call(next_function_call, messages, business_id, session_id)

            return func.HttpResponse(
                json.dumps({"message": "Slot is not available. Please suggest another time."}),
                status_code=200,
                mimetype="application/json"
            )

        elif function_name == "bookSlot":
            booking_confirmation = result
            logging.info(f"Booking confirmed: {booking_confirmation}")
            return func.HttpResponse(
                json.dumps({"message": "Booking confirmed!", "details": booking_confirmation}),
                status_code=200,
                mimetype="application/json"
            )

        else:
            raise ValueError(f"Unhandled function name: {function_name}")

    except requests.exceptions.RequestException as e:
        logging.error(f"HTTP request error: {e}")
        return func.HttpResponse(
            json.dumps({"error": f"HTTP request failed: {e}"}),
            status_code=500,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Error handling function call: {e}")
        return func.HttpResponse(
            json.dumps({"error": f"Error processing function call: {e}"}),
            status_code=500,
            mimetype="application/json"
        )
    
def format_response(result, messages, function_name):
    """Format the function response using OpenAI."""
    logging.info(f"Formatting function response for {function_name}. Result: {result}")

    try:
        # Add the function response as a "function" message to the chat history
        messages.append({"role": "function", "name": function_name, "content": json.dumps(result)})

        # Create a follow-up request to OpenAI to format the response naturally
        follow_up_response = openai.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.7,
            top_p=0.95,
            max_tokens=800,
            user=ASSISTANT_ID
        )

        assistant_message = follow_up_response.choices[0].message

        # Check if the assistant suggests another function call
        if hasattr(assistant_message, "function_call") and assistant_message.function_call:
            logging.info(f"Assistant requested another function: {assistant_message.function_call.name}")
            return handle_function_call(assistant_message, messages, None, None)

        # Return the assistant's formatted response
        return func.HttpResponse(
            json.dumps({"response": assistant_message.content}),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f"Error formatting function response: {e}")
        return func.HttpResponse(
            json.dumps({"error": f"Error formatting function response: {e}"}),
            status_code=500,
            mimetype="application/json"
        )


def fetch_chat_history(business_id, session_id, limit=CHAT_HISTORY_LIMIT):
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content FROM chathistory WHERE business_id = %s AND session_id = %s "
            "ORDER BY timestamp DESC LIMIT %s",
            (business_id, session_id, limit)
        )
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
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chathistory (business_id, session_id, role, content) VALUES (%s, %s, %s, %s)",
            (business_id, session_id, role, content)
        )
        conn.commit()
        cursor.close()
        conn.close()
    except psycopg2.Error as e:
        logging.error(f"Error storing chat message: {e}")
