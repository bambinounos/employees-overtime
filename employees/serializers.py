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
            'is_recurring', 'recurrence_frequency', 'recurrence_end_date', 'parent_task'
        ]
        read_only_fields = ('parent_task',)

    def validate(self, data):
        """
        Check that the selected list belongs to the assigned employee.
        Also, validate recurrence fields.
        """
        task_list = data.get('list')
        assigned_to = data.get('assigned_to')

        if task_list and assigned_to:
            if task_list.board.employee != assigned_to:
                raise serializers.ValidationError(
                    {'list': 'The selected list does not belong to the assigned employee.'}
                )

        if data.get('is_recurring'):
            if not data.get('recurrence_frequency'):
                raise serializers.ValidationError({
                    'recurrence_frequency': 'La frecuencia de recurrencia es obligatoria para las tareas recurrentes.'
                })
            if not data.get('recurrence_end_date'):
                raise serializers.ValidationError({
                    'recurrence_end_date': 'La fecha de finalización de la recurrencia es obligatoria para las tareas recurrentes.'
                })

        return data

class TaskListSerializer(serializers.ModelSerializer):
    tasks = serializers.SerializerMethodField()

    class Meta:
        model = TaskList
        fields = ['id', 'name', 'order', 'tasks']

    def get_tasks(self, obj):
        # Exclude recurring "template" tasks from the board, only show instances
        tasks = obj.tasks.filter(is_recurring=False)
        serializer = TaskSerializer(tasks, many=True)
        return serializer.data

class TaskBoardSerializer(serializers.ModelSerializer):
    lists = TaskListSerializer(many=True, read_only=True)

    class Meta:
        model = TaskBoard
        fields = ['id', 'name', 'employee', 'lists']

class WorkLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkLog
        fields = ['id', 'employee', 'date', 'hours_worked', 'overtime_hours']
