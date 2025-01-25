import os
import logging
import openai
import requests
import json
import azure.functions as func
import psycopg2
import string
from rapidfuzz import process
from fuzzywuzzy import process
from uuid import uuid4
from urllib.parse import quote
from function_descriptions import function_descriptions
from function_endpoints import function_endpoints
from user_manager import get_or_create_user, update_user_details
import re
from dateutil.parser import parse
from datetime import datetime
import logging

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

import psycopg2

# Main Azure Function
# Main Azure Function
def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Processing chat request with OpenAI assistant.")
    try:
        # Parse the request body
        req_body = req.get_json()
        query = req_body.get("query", "").strip()
        sender_id = req_body.get("sender_id", "").strip()
        business_id = req_body.get("business_id", "").strip()

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
                json.dumps({"error": "SenderID is required."}),
                status_code=400,
                mimetype="application/json"
            )

        if not business_id:
            logging.error("BusinessID is missing in the request.")
            return func.HttpResponse(
                json.dumps({"error": "BusinessID is required."}),
                status_code=400,
                mimetype="application/json"
            )

        # Log received inputs
        logging.info(f"Query: {query}, SenderID: {sender_id}, BusinessID: {business_id}")

        # Preprocess the query to detect intent and extract details
        query_analysis = preprocess_query(query)
        intent = query_analysis.get("intent")
        extracted_details = query_analysis.get("details", {})

        logging.info(f"Preprocessed query - Intent: {intent}, Details: {extracted_details}")

        # Store the user's query
        logging.info("Storing user's query in chat history.")
        store_chat_message(business_id, sender_id, "user", query, "formatted")

        # Fetch chat history for context
        logging.info("Fetching chat history for context.")
        chat_history = fetch_chat_history(business_id, sender_id)
        messages = []
        for message in chat_history:
            if message["role"] == "function" and "name" not in message:
                logging.error(f"Function message missing 'name': {json.dumps(message, indent=2)}")
            messages.append({
                "role": message["role"],
                "content": message["content"],
                **({"name": message["name"]} if message["role"] == "function" else {})
            })
        messages.append({"role": "user", "content": query})

        # Add system instructions with dynamic context
        system_message = (
            f"You assist with service and booking inquiries for a business. The business ID is {business_id}. "
            f"Follow these steps: "
            f"1. For service inquiries, use `getBusinessServices` to fetch and present the list of services. "
            f"   - Call `getBusinessServices` only once per conversation unless explicitly requested. "
            f"   - Always include `sender_id` (user ID) and `business_id` (business ID) in function calls. "
            f"2. For booking inquiries: "
            f"   a. Automatically retrieve `duration_minutes` from service details. "
            f"   b. Ask for the date and time of the appointment. "
            f"   c. Call `checkSlot` to verify slot availability using the retrieved duration. "
            f"   d. Confirm the duration with the user only if it is ambiguous or missing. "
            f"   e. Always extract all user details provided in the query, including name, phone number, and email. "
            f"      - Return these details as structured JSON in function calls using the format: "
            f"        {{'function_call': {{'name': 'updateUserDetails', 'arguments': {{'name': 'John', 'phone_number': '9876543210', 'email': 'john.doe@example.com'}}}}}}. "
            f"      - If any details are missing, explicitly ask the user to provide them. "
            f"      - Use the function name `updateUserDetails` and include all available fields. "
            f"      - Do not respond with natural language if user details are provided. "
            f"   f. Always include extracted details in function calls like `checkSlot`, `bookSlot` and `updateUserDetails`. "
            f"3. If the slot is available, proceed to book: "
            f"   - Collect client details (name, phone number, email) after slot availability is confirmed. "
            f"   - Use `bookSlot` only after all details are confirmed. "
            f"4. Avoid asking for user details again if they are already stored. "
            f"5. Avoid redundant function calls: "
            f"   - Do not call `getBusinessServices` again if services have already been fetched in this session. "
            f"6. Clearly communicate progress and outcomes to the user at each step."
        )




        messages.insert(0, {"role": "system", "content": system_message})
        logging.debug(f"Constructed messages: {json.dumps(messages, indent=2)}")

        # Validate messages before sending to OpenAI
        for idx, message in enumerate(messages):
            if message["role"] == "function" and "name" not in message:
                logging.error(f"Function message at index {idx} is missing 'name': {json.dumps(message, indent=2)}")
                raise ValueError(f"Function message at index {idx} is missing 'name'.")

        # Call OpenAI assistant
        logging.debug(f"Messages array being sent to OpenAI:\n{json.dumps(messages, indent=2)}")
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

        # Store and send the assistant's response if content is available
        if assistant_response.content:
            logging.info("Storing assistant's response in chat history.")
            store_chat_message(business_id, sender_id, "assistant", assistant_response.content, "formatted")
            return func.HttpResponse(
                assistant_response.content, status_code=200, mimetype="text/plain"
            )

        # Immediately handle function calls
        if assistant_response.function_call:
            logging.info("Handling function call from assistant response.")
            return handle_function_call(assistant_response, business_id, sender_id)

        # Default fallback response
        logging.warning("Assistant response did not contain content or function call.")
        return func.HttpResponse(
            "I'm sorry, I couldn't process your request.",
            status_code=500,
            mimetype="text/plain"
        )

    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": "Internal Server Error", "details": str(e)}),
            status_code=500,
            mimetype="application/json"
        )




