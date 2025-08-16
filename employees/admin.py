from django.contrib import admin
from .models import Employee, Salary, WorkLog

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
