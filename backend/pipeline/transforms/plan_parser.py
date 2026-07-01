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

        for scenario_block in scenario_blocks:
            name_match = re.match(r'^([^\n]+)', scenario_block)
            scenario_name = name_match.group(1).strip() if name_match else 'Unknown Scenario'

            steps_match = re.search(r'\*\*Steps:?\*\*\s*\n([\s\S]*?)(?=\*\*Expected|$)', scenario_block)
            if steps_match:
                step_lines = re.findall(r'^\d+\.\s+(.+)$', steps_match.group(1), flags=re.MULTILINE)
                steps = step_lines
            else:
                steps = []

            expected_match = re.search(
                r'\*\*Expected:?\*\*\s*\n([\s\S]*?)(?=^##|^###|$)', scenario_block, flags=re.MULTILINE
            )
            if expected_match:
                expected_lines = re.findall(r'^[-*]\s+(.+)$', expected_match.group(1), flags=re.MULTILINE)
                expected = expected_lines
            else:
                expected = []

            if len(steps) == 0:
                continue

            scenarios.append(Scenario(
                flow_name=flow_name,
                scenario_name=scenario_name,
                steps=steps,
                expected=expected,
                file_name=f"{to_collection_slug(flow_name)}-{to_collection_slug(scenario_name)}",
            ))

    return scenarios


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