def handle_function_call(assistant_response, business_id, sender_id):
    try:
        function_call = assistant_response.function_call

        # Log the raw function_call for debugging
        logging.debug(f"Raw function_call: {function_call}")

        # Validate function_call structure
        if not function_call or not hasattr(function_call, "name") or not hasattr(function_call, "arguments"):
            logging.error("Malformed function_call data. Missing 'name' or 'arguments'.")
            raise ValueError("Malformed function_call data. Missing 'name' or 'arguments'.")

        function_name = function_call.name
        arguments = json.loads(function_call.arguments)

        # Log the parsed function name and arguments
        logging.info(f"Handling function call: {function_name} with arguments: {arguments}")

        # Add required parameters
        arguments["sender_id"] = sender_id
        arguments["business_id"] = business_id

        # Dispatch to the appropriate function
        if function_name == "getBusinessServices":
            logging.debug("Dispatching to handle_get_business_services.")
            return handle_get_business_services(arguments, business_id, sender_id)
        elif function_name == "checkSlot":
            logging.debug("Dispatching to handle_check_slot.")
            return handle_check_slot(arguments, business_id, sender_id)
        elif function_name == "bookSlot":
            logging.debug("Dispatching to handle_book_slot.")
            return handle_book_slot(arguments, business_id, sender_id)
        elif function_name == "updateUserDetails":
            try:
                # Update user details
                logging.info(f"Updating user details with arguments: {arguments}")
                update_user_details(sender_id, arguments)
                logging.info(f"User details updated successfully for sender_id: {sender_id}")

                # Continue the booking flow
                if "preferredDateTime" in arguments and "serviceID" in arguments:
                    return handle_check_slot(arguments, business_id, sender_id)

                # If no further flow, acknowledge success
                return func.HttpResponse(
                    "User details updated successfully.",
                    status_code=200,
                    mimetype="text/plain"
                )
            except Exception as e:
                logging.error(f"Failed to update user details: {e}")
                return func.HttpResponse(
                    "Failed to update user details.",
                    status_code=500,
                    mimetype="text/plain"
                )
        else:
            logging.error(f"Unsupported function name: {function_name}")
            raise ValueError(f"Unsupported function name: {function_name}")

    except Exception as e:
        logging.error(f"Error in handle_function_call: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Function call failed", "details": str(e)}),
            status_code=500,
            mimetype="application/json"
        )



