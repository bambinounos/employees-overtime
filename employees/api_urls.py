from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import WorkLogViewSet, TaskBoardViewSet, TaskViewSet

router = DefaultRouter()
router.register(r'worklogs', WorkLogViewSet)
router.register(r'boards', TaskBoardViewSet)
router.register(r'tasks', TaskViewSet)


urlpatterns = [
    path('', include(router.urls)),
]
