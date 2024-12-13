import logging
import json
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import azure.functions as func  # Import Azure Functions module

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

SERVICE_ACCOUNT_FILE = 'service-account.json'  # Adjust the path if necessary
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'luminlabsdemo@gmail.com'

import os
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

def get_calendar_service():
    # Retrieve the private key directly from the environment
    private_key_raw = os.getenv("GOOGLE_PRIVATE_KEY", "")
    
    # Replace literal `\n` with actual newlines
    private_key_processed = private_key_raw.replace("\\n", "\n").strip()

    service_account_info = {
        "type": "service_account",
        "project_id": os.getenv("GOOGLE_PROJECT_ID"),
        "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
        "private_key": private_key_processed,
        "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{os.getenv('GOOGLE_CLIENT_EMAIL')}"
    }

    # Debugging log for the private key
    if "PRIVATE KEY" in private_key_processed:
        logging.info(f"Private Key Loaded: {private_key_processed[:30]}...{private_key_processed[-30:]}")
    else:
        raise ValueError("Private key is missing or improperly formatted.")

    credentials = Credentials.from_service_account_info(service_account_info, scopes=['https://www.googleapis.com/auth/calendar'])
    return build('calendar', 'v3', credentials=credentials, cache_discovery=False)

def add_calendar_entry(calendar_id, summary, description, start_time, end_time):
    service = get_calendar_service()
    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time,
            'timeZone': 'Australia/Sydney',
        },
        'end': {
            'dateTime': end_time,
            'timeZone': 'Australia/Sydney',
        },
    }
    try:
        return service.events().insert(calendarId=calendar_id, body=event).execute()
    except HttpError as e:
        logger.error(f"Error adding calendar entry: {e}")
        raise e

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Processing chat request with OpenAI assistant.")

    try:
        req_body = req.get_json()
        query = req_body.get("query")
        business_context = req_body.get("businessContext")
        session_id = req_body.get("sessionID") or str(uuid4())

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

        chat_history = fetch_chat_history(business_id, session_id)
        messages = [{"role": message["role"], "content": message["content"]} for message in chat_history]

        messages.append({"role": "user", "content": query})

        messages.insert(0, {
            "role": "system",
            "content": f"You are helping to answer questions for a business with ID {business_context['businessID']}."
        })

        store_chat_message(business_id, session_id, "user", query)

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

        if hasattr(assistant_response, "function_call") and assistant_response.function_call:
            function_call = assistant_response.function_call
            function_name = function_call.name
            arguments = json.loads(function_call.arguments)

            logging.info(f"Function call requested: {function_name} with arguments {arguments}")

            # Intercept misclassified intents
            if function_name == "getBusinessServices" and any(keyword in query.lower() for keyword in ["available", "slot", "time"]):
                logging.info("Redirecting misclassified intent to 'checkSlot' function.")
                function_name = "checkSlot"
                arguments = {
                    "preferredDateTime": "2024-12-15T13:00:00",  # Extract dynamically in production
                    "durationMinutes": 60
                }

            endpoint_template = function_endpoints.get(function_name)
            if not endpoint_template:
                return func.HttpResponse(
                    f"No endpoint configured for function: {function_name}",
                    status_code=500,
                    headers={"Access-Control-Allow-Origin": "*"}
                )

            try:
                if function_name in ["checkSlot", "bookSlot"]:
                    endpoint = endpoint_template
                    function_response = requests.post(endpoint, json=arguments)
                else:
                    business_id = arguments.get("businessID")
                    fields = ",".join(arguments.get("fields", ["name", "description", "price"]))
                    service_name = arguments.get("service_name")
                    encoded_fields = quote(fields)
                    endpoint = endpoint_template.format(businessID=business_id, fields=encoded_fields)
                    if service_name:
                        endpoint += f"&service_name={quote(service_name)}"
                    function_response = requests.get(endpoint)

                function_response.raise_for_status()
                result = function_response.json()
                logging.info(f"{function_name} response: {result}")

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
