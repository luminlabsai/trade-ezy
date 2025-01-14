import dateparser
import logging
import re
from datetime import datetime

def parse_date_time(query):
    """Parse the date and time from the user query."""
    try:
        logging.info(f"Attempting to parse date and time from query: '{query}'")
        
        # Preprocess query to standardize formats
        query = query.lower()
        query = re.sub(r"\bat\b", " ", query)  # Replace "at" with a space
        query = re.sub(r"\bpm\b", " pm", query)  # Add space before "pm"
        query = re.sub(r"\bam\b", " am", query)  # Add space before "am"

        # Attempt parsing
        parsed_date = dateparser.parse(
            query,
            settings={
                "PREFER_DATES_FROM": "future",
                "RELATIVE_BASE": datetime.now(),
                "RETURN_AS_TIMEZONE_AWARE": False,
                "DATE_ORDER": "DMY",
            }
        )

        if parsed_date:
            logging.info(f"Successfully parsed date and time: {parsed_date.isoformat()}")
            return parsed_date.isoformat()
        else:
            logging.warning("Failed to parse date and time from query.")
            return None
    except Exception as e:
        logging.error(f"Error parsing date and time: {e}")
        return None


# Test cases
test_queries = [
    "Book Reiki for 4th January 2024 at 12:00pm",
    "Schedule an appointment tomorrow at 3 PM",
    "Can I book a session on Monday?",
    "Reserve a slot for 12th Feb at 10 am",
    "No specific date mentioned",
    "Invalid input"
]

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    for query in test_queries:
        print(f"Query: {query}")
        result = parse_date_time(query)
        print(f"Parsed Date and Time: {result}\n")