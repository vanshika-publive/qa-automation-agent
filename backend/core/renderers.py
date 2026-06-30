from rest_framework.renderers import BaseRenderer, JSONRenderer

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


class EventStreamRenderer(BaseRenderer):
    """Lets SSE views pass DRF content negotiation. A real browser's EventSource
    always sends `Accept: text/event-stream`, which the JSON-only EnvelopeRenderer
    doesn't declare, so DRF 406s before the view body runs. The view returns a raw
    StreamingHttpResponse, so .render() is never actually called — this only needs
    to exist so select_renderer() has a renderer whose media_type matches."""
    media_type = 'text/event-stream'
    format = 'txt'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data
