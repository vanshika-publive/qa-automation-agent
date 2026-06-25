from rest_framework.views import exception_handler


def _first_error_message(data):
    """
    Pull the first human-readable string out of a DRF error payload, which may be
    a {'detail': ...}, a {field: [messages]} validation map, or a bare list/string.
    """
    if isinstance(data, dict):
        if 'detail' in data:
            return str(data['detail'])
        for value in data.values():
            msg = _first_error_message(value)
            if msg:
                return msg
        return None
    if isinstance(data, (list, tuple)):
        for item in data:
            msg = _first_error_message(item)
            if msg:
                return msg
        return None
    return str(data)


def envelope_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        error_msg = _first_error_message(response.data) or str(response.data)
        response.data = {'data': None, 'error': error_msg}
    return response
