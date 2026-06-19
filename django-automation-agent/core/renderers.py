from rest_framework.renderers import JSONRenderer


class EnvelopeRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get('response') if renderer_context else None

        if response and response.status_code >= 400:
            if isinstance(data, dict) and 'error' in data:
                envelope = {'data': None, 'error': data['error']}
            elif isinstance(data, dict) and 'detail' in data:
                envelope = {'data': None, 'error': str(data['detail'])}
            else:
                envelope = {'data': None, 'error': str(data)}
        elif isinstance(data, dict) and 'data' in data and 'error' in data:
            envelope = data
        elif isinstance(data, dict) and 'pagination' in data:
            envelope = {
                'data': data.get('data'),
                'error': None,
                'pagination': data['pagination'],
            }
        else:
            envelope = {'data': data, 'error': None}

        return super().render(envelope, accepted_media_type, renderer_context)
