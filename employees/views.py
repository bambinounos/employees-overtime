from django.shortcuts import render
from .models import Employee, WorkLog
from django.contrib.auth.decorators import login_required
from datetime import date

def index(request):
    """Renders the home page."""
    return render(request, 'employees/index.html')

@login_required
def employee_list(request):
    """Renders the employee list page."""
    employees = Employee.objects.all()
    context = {'employees': employees}
    return render(request, 'employees/employee_list.html', context)

@login_required
def employee_calendar(request, employee_id):
    """Renders the calendar for a specific employee."""
    employee = Employee.objects.get(pk=employee_id)
    work_logs = WorkLog.objects.filter(employee=employee)

    events = []
    for log in work_logs:
        event = {
            'id': log.id,
            'startDate': log.date.strftime('%Y-%m-%d'),
            'endDate': log.date.strftime('%Y-%m-%d'),
            'name': f"Worked: {log.hours_worked}h, Overtime: {log.overtime_hours}h"
        }
        events.append(event)

    context = {
        'employee': employee,
        'events': events,
    }
    return render(request, 'employees/employee_calendar.html', context)

@login_required
def employee_salary(request, employee_id):
    """Renders the salary calculation page for a specific employee."""
    employee = Employee.objects.get(pk=employee_id)

    today = date.today()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    salary = employee.calculate_salary(year, month)

    context = {
        'employee': employee,
        'year': year,
        'month': month,
        'salary': salary,
    }
    return render(request, 'employees/employee_salary.html', context)