def handle_get_business_services(arguments, business_id, sender_id):
    """
    Handles the 'getBusinessServices' function call, fetching details for all or specific services.
    """
    logging.info("Entered handle_get_business_services function.")
    logging.debug(f"Arguments received: {arguments}, BusinessID: {business_id}, SenderID: {sender_id}")

    # Ensure the endpoint is configured
    endpoint = function_endpoints.get("getBusinessServices")
    if not endpoint:
        logging.error("Endpoint for getBusinessServices is not configured.")
        raise ValueError("Endpoint for getBusinessServices is not configured.")

    # Fetch all available business services early
    try:
        logging.info("Fetching business services from the endpoint.")
        response = requests.post(
            endpoint,
            json={
                "business_id": business_id,
                "sender_id": sender_id,
                "fields": ["service_id", "name", "price", "duration_minutes"]
            }
        )
        response.raise_for_status()
        business_services = response.json().get("services", [])

        if not business_services:
            logging.warning("No business services found for this business.")
            follow_up_message = "I couldn't find any services listed for this business. Please try again later."
            store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
            return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")
        logging.debug(f"Fetched business services: {business_services}")

    except requests.RequestException as e:
        logging.error(f"Error fetching business services: {e}")
        return func.HttpResponse(
            "Failed to fetch business services. Please try again later.",
            status_code=500,
            mimetype="text/plain"
        )

    # Extract and preprocess user query
    user_query = arguments.get("query", "").strip().lower()
    if not user_query:
        logging.info("User query is empty. Returning all business services.")
        services_response = serialize_services_as_text(business_services)
        store_chat_message(business_id, sender_id, "assistant", services_response, "formatted")
        return func.HttpResponse(services_response, status_code=200, mimetype="text/plain")

    logging.info(f"Processing user query: {user_query}")

    # Pass available business services to preprocess_query
    available_service_names = [service["name"] for service in business_services]
    preprocessed_query = preprocess_query(user_query, available_service_names)
    intent = preprocessed_query["intent"]
    details = preprocessed_query["details"]

    # Handle pricing intent with missing service name
    if intent == "pricing" and "service_name" not in details:
        logging.warning("Pricing intent detected but no service name matched.")
        fallback_message = details.get("fallback_message", "I couldn't understand your request. Please try again.")
        store_chat_message(business_id, sender_id, "assistant", fallback_message, "formatted")
        return func.HttpResponse(fallback_message, status_code=200, mimetype="text/plain")

    # Handle cases where a specific service is matched
    if "service_name" in details:
        matched_service_name = details["service_name"].lower()
        service_details = next((s for s in business_services if s["name"].lower() == matched_service_name), None)

        if service_details:
            service_message = serialize_service_details_as_text(service_details)
            store_chat_message(business_id, sender_id, "assistant", service_message, "formatted")
            return func.HttpResponse(service_message, status_code=200, mimetype="text/plain")

    # If no specific service is matched, return all services as a human-readable list
    services_response = serialize_services_as_text(business_services)
    store_chat_message(business_id, sender_id, "assistant", services_response, "formatted")
    return func.HttpResponse(services_response, status_code=200, mimetype="text/plain")



def serialize_services_as_text(business_services):
    """
    Serializes a list of business services into a human-readable text format.
    """
    if not business_services:
        return "No services are currently available."

    lines = []
    for service in business_services:
        # Ensure all required fields are present and handle missing values gracefully
        name = service.get('name', 'Unknown Service')
        price = service.get('price', 'N/A')
        duration = service.get('duration_minutes', 'N/A')

        # Format the line with service details
        line = f"- {name} (Price: ${price}, Duration: {duration} mins)"
        lines.append(line)

    return "Here are the services we offer:\n" + "\n".join(lines)



def serialize_service_details_as_text(service_details):
    """
    Serializes a single service's details into a human-readable text format.
    """
    return (
        f"Service: {service_details['name']}\n"
        f"Price: ${service_details['price']}\n"
        f"Duration: {service_details['duration_minutes']} mins\n"
    )


def handle_check_slot(arguments, business_id, sender_id):
    """
    Handles calling the checkSlot function to check slot availability.
    """

    # Retrieve existing user details
    user_info = get_or_create_user(sender_id)
    logging.info(f"Retrieved user details: {user_info}")
    logging.info(f"handle_check_slot arguments: {arguments}")

    # Check if AI has provided extracted user details
    if "function_call" in arguments:
        logging.info("Processing AI-provided user details.")
        handle_function_call(arguments["function_call"], business_id, sender_id)

    # Check for missing details
    missing_details = [
        field for field in ["name", "phone_number", "email"]
        if not user_info.get(field)
    ]

    if missing_details:
        follow_up_message = (
            f"The slot at {arguments.get('preferredDateTime')} is available. "
            f"However, I need your {', '.join(missing_details)} to proceed."
        )
        store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
        return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

    # Call checkSlot endpoint
    endpoint = function_endpoints.get("checkSlot")
    if not endpoint:
        raise ValueError("Endpoint for checkSlot is not configured.")

    logging.info(f"Calling checkSlot with arguments: {arguments}")
    payload = {
        "senderID": sender_id,
        "preferredDateTime": arguments.get("preferredDateTime"),
        "durationMinutes": arguments.get("durationMinutes"),
        "serviceID": arguments.get("serviceID"),
        "business_id": business_id
    }

    try:
        response = requests.post(endpoint, json=payload)
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as e:
        logging.error(f"Error calling checkSlot: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Failed to check slot availability. Please try again later."}),
            status_code=500,
            mimetype="application/json"
        )

    logging.info(f"Response from checkSlot: {result}")

    # Check slot availability
    if not result.get("isAvailable"):
        follow_up_message = (
            f"The slot at {arguments.get('preferredDateTime')} is unavailable. "
            "Please provide an alternative date and time."
        )
        store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
        return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

    # Slot is available
    follow_up_message = (
        f"The slot at {arguments.get('preferredDateTime')} is available. "
        "Would you like to proceed with confirming this booking?"
    )
    store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
    return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")



