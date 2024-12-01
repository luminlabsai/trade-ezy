import os
import logging
import openai
import requests
import json
import azure.functions as func
from function_descriptions import function_descriptions
from function_endpoints import function_endpoints

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "MISSING_KEY")
ASSISTANT_ID = "asst_x0xrh7dShxqC0eBHfIuunn1L"  # Replace with your assistant ID
API_TYPE = os.getenv("OPENAI_API_TYPE", "openai")  # Explicitly set to 'openai' or 'azure'

if OPENAI_API_KEY == "MISSING_KEY":
    logging.error("Required environment variable OPENAI_API_KEY is not set.")
    raise ValueError("Required environment variable is not set.")

# Initialize OpenAI client
openai.api_key = OPENAI_API_KEY
openai.api_type = API_TYPE

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

        # Call OpenAI assistant with the query and context
        try:
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": f"You are an assistant for the following business context: {business_context}"},
                    {"role": "user", "content": query}
                ],
                functions=function_descriptions,
                function_call="auto",  # Allow assistant to decide if a function call is needed
                temperature=0.7,
                top_p=0.95,
                max_tokens=800,
                user=ASSISTANT_ID  # Assistant ID for personalization
            )

            assistant_response = response.choices[0].message

            # Check if the assistant decides to call a function
            if hasattr(assistant_response, "function_call") and assistant_response.function_call:
                function_call = assistant_response.function_call
                function_name = function_call.name
                arguments = json.loads(function_call.arguments)

                # Retrieve the endpoint for the function
                endpoint_template = function_endpoints.get(function_name)
                if not endpoint_template:
                    logging.error(f"No endpoint configured for function: {function_name}")
                    return func.HttpResponse(
                        f"No endpoint configured for function: {function_name}",
                        status_code=500,
                        headers={"Access-Control-Allow-Origin": "http://localhost:3000"}
                    )

                # Include the fields parameter and check for a specific service name
                fields = arguments.get("fields", ["name", "description", "price", "duration_minutes"])
                arguments["fields"] = ",".join(fields)  # Convert list to a comma-separated string
                service_name = arguments.get("service_name")

                # Construct the endpoint with service_name if provided
                if service_name:
                    endpoint = f"{endpoint_template.format(businessID=arguments['businessID'], fields=arguments['fields'])}&service_name={service_name}"
                else:
                    endpoint = endpoint_template.format(**arguments)

                # Call the Azure Function
                try:
                    function_response = requests.get(endpoint)
                    if function_response.status_code == 200:
                        result = function_response.json()
                        return func.HttpResponse(
                            json.dumps(result),
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
            answer = assistant_response.content
            return func.HttpResponse(
                answer,
                status_code=200,
                headers={"Access-Control-Allow-Origin": "http://localhost:3000"}
            )
        except openai.OpenAIError as e:
            logging.error(f"OpenAI API Error: {e}")
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
