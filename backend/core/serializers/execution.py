from rest_framework import serializers


class ExecutionStepSerializer(serializers.Serializer):
    """Output representation of an ExecutionStep (camelCase)."""
    id = serializers.CharField()
    executionId = serializers.CharField(source='execution_id')
    stepName = serializers.CharField(source='step_name')
    status = serializers.CharField()
    log = serializers.CharField()
    startedAt = serializers.CharField(source='started_at')
    completedAt = serializers.CharField(source='completed_at')


class ExecutionSerializer(serializers.Serializer):
    """Base execution fields (camelCase). Used for the SSE stream payload."""
    id = serializers.CharField()
    testId = serializers.CharField(source='test_id')
    environmentId = serializers.CharField(source='environment_id')
    status = serializers.CharField()
    startedAt = serializers.CharField(source='started_at')
    completedAt = serializers.CharField(source='completed_at')
    durationMs = serializers.IntegerField(source='duration_ms')
    passCount = serializers.IntegerField(source='pass_count')
    failCount = serializers.IntegerField(source='fail_count')
    totalCount = serializers.IntegerField(source='total_count')
    reportDir = serializers.CharField(source='report_dir')


class _ExecutionJoinedSerializer(ExecutionSerializer):
    """Base fields plus the related-row joins both list and detail responses carry."""
    collectionId = serializers.SerializerMethodField()
    collectionName = serializers.SerializerMethodField()
    testName = serializers.SerializerMethodField()
    environmentName = serializers.SerializerMethodField()
    environmentUrl = serializers.SerializerMethodField()
    runNumber = serializers.SerializerMethodField()

    def get_collectionId(self, obj):
        return obj.test.collection_id

    def get_collectionName(self, obj):
        return obj.test.collection.name

    def get_testName(self, obj):
        return obj.test.name

    def get_environmentName(self, obj):
        return obj.environment.name

    def get_environmentUrl(self, obj):
        return obj.environment.base_url

    def get_runNumber(self, obj):
        # List rows carry it as a window annotation; detail passes it via context.
        return self.context.get('run_number', getattr(obj, 'run_number', None))


class ExecutionListSerializer(_ExecutionJoinedSerializer):
    """One row of the paginated executions list."""
    pass


class ExecutionDetailSerializer(_ExecutionJoinedSerializer):
    """Single execution with its pipeline steps and (when failed) a classified reason.

    Pass context={'run_number', 'steps', 'failure'} where 'failure' is the
    {category, summary, locator} dict from ExecutionService.failure_summary, or None.
    """
    steps = serializers.SerializerMethodField()
    failureCategory = serializers.SerializerMethodField()
    failureReason = serializers.SerializerMethodField()
    failureLocator = serializers.SerializerMethodField()

    def get_steps(self, obj):
        return ExecutionStepSerializer(self.context.get('steps', []), many=True).data

    def get_failureCategory(self, obj):
        return (self.context.get('failure') or {}).get('category')

    def get_failureReason(self, obj):
        return (self.context.get('failure') or {}).get('summary')

    def get_failureLocator(self, obj):
        return (self.context.get('failure') or {}).get('locator')
