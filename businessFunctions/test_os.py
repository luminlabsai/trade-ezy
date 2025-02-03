import os

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/kit/Library/CloudStorage/OneDrive-DigitideLtd/Lumin Labs/Dev/trade-ezy/businessFunctions/firebase_service_account.json"


print(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
