import re


_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_AADHAAR = re.compile(r"\b(?:\d[ -]?){11}\d\b")
_INDIAN_PHONE = re.compile(r"(?<!\w)(?:\+?91[ -]?)?[6-9]\d{9}(?!\w)")


def redact_common_identifiers(text: str) -> str:
    """Best-effort minimization for common direct identifiers before external NLP calls."""
    text = _EMAIL.sub("[EMAIL]", text)
    text = _AADHAAR.sub("[ID_NUMBER]", text)
    return _INDIAN_PHONE.sub("[PHONE]", text)
