import json
import logging

from pydantic import ValidationError

from backend.config import get_settings
from backend.models import Profile

logger = logging.getLogger(__name__)


def load_profile() -> Profile:
    """Load and validate the profile at the configured ``profile_path``."""
    profile_path = get_settings().profile_path
    with open(profile_path, "r") as f:
        data = json.load(f)
    return Profile(**data)


def validate_profile(profile_data: dict) -> Profile | None:
    """Validate ``profile_data`` against :class:`Profile`, or return ``None``."""
    try:
        return Profile(**profile_data)
    except ValidationError as e:
        logger.error("Profile validation error: %s", e)
        return None
