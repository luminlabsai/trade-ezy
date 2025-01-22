function_descriptions = [
    {
        "name": "getBusinessServices",
        "description": (
            "Retrieve details about the services a business offers. Use this to list or search for services "
            "offered by the business. Descriptions are excluded by default unless explicitly requested."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Fields to retrieve (e.g., name, price). Defaults to excluding descriptions. "
                        "Include 'description' in the fields to fetch service descriptions."
                    )
                },
                "service_name": {
                    "type": "string",
                    "description": (
                        "Optional service name to filter results. Use this to find a specific service by name."
                    )
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
            "Check availability using checkSlot before calling this function. Ensure all client details are collected "
            "before making the booking."
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
