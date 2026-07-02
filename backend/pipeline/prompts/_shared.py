def _publisher_section(publisher, body):
    if not publisher:
        return ''
    return f'\n\n## ACTIVE PUBLISHER: {publisher}\n{body}'


def _facts_section(facts, preamble):
    if not facts:
        return ''
    return f'\n\n## Verified Page Facts — {preamble}:\n{facts}'


def _heuristics_section(heuristics):
    if not heuristics:
        return ''
    return f'\n\n## Known Dashboard Quirks — you MUST follow these:\n{heuristics}'
