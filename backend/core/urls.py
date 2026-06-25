from django.urls import path

from .views import health, collections, environments, tests, executions

urlpatterns = [
    path('health', health.HealthView.as_view()),

    # --- Collections ---------------------------------------------------------
    path('collections', collections.CollectionListView.as_view()),
    path('collections/<str:pk>', collections.CollectionDetailView.as_view()),
    path('collections/<str:pk>/tests', collections.CollectionTestsView.as_view()),
    path('collections/<str:pk>/specs', collections.CollectionSpecsView.as_view()),
    path('collections/<str:pk>/run-all-specs', collections.CollectionRunSpecsView.as_view()),

    # --- Environments --------------------------------------------------------
    # active-publisher must precede <pk> or it would be captured as an id.
    path('environments', environments.EnvironmentListView.as_view()),
    path('environments/active-publisher', environments.EnvironmentPublisherView.as_view()),
    path('environments/<str:pk>', environments.EnvironmentDetailView.as_view()),

    # --- Tests ---------------------------------------------------------------
    path('tests/<str:pk>', tests.TestDetailView.as_view()),
    path('tests/<str:pk>/spec', tests.TestSpecView.as_view()),
    path('tests/<str:pk>/run-spec', tests.TestRunSpecView.as_view()),
    path('tests/<str:pk>/run', tests.TestRunView.as_view()),

    # --- Spec files (no resource id in the path) -----------------------------
    path('specs/view', tests.SpecReadView.as_view()),
    path('specs', tests.SpecDeleteView.as_view()),

    # --- Executions ----------------------------------------------------------
    path('executions', executions.ExecutionListView.as_view()),
    # Frontend posts here to start a run; reuses the TestRunView handler.
    path('executions/tests/<str:pk>/run', tests.TestRunView.as_view()),
    path('executions/<str:pk>', executions.ExecutionDetailView.as_view()),
    path('executions/<str:pk>/steps', executions.ExecutionStepsView.as_view()),
    path('executions/<str:pk>/tests', executions.ExecutionTestsView.as_view()),
    path('executions/<str:pk>/files', executions.ExecutionFilesView.as_view()),
    path('executions/<str:pk>/stream', executions.ExecutionStreamView.as_view()),
]