def handle_book_slot(arguments, business_id, sender_id):
    """
    Handles the 'bookSlot' function call to confirm a booking with all necessary details.
    """
    logging.info("Entered handle_book_slot function.")
    logging.info(f"handle_book_slot arguments: {arguments}")
    logging.debug(f"Arguments received: {arguments}, BusinessID: {business_id}, SenderID: {sender_id}")

    # Retrieve or create user record
    user_info = get_or_create_user(sender_id)
    logging.debug(f"Retrieved user info: {user_info}")

    # Check if AI has provided extracted user details
    if "function_call" in arguments:
        logging.info("Processing AI-provided user details.")
        handle_function_call(arguments["function_call"], business_id, sender_id)

    # Refresh user info after potential update
    user_info = get_or_create_user(sender_id)

    # Combine arguments and user info to get complete details
    client_name = arguments.get("clientName") or user_info.get("name")
    phone_number = arguments.get("phoneNumber") or user_info.get("phone_number")
    email_address = arguments.get("emailAddress") or user_info.get("email")
    service_id = arguments.get("serviceID")
    preferred_date_time = arguments.get("preferredDateTime")
    duration_minutes = arguments.get("durationMinutes")

    # Validate preferred_date_time format
    if preferred_date_time:
        try:
            datetime.fromisoformat(preferred_date_time)
        except ValueError:
            return func.HttpResponse(
                "Invalid preferredDateTime format. Must be ISO 8601.",
                status_code=400,
                mimetype="text/plain"
            )

    # Check for missing details
    missing_details = [
        key for key in ["name", "phone_number", "email"]
        if not user_info.get(key)
    ]

    if missing_details:
        missing_details_str = ", ".join(missing_details)
        follow_up_message = f"Could you please provide your {missing_details_str} to proceed with booking?"
        logging.info(f"Prompting user for missing details: {missing_details}")
        store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
        return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

    # Ensure the endpoint is configured
    endpoint = function_endpoints.get("bookSlot")
    if not endpoint:
        logging.error("Endpoint for bookSlot is not configured.")
        raise ValueError("Endpoint for bookSlot is not configured.")

    # Proceed with booking if slot is available
    booking_payload = {
        "business_id": business_id,
        "sender_id": sender_id,
        "clientName": client_name,
        "phoneNumber": phone_number,
        "emailAddress": email_address,
        "serviceID": service_id,
        "preferredDateTime": preferred_date_time,
        "durationMinutes": duration_minutes,
    }
    try:
        logging.info(f"Booking slot with payload: {booking_payload}")
        response = requests.post(endpoint, json=booking_payload)
        response.raise_for_status()
        result = response.json()
        follow_up_message = (
            f"Thank you, {client_name}. Your booking for {service_id} on {preferred_date_time} "
            f"has been successfully recorded. A confirmation email will be sent to {email_address}."
        )
        store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
        return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")
    except requests.RequestException as e:
        logging.error(f"Error calling bookSlot endpoint: {e}")
        return func.HttpResponse(
            "Failed to book slot. Please try again later.",
            status_code=500,
            mimetype="text/plain"
        )


