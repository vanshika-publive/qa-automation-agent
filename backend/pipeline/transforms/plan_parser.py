import re
from dataclasses import dataclass, field
from typing import List

from utils.slug import to_collection_slug


@dataclass
class Scenario:
    flow_name: str
    scenario_name: str
    steps: List[str]
    expected: List[str]
    file_name: str


def parse_plan_md(content: str) -> List[Scenario]:
    scenarios: List[Scenario] = []

    flow_blocks = re.split(r'^## Flow \d+[:\s\-\.]+', content, flags=re.MULTILINE)[1:]
    if len(flow_blocks) == 0:
        flow_blocks = re.split(r'^## ', content, flags=re.MULTILINE)[1:]

    for flow_block in flow_blocks:
        flow_name_match = re.match(r'^([^\n]+)', flow_block)
        raw_flow_name = flow_name_match.group(1).strip() if flow_name_match else 'Unknown Flow'
        flow_name = re.sub(r'^Flow \d+[:\s\-\.]+', '', raw_flow_name).strip() or raw_flow_name

        scenario_blocks = re.split(r'^### Scenario:\s*', flow_block, flags=re.MULTILINE)[1:]
        if len(scenario_blocks) == 0:
            scenario_blocks = re.split(r'^### ', flow_block, flags=re.MULTILINE)[1:]

        # A flow is ONE self-contained journey, so it maps to ONE test. When the planner splits a
        # single flow into multiple "### Scenario" blocks (e.g. a "Create ..." scenario and a
        # separate "Delete ..." scenario for the SAME item), they would otherwise become independent
        # pytest tests that cannot share runtime state — the delete test would compute its own fresh
        # ts and look for an item that was never created. Merge all scenarios of a flow, in order,
        # into a single scenario so create-then-delete/edit runs as one test. A flow with a single
        # scenario is unaffected (the common case).
        merged_steps: List[str] = []
        merged_expected: List[str] = []
        scenario_names: List[str] = []

        for scenario_block in scenario_blocks:
            name_match = re.match(r'^([^\n]+)', scenario_block)
            scenario_name = name_match.group(1).strip() if name_match else 'Unknown Scenario'

            steps_match = re.search(r'\*\*Steps:?\*\*\s*\n([\s\S]*?)(?=\*\*Expected|$)', scenario_block)
            if steps_match:
                steps = re.findall(r'^\d+\.\s+(.+)$', steps_match.group(1), flags=re.MULTILINE)
            else:
                steps = []

            expected_match = re.search(
                r'\*\*Expected:?\*\*\s*\n([\s\S]*?)(?=^##|^###|$)', scenario_block, flags=re.MULTILINE
            )
            if expected_match:
                expected = re.findall(r'^[-*]\s+(.+)$', expected_match.group(1), flags=re.MULTILINE)
            else:
                expected = []

            if len(steps) == 0:
                continue

            merged_steps.extend(steps)
            merged_expected.extend(expected)
            scenario_names.append(scenario_name)

        if not merged_steps:
            continue

        # Keep the single scenario's name when the flow wasn't split (preserves existing file names);
        # use the flow name when several scenarios were merged into one journey.
        merged_name = scenario_names[0] if len(scenario_names) == 1 else flow_name
        scenarios.append(Scenario(
            flow_name=flow_name,
            scenario_name=merged_name,
            steps=merged_steps,
            expected=merged_expected,
            file_name=f"{to_collection_slug(flow_name)}-{to_collection_slug(merged_name)}",
        ))

    return scenarios


