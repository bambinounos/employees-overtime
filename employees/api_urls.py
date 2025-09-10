from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import WorkLogViewSet, TaskBoardViewSet, TaskViewSet, kpi_history_api

router = DefaultRouter()
router.register(r'worklogs', WorkLogViewSet)
router.register(r'boards', TaskBoardViewSet)
router.register(r'tasks', TaskViewSet)


urlpatterns = [
    path('', include(router.urls)),
    path('employees/<int:employee_id>/kpi-history/', kpi_history_api, name='kpi_history_api'),
]
