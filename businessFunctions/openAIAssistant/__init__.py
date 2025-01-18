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
                f"Respond as if you're aware of all prior messages in the conversation."
                f"Do not ask the user for the businessID unless explicitly required."
                f"For queries about booking a service, first retrieve the service details using 'getBusinessServices'. "
                f"Then check slot availability using 'checkSlot'. If a slot is available, proceed to book it using 'bookSlot'. "
                f"Always confirm with the user before booking."
                f"Extract and convert date and time to ISO 8601 format (YYYY-MM-DDTHH:MM+10:00)."
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
            logging.info(f"Formatted response from handle_function_call: {formatted_response}")
            #
            if isinstance(formatted_response, func.HttpResponse):
                try:
                    response_body = formatted_response.get_body()
                    logging.info(f"HttpResponse body: {response_body}")

                    # Check if response_body is JSON or plain text
                    try:
                        parsed_response = json.loads(response_body)
                        formatted_content = parsed_response.get("response", response_body.decode("utf-8"))
                    except json.JSONDecodeError:
                        logging.warning("Response body is plain text, not JSON.")
                        formatted_content = response_body.decode("utf-8")

                    store_chat_message(business_id, session_id, "assistant", formatted_content, "formatted")
                    return func.HttpResponse(
                        formatted_content,
                        status_code=200,
                        mimetype="text/plain"
                    )
                except Exception as e:
                    logging.error(f"Error processing HttpResponse: {e}")
                    return func.HttpResponse(
                        json.dumps({"error": "Failed to process formatted response.", "details": str(e)}),
                        status_code=500,
                        mimetype="application/json"
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
            fields = ",".join(arguments.get("fields", ["name", "description", "price", "duration"]))
            endpoint_url = endpoint.format(
                businessID=quote(arguments["businessID"]),
                fields=quote(fields)
            )
            logging.info(f"Calling endpoint: {endpoint_url}")
            response = requests.get(endpoint_url)
            response.raise_for_status()

            result = response.json()
            formatted_response = format_response(result, messages, function_name)

            return func.HttpResponse(
                json.dumps({"response": formatted_response}),
                status_code=200,
                mimetype="application/json"
            )

        # Handle checkSlot
        elif function_name == "checkSlot":
            payload = prepare_check_slot_payload(arguments)
            logging.info(f"Calling checkSlot with payload: {payload}")
            response = requests.post(endpoint, json=payload)
            response.raise_for_status()

            response_data = response.json()
            logging.info(f"checkSlot result: {response_data}")
            store_chat_message(business_id, session_id, "assistant", json.dumps(response_data), "formatted")

            # If slot is available, call bookSlot
            if response_data.get("isAvailable"):
                logging.info("Slot is available, preparing to call bookSlot.")
                book_slot_payload = prepare_book_slot_payload(arguments, defaults={"durationMinutes": payload["durationMinutes"]})
                logging.info(f"Calling bookSlot with payload: {json.dumps(book_slot_payload, indent=2)}")

                book_slot_response = requests.post(function_endpoints["bookSlot"], json=book_slot_payload)
                book_slot_response.raise_for_status()

                book_slot_data = book_slot_response.json()
                logging.info(f"bookSlot result: {book_slot_data}")
                store_chat_message(business_id, session_id, "assistant", json.dumps(book_slot_data), "formatted")

                # Format the response naturally
                messages.append({
                    "role": "function",
                    "name": "bookSlot",
                    "content": json.dumps(book_slot_data)
                })
                formatted_response = openai.chat.completions.create(
                    model=LLM_MODEL,
                    messages=messages,
                    temperature=0.7,
                    top_p=0.95,
                    max_tokens=800,
                    user=ASSISTANT_ID
                )
                logging.info(f"Raw OpenAI response: {formatted_response}")

                formatted_message = formatted_response.choices[0].message.content
                if not formatted_message.strip():
                    raise ValueError("Formatted response from OpenAI is empty.")

                logging.info(f"Formatted bookSlot response: {formatted_message}")
                store_chat_message(business_id, session_id, "assistant", formatted_message, "formatted")

                # Return the formatted response after successful booking
                return func.HttpResponse(
                    formatted_message,
                    status_code=200,
                    mimetype="text/plain"
                )

            # If the slot is not available, return the fallback response
            logging.info("Slot is not available. Informing the assistant.")
            return func.HttpResponse(
                json.dumps({"response": "The requested time slot is not available."}),
                status_code=200,
                mimetype="application/json"
            )

        elif function_name == "bookSlot":
            logging.info(f"Calling bookSlot with arguments: {arguments}")
            response = requests.post(endpoint, json=arguments)
            response.raise_for_status()

            book_slot_data = response.json()
            logging.info(f"bookSlot result: {book_slot_data}")
            store_chat_message(business_id, session_id, "assistant", json.dumps(book_slot_data), "formatted")

            messages.append({
                "role": "function",
                "name": "bookSlot",
                "content": json.dumps(book_slot_data)
            })

            formatted_response = openai.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                temperature=0.7,
                top_p=0.95,
                max_tokens=800,
                user=ASSISTANT_ID
            )
            logging.info(f"Raw OpenAI response: {formatted_response}")

            formatted_message = formatted_response.choices[0].message.content
            if not formatted_message.strip():
                raise ValueError("Formatted response from OpenAI is empty.")

            logging.info(f"Formatted bookSlot response: {formatted_message}")
            # Final return
            try:
                # Ensure the formatted_message is a plain string
                if not isinstance(formatted_message, str) or not formatted_message.strip():
                    raise ValueError("Formatted message is empty or not a valid string.")

                logging.info(f"Returning formatted response to client: {formatted_message}")
                return func.HttpResponse(
                    formatted_message,
                    status_code=200,
                    mimetype="text/plain"
                )
            except Exception as e:
                logging.error(f"Error while returning the response: {e}")
                return func.HttpResponse(
                    json.dumps({"error": "Failed to process the final response.", "details": str(e)}),
                    status_code=500,
                    mimetype="application/json"
                )


    except requests.RequestException as e:
        logging.error(f"HTTP request error: {e}")
        return func.HttpResponse(
            json.dumps({"error": f"HTTP request failed: {e}"}),
            status_code=500,
            mimetype="application/json"
        )
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON response."}),
            status_code=500,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Internal Server Error", "details": str(e)}),
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
        logging.info(f"Raw OpenAI response: {formatted_response}")

        formatted_message = follow_up_response.choices[0].message.content
        logging.info(f"Formatted response: {formatted_message}")
        return formatted_message

    except Exception as e:
        logging.error(f"Error formatting function response: {e}")
        return "I'm sorry, there was an error formatting the response."