def fetch_service_details(business_id, service_id):
    """
    Fetch details for a specific service, such as durationMinutes, from the services data.
    """
    # Ensure the endpoint is configured
    service_endpoint = function_endpoints.get("getBusinessServices")
    if not service_endpoint:
        logging.error("getBusinessServices endpoint is not configured.")
        raise ValueError("getBusinessServices endpoint is not configured.")

    # Prepare the payload
    payload = {
        "business_id": business_id,
        "sender_id": "SYSTEM",  # Indicating a system call
        "fields": ["service_id", "name", "price", "_minutes"],
        "service_id": service_id
    }

    logging.info(f"Fetching service details with payload: {payload}")

    try:
        # Make the request to fetch service details
        response = requests.post(service_endpoint, json=payload)
        response.raise_for_status()

        # Parse the response
        services = response.json().get("services", [])
        if not services:
            logging.warning(f"No service found with ID: {service_id}")
            raise ValueError(f"Service ID {service_id} not found.")

        logging.info(f"Service details fetched successfully: {services[0]}")
        return services[0]  # Return the first matching service

    except requests.RequestException as e:
        logging.error(f"Error fetching service details: {e}")
        raise ValueError("Failed to fetch service details. Please try again later.")








def preprocess_query(query, business_services=None):
    """
    Detects user intent and extracts relevant details from the query.

    Args:
        query (str): User's input query.
        business_services (list): A list of service names relevant to the business.

    Returns:
        dict: Contains detected intent and extracted details.
    """
    # Define intent keywords and patterns
    slot_keywords = ["book", "schedule", "reserve", "appointment"]
    pricing_keywords = ["how much", "price", "cost"]
    user_detail_keywords = ["name", "phone", "email", "contact", "reach me"]
    date_time_pattern = r"\b(\d{1,2}(st|nd|rd|th)?\s\w+(\s\d{4})?\s?\d{1,2}(am|pm)?)\b"

    # Initialize intent and details
    intent = "general"
    details = {}

    query_lower = query.lower()

    # Debugging: Log the query
    logging.debug(f"Processing query: {query}")

    # Detect intents
    if any(keyword in query_lower for keyword in slot_keywords):
        intent = "booking"
    elif any(keyword in query_lower for keyword in pricing_keywords):
        intent = "pricing"
    elif any(keyword in query_lower for keyword in user_detail_keywords):
        intent = "user_details"

    # Process service name if the list is available
    if business_services:
        matched_service = process.extractOne(query_lower, business_services, scorer=process.fuzz.partial_ratio)
        if matched_service and matched_service[1] > 70:  # Confidence threshold
            details["service_name"] = matched_service[0]
        elif intent == "pricing":
            logging.warning("Pricing intent detected but no matching service name found.")
            details["fallback_message"] = "I couldn't find the service you're asking about. Can you clarify?"
    elif intent in ["pricing", "booking"]:
        logging.warning("No business services provided for service name matching.")

    # Extract date and time
    date_time_match = re.search(date_time_pattern, query)
    if date_time_match:
        details["preferredDateTime"] = parse_date_time(date_time_match.group(0))

    # Log the results
    logging.info(f"Preprocessed query: Intent: {intent}, Details: {details}")

    return {"intent": intent, "details": details}


def parse_date_time(date_string):
    """
    Parses a date string into a datetime object.
    """
    try:
        logging.info(f"Parsing date string: {date_string}")
        return parse(date_string, fuzzy=True)  # Fuzzy parsing allows flexibility
    except ValueError as e:
        logging.error(f"Error parsing date: {e}")
        return None





def extract_service_name_from_query(user_query, business_services):
    """
    Extracts the service name from the user query by matching it with available business services using fuzzy matching.
    """
    logging.debug(f"Extracting service name from query: '{user_query}'")
    logging.debug(f"Available business services for matching: {business_services}")

    # Check for missing inputs
    if not user_query:
        logging.warning("User query is missing. Returning None.")
        return None
    if not business_services:
        logging.warning("Available business services are missing. Returning None.")
        return None

    # Normalize and use fuzzy matching
    user_query_lower = user_query.strip().lower()
    business_services_lower = [service.lower() for service in business_services]

    # Use fuzzy matching for best match
    match, score = process.extractOne(user_query_lower, business_services_lower)
    if match and score >= 80:  # Threshold for matching (adjust as needed)
        matched_service = business_services[business_services_lower.index(match)]
        logging.info(f"Fuzzy matched service: '{matched_service}' (score: {score})")
        return matched_service

    logging.warning("No matching business service name found using fuzzy matching.")
    return None




