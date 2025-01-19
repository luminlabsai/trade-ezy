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

        # Handle intermediate response
        if assistant_response.content:
            logging.info(f"Sending response: {assistant_response.content}")
            store_chat_message(business_id, sender_id, "assistant", assistant_response.content, "formatted")
            return func.HttpResponse(assistant_response.content, status_code=200, mimetype="text/plain")

        # Handle function calls
        if assistant_response.function_call:
            return handle_function_call(assistant_response, business_id, sender_id)

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
        logging.info(f"Function endpoints loaded: {function_endpoints}")
        function_call = assistant_response.function_call
        function_name = function_call.name
        arguments = json.loads(function_call.arguments)

        logging.info(f"Processing function call: {function_name} with arguments: {arguments}")

        # Ensure the function name is valid
        if function_name not in function_endpoints:
            logging.error(f"Unknown function name received: {function_name}")
            raise ValueError(f"Unknown function name: {function_name}")

        # Call the function endpoint
        endpoint_url = function_endpoints[function_name]
        logging.info(f"Resolved endpoint for {function_name}: {endpoint_url}")
        response = call_function_endpoint(function_name, arguments, sender_id, business_id)

        if function_name == "getBusinessServices":
            services = response.get("services", [])
            if not services:
                raise ValueError("No services found in the response.")

            if "preferredDateTime" not in arguments:
                formatted_services = "\n".join(
                    f"- {service['name']} (Price: ${service.get('price', 'N/A')}, Duration: {service.get('duration_minutes', 'N/A')} minutes)"
                    for service in services
                )
                follow_up_message = f"The business offers the following services:\n{formatted_services}"
                store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
                return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

            # Extract service details for booking/checking slot
            service_id = services[0].get("service_id")
            duration_minutes = services[0].get("duration_minutes")
            service_name = services[0].get("name")
            preferred_date_time = arguments.get("preferredDateTime")

            if not all([service_id, duration_minutes, preferred_date_time, service_name]):
                raise ValueError("Missing service_id, duration_minutes, preferred_date_time, or service_name for checkSlot.")

            check_slot_arguments = {
                "businessID": business_id,
                "serviceID": service_id,
                "preferredDateTime": preferred_date_time,
                "durationMinutes": duration_minutes,
            }

            logging.info(f"Triggering checkSlot with arguments: {check_slot_arguments}")
            check_slot_response = call_function_endpoint("checkSlot", check_slot_arguments, sender_id, business_id)

            is_available = check_slot_response.get("isAvailable")
            if not is_available:
                follow_up_message = "The requested slot is not available."
                store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
                return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

            # If the user wants to check availability without booking
            if not arguments.get("book", False):  # `book` flag indicates booking intent
                follow_up_message = "The slot is available."
                store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
                return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

            # Prepare for booking
            follow_up_message = (
                "The slot is available! Please provide your name, phone number, and email address to proceed with booking."
            )
            store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")

            # Temporarily store service details in chat history for booking continuation
            store_chat_message(business_id, sender_id, "system", json.dumps({
                "serviceID": service_id,
                "preferredDateTime": preferred_date_time,
                "durationMinutes": duration_minutes,
                "appointmentPurpose": service_name,
            }), "raw")
            return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

        elif function_name == "checkSlot":
            is_available = response.get("isAvailable")
            logging.info(f"checkSlot response: {response}")

            if is_available:
                follow_up_message = (
                    "The slot is available! Please provide your name, phone number, and email address "
                    "to proceed with booking."
                )
                store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
                return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")
            else:
                follow_up_message = "The requested slot is not available."
                store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
                return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

        elif function_name == "bookSlot":
            # Extract booking details
            client_name = arguments.get("clientName")
            phone_number = arguments.get("phoneNumber")
            email_address = arguments.get("emailAddress")

            # Validate required details
            missing_details = []
            if not client_name:
                missing_details.append("name")
            if not phone_number:
                missing_details.append("phone number")
            if not email_address:
                missing_details.append("email address")

            if missing_details:
                follow_up_message = f"Please provide your {', '.join(missing_details)} to complete the booking."
                store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
                return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

            # Retrieve temporary service details
            chat_history = fetch_chat_history(business_id, sender_id)
            service_details = None
            for message in reversed(chat_history):
                if message["role"] == "system" and "serviceID" in message["content"]:
                    service_details = json.loads(message["content"])
                    break

            if not service_details:
                raise ValueError("Missing service details for booking.")

            # Call bookSlot with all required parameters
            book_slot_arguments = {
                "businessID": business_id,
                "serviceID": service_details["serviceID"],
                "preferredDateTime": service_details["preferredDateTime"],
                "durationMinutes": service_details["durationMinutes"],
                "clientName": client_name,
                "appointmentPurpose": service_details["appointmentPurpose"],
                "phoneNumber": phone_number,
                "emailAddress": email_address,
            }

            logging.info(f"Calling bookSlot with arguments: {book_slot_arguments}")
            book_slot_response = call_function_endpoint("bookSlot", book_slot_arguments, sender_id, business_id)

            booking_result = book_slot_response.get("result")
            if booking_result:
                follow_up_message = f"Booking successful! Details: {booking_result}"
            else:
                follow_up_message = "Booking failed. Please try again."

            store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
            return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

        else:
            logging.error(f"Unknown function name after processing: {function_name}")
            raise ValueError(f"Unknown function name: {function_name}")

    except Exception as e:
        logging.error(f"Unexpected error in function call handling: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Function call failed", "details": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


def call_function_endpoint(function_name, payload, sender_id, business_id):
    """
    Send a request to the specified function endpoint.
    :param function_name: Name of the function to call.
    :param payload: Payload to send in the request.
    :param sender_id: Sender ID for the request.
    :param business_id: Business ID for the request.
    :return: JSON response from the function.
    """
    try:
        endpoint_url = function_endpoints.get(function_name)
        if not endpoint_url:
            logging.error(f"Unknown function name in call_function_endpoint: {function_name}")
            raise ValueError(f"Unknown function name: {function_name}")

        logging.info(f"Resolved endpoint for {function_name}: {endpoint_url}")

        # Include required parameters in the payload
        payload["senderID"] = sender_id
        payload["businessID"] = business_id

        logging.info(f"Calling {function_name} at {endpoint_url} with payload: {payload}")

        # Send the POST request to the function endpoint
        response = requests.post(endpoint_url, json=payload)
        response.raise_for_status()

        # Parse and return the JSON response
        logging.info(f"Response from {function_name}: {response.json()}")
        return response.json()

    except requests.RequestException as e:
        logging.error(f"HTTP request error for function {function_name}: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error calling {function_name}: {e}")
        raise


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
