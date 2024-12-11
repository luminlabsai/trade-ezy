import os

# Base URL from environment variables
BASE_URL = os.getenv("FUNCTION_APP_BASE_URL", "http://localhost:7071")

function_endpoints = {
    "getBusinessServices": f"{BASE_URL}/api/getBusinessServices/{{businessID}}?fields={{fields}}",
    "getBusinessName": f"{BASE_URL}/api/getBusinessName/{{businessID}}",
    "check_slot": f"{BASE_URL}/api/gmailCheckSlot",
    "book_slot": f"{BASE_URL}/api/gmailBookSlot"
}