def prepare_check_slot_payload(arguments):
    if "serviceID" in arguments:
        # Fetch service duration if serviceID is provided
        service_id = arguments["serviceID"]
        # Fetch service details logic here...
        arguments["durationMinutes"] = 45  # Example duration; replace with fetched data

    # Validate arguments
    if not arguments.get("preferredDateTime") or not arguments.get("durationMinutes"):
        raise ValueError("Invalid arguments for checkSlot. 'preferredDateTime' and 'durationMinutes' are required.")
    return {
        "preferredDateTime": arguments["preferredDateTime"],
        "durationMinutes": arguments["durationMinutes"]
    }

def prepare_book_slot_payload(arguments, defaults=None):
    """
    Prepare and validate the payload for the bookSlot function.
    :param arguments: The raw arguments from the assistant's function call.
    :param defaults: Default values for optional fields.
    :return: A dictionary payload ready for the bookSlot API.
    :raises ValueError: If required fields are missing.
    """
    if defaults is None:
        defaults = {}

    # Validate required arguments
    required_fields = ["businessID", "serviceID", "preferredDateTime"]
    for field in required_fields:
        if not arguments.get(field):
            raise ValueError(f"Missing required parameter: {field}")

    # Construct payload with optional defaults
    payload = {
        "businessID": arguments["businessID"],
        "serviceID": arguments["serviceID"],
        "preferredDateTime": arguments["preferredDateTime"],
        "clientName": arguments.get("clientName", defaults.get("clientName", "Unknown Client")),
        "appointmentPurpose": arguments.get("appointmentPurpose", defaults.get("appointmentPurpose", "General Inquiry")),
        "phoneNumber": arguments.get("phoneNumber", defaults.get("phoneNumber", "0000000000")),
        "emailAddress": arguments.get("emailAddress", defaults.get("emailAddress", "noemail@example.com")),
        "durationMinutes": arguments.get("durationMinutes", defaults.get("durationMinutes"))
    }

    # Ensure durationMinutes is present
    if not payload["durationMinutes"]:
        raise ValueError("Missing required parameter: durationMinutes")

    return payload

def fetch_chat_history(business_id, session_id, limit=CHAT_HISTORY_LIMIT):
    """
    Fetch chat history for a given business ID and session ID.
    :param business_id: The ID of the business.
    :param session_id: The session ID for the conversation.
    :param limit: The maximum number of messages to fetch.
    :return: A list of dictionaries representing the chat history.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT role, content FROM chathistory
            WHERE business_id = %s AND session_id = %s
            ORDER BY timestamp ASC
            LIMIT %s
            """,
            (business_id, session_id, limit)
        )
        rows = cursor.fetchall()

        chat_history = []
        for row in rows:
            # Ensure content is returned as a string
            content = row[1]
            if isinstance(content, dict):
                content = json.dumps(content)  # Serialize to string if it's a dictionary
            chat_history.append({"role": row[0], "content": content})

        return chat_history
    except psycopg2.Error as e:
        logging.error(f"Error fetching chat history: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def store_chat_message(business_id, session_id, role, content, message_type="formatted"):
    """
    Store a chat message in the database.
    :param business_id: The ID of the business.
    :param session_id: The session ID for the conversation.
    :param role: The role of the message (e.g., 'user', 'assistant').
    :param content: The message content (must be serialized to string).
    :param message_type: 'raw' or 'formatted' for assistant messages.
    """
    try:
        # Ensure content is serialized if it's a dictionary
        if isinstance(content, dict):
            content = json.dumps(content)

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
        logging.info(f"Stored message: Role={role}, Type={message_type}, Content={content}")
    except (psycopg2.Error, ValueError) as e:
        logging.error(f"Error storing chat message: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
