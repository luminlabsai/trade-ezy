import os
import logging
import openai
import requests
import json
import azure.functions as func
import psycopg2
import string
from fuzzywuzzy import process
from uuid import uuid4
from urllib.parse import quote
from function_descriptions import function_descriptions
from function_endpoints import function_endpoints
from user_manager import get_or_create_user, update_user_details
import re
from dateutil.parser import parse
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
            f"You are assisting with service and booking inquiries for a business. "
            f"The unique ID of the business is {business_id}. "
            f"Here are the steps you should follow: "
            f"1. If the user asks about services, use `getBusinessServices` to fetch and present the list of services. "
            f"   - Only call `getBusinessServices` once per conversation unless explicitly asked to repeat it. "
            f"   - Always include the following parameters when calling functions: "
            f"     a. `sender_id`: The unique ID of the user. "
            f"     b. `business_id`: The unique ID of the business. "
            f"2. If the user expresses interest in booking a service: "
            f"   a. Automatically retrieve the duration (durationMinutes) from the service details."
            f"   b. Use the retrieved duration for checking slot availability and booking."
            f"   c. Only ask the user to confirm the duration if it is ambiguous or unavailable."
            f"3. Before proceeding with `bookSlot`, ensure you have collected all the necessary details: "
            f"   - Date and time of the appointment. "
            f"   - Client information (e.g., name, phone number, email address). "
            f"4. Use `bookSlot` to schedule the appointment only after all details are confirmed. "
            f"5. Avoid redundant function calls. "
            f"   - Do not call `getBusinessServices` if the list of services has already been fetched in this session. "
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

        # Validate function_call structure
        if not function_call or not hasattr(function_call, "name") or not hasattr(function_call, "arguments"):
            raise ValueError("Malformed function_call data. Missing 'name' or 'arguments'.")

        function_name = function_call.name
        arguments = json.loads(function_call.arguments)

        logging.info(f"Handling function call: {function_name} with arguments: {arguments}")

        # Add required parameters
        arguments["sender_id"] = sender_id
        arguments["business_id"] = business_id

        # Dispatch to the appropriate function
        if function_name == "getBusinessServices":
            response = handle_get_business_services(arguments, business_id, sender_id)
        elif function_name == "checkSlot":
            response = handle_check_slot(arguments, business_id, sender_id)
        elif function_name == "bookSlot":
            response = handle_book_slot(arguments, business_id, sender_id)
        elif function_name == "collectUserDetails":
            response = handle_collect_user_details(arguments, business_id, sender_id)
        else:
            raise ValueError(f"Unsupported function name: {function_name}")

        # Verify the function response message
        if isinstance(response, dict) and response.get("role") == "function" and "name" not in response:
            raise ValueError(f"Function response missing 'name': {response}")

        return response

    except Exception as e:
        logging.error(f"Error in handle_function_call: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Function call failed", "details": str(e)}),
            status_code=500,
            mimetype="application/json"
        )




