import os
import logging
import openai
import requests
import json
import azure.functions as func
import psycopg2
import string
import decimal
from rapidfuzz import process
from uuid import uuid4
from urllib.parse import quote
import re
from dateutil.parser import parse
from datetime import datetime
from system_instructions import get_system_instructions
from function_descriptions import function_descriptions
from function_endpoints import function_endpoints


# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "MISSING_KEY")
OPENAI_PROJECT_ID = os.getenv("OPENAI_PROJECT_ID", "MISSING_PROJECT") 
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
    Fetch chat history for context, excluding repetitive assistant function calls.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()

        # Fetch chat history, including all message types
        cursor.execute(
            """
            SELECT role, content, name
            FROM chathistory
            WHERE business_id = %s AND sender_id = %s
            ORDER BY timestamp DESC
            LIMIT %s
            """,
            (business_id, sender_id, limit)
        )
        rows = cursor.fetchall()

        # Process chat history into message format
        messages = []
        for row in rows:
            role, content, name = row
            message = {"role": role, "content": content}
            if role == "function" and name:
                message["name"] = name
            messages.append(message)

        logging.info(f"Fetched {len(messages)} messages for sender_id {sender_id}.")
        return messages[::-1]  # Reverse to chronological order for OpenAI

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
        # Log the message details for debugging
        truncated_content = content[:100] if content else "None"
        logging.info(f"Storing message: role={role}, name={name}, content={truncated_content}, message_type={message_type}")

        # Connect to the PostgreSQL database
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()

        # Insert the message into the `chathistory` table
        cursor.execute(
            """
            INSERT INTO chathistory (business_id, sender_id, role, content, message_type, name)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (business_id, sender_id, role, content, message_type, name)
        )
        conn.commit()

        # Log success message
        logging.info(f"Message stored successfully with message_type={message_type}.")
    except psycopg2.Error as e:
        # Log any database-specific errors
        logging.error(f"Database error while storing chat message: {e}")
    except Exception as e:
        # Log unexpected errors
        logging.error(f"Unexpected error storing chat message: {e}")
    finally:
        # Ensure the database connection is properly closed
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except Exception as cleanup_error:
            logging.error(f"Error during connection cleanup: {cleanup_error}")





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
def fetch_cached_services_from_db(sender_id):
    """
    Fetch cached services for the given sender_id from the PreloadedServices table.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cursor = conn.cursor()

        # Query to fetch cached services
        cursor.execute(
            """
            SELECT service_name, price, duration_minutes, description, business_id
            FROM PreloadedServices
            WHERE sender_id = %s
            """,
            (sender_id,)
        )
        rows = cursor.fetchall()

        # Convert the rows to a list of dictionaries
        cached_services = [
            {
                "service_name": row[0],
                "price": row[1],
                "duration_minutes": row[2],
                "description": row[3],
                "business_id": row[4]
            }
            for row in rows
        ]

        cursor.close()
        conn.close()
        logging.info(f"Fetched {len(cached_services)} cached services for sender_id: {sender_id}")
        return cached_services

    except psycopg2.Error as e:
        logging.error(f"Database error while fetching cached services: {e}")
        return []
    except Exception as e:
        logging.error(f"Unexpected error while fetching cached services: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



def fetch_and_store_services(business_id, sender_id):
    """
    Fetch all services for a business and store them in the PreloadedServices table.
    """
    try:
        # Fetch services from the backend
        response = requests.post(
            "https://trade-ezy-businessfunctions.azurewebsites.net/api/getBusinessServices",
            json={
                "business_id": business_id,
                "sender_id": sender_id
            }
        )

        if response.status_code == 200:
            services = response.json().get("services", [])
            logging.info(f"Fetched {len(services)} services for business_id: {business_id}")

            # Add business_id explicitly to each service
            for service in services:
                service["business_id"] = business_id

            # Store services in the database
            store_services_in_db(sender_id, services)
        else:
            logging.error(f"Failed to fetch services. Status code: {response.status_code}")
            raise Exception(f"Service fetch failed with status code {response.status_code}")

    except Exception as e:
        logging.error(f"Error in fetch_and_store_services: {e}", exc_info=True)



def are_services_cached(sender_id):
    """
    Check if services are already cached for the given sender_id.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM PreloadedServices WHERE sender_id = %s", (sender_id,))
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count > 0
    except psycopg2.Error as e:
        logging.error(f"Database error while checking cache: {e}")
        return False



def store_services_in_db(sender_id, services):
    """
    Store services in the PreloadedServices table.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=DB_PORT
        )
        cursor = conn.cursor()

        # Delete any existing services for the sender_id
        cursor.execute("DELETE FROM PreloadedServices WHERE sender_id = %s", (sender_id,))

        # Insert the new services
        for service in services:
            cursor.execute(
                """
                INSERT INTO PreloadedServices (sender_id, business_id, service_name, price, duration_minutes, description)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    sender_id,
                    service["business_id"],  # Ensure business_id is included
                    service.get("service_name"),
                    service.get("price"),
                    service.get("duration_minutes"),
                    service.get("description")
                )
            )

        conn.commit()
        cursor.close()
        conn.close()
        logging.info(f"Stored {len(services)} services for sender_id: {sender_id}")

    except psycopg2.Error as e:
        logging.error(f"Database error while storing services: {e}")


def serialize_services_as_text(business_services):
    """
    Serializes a list of business services into a human-readable text format.
    """
    if not business_services:
        return "No services are currently available."

    lines = []
    for service in business_services:
        # Ensure all required fields are present and handle missing values gracefully
        service_name = service.get('service_name', 'Unknown Service')
        price = service.get('price', 'N/A')
        duration = service.get('duration_minutes', 'N/A')

        # Format the line with service details
        line = f"- {service_name} (Price: ${price}, Duration: {duration} mins)"
        lines.append(line)

    return "Here are the services we offer:\n" + "\n".join(lines)




def serialize_service_details_as_text(service_details):
    return (
        f"Service: {service_details['service_name']}\n"
        f"Price: ${service_details['price']}\n"
        f"Duration: {service_details['duration_minutes']} mins\n"
    )



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
import decimal

def send_response_to_ai(raw_response, business_id, sender_id, function_name, fallback_message="I'm sorry, I couldn't process your request."):
    """
    Pass the raw response (e.g., from a function or database query) back to the AI for natural language formatting.
    Ensures proper readability for Meta Messenger and other platforms.
    """

    def decimal_to_float(obj):
        """ Convert Decimal to float for JSON serialization """
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        raise TypeError

    try:
        # Fetch chat history
        chat_history = fetch_chat_history(business_id, sender_id)
        messages = [{"role": message["role"], "content": message["content"]} for message in chat_history]

        # Ensure formatting instructions for Meta compatibility
        formatting_instructions = (
            "Format the response for clarity:\n"
            "- Use **bullet points (- )** for lists (e.g., services).\n"
            "- Ensure **newlines** (`\n\n`) for readability.\n"
            "- Keep it conversational and natural."
        )

        # Append system message to enforce formatting
        messages.append({"role": "system", "content": formatting_instructions})

        # Append the raw response as a function role message with a name
        messages.append({
            "role": "function",
            "name": function_name,  # This must be explicitly set
            "content": json.dumps(raw_response, default=decimal_to_float)
        })

        # Send to OpenAI for formatting
        logging.info(f"Sending raw response to AI for natural language formatting.")
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=messages,
            temperature=0.7,
            top_p=0.95,
            max_tokens=800,
            user=ASSISTANT_ID
        )

        formatted_response = response.choices[0].message.content
        logging.info(f"AI-formatted response: {formatted_response}")

        # Store and return the formatted response
        store_chat_message(business_id, sender_id, "assistant", formatted_response, "formatted")
        return func.HttpResponse(formatted_response, status_code=200, mimetype="text/plain")

    except Exception as e:
        logging.error(f"Error sending response to AI: {e}")
        return func.HttpResponse(fallback_message, status_code=200, mimetype="text/plain")




def handle_get_business_services(arguments, business_id, sender_id):
    """
    Handles the 'getBusinessServices' function call, fetching details for all or specific services.
    """
    logging.info("Entered handle_get_business_services function.")
    logging.debug(f"Arguments received: {arguments}, BusinessID: {business_id}, SenderID: {sender_id}")

    # Fetch cached services
    cached_services = fetch_cached_services_from_db(sender_id)
    if not cached_services:
        logging.info(f"No cached services found for sender_id: {sender_id}. Fetching from backend.")
        cached_services = fetch_and_store_services(business_id, sender_id)

    logging.info(f"Fetched {len(cached_services)} cached services for sender_id: {sender_id}")

    # If a specific service_name is provided, filter the results
    service_name = arguments.get("service_name", "").lower()
    if service_name:
        matched_service = next(
            (s for s in cached_services if s["service_name"].lower() == service_name),
            None
        )
        if matched_service:
            service_message = serialize_service_details_as_text(matched_service)
            store_chat_message(business_id, sender_id, "assistant", service_message, "formatted")

            # **Pass function_name explicitly**
            return send_response_to_ai(
                raw_response=matched_service,
                business_id=business_id,
                sender_id=sender_id,
                function_name="getBusinessServices"
            )

    # If no specific service is provided, return all services
    services_response = serialize_services_as_text(cached_services)
    store_chat_message(business_id, sender_id, "assistant", services_response, "formatted")

    # **Pass function_name explicitly**
    return send_response_to_ai(
        raw_response=cached_services,
        business_id=business_id,
        sender_id=sender_id,
        function_name="getBusinessServices"
    )



def handle_check_slot(arguments, business_id, sender_id):
    """
    Handles calling the checkSlot function to check slot availability.
    """

    # Validate required arguments
    if not all(k in arguments for k in ["preferredDateTime", "service_name", "durationMinutes"]):
        return func.HttpResponse(
            json.dumps({"error": "Missing required arguments for slot checking."}),
            status_code=400,
            mimetype="application/json"
        )

    # Call checkSlot endpoint
    endpoint = function_endpoints.get("checkSlot")
    if not endpoint:
        raise ValueError("Endpoint for checkSlot is not configured.")

    payload = {
        "sender_id": sender_id,
        "preferredDateTime": arguments["preferredDateTime"],
        "durationMinutes": arguments["durationMinutes"],
        "service_name": arguments["service_name"],  # Updated key
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



def resolve_missing_arguments(arguments, sender_id):
    """
    Fetch missing user details from the database and populate arguments.
    """
    required_fields = ["clientName", "phone_number", "email"]
    missing_fields = [field for field in required_fields if not arguments.get(field)]

    if missing_fields:
        try:
            conn = psycopg2.connect(
                host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
            )
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT name, phone_number, email
                FROM users
                WHERE sender_id = %s
                """,
                (sender_id,)
            )
            user_details = cursor.fetchone()
            if user_details:
                arguments["clientName"] = arguments.get("clientName") or user_details[0]
                arguments["phone_number"] = arguments.get("phone_number") or user_details[1]
                arguments["email"] = arguments.get("email") or user_details[2]
                logging.info(f"Resolved arguments: {arguments}")
            else:
                logging.warning(f"No user details found for sender_id {sender_id}.")
        except Exception as e:
            logging.error(f"Error resolving arguments: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return arguments


def handle_book_slot(arguments, business_id, sender_id):
    """
    Handles the 'bookSlot' function call with pre-resolved arguments.
    """
    # Resolve missing arguments from the database
    arguments = resolve_missing_arguments(arguments, sender_id)

    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()

        # Collect missing user details
        missing_details = {
            "clientName": arguments.get("clientName"),
            "phone_number": arguments.get("phone_number"),
            "email": arguments.get("email"),
        }
        missing_details = {key: value for key, value in missing_details.items() if not value}

        # If there are missing details, return an error response
        if missing_details:
            return func.HttpResponse(
                json.dumps({
                    "error": "Missing user details.",
                    "missing_details": {key: "Please provide this detail." for key in missing_details.keys()}
                }),
                status_code=400,
                mimetype="application/json"
            )

        # Save user details to the database
        try:
            cursor.execute(
                """
                INSERT INTO users (sender_id, name, phone_number, email, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (sender_id) DO UPDATE
                SET name = COALESCE(EXCLUDED.name, users.name),
                    phone_number = COALESCE(EXCLUDED.phone_number, users.phone_number),
                    email = COALESCE(EXCLUDED.email, users.email),
                    updated_at = NOW()
                """,
                (sender_id, arguments["clientName"], arguments["phone_number"], arguments["email"])
            )
            conn.commit()
        except Exception as e:
            logging.error(f"Error saving user details: {e}")
            return func.HttpResponse(
                json.dumps({"error": "Failed to save user details. Please try again."}),
                status_code=500,
                mimetype="application/json"
            )

        # Verify that user details were saved
        cursor.execute("SELECT name, phone_number, email FROM users WHERE sender_id = %s", (sender_id,))
        user = cursor.fetchone()
        if not user:
            return func.HttpResponse(
                json.dumps({"error": "User details could not be saved. Please try again."}),
                status_code=500,
                mimetype="application/json"
            )

        # Update arguments with saved details
        arguments["clientName"] = user[0]
        arguments["phone_number"] = user[1]
        arguments["email"] = user[2]

    except Exception as e:
        logging.error(f"Error handling user details: {e}")
        return func.HttpResponse(
            json.dumps({"error": "An error occurred while handling user details.", "details": str(e)}),
            status_code=500,
            mimetype="application/json"
        )
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    # Validate the required arguments
    if not arguments.get("service_name"):
        return func.HttpResponse(
            json.dumps({"error": "Missing required argument: service_name."}),
            status_code=400,
            mimetype="application/json"
        )


    # Query the database for duration and other service details using service_name
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT duration_minutes
            FROM Services
            WHERE business_id = %s AND service_name ILIKE %s
            """,
            (business_id, arguments["service_name"])
        )
        service_details = cursor.fetchone()
        if not service_details:
            return func.HttpResponse(
                json.dumps({"error": f"Service '{arguments['service_name']}' not found for the given business."}),
                status_code=404,
                mimetype="application/json"
            )
        arguments["durationMinutes"] = arguments.get("durationMinutes") or service_details[0]
    except Exception as e:
        logging.error(f"Error fetching service details: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Failed to retrieve service details. Please try again later."}),
            status_code=500,
            mimetype="application/json"
        )
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    # Construct the booking payload
    booking_payload = {
        "business_id": business_id,
        "sender_id": sender_id,
        "clientName": arguments["clientName"],
        "phone_number": arguments["phone_number"],
        "email": arguments["email"],
        "service_name": arguments["service_name"],  # Use service_name instead of service_id
        "preferredDateTime": arguments["preferredDateTime"],
        "durationMinutes": arguments["durationMinutes"],
    }

    # Log the payload for debugging
    logging.info(f"Booking payload: {booking_payload}")

    # Call bookSlot endpoint
    endpoint = function_endpoints.get("bookSlot")
    if not endpoint:
        raise ValueError("Endpoint for bookSlot is not configured.")

    try:
        response = requests.post(endpoint, json=booking_payload)
        response.raise_for_status()
        result = response.json()
        follow_up_message = (
            f"Thank you, {arguments['clientName']}. Your booking for '{arguments['service_name']}' on {arguments['preferredDateTime']} "
            f"has been successfully recorded. A confirmation email will be sent to {arguments['email']}."
        )
        store_chat_message(business_id, sender_id, "assistant", follow_up_message, "formatted")
        return func.HttpResponse(follow_up_message, status_code=200, mimetype="text/plain")
    except requests.RequestException as e:
        logging.error(f"Error calling bookSlot: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Failed to boosk slot. Please try again later."}),
            status_code=500,
            mimetype="application/json"
        )




def handle_create_or_update_user(arguments, business_id, sender_id, is_booking_flow=False):
    """
    Handles calling the create_or_update_user function to manage user information.
    """

    endpoint = function_endpoints.get("create_or_update_user")
    if not endpoint:
        raise ValueError("Endpoint for create_or_update_user is not configured.")

    # Build the payload with provided details
    payload = {
        "sender_id": sender_id,
        "business_id": business_id,
        "name": arguments.get("name"),
        "phone_number": arguments.get("phone_number"),
        "email": arguments.get("email"),
    }

    try:
        # Call the create_or_update_user function
        response = requests.post(endpoint, json=payload)
        response.raise_for_status()
        result = response.json()

        # Construct the success message
        success_message = f"Your details have been successfully {result['action']}."

        # Store the success message in the chat history
        store_chat_message(business_id, sender_id, "assistant", success_message, "formatted")

        # Respond to the user
        if not is_booking_flow:
            return func.HttpResponse(
                success_message,
                status_code=200,
                mimetype="text/plain"
            )

        # If part of a booking flow, return the updated arguments for the booking process
        return {
            "status": "success",
            "updated_arguments": {
                "clientName": payload["name"],
                "phone_number": payload["phone_number"],
                "email": payload["email"],
            }
        }

    except Exception as e:
        logging.error(f"Error in handle_create_or_update_user: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Failed to update user details.", "details": str(e)}),
            status_code=500,
            mimetype="application/json"
        )





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





def handle_function_call(assistant_response, business_id, sender_id):
    """
    Handles the function call requested by the AI assistant.
    """
    try:
        # Ensure services are preloaded (silent fetch if not already cached)
        if not are_services_cached(sender_id):
            logging.info(f"Services not cached for sender_id: {sender_id}. Fetching silently.")
            fetch_and_store_services(business_id, sender_id)

        # Extract the function_call object
        function_call = assistant_response.function_call

        # Validate the structure of function_call
        if not function_call or not hasattr(function_call, "name") or not hasattr(function_call, "arguments"):
            logging.error("Malformed function_call data. Missing 'name' or 'arguments'.")
            raise ValueError("Malformed function_call data. Missing 'name' or 'arguments'.")

        # Extract function name and arguments
        function_name = function_call.name
        try:
            # Parse arguments (handle both dict and JSON string formats)
            arguments = (
                function_call.arguments if isinstance(function_call.arguments, dict)
                else json.loads(function_call.arguments)
            )
            logging.info(f"Parsed arguments: {arguments}")
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse function_call arguments: {e}")
            raise ValueError("Invalid JSON format in function_call arguments.")

        # Add sender_id and business_id to the arguments
        arguments["sender_id"] = sender_id
        arguments["business_id"] = business_id

        # Debugging: Log function name and arguments before dispatch
        logging.info(f"Function name: {function_name}")
        logging.info(f"Function arguments before resolution: {arguments}")

        # Dispatch to the appropriate handler based on function_name
        if function_name == "create_or_update_user":
            logging.info(f"Dispatching to handle_create_or_update_user with arguments: {arguments}")
            return handle_create_or_update_user(arguments, business_id, sender_id)

        elif function_name == "getBusinessServices":
            logging.info(f"Dispatching to handle_get_business_services with arguments: {arguments}")
            return handle_get_business_services(arguments, business_id, sender_id)

        elif function_name == "checkSlot":
            logging.info(f"Dispatching to handle_check_slot with arguments: {arguments}")
            return handle_check_slot(arguments, business_id, sender_id)

        elif function_name == "bookSlot":
            logging.info("Resolving missing arguments for bookSlot.")
            arguments = resolve_missing_arguments(arguments, sender_id)
            logging.info(f"Resolved arguments for bookSlot: {arguments}")
            return handle_book_slot(arguments, business_id, sender_id)

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
        system_message = get_system_instructions(business_id)
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



        # Check if content contains a function_call-like JSON structure
        if assistant_response.content and not assistant_response.function_call:
            logging.warning("Assistant response contains a content field. Checking for potential function_call.")
            try:
                # Log the raw content for debugging
                logging.debug(f"Raw assistant_response.content: {assistant_response.content}")

                # Validate if content is JSON
                stripped_content = assistant_response.content.strip()
                if stripped_content.startswith("{") and stripped_content.endswith("}"):
                    # Attempt to parse the content as JSON
                    try:
                        content_data = json.loads(assistant_response.content)
                        logging.debug(f"Parsed content_data: {content_data}")

                        # Check if it contains function_call-like data
                        if "name" in content_data and "arguments" in content_data:
                            logging.info("Valid function_call structure detected in content field. Converting to function_call.")
                            assistant_response.function_call = {
                                "name": content_data["name"],
                                "arguments": json.dumps(content_data["arguments"])  # Serialize arguments
                            }
                            assistant_response.content = None  # Clear content field to avoid duplication
                        else:
                            logging.warning("Content is JSON but does not contain a valid function_call structure.")
                    except json.JSONDecodeError as e:
                        logging.error(f"Failed to parse assistant_response.content as JSON: {e}")
                else:
                    # Content is plain text, not JSON
                    logging.info("Content field is plain text. Proceeding as a regular content response.")

            except Exception as e:
                logging.error(f"Error processing function_call from content: {e}")


        # Check for function_call and handle it
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

