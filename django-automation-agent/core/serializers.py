from rest_framework import serializers


class CollectionSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    createdAt = serializers.CharField(source='created_at')
    testCount = serializers.IntegerField(source='test_count', default=0)


class EnvironmentListSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    baseUrl = serializers.CharField(source='base_url')
    description = serializers.CharField()
    isActive = serializers.BooleanField(source='is_active')
    createdAt = serializers.CharField(source='created_at')
    loginEmail = serializers.CharField(source='login_email')
    hasPassword = serializers.SerializerMethodField()

    def get_hasPassword(self, obj):
        if hasattr(obj, 'login_password'):
            return bool(obj.login_password)
        return obj.get('login_password', '') != '' if isinstance(obj, dict) else False


class TestSerializer(serializers.Serializer):
    id = serializers.CharField()
    collectionId = serializers.CharField(source='collection_id')
    name = serializers.CharField()
    prompt = serializers.CharField()
    status = serializers.CharField()
    environmentIds = serializers.SerializerMethodField()
    createdAt = serializers.CharField(source='created_at')

    def get_environmentIds(self, obj):
        from utils.json_utils import safe_json_parse
        raw = obj.environment_ids if hasattr(obj, 'environment_ids') else obj.get('environment_ids', '[]')
        return safe_json_parse(raw, [])


class ExecutionSerializer(serializers.Serializer):
    id = serializers.CharField()
    testId = serializers.CharField(source='test_id')
    environmentId = serializers.CharField(source='environment_id')
    status = serializers.CharField()
    startedAt = serializers.CharField(source='started_at')
    completedAt = serializers.CharField(source='completed_at', allow_null=True)
    durationMs = serializers.IntegerField(source='duration_ms', allow_null=True)
    passCount = serializers.IntegerField(source='pass_count')
    failCount = serializers.IntegerField(source='fail_count')
    totalCount = serializers.IntegerField(source='total_count')
    reportDir = serializers.CharField(source='report_dir', allow_null=True)


class ExecutionStepSerializer(serializers.Serializer):
    id = serializers.CharField()
    executionId = serializers.CharField(source='execution_id')
    stepName = serializers.CharField(source='step_name')
    status = serializers.CharField()
    log = serializers.CharField()
    startedAt = serializers.CharField(source='started_at')
    completedAt = serializers.CharField(source='completed_at', allow_null=True)
