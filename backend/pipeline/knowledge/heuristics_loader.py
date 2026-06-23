import functools
from pathlib import Path


@functools.lru_cache(maxsize=1)
def get_heuristics():
    heuristics_path = Path(__file__).parent / 'dashboardHeuristics.md'
    try:
        return heuristics_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return ''
