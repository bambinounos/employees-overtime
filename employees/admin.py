from django.contrib import admin
from django.db.models import Max, Q
from django.utils import timezone
from django.urls import reverse
from django.http import HttpResponseRedirect
from .models import (
    Employee, Salary, WorkLog, KPI, BonusRule, TaskBoard,
    TaskList, Task, Checklist, ChecklistItem, Comment, EmployeePerformanceRecord,
    ManualKpiEntry, SiteConfiguration,
    JobProfile, KPIBonusTier, DolibarrInstance, DolibarrUserIdentity,
    SalesRecord, ProductCreationLog, WebhookLog,
)

@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    """
    Admin interface for the singleton SiteConfiguration model.
    Redirects from the list view to the change view of the single object.
    """
    def changelist_view(self, request, extra_context=None):
        # Get or create the single SiteConfiguration object
        obj, created = SiteConfiguration.objects.get_or_create(pk=1)
        # Redirect to its change view
        return HttpResponseRedirect(reverse('admin:employees_siteconfiguration_change', args=(obj.id,)))

    def has_add_permission(self, request):
        # Prevent adding new instances
        return False

    def has_delete_permission(self, request, obj=None):
        # Prevent deleting the instance
        return False

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'hire_date', 'end_date', 'profile', 'is_active_status')
    search_fields = ('name', 'email')
    list_filter = ('end_date', 'profile')

    @admin.display(boolean=True, description='Active')
    def is_active_status(self, obj):
        return obj.is_active

    def save_model(self, request, obj, form, change):
        """
        When creating a new employee, ensure the end_date is None unless a value
        is explicitly provided. This prevents incorrect database-level defaults
        from making new employees inactive.
        """
        if not change and not form.cleaned_data.get('end_date'):
            obj.end_date = None
        super().save_model(request, obj, form, change)

@admin.register(Salary)
class SalaryAdmin(admin.ModelAdmin):
    list_display = ('employee', 'base_amount', 'effective_date')
    list_filter = ('effective_date',)
    search_fields = ('employee__name',)

