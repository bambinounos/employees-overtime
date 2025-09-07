import csv
from django.http import HttpResponse
from django.shortcuts import render, redirect
from .models import Employee, WorkLog, TaskBoard, EmployeePerformanceRecord, CompanySettings
from django.contrib.auth.decorators import login_required
from datetime import date
from decimal import Decimal
from django.contrib import messages
import calendar

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

@login_required
def task_board(request):
    """Renders the task board for the logged-in employee."""
    try:
        employee = request.user.employee
        # Get or create a board for the employee to ensure one always exists.
        board, created = TaskBoard.objects.get_or_create(
            employee=employee,
            defaults={'name': f"Tablero de {employee.name}"}
        )
        # If the board is newly created, add some default lists.
        if created:
            from .models import TaskList
            TaskList.objects.create(board=board, name="Pendiente", order=1)
            TaskList.objects.create(board=board, name="En Progreso", order=2)
            TaskList.objects.create(board=board, name="Hecho", order=3)

    except Employee.DoesNotExist:
        # Handle case where the user is not linked to an employee profile
        board = None

    context = {
        'board': board,
    }
    return render(request, 'employees/task_board.html', context)

@login_required
def performance_report(request):
    """
    Renders the performance report page or handles CSV export.
    """
    all_employees = Employee.objects.all()
    selected_employee_id = request.GET.get('employee_id')

    records = None
    if selected_employee_id:
        records = EmployeePerformanceRecord.objects.filter(
            employee_id=selected_employee_id
        ).order_by('-date', 'kpi__name').select_related('employee', 'kpi')

        # Check if a CSV export is requested
        if request.GET.get('format') == 'csv':
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="performance_report_{selected_employee_id}.csv"'

            writer = csv.writer(response)
            writer.writerow(['Period', 'KPI', 'Result', 'Target Met', 'Bonus Awarded'])
            for record in records:
                writer.writerow([
                    record.date.strftime('%Y-%m'),
                    record.kpi.name,
                    record.actual_value,
                    'Yes' if record.target_met else 'No',
                    record.bonus_awarded
                ])
            return response

    # If not exporting, render the HTML page as usual
    context = {
        'all_employees': all_employees,
        'selected_employee_id': int(selected_employee_id) if selected_employee_id else None,
        'records': records,
    }
    return render(request, 'employees/performance_report.html', context)


@login_required
def company_settings(request):
    """
    View to manage company-wide settings.
    """
    settings = CompanySettings.load()

    if request.method == 'POST':
        settings.calculation_basis = request.POST.get('calculation_basis', settings.calculation_basis)
        base_hours = request.POST.get('base_hours')
        if base_hours:
            settings.base_hours = Decimal(base_hours)
        settings.save()
        messages.success(request, 'Configuración guardada exitosamente.')
        return redirect('company_settings')

    context = {
        'settings': settings,
    }
    return render(request, 'employees/company_settings.html', context)
