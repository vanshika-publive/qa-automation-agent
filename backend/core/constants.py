class PaginationDefaults:
    PAGE = 1
    PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100


class ExecutionStatus:
    RUNNING = 'running'
    PASSED = 'passed'
    FAILED = 'failed'
    QUEUED = 'queued'


class TestStatus:
    ACTIVE = 'active'
    DELETED = 'deleted'


class SSEConstants:
    POLL_INTERVAL_S = 0.8