def handle_get_business_services(arguments, business_id, sender_id):
    logging.info("Entered handle_get_business_services function.")
    logging.debug(f"Arguments received: {arguments}, BusinessID: {business_id}, SenderID: {sender_id}")

    endpoint = function_endpoints.get("getBusinessServices")
    if not endpoint:
        logging.error("Endpoint for getBusinessServices is not configured.")
        raise ValueError("Endpoint for getBusinessServices is not configured.")

    # Ensure required arguments are included
    arguments.setdefault("sender_id", sender_id)
    arguments.setdefault("business_id", business_id)
    logging.debug(f"Updated arguments for getBusinessServices: {arguments}")

    # Fetch all available services
    try:
        logging.info("Sending request to fetch all available services.")
        available_services_response = requests.post(
            endpoint,
            json={"business_id": business_id, "sender_id": sender_id, "fields": ["name", "service_id"]}
        )
        available_services_response.raise_for_status()
        available_services = [
            service["name"].lower() for service in available_services_response.json().get("services", [])
        ]
        if not available_services:
            logging.warning("No services found for the business.")
            follow_up_message = (
                "I couldn't find any services listed for this business. Please try again later."
            )
            store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
            return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")
        logging.debug(f"Available services fetched: {available_services}")
    except requests.RequestException as e:
        logging.error(f"Error fetching available services: {e}")
        return func.HttpResponse(
            "Failed to fetch available services. Please try again later.",
            status_code=500,
            mimetype="text/plain"
        )

    # Extract service_name from the query
    user_query = arguments.get("query", "").strip()
    logging.info(f"Extracting service name from user query: {user_query}")
    specific_service_name = extract_service_name_from_query(user_query, available_services)
    if not user_query:
        logging.info("User query is empty. Returning all available services.")
        follow_up_message = (
            f"We offer the following services: {', '.join([service.capitalize() for service in available_services])}. "
            "Let me know which one you're interested in."
        )
        store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
        return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

    logging.debug(f"Specific service name extracted: {specific_service_name}")

    # If no matching service is found, return the list of services
    if not specific_service_name:
        follow_up_message = (
            f"I couldn't find a matching service for '{user_query}'. "
            f"We offer the following services: {', '.join([service.capitalize() for service in available_services])}."
        )
        logging.info("No matching service name found. Returning fallback message.")
        store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
        return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

    # Call getBusinessServices with specific service_name
    get_services_payload = {
        "sender_id": sender_id,
        "business_id": business_id,
        "fields": ["name", "price", "description"],
        "service_name": specific_service_name
    }
    logging.debug(f"Payload for getBusinessServices call: {get_services_payload}")

    try:
        logging.info(f"Calling getBusinessServices endpoint with payload: {get_services_payload}")
        response = requests.post(endpoint, json=get_services_payload)
        response.raise_for_status()
        result = response.json()
        logging.debug(f"Response from getBusinessServices: {result}")
    except requests.RequestException as e:
        logging.error(f"Error calling getBusinessServices: {e}")
        return func.HttpResponse(
            "Failed to retrieve service details. Please try again later.",
            status_code=500,
            mimetype="text/plain"
        )

    services = result.get("services", [])
    logging.debug(f"Services retrieved: {services}")
    if not services:
        follow_up_message = f"No pricing details found for '{specific_service_name}'. Please try another query."
        logging.info(f"No matching services found. Returning follow-up message.")
        store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
        return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

    # Prepare the response for OpenAI
    function_response_message = {
        "role": "function",
        "name": "getBusinessServices",
        "content": json.dumps(result)
    }

    # Call OpenAI to format the response naturally
    try:
        logging.info("Sending request to OpenAI to format the response.")
        formatted_response = send_response_to_ai(
            function_response_message,
            business_id,
            sender_id,
            fallback_message="I couldn't retrieve the pricing details. Please try again."
        )
        return formatted_response
    except Exception as e:
        logging.error(f"Error formatting response with OpenAI: {e}.")
        return func.HttpResponse(
            "Failed to format the response. Please try again later.",
            status_code=500,
            mimetype="text/plain"
        )




def handle_check_slot(arguments, business_id, sender_id):
    endpoint = function_endpoints.get("checkSlot")
    if not endpoint:
        raise ValueError("Endpoint for checkSlot is not configured.")

    logging.info(f"Calling checkSlot with arguments: {arguments}")

    try:
        # Make the request to the checkSlot endpoint
        response = requests.post(endpoint, json={"business_id": business_id, "sender_id": sender_id, **arguments})
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as e:
        logging.error(f"Error calling checkSlot: {e}")
        return func.HttpResponse(
            "Failed to check slot availability. Please try again later.",
            status_code=500,
            mimetype="text/plain"
        )

    logging.info(f"Response from checkSlot: {result}")

    # Extract availability and preferred date-time
    is_available = result.get("isAvailable")
    preferred_date_time = arguments.get("preferredDateTime")

    if not is_available:
        # Slot is unavailable; ask for a new slot
        follow_up_message = (
            f"The slot at {preferred_date_time} is unavailable. "
            "Please provide an alternative date and time."
        )
        store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
        return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

    # Slot is available; check for missing user details
    user_info = get_or_create_user(sender_id)
    missing_details = []
    if not user_info.get("name"):
        missing_details.append("name")
    if not user_info.get("phone_number"):
        missing_details.append("phone number")
    if not user_info.get("email"):
        missing_details.append("email address")

    if missing_details:
        # Prompt for missing details
        follow_up_message = (
            f"The slot at {preferred_date_time} is available. "
            f"However, I need your {', '.join(missing_details)} to confirm the booking."
        )
        store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
        return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

    # Slot is available, and all details are present; confirm booking
    follow_up_message = (
        f"The slot at {preferred_date_time} is available. "
        "Would you like to proceed with confirming this booking?"
    )
    store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
    return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")





