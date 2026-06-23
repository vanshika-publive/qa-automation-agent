PLANNER_CUSTOM_TOOLS = [
    {
        'type': 'function',
        'function': {
            'name': 'planner_setup_page',
            'description': 'Navigate the browser to the target URL. MUST be called first.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'url': {'type': 'string'},
                },
                'required': ['url'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'planner_save_plan',
            'description': 'Save the completed markdown test plan to specs/plan.md. Call exactly once at the end.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'content': {'type': 'string'},
                },
                'required': ['content'],
            },
        },
    },
]
