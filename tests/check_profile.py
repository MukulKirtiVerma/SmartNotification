from pymongo import MongoClient
import json
from config.config import Config
client = MongoClient(Config.MONGODB_URL)
db = client["notification_system"]
profile = db["user_profiles"].find_one({"user_id": 1})

if profile:
    profile["_id"] = str(profile["_id"])
    print(json.dumps(profile, indent=2))
else:
    print("No profile found")