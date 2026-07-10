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


def _planning_memory_section(entries):
    """Human-authored navigation corrections for THIS test (max 4). Empty -> ''.

    Emitting nothing when there are no entries keeps the prompt byte-identical to the
    pre-feature baseline for uncorrected tests.
    """
    if not entries:
        return ''
    lines = '\n'.join(f'- {e}' for e in entries)
    return (
        '\n\n## Human Navigation Corrections — authoritative, follow them exactly:\n'
        'A human watched this test and left these navigation corrections. They override any '
        'guessed path or default when they conflict. They are about HOW to navigate/operate '
        'the UI, not what to verify.\n'
        f'{lines}'
    )
