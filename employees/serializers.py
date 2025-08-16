from rest_framework import serializers
from .models import WorkLog

class WorkLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkLog
        fields = ['id', 'employee', 'date', 'hours_worked', 'overtime_hours']
