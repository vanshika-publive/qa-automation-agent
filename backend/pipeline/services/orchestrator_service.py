import json
import re
from dataclasses import dataclass
from typing import List

from pipeline.infrastructure.ai_client import AiClientFactory
from pipeline.utils.agent_utils import AgentUtils
from pipeline.utils.credential_manager import CredentialManager
from pipeline.knowledge.dashboard_facts import detect_intent, expand_preconditions, facts_for_prompt
from pipeline.prompts.orchestrator_prompt import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    build_orchestrator_user_message,
)
from utils.markdown import strip_markdown_fences


@dataclass
class TestFlow:
    id: str
    name: str
    description: str
    steps: List[str]
    assertions: List[str]


@dataclass
class TestPlan:
    url: str
    title: str
    flows: List[TestFlow]
    pages: List[str]
    # True when the orchestrator had NO dashboard knowledge for this feature (facts_for_prompt
    # empty). In that case any URL path it emitted is a GUESS (e.g. /settings for a timezone that
    # actually lives under /configurations), so the planner must DISCOVER the real page by driving
    # the live sidebar rather than trusting the guessed path. Default False (known-fact flows).
    needs_discovery: bool = False


class OrchestratorService:

    @staticmethod
    def run(user_prompt: str, url: str) -> TestPlan:
        AgentUtils.reset_call_counter()
        ai = AiClientFactory.create()
        client = ai['client']
        model = ai['model']

        response = client.chat.completions.create(
            model=model,
            max_tokens=1024,
            temperature=0.2,
            messages=[
                {'role': 'system', 'content': ORCHESTRATOR_SYSTEM_PROMPT},
                {
                    'role': 'user',
                    'content': build_orchestrator_user_message(
                        user_prompt, url, CredentialManager.get_publisher()
                    ),
                },
            ],
            response_format={'type': 'json_object'},
        )

        raw = response.choices[0].message.content or ''
        cleaned = strip_markdown_fences(raw)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ValueError(
                f'Orchestrator: JSON parse failed.\nRaw response:\n{raw}\nError: {e}'
            )

        plan = OrchestratorService._validate_schema(parsed)
        expanded = OrchestratorService._expand_with_preconditions(plan, user_prompt)

        # No dashboard facts for this feature => any path the LLM emitted is a guess. Flag the plan
        # for live discovery and drop the guessed pages[] so the planner isn't biased toward them
        # (the guessed path also appears in step prose, which the planner is told to ignore).
        if not facts_for_prompt(user_prompt):
            expanded.needs_discovery = True
            expanded.pages = []
            print('[orchestrator] no facts for this feature — flagged needs_discovery '
                  '(planner will locate the page live)')

        AgentUtils.record_usage(response.usage)
        print(f'[orchestrator] {AgentUtils.get_token_summary()}')
        print(f'Orchestrator: Parsed {len(expanded.flows)} flows from prompt')
        return expanded

    @staticmethod
    def _validate_schema(obj: dict) -> TestPlan:
        if not obj or not isinstance(obj, dict):
            raise ValueError('Response is not an object')
        if not isinstance(obj.get('url'), str):
            raise ValueError('Missing TestPlan.url (string)')
        if not isinstance(obj.get('title'), str):
            raise ValueError('Missing TestPlan.title (string)')
        if not isinstance(obj.get('flows'), list) or len(obj['flows']) == 0:
            raise ValueError('TestPlan.flows must be a non-empty array')
        if not isinstance(obj.get('pages'), list):
            raise ValueError('TestPlan.pages must be an array')

        flows = []
        for f in obj['flows']:
            if not isinstance(f, dict):
                raise ValueError('Each flow must be an object')
            if not isinstance(f.get('id'), str):
                raise ValueError('TestFlow.id must be a string')
            if not isinstance(f.get('name'), str):
                raise ValueError('TestFlow.name must be a string')
            if not isinstance(f.get('description'), str):
                raise ValueError('TestFlow.description must be a string')
            if not isinstance(f.get('steps'), list):
                raise ValueError('TestFlow.steps must be an array')
            if not isinstance(f.get('assertions'), list):
                raise ValueError('TestFlow.assertions must be an array')
            flows.append(
                TestFlow(
                    id=f['id'],
                    name=f['name'],
                    description=f['description'],
                    steps=f['steps'],
                    assertions=f['assertions'],
                )
            )
        return TestPlan(url=obj['url'], title=obj['title'], flows=flows, pages=obj['pages'])

    @staticmethod
    def _expand_with_preconditions(plan: TestPlan, user_prompt: str) -> TestPlan:
        intent = detect_intent(user_prompt)
        if not intent:
            return plan
        preconditions = expand_preconditions(intent)
        if not preconditions:
            return plan

        expanded_flows = []
        for flow in plan.flows:
            flow_text = (' '.join(flow.steps) + ' ' + flow.description + ' ' + flow.name).lower()
            if intent['verb'] not in flow_text:
                expanded_flows.append(flow)
                continue

            to_insert = []
            for p in preconditions:
                match = re.match(r'^Fill (\S+(?: \S+)*?) with ', p)
                field_name = match.group(1).lower() if match else ''
                if not field_name or field_name.lower() not in flow_text:
                    to_insert.append(p)

            if not to_insert:
                expanded_flows.append(flow)
                continue

            verb_step_idx = next(
                (i for i, s in enumerate(flow.steps) if intent['verb'] in s.lower()), -1
            )
            insert_idx = verb_step_idx if verb_step_idx != -1 else len(flow.steps) - 1
            new_steps = flow.steps[:insert_idx] + to_insert + flow.steps[insert_idx:]
            expanded_flows.append(
                TestFlow(
                    id=flow.id, name=flow.name, description=flow.description,
                    steps=new_steps, assertions=flow.assertions,
                )
            )

        return TestPlan(url=plan.url, title=plan.title, flows=expanded_flows, pages=plan.pages)
