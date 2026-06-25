from rest_framework import serializers


class CollectionSerializer(serializers.Serializer):
    """Output representation of a Collection (camelCase, matches frontend types)."""
    id = serializers.CharField()
    name = serializers.CharField()
    createdAt = serializers.CharField(source='created_at')
    testCount = serializers.SerializerMethodField()

    def get_testCount(self, obj):
        # Annotated by CollectionManager.with_test_count(); absent on a freshly
        # created instance, where the count is always 0.
        return getattr(obj, 'test_count', 0)


class CollectionWriteSerializer(serializers.Serializer):
    """Input validation for create + rename. CharField trims and rejects blank."""
    name = serializers.CharField(
        error_messages={'required': 'name is required', 'blank': 'name is required'},
    )
