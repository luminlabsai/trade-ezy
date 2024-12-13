function_descriptions = [
    {
        "name": "getBusinessServices",
        "description": "Retrieve the services offered by a business.",
        "parameters": {
            "type": "object",
            "properties": {
                "businessID": {
                    "type": "string",
                    "description": "The unique identifier of the business."
                },
                "fields": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "The list of fields to include in the response."
                },
                "service_name": {
                    "type": "string",
                    "description": "The specific service to retrieve details for (optional)."
                }
            },
            "required": ["businessID", "fields"]
        }
    },
    {
        "name": "checkSlot",
        "description": "Check the availability of a calendar slot.",
        "parameters": {
            "type": "object",
            "properties": {
                "preferredDateTime": {
                    "type": "string",
                    "description": "The preferred start time in ISO 8601 format."
                },
                "durationMinutes": {
                    "type": "integer",
                    "description": "The duration of the appointment in minutes."
                }
            },
            "required": ["preferredDateTime", "durationMinutes"]
        }
    },
    {
        "name": "bookSlot",
        "description": "Book a calendar slot for a client.",
        "parameters": {
            "type": "object",
            "properties": {
                "preferredDateTime": {
                    "type": "string",
                    "description": "The preferred start time in ISO 8601 format."
                },
                "durationMinutes": {
                    "type": "integer",
                    "description": "The duration of the appointment in minutes."
                },
                "clientName": {
                    "type": "string",
                    "description": "The name of the client booking the appointment."
                },
                "appointmentPurpose": {
                    "type": "string",
                    "description": "The purpose of the appointment."
                }
            },
            "required": ["preferredDateTime", "durationMinutes", "clientName", "appointmentPurpose"]
        }
    }
]
