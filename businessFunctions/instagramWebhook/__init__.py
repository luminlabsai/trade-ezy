import logging
import json
import os
import requests
import azure.functions as func

# Load Meta App Credentials from Environment Variables
VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("META_PAGE_ACCESS_TOKEN")

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Received Instagram webhook request.")

    # ✅ Step 1: Handle Webhook Verification
    if req.method == "GET":
        verify_token = req.params.get("hub.verify_token")
        challenge = req.params.get("hub.challenge")
        if verify_token == VERIFY_TOKEN:
            return func.HttpResponse(challenge, status_code=200)
        return func.HttpResponse("Verification failed", status_code=403)

    # ✅ Step 2: Handle Incoming Messages
    if req.method == "POST":
        req_body = req.get_json()
        
        # Ensure it’s an Instagram Messaging Event
        if "entry" in req_body:
            for entry in req_body["entry"]:
                if "messaging" in entry:
                    for message_event in entry["messaging"]:
                        sender_id = message_event["sender"]["id"]
                        recipient_id = message_event["recipient"]["id"]

                        # Extract Message Text
                        if "message" in message_event:
                            user_message = message_event["message"]["text"]
                            logging.info(f"Message from {sender_id}: {user_message}")

                            # Process the message (Call your OpenAI assistant)
                            ai_response = get_ai_response(sender_id, recipient_id, user_message)

                            # Send AI Response Back to Instagram
                            send_message_to_instagram(sender_id, ai_response)

        return func.HttpResponse("EVENT_RECEIVED", status_code=200)

    return func.HttpResponse("Invalid request", status_code=400)

# ✅ Step 3: Process Query via AI
def get_ai_response(sender_id, recipient_id, message):
    """Call your openAIAssistant function to process the message."""
    ai_endpoint = "https://trade-ezy-businessfunctions.azurewebsites.net/api/openAIAssistant"
    payload = {
        "sender_id": sender_id,
        "business_id": get_business_id(recipient_id),  # Map Instagram Business ID to business_id
        "query": message
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(ai_endpoint, json=payload, headers=headers)
        response_json = response.json()
        return response_json.get("response", "Sorry, I couldn't process that request.")
    except Exception as e:
        logging.error(f"Error calling AI Assistant: {e}")
        return "There was an issue processing your request."

# ✅ Step 4: Send Response to Instagram
def send_message_to_instagram(sender_id, text):
    """Send a message back to the Instagram user via Meta Send API."""
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": sender_id},
        "message": {"text": text}
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers)
        logging.info(f"Sent message to {sender_id}: {text}")
    except Exception as e:
        logging.error(f"Error sending message: {e}")

# ✅ Step 5: Map Instagram Business ID to Your Business ID
def get_business_id(instagram_business_id):
    """Retrieve the business_id for the given Instagram account from your database."""
    # Replace with actual DB lookup logic
    business_mapping = {
        "17841405793187218": "9c146c31-39c8-4f03-bd38-ae9f0e9a0794"  # Example mapping
    }
    return business_mapping.get(instagram_business_id, "default_business_id")
