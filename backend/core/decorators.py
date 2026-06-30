from functools import wraps

from rest_framework.exceptions import NotFound


def validate_body(serializer_class):    #create
    """
    Validate request.data with an input serializer before the view body runs, and
    pass the cleaned values in as a `data` keyword argument.

    Keeps validation out of the view: the handler only ever sees valid input, and
    invalid input raises ValidationError (turned into a 404/400 envelope by
    core.exceptions.envelope_exception_handler).

        @validate_body(CollectionWriteSerializer)
        def create(self, request, data=None):
            CollectionService.create(data['name'])
    """
    def decorator(method):
        @wraps(method)
        def wrapper(self, request, *args, **kwargs):
            serializer = serializer_class(data=request.data)
            serializer.is_valid(raise_exception=True)
            kwargs['data'] = serializer.validated_data
            return method(self, request, *args, **kwargs)
        return wrapper
    return decorator


def fetch_object(model, error_message, select_related=()):
    """
    Look the row up by the URL's `pk` and pass it to the view as `obj`. A missing row
    raises NotFound — rendered as a 404 with `error_message` by the envelope handler —
    replacing the repeated `try: Model.objects.get(...) except DoesNotExist: 404` block.

    Uses the model's default manager, so soft-deleted rows count as absent.

        @fetch_object(Collection, 'Collection not found')
        def specs(self, request, obj=None, pk=None):
            ... use obj ...
    """
    def decorator(method):
        @wraps(method)
        def wrapper(self, request, *args, **kwargs):
            queryset = model.objects.all()
            if select_related:
                queryset = queryset.select_related(*select_related)
            try:
                kwargs['obj'] = queryset.get(id=kwargs.get('pk'))
            except model.DoesNotExist:
                raise NotFound(error_message)
            return method(self, request, *args, **kwargs)
        return wrapper
    return decorator
