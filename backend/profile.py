import json

from config import get_settings
from models import Profile
from pydantic import ValidationError

def load_profile():
    profile_path = get_settings().profile_path
    with open(profile_path, "r") as f:
        data = json.load(f)
    profile = Profile(**data)
    return profile


def validate_profile(profile_data): # validate the profile data against the Profile model (we can make it better later on)
    try:
        profile = Profile(**profile_data)
        return profile
    except ValidationError as e:
        print("Profile validation error:", e)
        return None