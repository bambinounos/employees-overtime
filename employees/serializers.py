from rest_framework import serializers
from .models import Employee, WorkLog, Task, TaskList, TaskBoard


class TaskSerializer(serializers.ModelSerializer):
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.filter(end_date__isnull=True)
    )

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'order', 'due_date', 'status', 'list', 'assigned_to',
            'is_recurring', 'recurrence_frequency', 'recurrence_end_date'
        ]

    def validate(self, data):
        """
        Check that the selected list belongs to the assigned employee.
        """
        task_list = data.get('list')
        assigned_to = data.get('assigned_to')

        if task_list and assigned_to:
            if task_list.board.employee != assigned_to:
                raise serializers.ValidationError(
                    {'list': 'The selected list does not belong to the assigned employee.'}
                )
        return data

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
