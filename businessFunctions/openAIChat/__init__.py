import os
import logging
import requests
import azure.functions as func

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "MISSING_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "MISSING_BASE")
DEPLOYMENT_NAME = "gpt-4o-mini"  # Replace with your Azure OpenAI deployment name
API_VERSION = "2024-08-01-preview"  # API version for Azure OpenAI

if OPENAI_API_KEY == "MISSING_KEY" or OPENAI_API_BASE == "MISSING_BASE":
    logging.error("Environment variables OPENAI_API_KEY or OPENAI_API_BASE are not set.")
    raise ValueError("Required environment variables are not set.")

# Ensure the base URL ends with a slash
if not OPENAI_API_BASE.endswith("/"):
    OPENAI_API_BASE = f"{OPENAI_API_BASE}/"

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Processing chat request.")

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

        # Prepare the payload for the OpenAI API request
        messages = [
            {"role": "system", "content": f"You are an assistant for the following business context: {business_context}"},
            {"role": "user", "content": query}
        ]

        payload = {
            "messages": messages,
            "temperature": 0.7,
            "top_p": 0.95,
            "max_tokens": 800
        }

        # Construct the full API endpoint
        endpoint = f"{OPENAI_API_BASE}openai/deployments/{DEPLOYMENT_NAME}/chat/completions?api-version={API_VERSION}"

        # Set headers
        headers = {
            "Content-Type": "application/json",
            "api-key": OPENAI_API_KEY
        }

        # Send the request to Azure OpenAI
        response = requests.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Extract the response content
        answer = response.json().get("choices")[0].get("message").get("content")
        return func.HttpResponse(
            answer, 
            status_code=200, 
            headers={"Access-Control-Allow-Origin": "http://localhost:3000"}
        )

    except requests.RequestException as e:
        logging.error(f"Failed to communicate with OpenAI API: {e}")
        return func.HttpResponse(
            "Error communicating with OpenAI API.", 
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
