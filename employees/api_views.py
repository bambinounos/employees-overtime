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
from django.db.models import Q
from django.utils import timezone
import hashlib
import hmac
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class WebhookRateThrottle(AnonRateThrottle):
    """Rate limiter for webhook endpoints. Applied manually AFTER logging,
    not via throttle_classes, to ensure all requests are logged."""
    rate = '300/min'

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
                 employees_to_check = Employee.objects.filter(Q(end_date__isnull=True) | Q(end_date__gte=date.today()))
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

        # Determine the time from the parent task's due date (localized to avoid UTC drift)
        due_time = timezone.localtime(parent_task.due_date).time()

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
            if next_date > timezone.now().date() or (parent_task.recurrence_end_date and next_date > parent_task.recurrence_end_date):
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
    twelve_months_ago = today.replace(day=1) - relativedelta(months=12)


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
    throttle_classes = []  # Throttle applied manually AFTER logging

    def post(self, request):
        # 1. Capture Raw Data for logging and verification
        try:
            body_unicode = request.body.decode('utf-8')
        except (UnicodeDecodeError, AttributeError):
            body_unicode = str(request.body)

        professional_id = request.headers.get('X-Dolibarr-Professional-ID')
        signature = request.headers.get('X-Dolibarr-Signature')

        # 2. Log reception immediately — BEFORE throttle check so no data is lost
        log = WebhookLog.objects.create(
            sender_ip=self.get_client_ip(request),
            headers=dict(request.headers),
            payload=request.data
        )

        # 3. Manual throttle check AFTER logging
        throttle = WebhookRateThrottle()
        if not throttle.allow_request(request, self):
            log.status = 'throttled'
            log.error_message = 'Rate limit exceeded (logged for retry)'
            log.save()
            wait = throttle.wait()
            return Response(
                {'error': 'Rate limit exceeded', 'retry_after': int(wait or 60)},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={'Retry-After': str(int(wait or 60))}
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

            if event_type == 'TEST_CONNECTION':
                log.status = 'processed'
                log.save()
                logger.info("Test connection successful from instance '%s'", instance.name)
                return Response({
                    'status': 'ok',
                    'message': 'Connection verified',
                    'instance': instance.name,
                    'timestamp': timezone.now().isoformat(),
                })
            elif event_type == 'BILL_VALIDATE':
                self.process_bill_validate(payload, instance)
            elif event_type == 'PROPAL_VALIDATE':
                self.process_proforma(payload, instance)
            elif event_type == 'ORDER_VALIDATE':
                self.process_order(payload, instance)
            elif event_type == 'PAYMENT_CUSTOMER_CREATE':
                self.process_payment(payload, instance)
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

    @staticmethod
    def _validate_int(value, field_name, allow_zero=False):
        """Validate and return a positive integer from webhook payload."""
        if value is None:
            return None
        try:
            result = int(value)
            if not allow_zero and result <= 0:
                logger.warning("Invalid %s: must be positive, got %s", field_name, result)
                return None
            if allow_zero and result < 0:
                logger.warning("Invalid %s: must be non-negative, got %s", field_name, result)
                return None
            return result
        except (ValueError, TypeError):
            logger.warning("Invalid %s: not a number, got %s", field_name, value)
            return None

    @staticmethod
    def _validate_amount(value, field_name):
        """Validate and return a Decimal amount from webhook payload."""
        try:
            from decimal import Decimal, InvalidOperation
            result = Decimal(str(value))
            if abs(result) > Decimal('99999999.99'):
                logger.warning("Suspicious %s: value too large: %s", field_name, result)
                return None
            return result
        except (InvalidOperation, ValueError, TypeError):
            logger.warning("Invalid %s: not a valid amount, got %s", field_name, value)
            return None

    def process_bill_validate(self, payload, instance):
        """
        Process BILL_VALIDATE events.

        Rules:
        - Invoice must have an order or proforma by the same employee.
        - Invoices without order or proforma are rejected (not a valid workflow).
        - Credit notes: attributed to the employee who made the original invoice.
        """
        obj = payload.get('object', {})

        # Validate inputs
        dolibarr_id = self._validate_int(obj.get('id'), 'dolibarr_id')
        if not dolibarr_id:
            return
        dolibarr_user_id = self._validate_int(obj.get('fk_user_author'), 'fk_user_author')
        if not dolibarr_user_id:
            return
        amount = self._validate_amount(obj.get('total_ht', 0), 'total_ht')
        if amount is None:
            return

        event_date = self._parse_event_date(obj)
        bill_type = self._validate_int(obj.get('type', 0), 'type', allow_zero=True) or 0
        dolibarr_ref = str(obj.get('ref', ''))[:100]
        origin_proforma_id = self._validate_int(obj.get('fk_propal'), 'fk_propal')
        origin_order_id = self._validate_int(obj.get('fk_commande'), 'fk_commande')

        if bill_type == 2:
            # --- CREDIT NOTE ---
            # Attribute to the employee who made the ORIGINAL invoice
            fk_facture_source = self._validate_int(obj.get('fk_facture_source'), 'fk_facture_source')
            original_invoice = None

            if fk_facture_source:
                original_invoice = SalesRecord.objects.filter(
                    dolibarr_instance=instance,
                    dolibarr_id=fk_facture_source,
                    status='invoiced',
                ).first()
            if not original_invoice and origin_proforma_id:
                original_invoice = SalesRecord.objects.filter(
                    dolibarr_instance=instance,
                    dolibarr_id=origin_proforma_id,
                    status='invoiced',
                ).first()

            if original_invoice:
                target_employee = original_invoice.employee
            else:
                target_employee = self._resolve_employee(instance, dolibarr_user_id)
                if not target_employee:
                    return
                logger.warning(
                    "Credit note %s: could not find original invoice, "
                    "attributing to issuer %s", dolibarr_ref, target_employee.name
                )

            # Credit notes must be negative
            SalesRecord.objects.create(
                employee=target_employee,
                dolibarr_instance=instance,
                dolibarr_id=dolibarr_id,
                dolibarr_ref=dolibarr_ref,
                origin_proforma_id=origin_proforma_id,
                origin_order_id=origin_order_id,
                status='credit_note',
                amount_untaxed=-abs(amount),
                date=event_date,
            )
            logger.info("Credit note %s attributed to employee %s", dolibarr_ref, target_employee.name)
        else:
            # --- REGULAR INVOICE ---
            employee = self._resolve_employee(instance, dolibarr_user_id)
            if not employee:
                return

            # Invoice must have originated from a proforma or order by the same employee
            origin_validated = False

            # Check proforma ownership
            if origin_proforma_id:
                proforma_record = SalesRecord.objects.filter(
                    dolibarr_instance=instance,
                    dolibarr_id=origin_proforma_id,
                    status='proforma',
                ).first()
                if proforma_record:
                    if proforma_record.employee_id != employee.pk:
                        logger.warning(
                            "Invoice %s by %s rejected: proforma belongs to %s",
                            dolibarr_ref, employee.name, proforma_record.employee.name
                        )
                        return
                    origin_validated = True

            # Check order ownership (Pedido → Factura flow)
            if not origin_validated and origin_order_id:
                order_record = SalesRecord.objects.filter(
                    dolibarr_instance=instance,
                    dolibarr_id=origin_order_id,
                    status='order',
                ).first()
                if order_record:
                    if order_record.employee_id != employee.pk:
                        logger.warning(
                            "Invoice %s by %s rejected: order belongs to %s",
                            dolibarr_ref, employee.name, order_record.employee.name
                        )
                        return
                    origin_validated = True

            # Reject invoices without proforma or order (not a valid workflow)
            if not origin_validated:
                logger.warning(
                    "Invoice %s by %s rejected: no proforma or order found. "
                    "Direct invoices are not allowed.",
                    dolibarr_ref, employee.name
                )
                return

            # Invoice amount must be positive
            if amount < 0:
                logger.warning(
                    "Invoice %s rejected: negative amount %s", dolibarr_ref, amount
                )
                return

            SalesRecord.objects.create(
                employee=employee,
                dolibarr_instance=instance,
                dolibarr_id=dolibarr_id,
                dolibarr_ref=dolibarr_ref,
                origin_proforma_id=origin_proforma_id,
                origin_order_id=origin_order_id,
                status='invoiced',
                amount_untaxed=amount,
                date=event_date,
            )

    def process_proforma(self, payload, instance):
        """Process PROPAL_VALIDATE events."""
        obj = payload.get('object', {})
        dolibarr_id = self._validate_int(obj.get('id'), 'dolibarr_id')
        dolibarr_user_id = self._validate_int(obj.get('fk_user_author'), 'fk_user_author')
        if not dolibarr_id or not dolibarr_user_id:
            return

        employee = self._resolve_employee(instance, dolibarr_user_id)
        if not employee:
            return

        amount = self._validate_amount(obj.get('total_ht', 0), 'total_ht')
        if amount is None:
            return

        SalesRecord.objects.create(
            employee=employee,
            dolibarr_instance=instance,
            dolibarr_id=dolibarr_id,
            dolibarr_ref=str(obj.get('ref', ''))[:100],
            status='proforma',
            amount_untaxed=amount,
            date=self._parse_event_date(obj),
        )

    def process_order(self, payload, instance):
        """Process ORDER_VALIDATE events (pedido validated)."""
        obj = payload.get('object', {})
        dolibarr_id = self._validate_int(obj.get('id'), 'dolibarr_id')
        dolibarr_user_id = self._validate_int(obj.get('fk_user_author'), 'fk_user_author')
        if not dolibarr_id or not dolibarr_user_id:
            return

        employee = self._resolve_employee(instance, dolibarr_user_id)
        if not employee:
            return

        amount = self._validate_amount(obj.get('total_ht', 0), 'total_ht')
        if amount is None:
            return

        origin_proforma_id = self._validate_int(obj.get('fk_propal'), 'fk_propal')

        # Same-user validation: if order has a proforma, must be same employee
        if origin_proforma_id:
            proforma_record = SalesRecord.objects.filter(
                dolibarr_instance=instance,
                dolibarr_id=origin_proforma_id,
                status='proforma',
            ).first()
            if proforma_record and proforma_record.employee_id != employee.pk:
                logger.warning(
                    "Order %s by %s rejected: proforma belongs to %s",
                    obj.get('ref'), employee.name, proforma_record.employee.name
                )
                return

        SalesRecord.objects.create(
            employee=employee,
            dolibarr_instance=instance,
            dolibarr_id=dolibarr_id,
            dolibarr_ref=str(obj.get('ref', ''))[:100],
            origin_proforma_id=origin_proforma_id,
            status='order',
            amount_untaxed=amount,
            date=self._parse_event_date(obj),
        )

    def process_product_creation(self, payload, instance):
        """
        Process PRODUCT_CREATE events with anti-fraud SKU validation.
        Duplicates are flagged and excluded from bonus calculations.
        """
        obj = payload.get('object', {})
        dolibarr_user_id = self._validate_int(obj.get('fk_user_author'), 'fk_user_author')
        dolibarr_product_id = self._validate_int(obj.get('id'), 'dolibarr_product_id')
        if not dolibarr_user_id or not dolibarr_product_id:
            return

        employee = self._resolve_employee(instance, dolibarr_user_id)
        if not employee:
            return

        product_ref = str(obj.get('ref', '')).strip()[:255]
        if not product_ref:
            logger.warning("Product creation rejected: empty product_ref")
            return

        # Use Dolibarr event date, not Django receipt time (avoids month-boundary errors)
        event_date = self._parse_event_date(obj)
        event_datetime = timezone.make_aware(
            datetime.combine(event_date, timezone.now().time())
        )

        # Anti-fraud: check for same SKU created this month in this instance
        duplicate_sku = ProductCreationLog.objects.filter(
            dolibarr_instance=instance,
            product_ref=product_ref,
            created_at__year=event_date.year,
            created_at__month=event_date.month,
        ).exists()

        log_entry = ProductCreationLog.objects.create(
            employee=employee,
            dolibarr_instance=instance,
            dolibarr_product_id=dolibarr_product_id,
            product_ref=product_ref,
            created_at=event_datetime,
            is_suspect_duplicate=duplicate_sku,
        )

        if duplicate_sku:
            logger.warning(
                "Suspect duplicate product creation: SKU '%s' already exists this month "
                "in instance '%s'. Log ID: %s",
                product_ref, instance.name, log_entry.pk
            )

    def process_payment(self, payload, instance):
        """
        Process PAYMENT_CUSTOMER_CREATE events.
        Updates payment_date on matching SalesRecords (invoices).
        """
        obj = payload.get('object', {})
        invoice_ids = obj.get('invoice_ids', [])
        payment_date_str = obj.get('date_payment')

        if not isinstance(invoice_ids, list):
            logger.warning("invoice_ids is not a list: %s", type(invoice_ids))
            return

        today = timezone.now().date()
        payment_date = today
        if payment_date_str:
            try:
                parsed = datetime.strptime(str(payment_date_str)[:10], '%Y-%m-%d').date()
                if parsed > today:
                    logger.warning("Payment date in the future (%s), using today", parsed)
                elif parsed < date(2020, 1, 1):
                    logger.warning("Payment date too old (%s), using today", parsed)
                else:
                    payment_date = parsed
            except (ValueError, TypeError):
                pass  # keep today as default

        updated = 0
        for inv_id in invoice_ids:
            validated_id = self._validate_int(inv_id, 'invoice_id')
            if not validated_id:
                continue
            count = SalesRecord.objects.filter(
                dolibarr_instance=instance,
                dolibarr_id=validated_id,
                status='invoiced',
                payment_date__isnull=True,
            ).update(payment_date=payment_date)
            updated += count

        logger.info(
            "Payment processed: %d invoice(s) marked as paid in instance '%s'",
            updated, instance.name
        )
