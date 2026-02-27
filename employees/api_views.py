from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from .models import WorkLog, TaskBoard, Task, EmployeePerformanceRecord, Employee, DolibarrInstance, DolibarrUserIdentity, SalesRecord, WebhookLog, ProductCreationLog
from .serializers import WorkLogSerializer, TaskBoardSerializer, TaskSerializer
from datetime import date, datetime, timedelta
from collections import defaultdict
from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone
import hashlib
import hmac
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class WebhookRateThrottle(AnonRateThrottle):
    """Rate limiter for webhook endpoints: 60 requests/minute."""
    rate = '60/min'

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
        employee_id = self.request.query_params.get('employee_id')

        # Determine the base set of employees to check tasks for
        employees_to_check = []
        if user.is_superuser:
            if employee_id:
                # Superuser is viewing a specific employee's board
                try:
                    employees_to_check = [Employee.objects.get(pk=employee_id)]
                except Employee.DoesNotExist:
                    return Task.objects.none() # Return empty if employee not found
            else:
                # Superuser is viewing their own board or a general view
                 employees_to_check = Employee.objects.filter(end_date__isnull=True)
        elif hasattr(user, 'employee'):
            # Regular employee viewing their own board
            employees_to_check = [user.employee]


        # Generate recurring tasks that are due for the determined employees
        if employees_to_check:
             for employee in employees_to_check:
                parent_tasks = Task.objects.filter(
                    assigned_to=employee,
                    is_recurring=True,
                    recurrence_end_date__gte=timezone.now().date()
                )
                for parent in parent_tasks:
                    self.generate_missing_tasks(parent)


        # Filter the final queryset based on user permissions and employee_id
        base_queryset = Task.objects.filter(is_recurring=False)
        if user.is_superuser:
            if employee_id:
                return base_queryset.filter(assigned_to__id=employee_id)
            return base_queryset
        elif hasattr(user, 'employee'):
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

