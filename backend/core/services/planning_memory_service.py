import json
import uuid

from core.constants import PlanningMemory as PlanningMemoryLimits
from core.models import TestPlanningMemory
from utils.datetime_utils import DateTimeUtils


class PlanningMemoryCapReached(Exception):
    """Raised when a test already holds the maximum number of memory entries."""


class PlanningMemoryService:
    """Per-test human-authored navigation corrections.

    Only ever written through human-initiated API paths — the pipeline never calls
    create()/update(). Capped at PlanningMemoryLimits.MAX_ENTRIES at the app layer.
    """

    @staticmethod
    def list_for_test(test_id: str):
        return TestPlanningMemory.objects.filter(test_id=test_id).order_by('created_at')

    @staticmethod
    def contents_for_test(test_id: str) -> list:
        """The bare correction strings, oldest first — used for planner-prompt injection."""
        return list(
            PlanningMemoryService.list_for_test(test_id).values_list('content', flat=True)
        )

    @staticmethod
    def create(test_id: str, content: str) -> TestPlanningMemory:
        if PlanningMemoryService.list_for_test(test_id).count() >= PlanningMemoryLimits.MAX_ENTRIES:
            raise PlanningMemoryCapReached(
                f'Planning memory is full ({PlanningMemoryLimits.MAX_ENTRIES} entries). '
                'Edit or delete an existing entry to make room.'
            )
        now = DateTimeUtils.now_iso()
        return TestPlanningMemory.objects.create(
            id=str(uuid.uuid4()),
            test_id=test_id,
            content=content,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def update(memory: TestPlanningMemory, content: str) -> TestPlanningMemory:
        memory.content = content
        memory.updated_at = DateTimeUtils.now_iso()
        memory.save()
        return memory

    @staticmethod
    def soft_delete(memory_id: str) -> int:
        return TestPlanningMemory.objects.filter(id=memory_id).update(
            deleted_at=DateTimeUtils.now_iso()
        )

    @staticmethod
    def classify_text(content: str) -> dict:
        """Advisory intent-vs-navigation check on a submitted correction.

        Returns {'kind': 'navigation'|'scope'}. NEVER blocks a write — the caller shows
        a non-blocking hint when kind == 'scope'. Any error degrades to 'navigation'
        (assume a valid nav correction rather than nag the user on a flaky call).
        """
        prompt = (
            "You classify a note a QA engineer attached to a browser test on a fixed dashboard.\n"
            "Decide if it is a NAVIGATION correction (how to reach/operate the UI: which "
            "button, menu, page, or path to use) or a SCOPE change (what the test should "
            "verify: new assertions, extra cases, different data to check).\n"
            "Reply with JSON only: {\"kind\": \"navigation\"} or {\"kind\": \"scope\"}.\n\n"
            f"Note: {content}"
        )
        try:
            from pipeline.infrastructure.ai_client import AiClientFactory
            ai = AiClientFactory.create()
            response = ai['client'].chat.completions.create(
                model=ai['model'],
                temperature=0,
                max_tokens=32,
                response_format={'type': 'json_object'},
                messages=[{'role': 'user', 'content': prompt}],
            )
            parsed = json.loads(response.choices[0].message.content)
            kind = parsed.get('kind')
            return {'kind': kind if kind in ('navigation', 'scope') else 'navigation'}
        except Exception:
            return {'kind': 'navigation'}
