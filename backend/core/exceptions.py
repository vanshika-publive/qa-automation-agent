from rest_framework.views import exception_handler


def envelope_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        if isinstance(response.data, dict) and 'detail' in response.data:
            error_msg = str(response.data['detail'])
        elif isinstance(response.data, list):
            error_msg = '; '.join(str(e) for e in response.data)
        else:
            error_msg = str(response.data)
        response.data = {'data': None, 'error': error_msg}
    return response
