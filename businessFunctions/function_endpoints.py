import os

# Base URL from environment variables
BASE_URL = os.getenv("FUNCTION_APP_BASE_URL", "http://localhost:7071")

function_endpoints = {
    "getBusinessServices": f"{BASE_URL}/api/getBusinessServices/{{businessID}}?fields={{fields}}",
    "getBusinessName": f"{BASE_URL}/api/getBusinessName/{{businessID}}",
    "checkSlot": f"{BASE_URL}/api/checkSlot",
    "bookSlot": f"{BASE_URL}/api/bookSlot"
}
