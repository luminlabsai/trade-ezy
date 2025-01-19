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
from user_manager import get_or_create_user, update_user_details
import re

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
        sender_id = req_body.get("senderID")
        business_context = req_body.get("businessContext")
        business_id = business_context.get("businessID") if business_context else None

        # Validate inputs
        if not query:
            logging.error("Query is missing in the request.")
            return func.HttpResponse(
                json.dumps({"error": "Query is missing."}),
                status_code=400,
                mimetype="application/json"
            )

        if not sender_id:
            logging.error("SenderID is missing in the request.")
            return func.HttpResponse(
                json.dumps({"error": "senderID is required."}),
                status_code=400,
                mimetype="application/json"
            )

        if not business_id:
            logging.error("BusinessID is missing in the request.")
            return func.HttpResponse(
                json.dumps({"error": "businessID is required."}),
                status_code=400,
                mimetype="application/json"
            )

        # Log received inputs
        logging.info(f"Query: {query}, SenderID: {sender_id}, BusinessID: {business_id}")

        # Step 1: Extract user details from the query
        user_details = extract_user_details(query)
        if user_details:
            logging.info(f"Extracted user details: {user_details}")
            update_user_details(sender_id, user_details)  # Update user details in the database

        # Fetch chat history for the sender
        chat_history = fetch_chat_history(business_id, sender_id)
        messages = [
            {"role": message["role"], "content": message["content"]}
            for message in chat_history
        ]

        # Add the user's current query to messages
        messages.append({"role": "user", "content": query})

        # Add system instructions
        messages.insert(0, {
            "role": "system",
            "content": (
                f"You are assisting with service and booking inquiries for a business. "
                f"The unique ID of the business is {business_id}. "
                f"1. If the user asks about services, use `getBusinessServices`. "
                f"2. If the user asks to book a service, first use `getBusinessServices` to retrieve the service ID. "
                f"3. Then use `checkSlot` to verify availability of the slot at the requested time. "
                f"4. Finally, use `bookSlot` to schedule the appointment if the slot is available. "
                f"Ensure each step is processed before moving to the next."
            )
        })

        # Store the user's query
        store_chat_message(business_id, sender_id, "user", query, "formatted")

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

        # Step 2: Process assistant's content
        user_response = None
        if assistant_response.content:
            logging.info(f"Sending response: {assistant_response.content}")
            store_chat_message(business_id, sender_id, "assistant", assistant_response.content, "formatted")
            user_response = func.HttpResponse(assistant_response.content, status_code=200, mimetype="text/plain")

        # Step 3: Process assistant's function call
        function_response = None
        if assistant_response.function_call:
            function_response = handle_function_call(assistant_response, business_id, sender_id)

        # Step 4: Combine responses if both are present
        if user_response and function_response:
            logging.info("Returning combined response for content and function call.")
            return func.HttpResponse(
                json.dumps({
                    "content": assistant_response.content,
                    "function_response": json.loads(function_response.get_body().decode())
                }),
                status_code=200,
                mimetype="application/json"
            )

        # Step 5: Return individual response
        if user_response:
            return user_response
        if function_response:
            return function_response

        # Default fallback response
        return func.HttpResponse(
            "I'm sorry, I couldn't process your request.",
            status_code=500,
            mimetype="text/plain"
        )

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Internal Server Error", "details": str(e)}),
            status_code=500,
            mimetype="application/json"
        )



