import json

from config import get_settings
from models import Profile


def load_profile():
    profile_path = get_settings().profile_path
    with open(profile_path, "r") as f:
        data = json.load(f)
