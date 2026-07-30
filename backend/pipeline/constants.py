AI_MODEL = 'gpt-4o'

# gpt-4o token pricing, USD per 1M tokens (as of 2026-07). Cached input is billed at
# half the standard input rate; `cached_tokens` is a subset of `prompt_tokens`.
AI_PRICE_INPUT_PER_M = 2.50
AI_PRICE_CACHED_INPUT_PER_M = 1.25
AI_PRICE_OUTPUT_PER_M = 10.00

MCP_TIMEOUT_MS = 30_000
MCP_PROTOCOL_VERSION = '2024-11-05'
PLAYWRIGHT_BROWSER = 'chromium'

PIPELINE_KILL_TIMEOUT_MS = 4 * 60_000  # outer backstop; per-test pytest-timeout is 30s
MAX_PLANNER_ITERATIONS = 12
MAX_GENERATOR_ITERATIONS = 10
PLANNER_NUDGE_THRESHOLD = 0.75
GENERATOR_NUDGE_THRESHOLD = 0.7
GENERATOR_FINAL_WARNING_THRESHOLD = 0.87

# Spec file matching — shared with core/services/test_service.py
EXCLUDED_SPEC_FILES = frozenset(['conftest.py', 'helpers.py'])
MIN_SLUG_WORD_LENGTH = 3

# Results parsing — shared with core/services/execution_service.py
ERROR_TRUNCATE_LENGTH = 400

SESSION_EXPIRY_SECONDS = 60 * 60 * 24
LOGIN_TIMEOUT_MS = 30_000
LOGIN_PATH = '/login'

# Retention — bounded growth of per-run artifacts (core/services/retention_service.py),
# enforced on every pipeline-run teardown alongside the MCP-artifact/plan-snapshot cleanup.
EXECUTION_RETENTION_PER_TEST = 20
SCREENSHOT_RETENTION_DAYS = 30