def get_service_name(service_id, business_id):
    """
    Retrieve the service name for a given service_id and business_id.

    Args:
        service_id (str): The UUID of the service.
        business_id (str): The UUID of the business.

    Returns:
        str: The name of the service, or None if not found.
    """
    # Database connection details from environment variables
    db_config = {
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT")
    }

    query = """
        SELECT name
        FROM public.business_services
        WHERE service_id = %s AND business_id = %s
    """

    try:
        with psycopg2.connect(**db_config) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (service_id, business_id))
                result = cursor.fetchone()
                if result:
                    service_name = result[0]
                    logging.info(f"Service found: {service_name} for ServiceID: {service_id}, BusinessID: {business_id}")
                    return service_name
                else:
                    logging.warning(f"No service found for ServiceID: {service_id}, BusinessID: {business_id}")
                    return None

    except psycopg2.Error as e:
        logging.error(f"Database error while fetching service name: {e}")
        return None

    except Exception as e:
        logging.error(f"Unexpected error while fetching service name: {e}")
        return None



def send_response_to_ai(system_message, business_id, sender_id, fallback_message):
    """
    Pass the system response back to the AI for natural language formatting.
    """
    try:
        # Fetch chat history
        chat_history = fetch_chat_history(business_id, sender_id)
        messages = [{"role": message["role"], "content": message["content"]} for message in chat_history]
        messages.append(system_message)

        # Send to OpenAI
        logging.info(f"Sending response to AI for natural language formatting.")
        response = openai.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.7,
            top_p=0.95,
            max_tokens=800,
            user=ASSISTANT_ID
        )

        formatted_response = response.choices[0].message.content
        logging.info(f"AI formatted response: {formatted_response}")
        store_chat_message(business_id, sender_id, "assistant", formatted_response, "formatted")
        return func.HttpResponse(formatted_response, status_code=200, mimetype="text/plain")

    except Exception as e:
        logging.error(f"Error sending response to AI: {e}")
        return func.HttpResponse(fallback_message, status_code=200, mimetype="text/plain")



def get_user_details(sender_id):
    """
    Retrieve user details for the given `sender_id` from the `users` table.
    Returns a dictionary with the user details or an empty dictionary if no details are found.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name, phone_number, email
            FROM users
            WHERE sender_id = %s;
            """,
            (sender_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "name": row[0],
                "phone_number": row[1],
                "email": row[2]
            }
        else:
            return {}
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        return {}


def check_missing_user_details(sender_id):
    """
    Check the `users` table for missing details for the given `sender_id`.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name, phone_number, email FROM users WHERE sender_id = %s;
            """,
            (sender_id,)
        )
        user = cursor.fetchone()
        if not user:
            return ["name", "phone_number", "email"]  # All details are missing

        missing = []
        if not user[0]:
            missing.append("name")
        if not user[1]:
            missing.append("phone_number")
        if not user[2]:
            missing.append("email")
        return missing

    except Exception as e:
        logging.error(f"Error checking missing user details: {e}")
        return ["name", "phone_number", "email"]
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


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

        # Store the response as a function message
        if function_name == "bookSlot":
            booking_result = result.get("result")
            follow_up_message = (
                f"Booking successful! Details: {booking_result}"
                if booking_result
                else "Booking failed. Please try again."
            )
            # Store as a function message with the correct name
            store_chat_message(
                business_id,
                sender_id,
                "function",
                json.dumps(result),  # The full function response
                "formatted",
                name=function_name  # Ensure the name field is stored
            )
            store_chat_message(
                business_id,
                sender_id,
                "assistant",
                follow_up_message,
                "formatted"
            )
            return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

        # For other functions, store the response with the name
        store_chat_message(
            business_id,
            sender_id,
            "function",
            json.dumps(result),  # The full function response
            "formatted",
            name=function_name  # Ensure the name field is stored
        )

        return result

    except requests.RequestException as e:
        logging.error(f"HTTP request error for {function_name}: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error in {function_name}: {e}")
        raise



def extract_user_details(user_query):
    """
    Extract user details (name, phone number, email) from the query.
    """
    import re
    extracted_details = {}

    try:
        # Extract phone number
        phone_match = re.search(r'\b\d{10}\b', user_query)  # Matches 10-digit phone numbers
        if phone_match:
            extracted_details["phone_number"] = phone_match.group()

        # Extract name (assumes format "My name is [Name]")
        name_match = re.search(r"my name is ([A-Z][a-z]+)", user_query, re.IGNORECASE)
        if name_match:
            extracted_details["name"] = name_match.group(1)

        # Extract email address
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', user_query)
        if email_match:
            extracted_details["email"] = email_match.group()

        logging.debug(f"Extracted details: {extracted_details}")
    except Exception as e:
        logging.error(f"Error extracting details: {e}", exc_info=True)

    return extracted_details