class DolibarrWebhookView(APIView):
    """
    Endpoint to receive webhooks from Dolibarr.
    Validates HMAC signature and processes sales/product events.
    Supports: BILL_VALIDATE (invoices & credit notes), PROPAL_VALIDATE, PRODUCT_CREATE.
    """
    permission_classes = [AllowAny]  # We use HMAC for auth
    throttle_classes = [WebhookRateThrottle]

    def post(self, request):
        # 1. Capture Raw Data for logging and verification
        try:
            body_unicode = request.body.decode('utf-8')
        except (UnicodeDecodeError, AttributeError):
            body_unicode = str(request.body)

        professional_id = request.headers.get('X-Dolibarr-Professional-ID')
        signature = request.headers.get('X-Dolibarr-Signature')

        # 2. Log reception immediately (audit trail per FEASIBILITY_REPORT)
        log = WebhookLog.objects.create(
            sender_ip=self.get_client_ip(request),
            headers=dict(request.headers),
            payload=request.data
        )

        try:
            # 3. Authenticate Instance
            if not professional_id or not signature:
                raise ValueError("Missing authentication headers: X-Dolibarr-Professional-ID and X-Dolibarr-Signature required")

            try:
                instance = DolibarrInstance.objects.get(professional_id=professional_id)
            except DolibarrInstance.DoesNotExist:
                raise ValueError(f"Unknown Dolibarr instance: professional_id={professional_id}")

            # 4. Validate HMAC-SHA256 signature
            computed_signature = hmac.new(
                key=instance.api_secret.encode('utf-8'),
                msg=request.body,
                digestmod=hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(computed_signature, signature):
                raise ValueError("Invalid HMAC signature")

            # 5. Process Event
            payload = request.data
            event_type = payload.get('trigger_code')

            if event_type == 'BILL_VALIDATE':
                self.process_bill_validate(payload, instance)
            elif event_type == 'PROPAL_VALIDATE':
                self.process_proforma(payload, instance)
            elif event_type == 'PRODUCT_CREATE':
                self.process_product_creation(payload, instance)
            else:
                logger.warning("Unknown trigger_code received: %s from instance %s", event_type, instance.name)

            log.status = 'processed'
            log.save()
            return Response({'status': 'ok'})

        except ValueError as e:
            log.status = 'error'
            log.error_message = str(e)
            log.save()
            logger.warning("Webhook validation error: %s", e)
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            log.status = 'error'
            log.error_message = str(e)
            log.save()
            logger.exception("Unexpected error processing webhook")
            return Response({'error': 'Internal processing error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def _resolve_employee(self, instance, dolibarr_user_id):
        """Resolve a Dolibarr user ID to a local Employee. Returns None if not mapped."""
        try:
            identity = DolibarrUserIdentity.objects.get(
                dolibarr_instance=instance,
                dolibarr_user_id=dolibarr_user_id
            )
            return identity.employee
        except DolibarrUserIdentity.DoesNotExist:
            logger.warning(
                "Employee not mapped for dolibarr_user_id=%s in instance '%s'. "
                "Admin should create a DolibarrUserIdentity mapping.",
                dolibarr_user_id, instance.name
            )
            return None

    @staticmethod
    def _parse_event_date(obj):
        """Extract the event date from the payload, falling back to today."""
        date_str = obj.get('date_validation') or obj.get('date_creation')
        if date_str:
            try:
                return datetime.strptime(str(date_str)[:10], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass
        return timezone.now().date()

    def process_bill_validate(self, payload, instance):
        """
        Process BILL_VALIDATE events.
        Distinguishes between regular invoices (type=0) and credit notes (type=2)
        per FEASIBILITY_REPORT section 2.1 events 2 & 3.
        """
        obj = payload.get('object', {})
        dolibarr_user_id = obj.get('fk_user_author')

        employee = self._resolve_employee(instance, dolibarr_user_id)
        if not employee:
            return

        event_date = self._parse_event_date(obj)
        bill_type = obj.get('type', 0)

        # type=2 in Dolibarr = Credit Note (Nota de Credito)
        if int(bill_type) == 2:
            # Credit notes: negative amount to deduct from commissions
            amount = obj.get('total_ht', 0)
            SalesRecord.objects.create(
                employee=employee,
                dolibarr_instance=instance,
                dolibarr_id=obj.get('id'),
                dolibarr_ref=obj.get('ref'),
                origin_proforma_id=obj.get('fk_propal'),
                status='credit_note',
                amount_untaxed=-abs(amount),  # Always negative for credit notes
                date=event_date,
            )
            logger.info("Credit note %s processed for employee %s", obj.get('ref'), employee.name)
        else:
            # Regular invoice
            SalesRecord.objects.create(
                employee=employee,
                dolibarr_instance=instance,
                dolibarr_id=obj.get('id'),
                dolibarr_ref=obj.get('ref'),
                origin_proforma_id=obj.get('fk_propal'),
                status='invoiced',
                amount_untaxed=obj.get('total_ht', 0),
                date=event_date,
            )

    def process_proforma(self, payload, instance):
        """Process PROPAL_VALIDATE events (proforma/proposal validated)."""
        obj = payload.get('object', {})
        dolibarr_user_id = obj.get('fk_user_author')

        employee = self._resolve_employee(instance, dolibarr_user_id)
        if not employee:
            return

        event_date = self._parse_event_date(obj)

        SalesRecord.objects.create(
            employee=employee,
            dolibarr_instance=instance,
            dolibarr_id=obj.get('id'),
            dolibarr_ref=obj.get('ref'),
            status='proforma',
            amount_untaxed=obj.get('total_ht', 0),
            date=event_date,
        )

    def process_product_creation(self, payload, instance):
        """
        Process PRODUCT_CREATE events with anti-fraud SKU validation.
        Per FEASIBILITY_REPORT section 3.2.C.4: If a product with the same SKU
        was already created this month in this instance, the new entry is marked
        as a suspected duplicate (not eligible for bonus).
        """
        obj = payload.get('object', {})
        dolibarr_user_id = obj.get('fk_user_author')

        employee = self._resolve_employee(instance, dolibarr_user_id)
        if not employee:
            return

        product_ref = obj.get('ref', '')
        now = timezone.now()

        # Anti-fraud: check for same SKU created this month in this instance
        duplicate_sku = ProductCreationLog.objects.filter(
            dolibarr_instance=instance,
            product_ref=product_ref,
            created_at__year=now.year,
            created_at__month=now.month,
        ).exists()

        log_entry = ProductCreationLog.objects.create(
            employee=employee,
            dolibarr_instance=instance,
            dolibarr_product_id=obj.get('id'),
            product_ref=product_ref,
            created_at=now,
            is_suspect_duplicate=duplicate_sku,
        )

        if duplicate_sku:
            logger.warning(
                "Suspect duplicate product creation: SKU '%s' already exists this month "
                "in instance '%s'. Log ID: %s",
                product_ref, instance.name, log_entry.pk
            )
