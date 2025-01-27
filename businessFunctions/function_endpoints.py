import os

# Base URL from environment variables
BASE_URL = os.getenv("FUNCTION_APP_BASE_URL", "http://localhost:7071")

function_endpoints = {
    "getBusinessServices": f"{BASE_URL}/api/getBusinessServices",
    "checkSlot": f"{BASE_URL}/api/checkSlot",
    "bookSlot": f"{BASE_URL}/api/bookSlot",
    "create_or_update_user": f"{BASE_URL}/api/create_or_update_user"  # Added the new function endpoint
}
