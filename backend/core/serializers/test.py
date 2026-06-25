from rest_framework import serializers

from utils.json_utils import safe_json_parse


class TestSerializer(serializers.Serializer):
    """Output representation of a Test (camelCase, matches frontend types)."""
    id = serializers.CharField()
    collectionId = serializers.CharField(source='collection_id')
    name = serializers.CharField()
    prompt = serializers.CharField(allow_blank=True)
    status = serializers.CharField()
    environmentIds = serializers.SerializerMethodField()
    createdAt = serializers.CharField(source='created_at')

    def get_environmentIds(self, obj):
        return safe_json_parse(obj.environment_ids, [])


class TestCreateSerializer(serializers.Serializer):
    """Input validation for creating a Test within a collection."""
    name = serializers.CharField(
        error_messages={'required': 'name is required', 'blank': 'name is required'},
    )
    prompt = serializers.CharField(required=False, allow_blank=True, default='')


class TestUpdateSerializer(serializers.Serializer):
    """
    Input validation for updating a Test. All fields optional; only sent keys
    reach validated_data so the service applies a partial update.
    """
    name = serializers.CharField(required=False, allow_blank=True)
    prompt = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField(required=False)
    collectionId = serializers.CharField(required=False)
    environmentIds = serializers.ListField(child=serializers.CharField(), required=False)
    duplicate = serializers.BooleanField(required=False, default=False)

    def validate_collectionId(self, value):
        from core.models import Collection
        if value and not Collection.objects.filter(id=value).exists():
            raise serializers.ValidationError('Collection not found')
        return value


class SpecSaveSerializer(serializers.Serializer):
    """Input validation for hand-saving a generated spec file."""
    content = serializers.CharField(
        error_messages={'required': 'content is required', 'blank': 'content is required'},
    )
    filename = serializers.CharField(
        error_messages={'required': 'filename is required', 'blank': 'filename is required'},
    )

    def validate_content(self, value):
        if 'import' not in value:
            raise serializers.ValidationError('content must contain an import statement')
        if 'def test' not in value:
            raise serializers.ValidationError('content must contain a def test_... function')
        return value


class RunSerializer(serializers.Serializer):
    """Input validation for kicking off a pipeline run."""
    environmentId = serializers.CharField(
        error_messages={'required': 'environmentId is required', 'blank': 'environmentId is required'},
    )


class RunSpecSerializer(RunSerializer):
    """Input validation for re-running a specific spec file."""
    filename = serializers.CharField(
        error_messages={'required': 'filename is required', 'blank': 'filename is required'},
    )
