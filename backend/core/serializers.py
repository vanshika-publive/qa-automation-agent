from rest_framework import serializers


class CollectionSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    created_at = serializers.CharField()
    test_count = serializers.IntegerField(default=0)


class EnvironmentListSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    base_url = serializers.CharField()
    description = serializers.CharField()
    is_active = serializers.BooleanField()
    created_at = serializers.CharField()
    login_email = serializers.CharField()
    publisher = serializers.CharField(allow_blank=True, required=False)
    has_password = serializers.SerializerMethodField()

    def get_has_password(self, obj):
        if hasattr(obj, 'login_password'):
            return bool(obj.login_password)
        return obj.get('login_password', '') != '' if isinstance(obj, dict) else False


class TestSerializer(serializers.Serializer):
    id = serializers.CharField()
    collection_id = serializers.CharField()
    name = serializers.CharField()
    prompt = serializers.CharField()
    status = serializers.CharField()
    environment_ids = serializers.SerializerMethodField()
    created_at = serializers.CharField()

    def get_environment_ids(self, obj):
        from utils.json_utils import safe_json_parse
        raw = obj.environment_ids if hasattr(obj, 'environment_ids') else obj.get('environment_ids', '[]')
        return safe_json_parse(raw, [])


class ExecutionSerializer(serializers.Serializer):
    id = serializers.CharField()
    test_id = serializers.CharField()
    environment_id = serializers.CharField()
    status = serializers.CharField()
    started_at = serializers.CharField()
    completed_at = serializers.CharField(allow_null=True)
    duration_ms = serializers.IntegerField(allow_null=True)
    pass_count = serializers.IntegerField()
    fail_count = serializers.IntegerField()
    total_count = serializers.IntegerField()
    report_dir = serializers.CharField(allow_null=True)


class ExecutionStepSerializer(serializers.Serializer):
    id = serializers.CharField()
    execution_id = serializers.CharField()
    step_name = serializers.CharField()
    status = serializers.CharField()
    log = serializers.CharField()
    started_at = serializers.CharField()
    completed_at = serializers.CharField(allow_null=True)
