import os
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve

urlpatterns = [
    path('api/', include('core.urls')),
]

reports_root = os.path.join(settings.PLAYWRIGHT_PROJECT_ROOT, 'reports')
urlpatterns += [
    re_path(r'^reports/(?P<path>.*)$', serve, {'document_root': reports_root}),
]
