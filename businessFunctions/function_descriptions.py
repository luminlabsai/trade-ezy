function_descriptions = [
        {
        "name": "getBusinessServices",
        "description": (
            "Retrieve details about the services a business offers. Use this function to list all services or to search "
            "for specific services by name. You can query additional details like cost, duration, or descriptions by "
            "specifying fields in the request. If no `fields` or `service_name` is provided, the function will return "
            "basic details (service_name, duration_minutes, and price) for all services offered by the business."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "A list of fields to retrieve for each service. Valid fields include 'service_id', 'service_name', "
                        "'description', 'duration_minutes', and 'price'. Defaults to basic details (service_name, "
                        "duration_minutes, and price) if not specified. Include 'description' to fetch full service "
                        "descriptions."
                    )
                },
                "service_name": {
                    "type": "string",
                    "description": (
                        "An optional parameter to filter results by a specific service name. Use this to find details "
                        "about a particular service (e.g., cost, duration) or to check if the service is offered by the "
                        "business. Case-insensitive partial matches are supported."
                    )
                }
            },
            "required": ["sender_id", "business_id"]
        }
    },

    {
        "name": "checkSlot",
        "description": (
            "Check the availability of a slot for a specific service on a specific date and time. "
            "Requires the service_name, business_id, and durationMinutes to perform the check."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "The name of the service to check."},
                "preferredDateTime": {"type": "string", "description": "The preferred date and time for the slot."},
                "durationMinutes": {"type": "integer", "description": "Duration of the service in minutes."},
                "business_id": {"type": "string", "description": "The ID of the business offering the service."},
            },
            "required": ["service_name", "preferredDateTime", "durationMinutes", "business_id"]
        }
    },
    {
        "name": "bookSlot",
        "description": (
            "Book a slot for a specific service on a specific date and time. Requires the slot to be available. "
            "Ensure all client details (e.g., name) are collected and validated before calling this function."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "The name of the service to book."},
                "preferredDateTime": {"type": "string", "description": "The preferred date and time for the booking."},
                "business_id": {"type": "string", "description": "The ID of the business offering the service."},
                "clientName": {"type": "string", "description": "The name of the client making the booking."},
                "durationMinutes": {"type": "integer", "description": "The duration of the service in minutes."}
            },
            "required": ["service_name", "preferredDateTime", "business_id", "clientName", "durationMinutes"]
        }
    },
    {
        "name": "create_or_update_user",
        "description": (
            "Collect and update user details (e.g., name, phone number, email) for a sender ID in the database. "
            "This ensures the user profile is up-to-date for booking and other interactions. "
            "The response must use the `function_call` field without wrapping or additional text."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The name of the user."},
                "phone_number": {"type": "string", "description": "The phone number of the user."},
                "email": {"type": "string", "description": "The email address of the user."}
            },
            "required": ["name", "phone_number", "email"]
        }
    }
]
