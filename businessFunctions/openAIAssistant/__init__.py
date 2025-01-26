import os
import logging
import openai
import requests
import json
import azure.functions as func
import psycopg2
import string
from rapidfuzz import process
from uuid import uuid4
from urllib.parse import quote
import re
from dateutil.parser import parse
from datetime import datetime
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



# Utility functions
def extract_user_details(user_query):
    """
    Extract user details (name, phone number, email) from the query.
    """
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






# Service related helper functions
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


def extract_service_id(content, business_id):
    """
    Extracts service ID by matching a service name in the content string to the services offered by the business.

    Args:
        content (str): The input string containing the service name.
        business_id (str): The ID of the business to fetch services from.

    Returns:
        str: Service ID if found, otherwise None.
    """
    try:
        # Fetch all services for the business
        business_services = fetch_service_details(business_id, None)  # Fetch all services

        # Extract service name from content
        service_name = extract_service_name_from_query(content, [service["name"] for service in business_services])
        if service_name:
            # Match service name to get its ID
            for service in business_services:
                if service["name"] == service_name:
                    return service["service_id"]
    except Exception as e:
        logging.error(f"Failed to extract service ID: {e}")
    return None




def extract_duration(service_id, business_id):
    """
    Extracts the duration in minutes for a specific service ID.

    Args:
        service_id (str): The ID of the service.
        business_id (str): The ID of the business.

    Returns:
        int: Duration in minutes if found, otherwise None.
    """
    try:
        # Fetch service details for the given service ID
        service_details = fetch_service_details(business_id, service_id)
        return service_details.get("duration_minutes") if service_details else None
    except Exception as e:
        logging.error(f"Failed to extract duration: {e}")
    return None


# Database helper functions
def get_or_create_user(sender_id):
    """
    Retrieve or create a user record in the database.

    Args:
        sender_id (str): The sender ID of the user.

    Returns:
        dict: A dictionary of user details (e.g., {"name": "John", "email": "john@example.com"}).
    """
    try:
        query = "SELECT sender_id, name, phone_number, email FROM public.users WHERE sender_id = %s"
        with psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (sender_id,))
                result = cursor.fetchone()
                if result:
                    return {
                        "sender_id": result[0],
                        "name": result[1],
                        "phone_number": result[2],
                        "email": result[3]
                    }

                # Create a new user if none exists
                insert_query = """
                    INSERT INTO public.users (sender_id, created_at, updated_at)
                    VALUES (%s, NOW(), NOW())
                """
                cursor.execute(insert_query, (sender_id,))
                conn.commit()
                logging.info(f"New user created with sender_id: {sender_id}")
                return {"sender_id": sender_id, "name": None, "phone_number": None, "email": None}
    except Exception as e:
        logging.error(f"Error in get_or_create_user: {e}")
        return None






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


# Endpoint handlers

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