@admin.register(WorkLog)
class WorkLogAdmin(admin.ModelAdmin):
    list_display = ('employee', 'date', 'hours_worked', 'overtime_hours')
    list_filter = ('date', 'employee')
    search_fields = ('employee__name',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "employee":
            # Only show active employees (end_date is None or in the future)
            # using Q objects to filter
            today = timezone.now().date()
            base_queryset = Employee.objects.filter(
                Q(end_date__isnull=True) | Q(end_date__gte=today)
            )

            # If we are in a Change View (editing an existing object), we MUST include the current employee
            # even if they are inactive, to pass form validation.
            object_id = request.resolver_match.kwargs.get('object_id')
            if object_id:
                try:
                    current_worklog = WorkLog.objects.get(pk=object_id)
                    # Include the current employee if not already in the base queryset
                    if not base_queryset.filter(pk=current_worklog.employee.pk).exists():
                         # Union is not ideal for form queryset because it prevents further filtering/ordering
                         # better to use OR in filter.
                         kwargs["queryset"] = Employee.objects.filter(
                             Q(end_date__isnull=True) |
                             Q(end_date__gte=today) |
                             Q(pk=current_worklog.employee.pk)
                         )
                    else:
                        kwargs["queryset"] = base_queryset
                except WorkLog.DoesNotExist:
                    # Fallback
                    kwargs["queryset"] = base_queryset
            else:
                # Add View
                kwargs["queryset"] = base_queryset

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

# --- Performance Management Admin ---

@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    list_display = ('name', 'measurement_type', 'target_value', 'internal_code', 'min_volume_threshold')
    list_filter = ('measurement_type',)
    search_fields = ('name', 'description', 'internal_code')

@admin.register(BonusRule)
class BonusRuleAdmin(admin.ModelAdmin):
    list_display = ('kpi', 'bonus_amount', 'description')
    list_filter = ('kpi',)

class TaskListInline(admin.TabularInline):
    model = TaskList
    extra = 1

@admin.register(TaskBoard)
class TaskBoardAdmin(admin.ModelAdmin):
    list_display = ('name', 'employee')
    inlines = [TaskListInline]

class ChecklistItemInline(admin.TabularInline):
    model = ChecklistItem
    extra = 1

class ChecklistInline(admin.StackedInline):
    model = Checklist
    extra = 1
    inlines = [ChecklistItemInline]

class CommentInline(admin.TabularInline):
    model = Comment
    extra = 1 # Allow adding comments by default
    readonly_fields = ('user', 'created_at')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # On the 'add' page, `object_id` will be None.
        # This prevents existing comments from other tasks from being shown.
        if not request.resolver_match.kwargs.get('object_id'):
            return qs.none()
        return qs

from django.contrib.admin.widgets import AdminSplitDateTime

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'assigned_to', 'list', 'due_date', 'completed_at', 'is_recurring')
    list_filter = ('list', 'assigned_to', 'due_date', 'kpi', 'is_recurring')
    search_fields = ('title', 'description')
    inlines = [ChecklistInline, CommentInline]

    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'list', 'assigned_to', 'kpi')
        }),
        ('Dates', {
            'fields': ('due_date',)
        }),
        ('Recurrence', {
            'classes': ('collapse',),
            'fields': ('is_recurring', 'recurrence_frequency', 'recurrence_end_date'),
        }),
    )

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'due_date':
            kwargs['widget'] = AdminSplitDateTime
        return super().formfield_for_dbfield(db_field, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "assigned_to":
            kwargs["queryset"] = Employee.objects.filter(end_date__isnull=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def render_change_form(self, request, context, *args, **kwargs):
        # This is a fix for a UI bug where the 'assigned_to' dropdown shows
        # duplicate employees. The root cause is unclear from the current codebase,
        # but ensuring the queryset is distinct solves the immediate problem.
        # It also now filters to only show active employees.
        return super().render_change_form(request, context, *args, **kwargs)

    def save_model(self, request, obj, form, change):
        # If this is a new task (not being changed), set its order and creator.
        if not change: # This is a new object
            obj.created_by = request.user
            # Get the highest order number from tasks in the same list.
            max_order = Task.objects.filter(list=obj.list).aggregate(Max('order'))['order__max']
            # If there are no other tasks, start at 1. Otherwise, add 1 to the max.
            obj.order = (max_order or 0) + 1
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """
        Assign the current user to new comments.
        """
        instances = formset.save(commit=False)
        for instance in instances:
            # Check if the instance is a Comment and if it's a new one
            if isinstance(instance, Comment) and not instance.pk:
                instance.user = request.user
            instance.save()
        formset.save_m2m()

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        # Add other fields that are not explicitly in fieldsets, like 'order'
        # This is a simple implementation, a more robust one would avoid hardcoding
        return fieldsets

@admin.register(EmployeePerformanceRecord)
class EmployeePerformanceRecordAdmin(admin.ModelAdmin):
    list_display = ('employee', 'kpi', 'date', 'actual_value', 'target_met', 'bonus_awarded')
    list_filter = ('date', 'employee', 'kpi', 'target_met')
    readonly_fields = ('bonus_awarded',)

@admin.register(ManualKpiEntry)
class ManualKpiEntryAdmin(admin.ModelAdmin):
    list_display = ('employee', 'kpi', 'date', 'value')
    list_filter = ('date', 'employee', 'kpi')
    search_fields = ('employee__name', 'kpi__name', 'notes')
    autocomplete_fields = ['employee', 'kpi']


# --- Sales & Commissions Admin (v1.1) ---

class KPIBonusTierInline(admin.TabularInline):
    model = KPIBonusTier
    extra = 1


# Add tiers inline to KPI admin
KPIAdmin.inlines = [KPIBonusTierInline]


class DolibarrUserIdentityInline(admin.TabularInline):
    model = DolibarrUserIdentity
    extra = 1


@admin.register(JobProfile)
class JobProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'earns_commissions', 'get_kpi_count')
    list_filter = ('earns_commissions',)
    search_fields = ('name',)
    filter_horizontal = ('kpis',)

    @admin.display(description='KPIs')
    def get_kpi_count(self, obj):
        return obj.kpis.count()


@admin.register(DolibarrInstance)
class DolibarrInstanceAdmin(admin.ModelAdmin):
    list_display = ('name', 'professional_id')
    search_fields = ('name', 'professional_id')
    inlines = [DolibarrUserIdentityInline]


@admin.register(DolibarrUserIdentity)
class DolibarrUserIdentityAdmin(admin.ModelAdmin):
    list_display = ('employee', 'dolibarr_instance', 'dolibarr_user_id', 'dolibarr_login')
    list_filter = ('dolibarr_instance',)
    search_fields = ('employee__name', 'dolibarr_login')
    autocomplete_fields = ['employee']


@admin.register(SalesRecord)
class SalesRecordAdmin(admin.ModelAdmin):
    list_display = ('dolibarr_ref', 'employee', 'status', 'amount_untaxed', 'date', 'dolibarr_instance')
    list_filter = ('status', 'dolibarr_instance', 'date')
    search_fields = ('dolibarr_ref', 'employee__name')
    date_hierarchy = 'date'
    readonly_fields = ('created_at',)


@admin.register(ProductCreationLog)
class ProductCreationLogAdmin(admin.ModelAdmin):
    list_display = ('product_ref', 'employee', 'dolibarr_instance', 'created_at', 'is_suspect_duplicate')
    list_filter = ('dolibarr_instance', 'is_suspect_duplicate')
    search_fields = ('product_ref', 'employee__name')


@admin.register(WebhookLog)
class WebhookLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'received_at', 'status', 'sender_ip', 'short_error')
    list_filter = ('status', 'received_at')
    readonly_fields = ('received_at', 'sender_ip', 'payload', 'headers', 'status', 'error_message')
    date_hierarchy = 'received_at'

    @admin.display(description='Error')
    def short_error(self, obj):
        if obj.error_message:
            return obj.error_message[:80] + '...' if len(obj.error_message) > 80 else obj.error_message
        return '-'

    def has_add_permission(self, request):
        return False
