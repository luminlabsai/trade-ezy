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
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")  # Default to gpt-4 if not set
CHAT_HISTORY_LIMIT = int(os.getenv("CHAT_HISTORY_LIMIT", 10))  # Default to 10 if not set
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT", 5432)

if OPENAI_API_KEY == "MISSING_KEY":
    logging.error("Required environment variable OPENAI_API_KEY is not set.")
    raise ValueError("Required environment variable is not set.")

# Initialize OpenAI client
openai.api_key = OPENAI_API_KEY

def fetch_chat_history(business_id, session_id, limit=CHAT_HISTORY_LIMIT):
    """Retrieve the last 'n' chat messages for a specific business and session."""
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
    """Store a chat message in the database."""
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

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Processing chat request with OpenAI assistant.")

    try:
        req_body = req.get_json()
        query = req_body.get("query")
        business_context = req_body.get("businessContext")
        session_id = req_body.get("sessionID") or str(uuid4())  # Generate a new session ID if not provided

        if not query:
            return func.HttpResponse(
                "Query is missing.",
                status_code=400,
                headers={"Access-Control-Allow-Origin": "*"}
            )

        if not business_context:
            return func.HttpResponse(
                "Business context is missing.",
                status_code=400,
                headers={"Access-Control-Allow-Origin": "*"}
            )

        business_id = business_context["businessID"]

        # Fetch chat history
        chat_history = fetch_chat_history(business_id, session_id)
        messages = [{"role": message["role"], "content": message["content"]} for message in chat_history]

        # Add the current query to the messages
        messages.append({"role": "user", "content": query})

        # Add the business context to the assistant's context
        messages.insert(0, {
            "role": "system",
            "content": f"You are helping to answer questions for a business with ID {business_context['businessID']}."
        })

        # Store the user's query in the database
        store_chat_message(business_id, session_id, "user", query)

        # Call OpenAI assistant with the full context
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

        assistant_response = response.choices[0].message

        # Check if the assistant decides to call a function
        if hasattr(assistant_response, "function_call") and assistant_response.function_call:
            function_call = assistant_response.function_call
            function_name = function_call.name
            arguments = json.loads(function_call.arguments)

            logging.info(f"Function call requested: {function_name} with arguments {arguments}")

            # Retrieve the endpoint for the function
            endpoint_template = function_endpoints.get(function_name)
            if not endpoint_template:
                return func.HttpResponse(
                    f"No endpoint configured for function: {function_name}",
                    status_code=500,
                    headers={"Access-Control-Allow-Origin": "*"}
                )

            # Replace placeholders for dynamic parameters
            try:
                if function_name == "getBusinessServices":
                    business_id = arguments.get("businessID")
                    fields = ",".join(arguments.get("fields", ["name", "description", "price"]))  # Default fields
                    service_name = arguments.get("service_name")

                    # URL-encode fields and service_name
                    encoded_fields = quote(fields)
                    endpoint = endpoint_template.format(businessID=business_id, fields=encoded_fields)
                    if service_name:
                        endpoint += f"&service_name={quote(service_name)}"

                    # Log the constructed endpoint
                    logging.info(f"Constructed URL for getBusinessServices: {endpoint}")

                else:
                    endpoint = endpoint_template

                # Make the HTTP request
                logging.info(f"Calling {function_name} at {endpoint} with arguments: {arguments}")
                function_response = requests.get(endpoint) if function_name == "getBusinessServices" else requests.post(endpoint, json=arguments)
                function_response.raise_for_status()
                result = function_response.json()
                logging.info(f"{function_name} response: {result}")

                # Send function result back to OpenAI for formatting
                follow_up_response = openai.chat.completions.create(
                    model=LLM_MODEL,
                    messages=[
                        *messages,
                        {"role": "function", "name": function_name, "content": json.dumps(result)}
                    ],
                    temperature=0.7,
                    top_p=0.95,
                    max_tokens=800,
                    user=ASSISTANT_ID
                )

                final_response = follow_up_response.choices[0].message.content
                store_chat_message(business_id, session_id, "assistant", final_response)

                return func.HttpResponse(
                    final_response,
                    status_code=200,
                    headers={"Access-Control-Allow-Origin": "*"}
                )
            except requests.RequestException as e:
                logging.error(f"Error calling {function_name}: {e}")
                return func.HttpResponse(
                    f"Error calling function {function_name}: {e}",
                    status_code=500,
                    headers={"Access-Control-Allow-Origin": "*"}
                )

        # Store the assistant's response
        store_chat_message(business_id, session_id, "assistant", assistant_response.content)

        return func.HttpResponse(
            assistant_response.content,
            status_code=200,
            headers={"Access-Control-Allow-Origin": "*"}
        )

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return func.HttpResponse(
            "Internal Server Error",
            status_code=500,
            headers={"Access-Control-Allow-Origin": "*"}
        )

