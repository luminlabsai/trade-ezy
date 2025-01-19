function_descriptions = [
    {
        "name": "getBusinessServices",
        "description": (
            "Retrieve details about the services a business offers. Use this to list or search for services "
            "offered by the business before checking availability or booking."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Fields to retrieve (e.g., name, price). Defaults to all fields."
                },
                "service_name": {
                    "type": "string",
                    "description": "Optional service name to filter results. Use this to find a specific service."
                }
            },
            "required": []
        }
    },
    {
        "name": "checkSlot",
        "description": (
            "Check the availability of a slot for a specific service on a specific date and time. "
            "Requires the service ID from getBusinessServices."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "serviceID": {"type": "string", "description": "The unique ID of the service."},
                "preferredDateTime": {"type": "string", "description": "The preferred date and time for the slot."},
                "durationMinutes": {"type": "integer", "description": "Duration of the service in minutes."}
            },
            "required": ["serviceID", "preferredDateTime", "durationMinutes"]
        }
    },
    {
        "name": "bookSlot",
        "description": (
            "Book a slot for a specific service on a specific date and time. Requires the slot to be available. "
            "Check availability using checkSlot before calling this function."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "serviceID": {"type": "string", "description": "The unique ID of the service."},
                "preferredDateTime": {"type": "string", "description": "The preferred date and time for the booking."},
                "durationMinutes": {"type": "integer", "description": "Duration of the service in minutes."},
                "clientName": {"type": "string", "description": "The name of the client making the booking."}
            },
            "required": ["serviceID", "preferredDateTime", "durationMinutes", "clientName"]
        }
    }
]
