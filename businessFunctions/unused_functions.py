# Functions not in use now
def extract_service_name_from_id(service_id):
    """
    Fetches the service name corresponding to the given service ID from the database.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
        )
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name
            FROM services
            WHERE service_id = %s
            """,
            (service_id,)
        )
        result = cursor.fetchone()
        if result:
            service_name = result[0]
            logging.info(f"Service name for service_id {service_id} is {service_name}.")
            return service_name
        else:
            logging.warning(f"No service found for service_id {service_id}.")
            return None
    except Exception as e:
        logging.error(f"Error fetching service name for service_id {service_id}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



def extract_service_id(content, business_id):
    """
    Extracts service ID by matching a service name in the content string to the services offered by the business.

    Args:
        content (str): The input string containing the service name.
        business_id (str): The ID of the business to fetch services from.

    Returns:
        str: Service ID if found, otherwise None.
    """
    try:
        # Fetch all services for the business
        business_services = fetch_service_details(business_id, None)  # Fetch all services

        # Extract service name from content
        service_name = extract_service_name_from_query(content, [service["name"] for service in business_services])
        if service_name:
            # Match service name to get its ID
            for service in business_services:
                if service["name"] == service_name:
                    return service["service_id"]
    except Exception as e:
        logging.error(f"Failed to extract service ID: {e}")
    return None



def extract_duration(service_id, business_id):
    """
    Extracts the duration in minutes for a specific service ID.

    Args:
        service_id (str): The ID of the service.
        business_id (str): The ID of the business.

    Returns:
        int: Duration in minutes if found, otherwise None.
    """
    try:
        # Fetch service details for the given service ID
        service_details = fetch_service_details(business_id, service_id)
        return service_details.get("duration_minutes") if service_details else None
    except Exception as e:
        logging.error(f"Failed to extract duration: {e}")
    return None


def fetch_service_details(business_id, service_id):
    """
    Fetch details for a specific service, such as durationMinutes, from the services data.
    """
    # Ensure the endpoint is configured
    service_endpoint = function_endpoints.get("getBusinessServices")
    if not service_endpoint:
        logging.error("getBusinessServices endpoint is not configured.")
        raise ValueError("getBusinessServices endpoint is not configured.")

    # Prepare the payload
    payload = {
        "business_id": business_id,
        "sender_id": "SYSTEM",  # Indicating a system call
        "fields": ["service_id", "name", "price", "_minutes"],
        "service_id": service_id
    }

    logging.info(f"Fetching service details with payload: {payload}")

    try:
        # Make the request to fetch service details
        response = requests.post(service_endpoint, json=payload)
        response.raise_for_status()

        # Parse the response
        services = response.json().get("services", [])
        if not services:
            logging.warning(f"No service found with ID: {service_id}")
            raise ValueError(f"Service ID {service_id} not found.")

        logging.info(f"Service details fetched successfully: {services[0]}")
        return services[0]  # Return the first matching service

    except requests.RequestException as e:
        logging.error(f"Error fetching service details: {e}")
        raise ValueError("Failed to fetch service details. Please try again later.")



def extract_preferred_date_time(content):
    """
    Extracts preferred date and time from the content string using a regex pattern.

    Args:
        content (str): The input string containing the date and time.

    Returns:
        datetime: Parsed datetime object if found, otherwise None.
    """
    date_time_pattern = r"\b(\d{1,2}(st|nd|rd|th)?\s\w+(\s\d{4})?\s\d{1,2}(am|pm)?)\b"
    date_time_match = re.search(date_time_pattern, content)
    if date_time_match:
        return parse_date_time(date_time_match.group(0))
    return None