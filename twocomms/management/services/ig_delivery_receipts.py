"""Shared validation for durable Instagram provider receipt identifiers."""

MAX_PROVIDER_MESSAGE_ID_LENGTH = 255


def normalize_provider_message_id(value) -> str:
    """Return one bounded nonblank receipt ID, or an empty string."""
    if not isinstance(value, str):
        return ""
    normalized = value.strip()
    if not normalized or len(normalized) > MAX_PROVIDER_MESSAGE_ID_LENGTH:
        return ""
    return normalized


def normalize_provider_message_ids(values) -> tuple[str, ...]:
    """Return unique valid IDs while preserving provider order."""
    if values is None:
        return ()
    if isinstance(values, (str, bytes)):
        values = (values,)
    try:
        candidates = iter(values)
    except TypeError:
        return ()
    normalized = []
    seen = set()
    for value in candidates:
        receipt_id = normalize_provider_message_id(value)
        if receipt_id and receipt_id not in seen:
            normalized.append(receipt_id)
            seen.add(receipt_id)
    return tuple(normalized)
