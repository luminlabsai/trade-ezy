import logging
import os
import azure.functions as func
from azure.cosmos import CosmosClient, exceptions
import json

# Cosmos DB configuration from environment variables
COSMOS_DB_URI = os.getenv("COSMOS_DB_URI")
COSMOS_DB_KEY = os.getenv("COSMOS_DB_KEY")
COSMOS_DB_DATABASE_ID = os.getenv("COSMOS_DB_DATABASE_ID")
COSMOS_DB_CONTAINER_ID = os.getenv("COSMOS_DB_CONTAINER_ID")

# Initialize the Cosmos client
client = CosmosClient(COSMOS_DB_URI, COSMOS_DB_KEY)
database = client.get_database_client(COSMOS_DB_DATABASE_ID)
container = database.get_container_client(COSMOS_DB_CONTAINER_ID)

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Processing request to get business name.")

    # Get businessId from the route parameters
    business_id = req.route_params.get("businessId")
    if business_id:
        business_id = business_id.strip()  # Remove extra spaces or newlines

    if not business_id:
        logging.warning("Missing business_id in the request.")
        return func.HttpResponse(
            json.dumps({"error": "Business ID is required."}),
            status_code=400,
            mimetype="application/json"
        )

    try:
        # Log the incoming business_id
        logging.info(f"Received business_id: {business_id}")

        # Query Cosmos DB for a business with the specified business_id
        query = "SELECT * FROM c WHERE c.business_id = @businessId"
        parameters = [{"name": "@businessId", "value": business_id}]
        logging.info(f"Query: {query}")
        logging.info(f"Parameters: {parameters}")

        # Query the database
        items = list(container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))

        # Log results
        if items:
            logging.info(f"Query succeeded. Number of items found: {len(items)}")
            business = items[0]
            logging.info(f"Business found: {business}")
            return func.HttpResponse(
                json.dumps({"name": business["name"]}),
                status_code=200,
                mimetype="application/json"
            )
        else:
            logging.warning(f"No business found for business_id: {business_id}")
            return func.HttpResponse(
                json.dumps({"error": "Business not found."}),
                status_code=404,
                mimetype="application/json"
            )

    except exceptions.CosmosHttpResponseError as e:
        logging.error(f"Cosmos DB error: {str(e)}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": "An error occurred while querying the database."}),
            status_code=500,
            mimetype="application/json"
        )

