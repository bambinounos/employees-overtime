from rest_framework import serializers
from .models import WorkLog, Task, TaskList, TaskBoard

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'order', 'due_date', 'list',
            'is_recurring', 'recurrence_frequency', 'recurrence_end_date'
        ]

class TaskListSerializer(serializers.ModelSerializer):
    tasks = TaskSerializer(many=True, read_only=True)

    class Meta:
        model = TaskList
        fields = ['id', 'name', 'order', 'tasks']

class TaskBoardSerializer(serializers.ModelSerializer):
    lists = TaskListSerializer(many=True, read_only=True)

    class Meta:
        model = TaskBoard
        fields = ['id', 'name', 'employee', 'lists']

class WorkLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkLog
        fields = ['id', 'employee', 'date', 'hours_worked', 'overtime_hours']
