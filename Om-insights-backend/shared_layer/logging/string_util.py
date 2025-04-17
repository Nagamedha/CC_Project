import logging
from re import sub
from typing import Dict, List, Set, Mapping

logger = logging.getLogger(__name__)

# Number of chars to show when redacting a string
MASK_CHARS_TO_SHOW = 3

REDACT_KEYS = {
    "username", "password", "Authorization", "authorization", "api_key", "X-API-KEY",
    "email", "first_name", "firstname", "name", "full_name", "fullname", "last_name", "lastname",
    "phone_number", "gift_card_number", "giftcard_number", "credit_card_number", "creditcard",
}

SENSITIVE_PATTERNS = [
    r"\d{3}-\d{2}-\d{4}",  # Social Security Number (SSN) pattern
    r"\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}",  # Credit card number pattern
    r"\(?\d{3}\)?[-\s.]?\d{3}[-\s.]?\d{4}",  # Phone number
    r"(0[1-9]|1[0-2])[-/.](0[1-9]|[12][0-9]|3[01])[-/.](19|20)\d\d",  # Date of birth
    r"((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)",  # IP address
    r"([a-z0-9!#$%&'+\/=?^`{|.}-]+@(?:[a-z0-9](?:[a-z0-9-][a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-][a-z0-9])?)",  # Email
    r"^(?:[A-Za-z0-9+/]{4})(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$",  # Base64
    r"[a-zA-Z0-9]{32}"  # API key
]

REDACTED_STR = "<REDACTED>"


class StringUtil:
    """
    Utility class for string operations.
    """

    EMAIL_PATTERN = r"([a-z0-9!#$%&'+\/=?^`{|.}-]+@(?:[a-z0-9](?:[a-z0-9-][a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-][a-z0-9])?)"

    @staticmethod
    def redact(value: str, redact_patterns: List[str] = None):
        """
        Redacts sensitive information from a given string.
        """
        if isinstance(value, str):
            redact_patterns = redact_patterns or []
            redact_patterns.extend(SENSITIVE_PATTERNS)
            for pattern in redact_patterns:
                if pattern:
                    value = sub(pattern, REDACTED_STR, value)
        return value

    @staticmethod
    def redact_dict(msg: Mapping, redact_keys: Set[str] = None) -> Dict:
        """
        Redacts values for specific keys in a dictionary.
        """
        if isinstance(msg, dict):
            redact_keys = redact_keys or set()
            redact_keys.update