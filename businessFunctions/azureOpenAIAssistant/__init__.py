import os
import logging
import azure.functions as func
from openai import AzureOpenAI
import time

# Configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "MISSING_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "MISSING_KEY")
AZURE_OPENAI_API_VERSION = "2024-05-01-preview"  # Ensure this matches your API version
ASSISTANT_ID = "asst_xfwsQUXCHdbDUlCMXSuWbzUJ"  # Replace with your assistant ID

if AZURE_OPENAI_ENDPOINT == "MISSING_ENDPOINT" or AZURE_OPENAI_API_KEY == "MISSING_KEY":
    logging.error("Required environment variables are not set.")
    raise ValueError("Required environment variables are not set.")

# Initialize Azure OpenAI client
client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION
)

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Processing chat request with Azure OpenAI assistant using threads.")

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

        if not query:
            return func.HttpResponse(
                "Query is missing.",
                status_code=400,
                headers={"Access-Control-Allow-Origin": "http://localhost:3000"}
            )

        if not business_context:
            return func.HttpResponse(
                "Business context is missing.",
                status_code=400,
                headers={"Access-Control-Allow-Origin": "http://localhost:3000"}
            )

        # Create a new thread
        thread = client.beta.threads.create()

        # Add a user question to the thread
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=query
        )

        # Run the thread with the assistant
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )

        # Polling until the run completes or fails
        while run.status in ['queued', 'in_progress', 'cancelling']:
            time.sleep(1)
            run = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )

        # Handle the run result
        if run.status == 'completed':
            # Fetch the messages from the completed thread
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            responses = [msg['content'] for msg in messages if msg['role'] == 'assistant']
            answer = responses[-1] if responses else "No response from assistant."
            return func.HttpResponse(
                answer,
                status_code=200,
                headers={"Access-Control-Allow-Origin": "http://localhost:3000"}
            )
        elif run.status == 'requires_action':
            # Handle cases where the assistant requires action (e.g., function calls)
            return func.HttpResponse(
                "Assistant requires additional actions. Please implement the required logic.",
                status_code=500,
                headers={"Access-Control-Allow-Origin": "http://localhost:3000"}
            )
        else:
            logging.error(f"Run failed with status: {run.status}")
            return func.HttpResponse(
                f"Assistant run failed with status: {run.status}.",
                status_code=500,
                headers={"Access-Control-Allow-Origin": "http://localhost:3000"}
            )

    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return func.HttpResponse(
            "Internal Server Error",
            status_code=500,
            headers={"Access-Control-Allow-Origin": "http://localhost:3000"}
        )