def fetch_chat_history(business_id, sender_id, limit=CHAT_HISTORY_LIMIT):
    """
    Fetch chat history for context.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT role, content, name
            FROM chathistory
            WHERE business_id = %s AND sender_id = %s
            ORDER BY timestamp ASC
            LIMIT %s
            """,
            (business_id, sender_id, limit)
        )
        rows = cursor.fetchall()
        return [
            {"role": row[0], "content": row[1], "name": row[2]} if row[0] == "function" else {"role": row[0], "content": row[1]}
            for row in rows
        ]
    except Exception as e:
        logging.error(f"Error fetching chat history: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()





def store_chat_message(business_id, sender_id, role, content, message_type="formatted", name=None):
    """
    Store chat messages in the `chathistory` table.
    """
    try:
        logging.info(f"Storing message: role={role}, name={name}, content={content[:100]}")  # Log truncated content
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chathistory (business_id, sender_id, role, content, message_type, name)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (business_id, sender_id, role, content, message_type, name)
        )
        conn.commit()
        logging.info("Message stored successfully.")
    except psycopg2.Error as e:
        logging.error(f"Database error while storing chat message: {e}")
    except Exception as e:
        logging.error(f"Unexpected error storing chat message: {e}")
    finally:
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except Exception as cleanup_error:
            logging.error(f"Error during connection cleanup: {cleanup_error}")



def update_booking(booking_id, updates):
    """
    Update booking details in the `bookings` table.
    """
    try:
        # Log input details
        logging.info(f"Updating booking with ID: {booking_id}, Updates: {updates}")

        # Prepare database connection
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()

        # Build the SQL query dynamically
        set_clause = ", ".join([f"{key} = %s" for key in updates.keys()])
        query = f"""
            UPDATE bookings
            SET {set_clause}, updated_at = NOW()
            WHERE booking_id = %s;
        """
        logging.debug(f"Generated query: {query}")

        # Execute the query
        cursor.execute(query, list(updates.values()) + [booking_id])
        conn.commit()

        logging.info(f"Booking with ID: {booking_id} successfully updated.")

    except psycopg2.Error as e:
        logging.error(f"Database error while updating booking: {e}")
    except Exception as e:
        logging.error(f"Unexpected error while updating booking: {e}")
    finally:
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except Exception as cleanup_error:
            logging.error(f"Error during connection cleanup: {cleanup_error}")





def create_booking(sender_id, business_id, service_name=None, preferred_date_time=None):
    """
    Create a new booking entry in the `bookings` table.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO bookings (sender_id, business_id, service_name, preferred_date_time)
            VALUES (%s, %s, %s, %s)
            RETURNING booking_id;
            """,
            (sender_id, business_id, service_name, preferred_date_time)
        )
        booking_id = cursor.fetchone()[0]
        conn.commit()
        logging.info(f"Booking created successfully with ID: {booking_id}")
        return booking_id
    except psycopg2.Error as db_error:
        logging.error(f"Database error creating booking: {db_error}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error creating booking: {e}")
        raise
    finally:
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except Exception as cleanup_error:
            logging.error(f"Error during connection cleanup: {cleanup_error}")





def get_active_booking(sender_id, business_id):
    """
    Retrieve an active booking for the given sender_id and business_id.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT booking_id, sender_id, business_id, service_name, 
                   preferred_date_time, confirmed, created_at, updated_at
            FROM bookings
            WHERE sender_id = %s AND business_id = %s AND confirmed = FALSE
            ORDER BY created_at DESC LIMIT 1;
            """,
            (sender_id, business_id)
        )
        booking = cursor.fetchone()
        if booking:
            logging.info(f"Active booking found: {booking}")
            return {
                "booking_id": booking[0],
                "sender_id": booking[1],
                "business_id": booking[2],
                "service_name": booking[3],
                "preferred_date_time": booking[4],
                "confirmed": booking[5],
                "created_at": booking[6],
                "updated_at": booking[7],
            }
        else:
            logging.info("No active booking found.")
            return None
    except psycopg2.Error as db_error:
        logging.error(f"Database error retrieving active booking: {db_error}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error retrieving active booking: {e}")
        raise
    finally:
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except Exception as cleanup_error:
            logging.error(f"Error during connection cleanup: {cleanup_error}")

