GENERATOR_CUSTOM_TOOLS = [
    {
        'type': 'function',
        'function': {
            'name': 'generator_setup_page',
            'description': 'Navigate and reset action log. Use SCENARIO page URL, not base dashboard URL.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'url': {'type': 'string'},
                    'scenarioName': {'type': 'string'},
                },
                'required': ['url', 'scenarioName'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'generator_read_log',
            'description': 'Return browser actions recorded so far as JSON.',
            'parameters': {
                'type': 'object',
                'properties': {},
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'generator_write_test',
            'description': 'Write the generated Python pytest-playwright test to tests/<filename>.py. This is the ONLY way to persist the test — returning the code as a chat message does nothing.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'fileName': {'type': 'string'},
                    'content': {'type': 'string'},
                },
                'required': ['fileName', 'content'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'generator_discover_limits',
            'description': 'Read field length constraints (DOM maxLength, minLength, validation messages). Call after browser_snapshot, before fill calls.',
            'parameters': {
                'type': 'object',
                'properties': {},
            },
        },
    },
]