def handle_book_slot(arguments, business_id, sender_id):
    logging.info("Entered handle_book_slot function.")
    logging.debug(f"Arguments received: {arguments}, BusinessID: {business_id}, SenderID: {sender_id}")

    endpoint = function_endpoints.get("bookSlot")
    if not endpoint:
        logging.error("Endpoint for bookSlot is not configured.")
        raise ValueError("Endpoint for bookSlot is not configured.")

    logging.info("Preparing to book slot.")

    # Retrieve the latest user details
    try:
        user_info = get_or_create_user(sender_id)
        logging.debug(f"Retrieved user info: {user_info}")
    except Exception as e:
        logging.error(f"Error retrieving user info: {e}")
        return func.HttpResponse(
            "Failed to retrieve user details. Please try again later.",
            status_code=500,
            mimetype="text/plain"
        )

    # Extract or fallback to user details
    client_name = arguments.get("clientName") or user_info.get("name")
    phone_number = arguments.get("phoneNumber") or user_info.get("phone_number")
    email_address = arguments.get("emailAddress") or user_info.get("email")
    service_id = arguments.get("serviceID")
    preferred_date_time = arguments.get("preferredDateTime")
    duration_minutes = arguments.get("durationMinutes")

    logging.debug(f"Extracted details: {locals()}")

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

    # Fetch service duration if not provided
    if not duration_minutes and service_id:
        try:
            service_details = fetch_service_details(business_id, service_id)
            duration_minutes = service_details.get("duration_minutes")
        except Exception as e:
            logging.error(f"Failed to fetch service duration: {e}")
            return func.HttpResponse(
                "Failed to retrieve service details. Please try again later.",
                status_code=500,
                mimetype="text/plain"
            )

    # Validate all required details
    missing_details = [key for key in ["name", "phone_number", "email", "service", "preferred_date_time", "duration_minutes"]
                       if not locals().get(key)]
    if missing_details:
        follow_up_message = f"Please provide your {', '.join(missing_details)} to confirm the booking."
        logging.info(f"Missing details: {missing_details}")
        store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
        return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

    # Prepare and send booking request
    booking_payload = {
        "business_id": business_id,
        "sender_id": sender_id,
        "clientName": client_name,
        "phoneNumber": phone_number,
        "emailAddress": email_address,
        "serviceID": service_id,
        "preferredDateTime": preferred_date_time,
        "durationMinutes": duration_minutes
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
    service_endpoint = function_endpoints.get("getBusinessServices")
    if not service_endpoint:
        raise ValueError("getBusinessServices endpoint is not configured.")

    payload = {
        "business_id": business_id,
        "sender_id": "SYSTEM",  # Indicating a system call
        "fields": ["service_id", "name", "duration_minutes"],
        "service_name": service_id
    }
    logging.info(f"Fetching service details with payload: {payload}")
    response = requests.post(service_endpoint, json=payload)
    response.raise_for_status()
    services = response.json().get("services", [])
    if services:
        return services[0]
    raise ValueError(f"Service ID {service_id} not found.")




def handle_collect_user_details(arguments, business_id, sender_id):
    logging.info("Entered handle_collect_user_details function.")
    logging.debug(f"Arguments received: {arguments}, BusinessID: {business_id}, SenderID: {sender_id}")

    # Extract user query
    user_query = arguments.get("query", "").strip()
    if not user_query:
        logging.warning("User query is missing or empty.")
        return func.HttpResponse(
            json.dumps({"error": "No user query provided for extracting details."}),
            status_code=400,
            mimetype="application/json"
        )
    logging.info(f"Processing user query for details extraction: {user_query}")

    # Extract details from the user query
    try:
        extracted_details = extract_user_details(user_query)
        logging.debug(f"Extracted details from query: {extracted_details}")
    except Exception as e:
        logging.error(f"Error during details extraction: {e}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": "Failed to extract user details. Please try again later."}),
            status_code=500,
            mimetype="application/json"
        )

    # Update user information in the database if new details are found
    if extracted_details:
        try:
            logging.info(f"Updating user details in the database: {extracted_details}")
            update_user_details(sender_id, extracted_details)
            logging.info("User details successfully updated.")
        except Exception as e:
            logging.error(f"Error updating user details: {e}", exc_info=True)
            return func.HttpResponse(
                json.dumps({"error": "Failed to update user details. Please try again later."}),
                status_code=500,
                mimetype="application/json"
            )
    else:
        logging.warning("No details extracted from the user query.")

    # Retrieve the current user information from the database
    try:
        current_user_info = get_user_details(sender_id)
        logging.debug(f"Current user details from database: {current_user_info}")
        missing_details = [
            key for key in ["name", "phone_number", "email"]
            if not current_user_info.get(key)
        ]
    except Exception as e:
        logging.error(f"Error fetching current user details: {e}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": "Failed to fetch current user details. Please try again later."}),
            status_code=500,
            mimetype="application/json"
        )

    # Determine the next step based on missing details
    if missing_details:
        follow_up_message = f"Could you please provide your {', '.join(missing_details)}?"
        logging.info(f"Missing details detected: {missing_details}")
    else:
        follow_up_message = (
            "Thank you! All your details have been recorded. "
            "You can now proceed with booking or other requests."
        )
        logging.info("All user details are complete.")

    # Store the follow-up message in chat history
    try:
        logging.info("Storing follow-up message in chat history.")
        store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
    except Exception as e:
        logging.error(f"Error storing follow-up message: {e}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": "Failed to store follow-up message in chat history. Please try again later."}),
            status_code=500,
            mimetype="application/json"
        )

    # Return the follow-up message as a response
    logging.info(f"Returning follow-up message: {follow_up_message}")
    return func.HttpResponse(
        json.dumps({"message": follow_up_message}),
        status_code=200,
        mimetype="application/json"
    )



