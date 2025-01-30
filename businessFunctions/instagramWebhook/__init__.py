import logging
import json
import os
import requests
import azure.functions as func
from userMappingService import get_or_create_sender_id
from businessMappingService import get_business_id

# Load Meta App Credentials from Environment Variables
VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("META_PAGE_ACCESS_TOKEN")

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("📩 Received Instagram webhook request.")

    try:
        req_body = req.get_json()
        logging.info(f"📥 Raw Payload: {json.dumps(req_body, indent=2)}")

        # ✅ Step 1: Handle Webhook Verification
        if req.method == "GET":
            verify_token = req.params.get("hub.verify_token")
            challenge = req.params.get("hub.challenge")
            if verify_token == VERIFY_TOKEN:
                logging.info("✅ Webhook verification successful.")
                return func.HttpResponse(challenge, status_code=200)
            logging.warning("🚨 Webhook verification failed.")
            return func.HttpResponse("Verification failed", status_code=403)

        # ✅ Step 2: Handle Incoming Messages
        if req.method == "POST":
            if "entry" in req_body:
                for entry in req_body["entry"]:
                    if "messaging" in entry:
                        for message_event in entry["messaging"]:
                            
                            # ✅ Ignore echoed messages (sent by the business itself)
                            if "message" in message_event and message_event["message"].get("is_echo"):
                                logging.info("🔄 Ignoring echoed message (already sent by the business).")
                                continue  # Skip processing

                            sender_id = message_event["sender"]["id"]
                            recipient_id = message_event["recipient"]["id"]

                            # Extract Message Text
                            if "message" in message_event:
                                user_message = message_event["message"]["text"]
                                logging.info(f"💬 Message from {sender_id}: {user_message}")

                                # Process the message
                                process_instagram_message(sender_id, recipient_id, user_message)

            return func.HttpResponse("EVENT_RECEIVED", status_code=200)

    except Exception as e:
        logging.error(f"❌ Error processing webhook request: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Internal server error.", "details": str(e)}),
            status_code=500,
            mimetype="application/json"
        )

    return func.HttpResponse("Invalid request", status_code=400)


def process_instagram_message(instagram_id, recipient_id, message_text):
    """
    Processes an Instagram message while keeping sender/recipient logic as Instagram sends it.
    """
    if get_business_id(instagram_id):  
        logging.info(f"📩 Outbound Message (Business → User) | Sender: {instagram_id}, Recipient: {recipient_id}")
    else:
        logging.info(f"📨 Inbound Message (User → Business) | Sender: {instagram_id}, Recipient: {recipient_id}")

    # Fetch mapped sender UUID
    sender_id = get_or_create_sender_id(instagram_id)
    if not sender_id:
        logging.error(f"❌ Failed to retrieve or create sender_id for Instagram ID: {instagram_id}")
        return

    logging.info(f"✅ Mapped Instagram user {instagram_id} to sender_id {sender_id}")

    # Fetch mapped business UUID
    business_id = get_business_id(recipient_id)
    if not business_id:
        logging.error(f"❌ No business_id mapping found for Instagram Business ID: {recipient_id}")
        return

    logging.info(f"✅ Mapped Instagram Business ID {recipient_id} to business_id {business_id}")

    # Send message to OpenAI
    ai_response = get_ai_response(sender_id, business_id, message_text)
    logging.info(f"🤖 AI Response: {ai_response}")

    # Send AI Response Back to Instagram
    send_message_to_instagram(instagram_id, ai_response)


def get_ai_response(sender_id, business_id, message):
    """Call openAIAssistant and handle both plain text and JSON responses."""
    ai_endpoint = "https://trade-ezy-businessfunctions.azurewebsites.net/api/openAIAssistant"
    payload = {
        "sender_id": sender_id,
        "business_id": business_id,
        "query": message
    }
    headers = {"Content-Type": "application/json"}

    try:
        logging.info(f"📡 Sending request to AI Assistant: {json.dumps(payload, indent=2)}")

        response = requests.post(ai_endpoint, json=payload, headers=headers, timeout=200)
        logging.info(f"🔍 AI Assistant Response Code: {response.status_code}")

        if response.status_code != 200:
            logging.error(f"🚨 AI Assistant returned HTTP {response.status_code}: {response.text}")
            return "🤖 AI Assistant encountered an error."

        # ✅ Handle both JSON and raw text responses
        try:
            response_json = response.json()
            logging.info(f"🔍 AI Assistant JSON Response: {response_json}")

            if isinstance(response_json, dict) and "response" in response_json:
                return response_json["response"]
            else:
                logging.warning(f"⚠️ AI Assistant returned unexpected JSON format: {response_json}")
                return response.text.strip()  # Fallback to plain text

        except requests.exceptions.JSONDecodeError:
            logging.info(f"✅ AI Assistant returned plain text: {response.text.strip()}")
            return response.text.strip()  # ✅ Assume plain text response for Meta

    except requests.exceptions.Timeout:
        logging.error(f"❌ AI Assistant request timed out after 200 seconds.")
        return "🤖 AI Assistant took too long to respond."

    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Error calling AI Assistant: {e}")
        return "🤖 AI Assistant is currently unavailable."


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
        if response.status_code == 200:
            logging.info(f"📤 Sent message to {sender_id}: {text}")
        else:
            logging.error(f"❌ Failed to send message. Response: {response.text}")

    except Exception as e:
        logging.error(f"❌ Error sending message to Instagram: {e}")
