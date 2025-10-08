from rest_framework import serializers
from .models import Employee, WorkLog, Task, TaskList, TaskBoard, Checklist, ChecklistItem
from datetime import date, timedelta, datetime


class ChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistItem
        fields = ['id', 'text', 'is_completed']

class ChecklistSerializer(serializers.ModelSerializer):
    items = ChecklistItemSerializer(many=True, read_only=True)

    class Meta:
        model = Checklist
        fields = ['id', 'title', 'items']

class TaskSerializer(serializers.ModelSerializer):
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.filter(end_date__isnull=True)
    )
    checklists = ChecklistSerializer(many=True, read_only=True)
    due_date_status = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'order', 'due_date', 'status', 'list', 'assigned_to',
            'is_recurring', 'recurrence_frequency', 'recurrence_end_date', 'parent_task',
            'checklists', 'due_date_status'
        ]
        read_only_fields = ('parent_task',)

    def get_due_date_status(self, obj):
        if not obj.due_date:
            return 'a_tiempo' # Or 'sin_fecha' if you want to handle it differently

        # Ensure we are comparing date objects, not datetime
        # obj.due_date might be a datetime object
        due_date = obj.due_date
        if isinstance(due_date, datetime):
            due_date = due_date.date()

        today = date.today()
        if due_date < today:
            return 'vencido'
        elif due_date <= today + timedelta(days=3):
            return 'por_vencer'
        else:
            return 'a_tiempo'

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
