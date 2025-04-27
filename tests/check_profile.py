from pymongo import MongoClient
import json
from datetime import datetime
from config.config import current_config


# Function to convert datetime objects to ISO format strings
def json_serial(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


# Connect to MongoDB
client = MongoClient(current_config.MONGODB_URL)
db = client.get_database()

# Try to find a profile
profile = db["user_profiles"].find_one({"user_id": 1})  # Try user_id 1 instead of 0

if profile:
    # Convert ObjectId to string
    profile["_id"] = str(profile["_id"])

    # Use the custom serializer function for datetime objects
    print(json.dumps(profile, indent=2, default=json_serial))
else:
    print("No profile found for user_id: 1")

    # List all collections
    print("\nAvailable collections:")
    print(db.list_collection_names())

    # Check for any profiles
    print("\nChecking for any profiles:")
    any_profile = db["user_profiles"].find_one()
    if any_profile:
        print(f"Found a profile with user_id: {any_profile.get('user_id')}")
    else:
        print("No profiles exist in the collection")

    # Count total documents
    count = db["user_profiles"].count_documents({})
    print(f"\nTotal documents in user_profiles: {count}")