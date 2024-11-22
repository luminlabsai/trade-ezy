function_descriptions = [
    {
        "name": "getBusinessServices",
        "description": "Retrieve the list of services offered by a business based on its business ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "businessId": {
                    "type": "string",
                    "description": "The unique ID of the business."
                }
            },
            "required": ["businessId"]
        }
    },
    {
        "name": "getBusinessName",
        "description": "Retrieve the name of a business based on its business ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "businessId": {
                    "type": "string",
                    "description": "The unique ID of the business."
                }
            },
            "required": ["businessId"]
        }
    }
]
