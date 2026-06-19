import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

from pipeline.ai_client import create_ai_client
from pipeline.knowledge.dashboard_facts import detect_intent, expand_preconditions
from utils.markdown import strip_markdown_fences
from pipeline.prompts.orchestrator_prompt import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    build_orchestrator_user_message,
)


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


def validate_test_plan_schema(obj):
    """Validate that a parsed JSON object conforms to the TestPlan schema."""
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

    return TestPlan(
        url=obj['url'],
        title=obj['title'],
        flows=flows,
        pages=obj['pages'],
    )


def parse_user_intent(user_prompt: str, url: str) -> TestPlan:
    """Send the user prompt to the orchestrator LLM and return a validated TestPlan."""
    ai = create_ai_client()
    client = ai['client']
    model = ai['model']

    response = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        temperature=0.2,
        messages=[
            {'role': 'system', 'content': ORCHESTRATOR_SYSTEM_PROMPT},
            {'role': 'user', 'content': build_orchestrator_user_message(user_prompt, url)},
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

    plan = validate_test_plan_schema(parsed)
    expanded = expand_plan_with_preconditions(plan, user_prompt)
    print(f'Orchestrator: Parsed {len(expanded.flows)} flows from prompt')
    return expanded


def expand_plan_with_preconditions(plan: TestPlan, user_prompt: str) -> TestPlan:
    """
    Belt-and-suspenders for publish flows: inject Summary/Meta steps
    if the LLM skipped them. Idempotent.
    """
    intent = detect_intent(user_prompt)
    if not intent:
        return plan

    preconditions = expand_preconditions(intent)
    if len(preconditions) == 0:
        return plan

    expanded_flows = []
    for flow in plan.flows:
        # Only expand flows that mention the target verb, to avoid contaminating unrelated flows.
        flow_text = (' '.join(flow.steps) + ' ' + flow.description + ' ' + flow.name).lower()
        verb_mentioned = intent['verb'] in flow_text
        if not verb_mentioned:
            expanded_flows.append(flow)
            continue

        to_insert = []
        for p in preconditions:
            match = re.match(r'^Fill (\S+(?: \S+)*?) with ', p)
            field_name = match.group(1).lower() if match else ''
            if not field_name:
                to_insert.append(p)
            elif field_name.lower() not in flow_text:
                to_insert.append(p)

        if len(to_insert) == 0:
            expanded_flows.append(flow)
            continue

        verb_step_idx = -1
        for i, s in enumerate(flow.steps):
            if intent['verb'] in s.lower():
                verb_step_idx = i
                break

        insert_idx = verb_step_idx if verb_step_idx != -1 else len(flow.steps) - 1
        new_steps = flow.steps[:insert_idx] + to_insert + flow.steps[insert_idx:]

        expanded_flows.append(
            TestFlow(
                id=flow.id,
                name=flow.name,
                description=flow.description,
                steps=new_steps,
                assertions=flow.assertions,
            )
        )

    return TestPlan(
        url=plan.url,
        title=plan.title,
        flows=expanded_flows,
        pages=plan.pages,
    )
