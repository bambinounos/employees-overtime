from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from .models import WorkLog, TaskBoard, Task, EmployeePerformanceRecord, Employee
from .serializers import WorkLogSerializer, TaskBoardSerializer, TaskSerializer
from datetime import date, timedelta
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone

class WorkLogViewSet(viewsets.ModelViewSet):
    queryset = WorkLog.objects.all()
    serializer_class = WorkLogSerializer

class TaskBoardViewSet(viewsets.ReadOnlyModelViewSet):
    """A viewset for viewing task boards."""
    queryset = TaskBoard.objects.all()
    serializer_class = TaskBoardSerializer

    def get_queryset(self):
        """
        This view should return the board for the currently authenticated user.
        """
        user = self.request.user
        if hasattr(user, 'employee'):
            return TaskBoard.objects.filter(employee=user.employee)
        return TaskBoard.objects.none()

class TaskViewSet(viewsets.ModelViewSet):
    """A viewset for viewing and editing tasks."""
    queryset = Task.objects.all()
    serializer_class = TaskSerializer

    def get_queryset(self):
        """
        This view should return a list of all the tasks
        for the currently authenticated user, excluding recurring templates.
        If the user is a superuser, it should return all tasks (excluding templates).
        Before returning, it checks for and generates any overdue recurring task instances.
        """
        user = self.request.user

        # Determine the base set of employees to check tasks for
        if user.is_superuser:
            employees = Employee.objects.all()
        elif hasattr(user, 'employee'):
            employees = Employee.objects.filter(pk=user.employee.pk)
        else:
            return Task.objects.none()

        # Generate recurring tasks that are due
        for employee in employees:
            parent_tasks = Task.objects.filter(
                assigned_to=employee,
                is_recurring=True,
                recurrence_end_date__gte=timezone.now().date()
            )
            for parent in parent_tasks:
                self.generate_missing_tasks(parent)

        # Return the visible tasks (non-templates) for the user
        base_queryset = Task.objects.filter(is_recurring=False)
        if user.is_superuser:
            return base_queryset
        if hasattr(user, 'employee'):
            return base_queryset.filter(assigned_to=user.employee)
        return Task.objects.none()

    def generate_missing_tasks(self, parent_task):
        """
        Generates instances for a recurring task that are due but not yet created.
        This process is idempotent; it will not create duplicate tasks for the same day.
        """
        last_instance = Task.objects.filter(parent_task=parent_task).order_by('-due_date').first()

        # Determine the date to start generating tasks from.
        if last_instance:
            start_date = timezone.localtime(last_instance.due_date).date()
        else:
            # If no instances exist, start from the parent's due date. To ensure the first
            # task is created by the loop, we set the start date to the day before.
            start_date = timezone.localtime(parent_task.due_date).date() - timedelta(days=1)

        # Determine the time from the parent task's due date
        due_time = parent_task.due_date.time()

        # Loop to generate missing tasks until today.
        next_date = start_date
        while True:
            # Calculate the next theoretical due date.
            if parent_task.recurrence_frequency == 'daily':
                next_date += timedelta(days=1)
            elif parent_task.recurrence_frequency == 'weekly':
                next_date += timedelta(weeks=1)
            elif parent_task.recurrence_frequency == 'monthly':
                next_date += relativedelta(months=1)
            elif parent_task.recurrence_frequency == 'yearly':
                next_date += relativedelta(years=1)
            else:
                break  # Should not happen

            # Stop if the next date is in the future or after the end date.
            if next_date > timezone.now().date() or next_date > parent_task.recurrence_end_date:
                break

            # Combine date and time to get the final due datetime.
            # This requires making the naive datetime object timezone-aware.
            from datetime import datetime
            naive_datetime = datetime.combine(next_date, due_time)
            due_datetime = timezone.make_aware(naive_datetime)

            # Idempotency check: only create the task if one for that day doesn't exist.
            if not Task.objects.filter(parent_task=parent_task, due_date__date=due_datetime.date()).exists():
                Task.objects.create(
                    parent_task=parent_task,
                    list=parent_task.list,
                    assigned_to=parent_task.assigned_to,
                    created_by=parent_task.created_by,
                    kpi=parent_task.kpi,
                    title=f"{parent_task.title} - {next_date.strftime('%Y-%m-%d')}",
                    description=parent_task.description,
                    order=parent_task.order,
                    due_date=due_datetime,
                    is_recurring=False
                )

    def create(self, request, *args, **kwargs):
        """
        Overrides the create method to handle recurring tasks.
        If a task is marked as recurring, it creates a parent "template" task
        and then generates a series of individual child tasks.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        is_recurring = serializer.validated_data.get('is_recurring', False)

        if not is_recurring:
            # Default behavior: create a single task
            serializer.save(created_by=request.user)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

        # Recurring task logic
        try:
            with transaction.atomic():
                # 1. Create the parent "template" task
                parent_task = serializer.save(created_by=request.user)
                # 2. Generate the first visible task instance
                if parent_task.due_date and parent_task.recurrence_end_date and parent_task.due_date.date() <= parent_task.recurrence_end_date:
                    Task.objects.create(
                        parent_task=parent_task,
                        list=parent_task.list,
                        assigned_to=parent_task.assigned_to,
                        created_by=request.user,
                        kpi=parent_task.kpi,
                        title=f"{parent_task.title} - {parent_task.due_date.strftime('%Y-%m-%d')}",
                        description=parent_task.description,
                        order=parent_task.order,
                        due_date=parent_task.due_date,
                        is_recurring=False  # Child tasks are not recurring themselves
                    )
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=True, methods=['post'])
    def move(self, request, pk=None):
        """Move a task to a new list and/or new order."""
        task = self.get_object()
        new_list_id = request.data.get('list_id')
        new_order = request.data.get('order')

        if new_list_id is None or new_order is None:
            return Response(
                {"error": "list_id and order are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            from .models import TaskList
            from datetime import datetime

            new_list = TaskList.objects.get(id=new_list_id)
            task.list = new_list
            task.order = new_order

            if new_list.name.lower() == 'hecho':
                task.completed_at = timezone.now()
                task.status = 'completed'

            task.save()
            return Response({'status': 'task moved'})
        except TaskList.DoesNotExist:
            return Response({'error': 'List not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def mark_as_complete(self, request, pk=None):
        """
        Mark a task as complete. If it's a recurring task, generate the next one.
        """
        task = self.get_object()

        # Only superusers can mark tasks as complete.
        if not request.user.is_superuser:
            return Response({"error": "You do not have permission to perform this action."}, status=status.HTTP_403_FORBIDDEN)

        from datetime import datetime
        from .models import TaskList

        with transaction.atomic():
            task.status = 'completed'
            task.completed_at = timezone.now()
            task.save()

            # Recalculate bonus for the affected employee
            try:
                employee = task.assigned_to
                today = timezone.now().date()
                employee.calculate_performance_bonus(today.year, today.month)
            except Employee.DoesNotExist:
                pass

        return Response({'status': 'task marked as complete', 'task': self.get_serializer(task).data})

    @action(detail=True, methods=['post'])
    def mark_as_unfulfilled(self, request, pk=None):
        """Mark a task as unfulfilled and move it to the 'Pendiente' list."""
        task = self.get_object()

        # Only superusers can mark tasks as un-fulfilled.
        if not request.user.is_superuser:
            return Response({"error": "You do not have permission to perform this action."}, status=status.HTTP_403_FORBIDDEN)

        from .models import TaskList
        task.status = 'unfulfilled'
        task.completed_at = None  # Also clear the completion date

        # Move the task back to the "Pendiente" list
        try:
            board = task.list.board
            pending_list = board.lists.get(name__iexact="Pendiente")
            task.list = pending_list
        except TaskList.DoesNotExist:
            # If for some reason the list doesn't exist, we can't move it,
            # but we should still save the status change.
            pass

        task.save()

        # Recalculate bonus for the affected employee
        try:
            employee = task.assigned_to
            today = timezone.now().date()
            employee.calculate_performance_bonus(today.year, today.month)
        except Employee.DoesNotExist:
            pass

        return Response({'status': 'task marked as unfulfilled'})

@api_view(['GET'])
def kpi_history_api(request, employee_id):
    """
    API endpoint to retrieve the last 12 months of KPI performance data for a specific employee.
    """
    try:
        employee = Employee.objects.get(pk=employee_id)
    except Employee.DoesNotExist:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

    # Calculate the date 12 months ago from the first day of the current month
    today = timezone.now().date()
    twelve_months_ago = (today.replace(day=1) - timedelta(days=1)).replace(day=1) - timedelta(days=365)


    records = EmployeePerformanceRecord.objects.filter(
        employee=employee,
        date__gte=twelve_months_ago
    ).order_by('date').select_related('kpi')

    # Group data by KPI name
    kpi_data = defaultdict(lambda: {'labels': [], 'data': []})
    for record in records:
        kpi_name = record.kpi.name
        # Format date as 'YYYY-Mon' (e.g., '2023-Sep')
        month_label = record.date.strftime('%Y-%b')
        kpi_data[kpi_name]['labels'].append(month_label)
        kpi_data[kpi_name]['data'].append(record.actual_value)

    return Response(kpi_data)
