from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from core.constants import PlanningMemory as PlanningMemoryLimits
from core.decorators import validate_body, fetch_object
from core.models import Test, Environment, TestPlanningMemory
from core.serializers import (
    PlanningMemorySerializer,
    PlanningMemoryWriteSerializer,
    CorrectionWriteSerializer,
)
from core.services.execution_service import ExecutionService
from core.services.planning_memory_service import (
    PlanningMemoryService,
    PlanningMemoryCapReached,
)

PLANNING_MEMORY_MAX = PlanningMemoryLimits.MAX_ENTRIES


class TestPlanningMemoryListView(APIView):
    """/tests/<pk>/planning-memory"""

    @fetch_object(Test, 'Test not found')
    def get(self, request, obj=None, pk=None):
        entries = PlanningMemoryService.list_for_test(obj.id)
        return Response(PlanningMemorySerializer(entries, many=True).data)

    @fetch_object(Test, 'Test not found')
    @validate_body(PlanningMemoryWriteSerializer)
    def post(self, request, obj=None, data=None, pk=None):
        try:
            entry = PlanningMemoryService.create(obj.id, data['content'])
        except PlanningMemoryCapReached as exc:
            return Response({'error': str(exc)}, status=status.HTTP_409_CONFLICT)
        payload = dict(PlanningMemorySerializer(entry).data)
        # Advisory only — the frontend shows a non-blocking hint when kind == 'scope'.
        payload['advisory'] = PlanningMemoryService.classify_text(data['content'])
        return Response(payload, status=status.HTTP_201_CREATED)


class TestPlanningMemoryDetailView(APIView):
    """/tests/<pk>/planning-memory/<mid>"""

    @validate_body(PlanningMemoryWriteSerializer)
    def patch(self, request, data=None, pk=None, mid=None):
        try:
            memory = TestPlanningMemory.objects.get(id=mid)
        except TestPlanningMemory.DoesNotExist:
            raise NotFound('Planning memory entry not found')
        entry = PlanningMemoryService.update(memory, data['content'])
        return Response(PlanningMemorySerializer(entry).data)

    def delete(self, request, pk=None, mid=None):
        if not PlanningMemoryService.soft_delete(mid):
            return Response(
                {'error': 'Planning memory entry not found'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({'id': mid})


class TestCorrectionsView(APIView):
    """/tests/<pk>/corrections — human-initiated corrective replan."""

    @validate_body(CorrectionWriteSerializer)
    @fetch_object(Test, 'Test not found')
    def post(self, request, obj=None, data=None, pk=None):
        environment_id = data['environmentId']
        if not Environment.objects.filter(id=environment_id).exists():
            return Response({'error': 'Environment not found'}, status=status.HTTP_404_NOT_FOUND)
        # Terminal-at-cap: a successful correction records a Planning Memory entry, so refuse
        # up front when full rather than replanning and silently dropping the lesson. The user
        # edits/deletes an existing entry to make room (guardrail 5).
        if PlanningMemoryService.list_for_test(obj.id).count() >= PLANNING_MEMORY_MAX:
            return Response(
                {'error': (
                    f'Planning memory is full ({PLANNING_MEMORY_MAX} entries) and this is a new '
                    'correction. Edit or delete an existing entry to make room, then try again.'
                )},
                status=status.HTTP_409_CONFLICT,
            )
        execution_id = ExecutionService.create_execution(obj.id, environment_id)
        ExecutionService.launch_correction(
            execution_id, obj.id, environment_id, data['failedAtStep'], data['correction'],
        )
        # Advisory only (non-blocking) — the replan proceeds regardless of the classification.
        advisory = PlanningMemoryService.classify_text(data['correction'])
        return Response(
            {'executionId': execution_id, 'advisory': advisory},
            status=status.HTTP_202_ACCEPTED,
        )
