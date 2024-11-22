import os
import logging
import openai
import azure.functions as func

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
                model="gpt-4",  # Replace with your assistant's model if necessary
                messages=[
                    {"role": "system", "content": f"You are an assistant for the following business context: {business_context}"},
                    {"role": "user", "content": query}
                ],
                temperature=0.7,
                top_p=0.95,
                max_tokens=800,
                user=ASSISTANT_ID  # Assistant ID for personalization
            )

            # Extract the assistant's response
            answer = response.choices[0].message.content

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