def preserve_prefix_steps(plan_md: str, prefix_steps: List[str]) -> str:
    """Force the first scenario's leading steps to be exactly `prefix_steps`.

    Used by the corrective-replan flow so the human-validated prefix (steps 1..N-1) is
    guaranteed byte-identical, not re-derived: whatever the planner wrote for those
    positions is discarded and replaced with the originals, and everything the planner
    produced beyond the prefix length is kept as the corrected tail. Targets the FIRST
    Steps block (corrective replan operates on the plan's first/primary scenario).
    """
    if not prefix_steps:
        return plan_md
    pattern = re.compile(
        r'(\*\*Steps:?\*\*\s*\n)([\s\S]*?)(?=\n\s*\*\*Expected|\Z)', flags=re.MULTILINE
    )
    match = pattern.search(plan_md)
    if not match:
        return plan_md
    produced = re.findall(r'^\s*\d+\.\s+(.+)$', match.group(2), flags=re.MULTILINE)
    tail = produced[len(prefix_steps):]
    combined = list(prefix_steps) + tail
    new_block = '\n'.join(f'{i + 1}. {step}' for i, step in enumerate(combined))
    return plan_md[:match.start(2)] + new_block + plan_md[match.end(2):]


def extract_scenario_url(steps: List[str], base_url: str) -> str:
    for step in steps:
        goto_match = re.search(r"page\.goto\(['\"`](https?:\/\/[^'\"`]+|\/[^'\"`]+)['\"`]\)", step)
        if goto_match:
            matched = goto_match.group(1)
            return matched if matched.startswith('http') else f"{base_url}{matched}"

        navigate_match = re.search(
            r"(?:navigate|go|visit|open)\s+(?:to\s+)?(?:the\s+)?(?:url\s+)?['\"]?(\/[a-z0-9/_?=&-]+)",
            step, flags=re.IGNORECASE
        )
        if navigate_match:
            return f"{base_url}{navigate_match.group(1)}"

        if re.search(r'article.*(creat|add|new)|create.*article|add.*article', step, flags=re.IGNORECASE):
            return f"{base_url}/posts/article/create"
        if re.search(r'video.*(creat|add|new)|create.*video', step, flags=re.IGNORECASE):
            return f"{base_url}/posts/video/create"
        if re.search(r'web.?story.*(creat|add|new)|create.*web.?story', step, flags=re.IGNORECASE):
            return f"{base_url}/posts/web-story/create"
        if re.search(r'live.?blog.*(creat|add|new)|create.*live.?blog', step, flags=re.IGNORECASE):
            return f"{base_url}/posts/live-blog/create"
        if re.search(r'custom.?content|custom.?page', step, flags=re.IGNORECASE):
            return f"{base_url}/posts/custom-page/create"
        # Entity pages - use the verified /posts/entity/<plural>/<singular>/create pattern
        if re.search(r'geograph', step, flags=re.IGNORECASE):
            return f"{base_url}/posts/entity/geographies/geography/create"
        if re.search(r'\bfood\b', step, flags=re.IGNORECASE):
            return f"{base_url}/posts/entity/foods/food/create"
        if re.search(r'horoscope', step, flags=re.IGNORECASE):
            return f"{base_url}/posts/entity/horoscopes/horoscope/create"
        if re.search(r'breaking.?news|news.?update', step, flags=re.IGNORECASE):
            return f"{base_url}/posts/entity/news_updates/news_update/create"
        if re.search(r'articles?\s*(page|list|view)|posts?\s*(page|list|view)', step, flags=re.IGNORECASE):
            return f"{base_url}/posts"
        if re.search(r'categor', step, flags=re.IGNORECASE):
            return f"{base_url}/categories"
        if re.search(r'tags?\s*(page|list|view)', step, flags=re.IGNORECASE):
            return f"{base_url}/tags"
        if re.search(r'team', step, flags=re.IGNORECASE):
            return f"{base_url}/team-members"
        if re.search(r'media', step, flags=re.IGNORECASE):
            return f"{base_url}/media"
        if re.search(r'settings', step, flags=re.IGNORECASE):
            return f"{base_url}/settings"
        if re.search(r'draft', step, flags=re.IGNORECASE):
            return f"{base_url}/posts/draft"

    return base_url
