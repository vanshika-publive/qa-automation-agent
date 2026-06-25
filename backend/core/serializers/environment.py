from rest_framework import serializers


class EnvironmentSerializer(serializers.Serializer):
    """Output representation of an Environment (camelCase, matches frontend types)."""
    id = serializers.CharField()
    name = serializers.CharField(allow_null=True)
    baseUrl = serializers.CharField(source='base_url', allow_null=True)
    description = serializers.CharField()
    isActive = serializers.BooleanField(source='is_active')
    createdAt = serializers.CharField(source='created_at')
    loginEmail = serializers.CharField(source='login_email')
    publisher = serializers.SerializerMethodField()
    hasPassword = serializers.SerializerMethodField()

    def get_publisher(self, obj):
        return obj.publisher or ''

    def get_hasPassword(self, obj):
        return bool(obj.login_password)


class EnvironmentCreateSerializer(serializers.Serializer):
    """Input validation for creating an Environment."""
    name = serializers.CharField(
        error_messages={'required': 'name is required', 'blank': 'name is required'},
    )
    baseUrl = serializers.CharField(
        error_messages={'required': 'baseUrl is required', 'blank': 'baseUrl is required'},
    )
    loginEmail = serializers.CharField(
        error_messages={'required': 'loginEmail is required', 'blank': 'loginEmail is required'},
    )
    loginPassword = serializers.CharField(
        error_messages={'required': 'loginPassword is required', 'blank': 'loginPassword is required'},
    )
    description = serializers.CharField(required=False, allow_blank=True, default='')
    isActive = serializers.BooleanField(required=False, default=True)


class EnvironmentUpdateSerializer(serializers.Serializer):
    """
    Input validation for updating an Environment. Every field optional —
    only keys actually sent end up in validated_data, so the service can tell
    "set to blank" apart from "leave unchanged".
    """
    name = serializers.CharField(required=False, allow_blank=True)
    baseUrl = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    isActive = serializers.BooleanField(required=False)
    loginEmail = serializers.CharField(required=False, allow_blank=True)
    loginPassword = serializers.CharField(required=False, allow_blank=True)