def handle_function_call(assistant_response, business_id, sender_id):
    try:
        function_call = assistant_response.function_call
        function_name = function_call.name
        arguments = json.loads(function_call.arguments)

        logging.info(f"Handling function call: {function_name} with arguments: {arguments}")

        # Ensure the user exists before proceeding
        user_info = get_or_create_user(sender_id)

        # Update user details if available in arguments
        if "clientName" in arguments or "phoneNumber" in arguments or "emailAddress" in arguments:
            logging.info(f"Updating user details with arguments: {arguments}")
            update_user_details(sender_id, arguments)

        # Get the appropriate endpoint
        endpoint = function_endpoints.get(function_name)
        if not endpoint:
            raise ValueError(f"No endpoint configured for function: {function_name}")

        # Handle specific function calls
        if function_name == "getBusinessServices":
            logging.info(f"Calling {function_name} at {endpoint} with arguments: {arguments}")
            
            response = requests.post(
                endpoint,
                json={"senderID": sender_id, "businessID": business_id, **arguments}
            )
            response.raise_for_status()
            result = response.json()
            logging.info(f"Response from {function_name}: {result}")

            # Process the result
            services = result.get("services", [])
            if not services:
                follow_up_message = "No services found. Please try again with a different query."
                store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
                return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

            # Handle single or multiple services
            if len(services) == 1:
                selected_service = services[0]
                logging.info(f"Storing selected service context: {selected_service}")
                store_chat_message(business_id, sender_id, "system", json.dumps({"service": selected_service}), "raw")
                follow_up_message = (
                    f"The service '{selected_service['name']}' is priced at "
                    f"${selected_service['price']:.2f} for {selected_service['duration_minutes']} minutes. "
                    "Would you like to book this service?"
                )
            else:
                follow_up_message = (
                    "Multiple services matched your query. Please specify:\n" +
                    "\n".join(f"- {service['name']} (${service['price']})" for service in services)
                )

            store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
            return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")


        elif function_name == "checkSlot":
            logging.info(f"Calling {function_name} at {endpoint} with arguments: {arguments}")
            response = requests.post(
                endpoint,
                json={"senderID": sender_id, **arguments}
            )
            response.raise_for_status()
            result = response.json()
            logging.info(f"Response from {function_name}: {result}")

            is_available = result.get("isAvailable")
            if is_available:
                logging.info(f"Slot is available for arguments: {arguments}")

                # Fetch user details to check if booking can proceed automatically
                client_name = user_info.get("name")
                phone_number = user_info.get("phone_number")
                email_address = user_info.get("email")

                # Ensure all booking details are present
                if client_name and phone_number and email_address:
                    # Automatically transition to bookSlot
                    book_slot_payload = {
                        **arguments,
                        "clientName": client_name,
                        "phoneNumber": phone_number,
                        "emailAddress": email_address,
                        "businessID": business_id,
                        "senderID": sender_id,
                    }
                    logging.info(f"Automatically transitioning to bookSlot with payload: {book_slot_payload}")
                    return call_function_endpoint("bookSlot", book_slot_payload, sender_id, business_id)
                else:
                    # Prompt for missing details
                    missing_details = []
                    if not client_name:
                        missing_details.append("name")
                    if not phone_number:
                        missing_details.append("phone number")
                    if not email_address:
                        missing_details.append("email address")

                    follow_up_message = (
                        f"The slot is available! Please provide your {', '.join(missing_details)} "
                        f"to proceed with booking."
                    )
                    store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
                    return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")
            else:
                follow_up_message = "The requested slot is not available. Please try a different time."
                store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
                return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

        # bookSlot
        elif function_name == "bookSlot":
            logging.info(f"Fetching user details to complete booking.")
            user_info = get_or_create_user(sender_id)
            logging.info(f"User found: {user_info}")

            # Extract user and assistant-provided details
            client_name = arguments.get("clientName") or user_info.get("name")
            phone_number = arguments.get("phoneNumber") or user_info.get("phone_number")
            email_address = arguments.get("emailAddress") or user_info.get("email")
            service = arguments.get("service")

            # Retrieve service context from chat history if not provided
            if not service:
                chat_history = fetch_chat_history(business_id, sender_id)
                for message in reversed(chat_history):
                    if message["role"] == "system" and "services" in message["content"]:
                        try:
                            services_context = json.loads(message["content"])
                            service_context = services_context.get("services", [])[0]  # Assume the first service
                            if service_context:
                                service = service_context.get("name")
                                logging.info(f"Using service from chat context: {service}")
                                break
                        except json.JSONDecodeError as e:
                            logging.error(f"Failed to parse system message content: {e}")

            # Identify missing details
            missing_details = []
            if not client_name:
                missing_details.append("name")
            if not phone_number:
                missing_details.append("phone number")
            if not email_address:
                missing_details.append("email address")
            if not service:
                missing_details.append("service")

            if missing_details:
                logging.warning(f"Missing booking details: {missing_details}. Requesting more information.")
                follow_up_message = f"Please provide your {', '.join(missing_details)} to proceed with the booking."
                store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
                return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

            # Prepare the booking payload
            book_slot_payload = {
                "clientName": client_name,
                "phoneNumber": phone_number,
                "emailAddress": email_address,
                "service": service,  # Include service name
                "businessID": business_id,
                "senderID": sender_id,
                "preferredDateTime": arguments.get("preferredDateTime"),
                "durationMinutes": arguments.get("durationMinutes"),
            }

            logging.info(f"Calling {function_name} at {endpoint} with payload: {book_slot_payload}")
            response = requests.post(endpoint, json=book_slot_payload)
            response.raise_for_status()
            result = response.json()
            logging.info(f"Response from {function_name}: {result}")

            # Process booking result
            booking_result = result.get("result")
            follow_up_message = (
                f"Booking successful! Details: {booking_result}"
                if booking_result
                else "Booking failed. Please try again."
            )
            store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
            return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")


        else:
            raise ValueError(f"Unsupported function name: {function_name}")

    except requests.exceptions.RequestException as e:
        logging.error(f"HTTP error for {function_name}: {e}")
        return func.HttpResponse(
            json.dumps({"error": f"HTTP request to {function_name} failed", "details": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Error handling function call: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Function call failed", "details": str(e)}),
            status_code=500,
            mimetype="application/json"
        )



def call_function_endpoint(function_name, payload, sender_id, business_id):
    try:
        endpoint_url = function_endpoints.get(function_name)
        if not endpoint_url:
            logging.error(f"Unknown function name: {function_name}")
            raise ValueError(f"Unknown function name: {function_name}")

        logging.info(f"Calling {function_name} at {endpoint_url} with payload: {payload}")
        response = requests.post(endpoint_url, json=payload)
        response.raise_for_status()

        result = response.json()
        logging.info(f"Response from {function_name}: {result}")

        # Handle response for bookSlot if necessary
        if function_name == "bookSlot":
            booking_result = result.get("result")
            follow_up_message = (
                f"Booking successful! Details: {booking_result}"
                if booking_result
                else "Booking failed. Please try again."
            )
            store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
            return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

        return result

    except requests.RequestException as e:
        logging.error(f"HTTP request error for {function_name}: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error in {function_name}: {e}")
        raise


def extract_user_details(query):
    """
    Extract user details (name, email, phone number) from the user's query.

    Args:
        query (str): The user's input query.

    Returns:
        dict: A dictionary containing extracted user details.
    """
    details = {}

    # Match patterns for email
    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", query)
    if email_match:
        details["emailAddress"] = email_match.group(0).strip()

    # Match patterns for phone numbers (simplified for example)
    phone_match = re.search(r"(?:\+61|0)[4-5]\d{8}", query)
    if phone_match:
        details["phoneNumber"] = phone_match.group(0).strip()

    # Match for name (assume starts with "my name is")
    name_match = re.search(r"(?i)my name is ([a-zA-Z ]+)", query)
    if name_match:
        details["clientName"] = name_match.group(1).strip()

    return details




def fetch_chat_history(business_id, sender_id, limit=CHAT_HISTORY_LIMIT):
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT role, content FROM chathistory
            WHERE business_id = %s AND sender_id = %s
            ORDER BY timestamp ASC
            LIMIT %s
            """,
            (business_id, sender_id, limit)
        )
        rows = cursor.fetchall()
        return [{"role": row[0], "content": row[1]} for row in rows]
    except Exception as e:
        logging.error(f"Error fetching chat history: {e}")
        return []


def store_chat_message(business_id, sender_id, role, content, message_type="formatted"):
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chathistory (business_id, sender_id, role, content, message_type)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (business_id, sender_id, role, content, message_type)
        )
        conn.commit()
    except Exception as e:
        logging.error(f"Error storing chat message: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
