from django.contrib import admin
from .models import (
    Employee, Salary, WorkLog, KPI, BonusRule, TaskBoard,
    TaskList, Task, Checklist, ChecklistItem, Comment, EmployeePerformanceRecord,
    ManualKpiEntry
)

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'hire_date')
    search_fields = ('name', 'email')

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

# --- Performance Management Admin ---

@admin.register(KPI)
class KPIAdmin(admin.ModelAdmin):
    list_display = ('name', 'measurement_type', 'target_value')
    list_filter = ('measurement_type',)
    search_fields = ('name', 'description')

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
    extra = 0
    readonly_fields = ('user', 'created_at')

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
