function_descriptions = [
    {
        "name": "getBusinessServices",
        "description": "Retrieve details about the services a business offers.",
        "parameters": {
            "type": "object",
            "properties": {
                "businessID": {"type": "string", "description": "The unique ID of the business."},
                "fields": {"type": "array", "items": {"type": "string"}, "description": "Fields to retrieve (e.g., name, price)."},
                "service_name": {"type": "string", "description": "Optional service name to filter results."}
            },
            "required": ["businessID"]
        }
    },
    {
        "name": "checkSlot",
        "description": "Check the availability of a slot for a specific service on a specific date and time.",
        "parameters": {
            "type": "object",
            "properties": {
                "businessID": {"type": "string", "description": "The unique ID of the business."},
                "serviceID": {"type": "string", "description": "The unique ID of the service."},
                "preferredDateTime": {"type": "string", "description": "The preferred date and time for the slot."}
            },
            "required": ["businessID", "serviceID", "preferredDateTime"]
        }
    },
    {
        "name": "bookSlot",
        "description": "Book a slot for a specific service on a specific date and time.",
        "parameters": {
            "type": "object",
            "properties": {
                "businessID": {"type": "string", "description": "The unique ID of the business."},
                "serviceID": {"type": "string", "description": "The unique ID of the service."},
                "preferredDateTime": {"type": "string", "description": "The preferred date and time for the booking."},
                "clientName": {"type": "string", "description": "The name of the client making the booking."}
            },
            "required": ["businessID", "serviceID", "preferredDateTime", "clientName"]
        }
    }
]
