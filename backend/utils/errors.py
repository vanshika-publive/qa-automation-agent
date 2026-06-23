def to_message(err: Exception) -> str:
    return str(err) if err else 'Unknown error'
