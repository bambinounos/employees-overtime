from rest_framework import viewsets
from .models import WorkLog
from .serializers import WorkLogSerializer

class WorkLogViewSet(viewsets.ModelViewSet):
    queryset = WorkLog.objects.all()
    serializer_class = WorkLogSerializer
