import os
import logging
import openai
import requests
import json
import azure.functions as func
from function_descriptions import function_descriptions
from function_endpoints import function_endpoints
from azure.cosmos import CosmosClient

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "MISSING_KEY")
ASSISTANT_ID = "asst_x0xrh7dShxqC0eBHfIuunn1L"  # Replace with your assistant ID
API_TYPE = os.getenv("OPENAI_API_TYPE", "openai")  # Explicitly set to 'openai' or 'azure'
COSMOS_DB_URI = os.getenv("COSMOS_DB_URI", "MISSING_URI")
COSMOS_DB_KEY = os.getenv("COSMOS_DB_KEY", "MISSING_KEY")
COSMOS_DB_DATABASE_ID = "BusinessAutomationDB"
COSMOS_DB_CONTAINER_ID = "ChatHistory"

if OPENAI_API_KEY == "MISSING_KEY" or COSMOS_DB_URI == "MISSING_URI":
    logging.error("Required environment variables are not set.")
    raise ValueError("Required environment variables are not set.")

# Initialize OpenAI client and Cosmos DB client
openai.api_key = OPENAI_API_KEY
openai.api_type = API_TYPE
cosmos_client = CosmosClient(COSMOS_DB_URI, COSMOS_DB_KEY)
database = cosmos_client.get_database_client(COSMOS_DB_DATABASE_ID)
container = database.get_container_client(COSMOS_DB_CONTAINER_ID)

def fetch_chat_history(user_id):
    """Fetch chat history for a user from Cosmos DB."""
    query = f"SELECT * FROM c WHERE c.user_id = '{user_id}' ORDER BY c.timestamp ASC"
    try:
        return list(container.query_items(query, enable_cross_partition_query=True))
    except Exception as e:
        logging.error(f"Failed to fetch chat history: {e}")
        return []

def save_chat_message(user_id, role, content):
    """Save a chat message to Cosmos DB."""
    try:
        container.create_item({
            "id": f"{user_id}_{int(time.time())}",
            "user_id": user_id,
            "role": role,
            "content": content,
            "timestamp": int(time.time())
        })
    except Exception as e:
        logging.error(f"Failed to save chat message: {e}")

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Processing chat request with OpenAI assistant.")

    # Handle CORS preflight requests
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "http://localhost:3000",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            },
        )

    try:
        # Parse the incoming request
        req_body = req.get_json()
        query = req_body.get("query")
        business_context = req_body.get("businessContext")
        user_id = req_body.get("userID")

        if not query or not business_context or not user_id:
            return func.HttpResponse(
                "Query, business context, and user ID are required.",
                status_code=400,
                headers={"Access-Control-Allow-Origin": "http://localhost:3000"}
            )

        # Fetch chat history
        chat_history = fetch_chat_history(user_id)

        # Build conversation history for OpenAI
        messages = [{"role": "system", "content": f"You are an assistant for the following business context: {business_context}"}]
        for chat in chat_history:
            messages.append({"role": chat["role"], "content": chat["content"]})
        messages.append({"role": "user", "content": query})

        # Save user query to chat history
        save_chat_message(user_id, "user", query)

        # Call OpenAI assistant
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=messages,
            functions=function_descriptions,
            function_call="auto",
            temperature=0.7,
            top_p=0.95,
            max_tokens=800,
            user=ASSISTANT_ID
        )

        assistant_response = response.choices[0].message

        # Save assistant response to chat history
        save_chat_message(user_id, "assistant", assistant_response.content)

        # Handle function calls if required
        if hasattr(assistant_response, "function_call") and assistant_response.function_call:
            function_call = assistant_response.function_call
            function_name = function_call.name
            arguments = json.loads(function_call.arguments)

            endpoint_template = function_endpoints.get(function_name)
            if not endpoint_template:
                logging.error(f"No endpoint configured for function: {function_name}")
                return func.HttpResponse(
                    f"No endpoint configured for function: {function_name}",
                    status_code=500,
                    headers={"Access-Control-Allow-Origin": "http://localhost:3000"}
                )

            fields = arguments.get("fields", ["name", "description", "price", "duration_minutes"])
            arguments["fields"] = ",".join(fields)
            service_name = arguments.get("service_name")

            if service_name:
                endpoint = f"{endpoint_template.format(businessID=arguments['businessID'], fields=arguments['fields'])}&service_name={service_name}"
            else:
                endpoint = endpoint_template.format(**arguments)

            try:
                function_response = requests.get(endpoint)
                if function_response.status_code == 200:
                    result = function_response.json()
                    # Send result back to OpenAI for final formatting
                    follow_up_response = openai.chat.completions.create(
                        model="gpt-4",
                        messages=messages + [{"role": "function", "name": function_name, "content": json.dumps(result)}],
                        temperature=0.7,
                        top_p=0.95,
                        max_tokens=800,
                        user=ASSISTANT_ID
                    )
                    save_chat_message(user_id, "assistant", follow_up_response.choices[0].message.content)
                    return func.HttpResponse(
                        follow_up_response.choices[0].message.content,
                        status_code=200,
                        headers={"Access-Control-Allow-Origin": "http://localhost:3000"}
                    )
                else:
                    logging.error(f"Function call failed: {function_response.text}")
                    return func.HttpResponse(
                        f"Failed to call function {function_name}: {function_response.text}",
                        status_code=500,
                        headers={"Access-Control-Allow-Origin": "http://localhost:3000"}
                    )
            except requests.RequestException as e:
                logging.error(f"Error calling function {function_name}: {e}")
                return func.HttpResponse(
                    f"Error calling function {function_name}: {e}",
                    status_code=500,
                    headers={"Access-Control-Allow-Origin": "http://localhost:3000"}
                )

        # If no function call, return the assistant's response
        return func.HttpResponse(
            assistant_response.content,
            status_code=200,
            headers={"Access-Control-Allow-Origin": "http://localhost:3000"}
        )

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return func.HttpResponse(
            "Internal Server Error",
            status_code=500,
            headers={"Access-Control-Allow-Origin": "http://localhost:3000"}
        )