def handle_check_slot(arguments, business_id, sender_id):
    """
    Handles calling the checkSlot function to check slot availability.
    """

    # Validate required arguments
    if not all(k in arguments for k in ["preferredDateTime", "serviceID", "durationMinutes"]):
        return func.HttpResponse(
            "Missing required arguments for slot checking.",
            status_code=400,
            mimetype="text/plain"
        )

    # Call checkSlot endpoint
    endpoint = function_endpoints.get("checkSlot")
    if not endpoint:
        raise ValueError("Endpoint for checkSlot is not configured.")

    payload = {
        "senderID": sender_id,
        "preferredDateTime": arguments["preferredDateTime"],
        "durationMinutes": arguments["durationMinutes"],
        "serviceID": arguments["serviceID"],
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

    if not result.get("isAvailable"):
        follow_up_message = (
            f"The slot at {arguments['preferredDateTime']} is unavailable. "
            "Please provide an alternative date and time."
        )
        store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
        return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")

    # Slot is available, proceed to booking confirmation
    follow_up_message = (
        f"The slot at {arguments['preferredDateTime']} is available. "
        "Would you like to proceed with confirming this booking?"
    )
    store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
    return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")





def handle_book_slot(arguments, business_id, sender_id):
    """
    Handles the 'bookSlot' function call to confirm a booking with all necessary details.
    """

    # Retrieve user record
    user_info = get_or_create_user(sender_id)

    # Combine arguments and user info
    client_name = arguments.get("clientName") or user_info.get("name")
    phone_number = arguments.get("phoneNumber") or user_info.get("phone_number")
    email_address = arguments.get("emailAddress") or user_info.get("email")
    service_id = arguments.get("serviceID")
    preferred_date_time = arguments.get("preferredDateTime")
    duration_minutes = arguments.get("durationMinutes")

    # Ensure all required fields are present
    if not all([client_name, phone_number, email_address, service_id, preferred_date_time, duration_minutes]):
        return func.HttpResponse(
            "Missing required fields for booking.",
            status_code=400,
            mimetype="text/plain"
        )

    # Call bookSlot endpoint
    endpoint = function_endpoints.get("bookSlot")
    if not endpoint:
        raise ValueError("Endpoint for bookSlot is not configured.")

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
        logging.error(f"Error calling bookSlot: {e}")
        return func.HttpResponse(
            "Failed to book slot. Please try again later.",
            status_code=500,
            mimetype="text/plain"
        )







def extract_preferred_date_time(content):
    """
    Extracts preferred date and time from the content string using a regex pattern.

    Args:
        content (str): The input string containing the date and time.

    Returns:
        datetime: Parsed datetime object if found, otherwise None.
    """
    date_time_pattern = r"\b(\d{1,2}(st|nd|rd|th)?\s\w+(\s\d{4})?\s\d{1,2}(am|pm)?)\b"
    date_time_match = re.search(date_time_pattern, content)
    if date_time_match:
        return parse_date_time(date_time_match.group(0))
    return None






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





# Function call handler
def handle_function_call(assistant_response, business_id, sender_id):
    try:
        # Extract the function_call object
        function_call = assistant_response.function_call

        # Log the raw function_call for debugging
        logging.debug(f"Raw function_call: {function_call}")

        # Validate the structure of function_call
        if not function_call or not hasattr(function_call, "name") or not hasattr(function_call, "arguments"):
            logging.error("Malformed function_call data. Missing 'name' or 'arguments'.")
            raise ValueError("Malformed function_call data. Missing 'name' or 'arguments'.")

        # Extract function name and arguments
        function_name = function_call.name
        try:
            arguments = (
                function_call.arguments if isinstance(function_call.arguments, dict)
                else json.loads(function_call.arguments)
            )
            logging.info(f"Parsed arguments: {arguments}")
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse function_call arguments: {e}")
            raise ValueError("Invalid JSON format in function_call arguments.")

        # Add required parameters to the arguments
        arguments["sender_id"] = sender_id
        arguments["business_id"] = business_id

        # Dispatch to the appropriate function
        if function_name == "getBusinessServices":
            logging.info(f"Dispatching to handle_get_business_services with arguments: {arguments}")
            return handle_get_business_services(arguments, business_id, sender_id)

        elif function_name == "checkSlot":
            logging.info(f"Dispatching to handle_check_slot with arguments: {arguments}")
            return handle_check_slot(arguments, business_id, sender_id)

        elif function_name == "bookSlot":
            logging.info(f"Dispatching to handle_book_slot with arguments: {arguments}")
            return handle_book_slot(arguments, business_id, sender_id)

        elif function_name == "update_user_details":
            try:
                logging.info(f"Updating user details with arguments: {arguments}")

                # Call the function to update user details
                update_user_details(sender_id, arguments)
                logging.info(f"User details updated successfully for sender_id: {sender_id}")

                # Fetch chat history and check for booking context
                chat_history = fetch_chat_history(business_id, sender_id)
                for message in reversed(chat_history):  # Iterate in reverse for latest context
                    if "preferredDateTime" in message.get("content", ""):
                        arguments["preferredDateTime"] = extract_preferred_date_time(message["content"])
                    if "serviceID" in message.get("content", ""):
                        arguments["serviceID"] = extract_service_id(message["content"])
                    if "durationMinutes" in message.get("content", ""):
                        arguments["durationMinutes"] = extract_duration(message["content"])

                # Proceed to checkSlot if booking context exists
                if "preferredDateTime" in arguments and "serviceID" in arguments:
                    logging.info("Detected booking intent. Proceeding to checkSlot.")
                    return handle_check_slot(arguments, business_id, sender_id)

                # Conclude flow if no further context exists
                return func.HttpResponse(
                    json.dumps({"status": "success", "message": "User details updated successfully."}),
                    status_code=200,
                    mimetype="application/json"
                )
            except Exception as e:
                logging.error(f"Failed to update user details: {e}")
                return func.HttpResponse(
                    json.dumps({"status": "error", "message": f"Failed to update user details: {e}"}),
                    status_code=500,
                    mimetype="application/json"
                )

        else:
            logging.error(f"Unsupported function name: {function_name}")
            return func.HttpResponse(
                json.dumps({"error": "Unsupported function call", "function_name": function_name}),
                status_code=400,
                mimetype="application/json"
            )

    except Exception as e:
        logging.error(f"Error in handle_function_call: {e}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": "Function call failed", "details": str(e)}),
            status_code=500,
            mimetype="application/json"
        )






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

        # Store the user's query in chat history
        logging.info("Storing user's query in chat history.")
        store_chat_message(business_id, sender_id, "user", query, "formatted")

        # Fetch chat history for context
        logging.info("Fetching chat history for context.")
        chat_history = fetch_chat_history(business_id, sender_id)
        messages = [{"role": msg["role"], "content": msg["content"]} for msg in chat_history]
        messages.append({"role": "user", "content": query})

        # Add system instructions
        system_message = (
            f"You assist with service and booking inquiries for a business. The business ID is {business_id}. "
            f"Follow these steps: "
            f"1. For service inquiries, call `getBusinessServices` to retrieve service details. "
            f"   - Always include `sender_id` (user ID) and `business_id` (business ID) in function calls. "
            f"   - Do not call `getBusinessServices` again if services have already been fetched. "
            f"2. For booking inquiries: "
            f"   a. Automatically retrieve `durationMinutes` from service details. "
            f"   b. Ask the user for the preferred date and time for the appointment. "
            f"   c. Call `checkSlot` using the provided date, time, and duration to verify slot availability. "
            f"3. User details handling: "
            f"   - Whenever a user provides their name, phone number, or email address, extract them from the user message and only return a JSON object. "
            f"   - The function name must be `update_user_details`, with no other text. "
            f"   - The response format must be a complete JSON object with no additional characters such as backticks. "
            f"      Example output: "
            f'      {{"function_call": {{"name": "update_user_details", "arguments": {{"name": "John", "phone_number": "9876543210", "email": "john.doe@example.com"}}}}}}'
            f"4. If the slot is available, call `bookSlot` only after confirming all details with the user. "
            f"   - ensure that all the user details are available, if not ask for all the details and respond with the JSON object"
            f"5. Avoid redundant function calls and unnecessary prompts for user details if already provided. "
            f"6. Ensure all interactions are clear and professional, confirming progress at each step, except when providing JSON-only responses for function calls."
        )
        messages.insert(0, {"role": "system", "content": system_message})
        logging.debug(f"Constructed messages: {json.dumps(messages, indent=2)}")

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

        # Parse assistant response
        assistant_response = response.choices[0].message
        logging.info(f"Assistant raw response: {assistant_response}")

        # Immediately handle function calls
        if assistant_response.function_call:
            logging.info("Handling function call from assistant response.")
            return handle_function_call(assistant_response, business_id, sender_id)

        # Handle regular content responses
        if assistant_response.content:
            logging.info("Storing assistant's response in chat history.")
            store_chat_message(business_id, sender_id, "assistant", assistant_response.content, "formatted")
            return func.HttpResponse(
                assistant_response.content, status_code=200, mimetype="text/plain"
            )

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









# Functions not in use now

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


