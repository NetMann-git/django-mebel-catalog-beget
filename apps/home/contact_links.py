"""HTTP links accepted by the contact editor and the public contact block."""

from urllib.parse import urlsplit


def public_url(value):
    value = (value or "").strip()
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
        ):
            return ""
    except ValueError:
        return ""
    return value
