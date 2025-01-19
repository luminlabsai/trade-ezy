import os

# Base URL from environment variables
BASE_URL = os.getenv("FUNCTION_APP_BASE_URL", "http://localhost:7071")

function_endpoints = {
    "getBusinessServices": f"{os.getenv('FUNCTION_APP_BASE_URL', 'http://localhost:7071')}/api/getBusinessServices",
    "checkSlot": f"{os.getenv('FUNCTION_APP_BASE_URL', 'http://localhost:7071')}/api/checkSlot",
    "bookSlot": f"{os.getenv('FUNCTION_APP_BASE_URL', 'http://localhost:7071')}/api/bookSlot"
}

