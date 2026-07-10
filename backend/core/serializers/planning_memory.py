from rest_framework import serializers


class PlanningMemorySerializer(serializers.Serializer):
    """Output representation of a Planning Memory entry (camelCase)."""
    id = serializers.CharField()
    testId = serializers.CharField(source='test_id')
    content = serializers.CharField()
    createdAt = serializers.CharField(source='created_at')
    updatedAt = serializers.CharField(source='updated_at')


class PlanningMemoryWriteSerializer(serializers.Serializer):
    """Input validation for creating/editing a Planning Memory entry."""
    content = serializers.CharField(
        error_messages={'required': 'content is required', 'blank': 'content is required'},
    )


class CorrectionWriteSerializer(serializers.Serializer):
    """Input validation for a human-initiated corrective replan."""
    failedAtStep = serializers.IntegerField(
        min_value=1,
        error_messages={'required': 'failedAtStep is required'},
    )
    correction = serializers.CharField(
        error_messages={'required': 'correction is required', 'blank': 'correction is required'},
    )
    environmentId = serializers.CharField(
        error_messages={'required': 'environmentId is required', 'blank': 'environmentId is required'},
    )