def preprocess_query(query, business_services=None):
    """
    Detects user intent and extracts relevant details from the query.

    Args:
        query (str): User's input query.
        business_services (list): A list of service names relevant to the business.

    Returns:
        dict: Contains detected intent and extracted details.
    """
    # Define keywords and patterns
    slot_keywords = ["book", "schedule", "reserve", "appointment"]
    user_detail_keywords = ["name", "phone", "email", "contact", "reach me"]
    date_time_pattern = r"\b(\d{1,2}(st|nd|rd|th)?\s\w+(\s\d{4})?\s?\d{1,2}(am|pm)?)\b"
    
    # Initialize intent and details
    intent = "general"
    details = {}

    query_lower = query.lower()

    # Detect booking intent
    if any(keyword in query_lower for keyword in slot_keywords):
        intent = "booking"

    # Detect user detail intent
    if any(keyword in query_lower for keyword in user_detail_keywords):
        intent = "user_details"

    # Extract service name dynamically from business_services
    if business_services:
        matched_service = next(
            (service for service in business_services if service.lower() in query_lower), None
        )
        if matched_service:
            details["service_name"] = matched_service

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

    Args:
        date_string (str): The date string to parse.

    Returns:
        datetime or None: Parsed datetime object or None if parsing fails.
    """
    try:
        logging.info(f"Parsing date string: {date_string}")
        return parse(date_string, fuzzy=True)  # Fuzzy parsing allows flexibility
    except ValueError as e:
        logging.error(f"Error parsing date: {e}")
        return None







def extract_service_name_from_query(user_query, available_services):
    """
    Extracts the service name from the user query by matching it with available services using fuzzy matching.
    """
    logging.debug(f"Extracting service name from query: '{user_query}'")
    logging.debug(f"Available services for matching: {available_services}")

    # Check for missing inputs
    if not user_query:
        logging.warning("User query is missing. Returning None.")
        return None
    if not available_services:
        logging.warning("Available services are missing. Returning None.")
        return None

    # Normalize and use fuzzy matching
    user_query_lower = user_query.strip().lower()
    available_services_lower = [service.lower() for service in available_services]

    # Use fuzzy matching for best match
    match, score = process.extractOne(user_query_lower, available_services_lower)
    if match and score >= 80:  # Threshold for matching (adjust as needed)
        matched_service = available_services[available_services_lower.index(match)]
        logging.info(f"Fuzzy matched service: '{matched_service}' (score: {score})")
        return matched_service

    logging.warning("No matching service name found using fuzzy matching.")
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
        FROM public.services
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



def extract_user_details(query):
    """
    Extract user details (name, phone number, and email) from a query.

    Args:
        query (str): User input text.

    Returns:
        dict: Extracted details, e.g., {"name": "John Doe", "phone_number": "1234567890", "email": "john@example.com"}.
    """
    details = {}

    # Extract email
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    email_match = re.search(email_pattern, query)
    if email_match:
        details["email"] = email_match.group()

    # Extract phone number
    phone_pattern = r'(\+?\d{1,4}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?[\d\s.-]{7,10}'
    phone_match = re.search(phone_pattern, query)
    if phone_match:
        details["phone_number"] = phone_match.group().strip()

    # Extract name (simple heuristic for capitalized words)
    name_pattern = r'\b[A-Z][a-z]+\s[A-Z][a-z]+\b'
    name_match = re.search(name_pattern, query)
    if name_match:
        details["name"] = name_match.group()

    return details




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
