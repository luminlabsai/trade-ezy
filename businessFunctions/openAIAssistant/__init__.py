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
        messages = [
            {"role": message["role"], "content": message["content"]}
            for message in chat_history
            if message["role"] in {"user", "assistant", "system"}
        ]

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
        store_chat_message(business_id, session_id, "user", query, "formatted")

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
        logging.info(f"Assistant raw response: {assistant_response}")

        # Convert raw response to a JSON-serializable format
        assistant_raw_message = {
            "role": assistant_response.role,
            "content": assistant_response.content,
            "function_call": {
                "name": assistant_response.function_call.name,
                "arguments": assistant_response.function_call.arguments
            } if assistant_response.function_call else None
        }

        # Store the raw response in the database
        store_chat_message(business_id, session_id, "assistant", json.dumps(assistant_raw_message), "raw")

        # Check for a function call
        if assistant_response.function_call:
            # Handle function call
            formatted_response = handle_function_call(assistant_response, messages, business_id, session_id)
            if isinstance(formatted_response, func.HttpResponse):
                formatted_content = json.loads(formatted_response.get_body())
                store_chat_message(business_id, session_id, "assistant", formatted_content["response"], "formatted")
                return func.HttpResponse(
                    formatted_content["response"],
                    status_code=200,
                    mimetype="text/plain"
                )

        # Store and return the assistant's direct response
        store_chat_message(business_id, session_id, "assistant", assistant_response.content, "formatted")
        return func.HttpResponse(
            assistant_response.content,
            status_code=200,
            mimetype="text/plain"
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
        function_call = assistant_response.function_call
        function_name = function_call.name
        arguments = json.loads(function_call.arguments)

        logging.info(f"Handling function call: {function_name} with arguments: {arguments}")

        endpoint = function_endpoints.get(function_name)
        if not endpoint:
            raise ValueError(f"No endpoint configured for function: {function_name}")

        if function_name == "getBusinessServices":
            # Call the getBusinessServices endpoint
            endpoint_url = endpoint.format(
                businessID=quote(arguments["businessID"]),
                fields=quote(",".join(arguments["fields"]))
            )
            response = requests.get(endpoint_url)
            response.raise_for_status()
            result = response.json()
            formatted_response = format_response(result, messages, function_name)

            # Return formatted response as HttpResponse
            return func.HttpResponse(
                json.dumps({"response": formatted_response}),
                status_code=200,
                mimetype="application/json"
            )

        # Handle other function calls (checkSlot, bookSlot)
        response = requests.post(endpoint, json=arguments)
        response.raise_for_status()
        return func.HttpResponse(
            json.dumps(response.json()),
            status_code=200,
            mimetype="application/json"
        )

    except requests.RequestException as e:
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
        # Add the function response as a message
        messages.append({"role": "function", "name": function_name, "content": json.dumps(result)})

        # Call OpenAI to format the response naturally
        follow_up_response = openai.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.7,
            top_p=0.95,
            max_tokens=800,
            user=ASSISTANT_ID
        )

        formatted_message = follow_up_response.choices[0].message.content
        logging.info(f"Formatted response: {formatted_message}")
        return formatted_message

    except Exception as e:
        logging.error(f"Error formatting function response: {e}")
        return "I'm sorry, there was an error formatting the response."


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

def store_chat_message(business_id, session_id, role, content, message_type="formatted"):
    """
    Store a chat message in the database.
    :param business_id: The ID of the business.
    :param session_id: The session ID for the conversation.
    :param role: The role of the message (e.g., 'user', 'assistant').
    :param content: The message content.
    :param message_type: 'raw' or 'formatted' for assistant messages.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chathistory (business_id, session_id, role, content, message_type)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (business_id, session_id, role, content, message_type)
        )
        conn.commit()
        cursor.close()
        conn.close()
        logging.info(f"Stored message: Role={role}, Type={message_type}, Content={content}")
    except psycopg2.Error as e:
        logging.error(f"Error storing chat message: {e}")



