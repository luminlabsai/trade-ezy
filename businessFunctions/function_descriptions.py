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
    }
]
