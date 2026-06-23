from django.urls import path
from .views import health, collections, environments, tests, executions

urlpatterns = [
    # Health
    path('health', health.health_check),

    # Collections
    path('collections', collections.CollectionListCreate.as_view()),
    path('collections/<str:id>', collections.CollectionDelete.as_view()),

    # Environments
    path('environments', environments.EnvironmentListCreate.as_view()),
    path('environments/active-publisher', environments.ActivePublisher.as_view()),
    path('environments/<str:id>', environments.EnvironmentUpdateDelete.as_view()),

    # Specs
    path('collections/<str:collection_id>/specs', tests.collection_specs),
    path('specs/view', tests.view_spec),
    path('specs', tests.delete_spec),

    # Tests
    path('collections/<str:collection_id>/tests', tests.CollectionTests.as_view()),
    path('tests/<str:id>', tests.TestDetail.as_view()),
    path('tests/<str:id>/spec', tests.TestSpec.as_view()),
    path('tests/<str:id>/run-spec', tests.run_spec),

    # Execution run endpoints (must be before executions/<str:id> to avoid shadowing)
    path('collections/<str:collection_id>/run-all-specs', executions.run_all_specs),
    path('executions/tests/<str:test_id>/run', executions.run_test),

    # Execution CRUD
    path('executions', executions.ExecutionList.as_view()),
    path('executions/<str:id>', executions.ExecutionDetail.as_view()),
    path('executions/<str:id>/steps', executions.execution_steps),
    path('executions/<str:id>/tests', executions.execution_tests),
    path('executions/<str:id>/stream', executions.execution_stream),
]
