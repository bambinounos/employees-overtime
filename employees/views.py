import csv
from django.http import HttpResponse
from django.shortcuts import render, redirect
from .models import Employee, WorkLog, TaskBoard, EmployeePerformanceRecord, CompanySettings, KPI
from django.contrib.auth.decorators import login_required
from datetime import date
from decimal import Decimal
from django.contrib import messages
import calendar
from django.db.models import Max

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
    """
    Renders the task board.
    - For superusers, it allows selecting and viewing any employee's board.
    - For regular users, it shows their own task board.
    """
    user = request.user
    board = None
    all_employees = None
    selected_employee_id = None

    def _ensure_board_and_lists(employee):
        """Helper function to get/create board and default lists."""
        from .models import TaskList
        board, created = TaskBoard.objects.get_or_create(
            employee=employee,
            defaults={'name': f"Tablero de {employee.name}"}
        )
        if created:
            TaskList.objects.create(board=board, name="Pendiente", order=1)
            TaskList.objects.create(board=board, name="En Progreso", order=2)
            TaskList.objects.create(board=board, name="Hecho", order=3)
        return board

    if user.is_superuser:
        all_employees = Employee.objects.all()
        employee_id_str = request.GET.get('employee_id')

        if employee_id_str:
            try:
                selected_employee_id = int(employee_id_str)
                employee = Employee.objects.get(pk=selected_employee_id)
                board = _ensure_board_and_lists(employee)
            except (ValueError, Employee.DoesNotExist):
                messages.error(request, "Empleado no válido seleccionado.")
    else:
        # Regular user, show their own board
        try:
            employee = user.employee
            board = _ensure_board_and_lists(employee)
        except Employee.DoesNotExist:
            board = None # User not linked to an employee profile

    context = {
        'board': board,
        'all_employees': all_employees,
        'selected_employee_id': selected_employee_id,
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


from django.db.models import Avg, Sum, Count, F
from django.db.models.functions import Coalesce
from .models import Task
import json
from datetime import timedelta

@login_required
def strategic_dashboard(request):
    """
    Renders the main strategic dashboard, showing KPIs, rankings, and trends.
    """
    today = date.today()
    # Use the last day of the previous month as the primary period for reporting
    first_day_of_current_month = today.replace(day=1)
    last_day_of_previous_month = first_day_of_current_month - timedelta(days=1)
    year, month = last_day_of_previous_month.year, last_day_of_previous_month.month
    period_name = last_day_of_previous_month.strftime('%B %Y')

    # --- 1. KPIs ---
    kpis = {
        'tasks_completed': 0,
        'on_time_percentage': 100,
        'avg_ipac': 0,
        'total_bonus': 0
    }

    # Calculate overall task completion
    completed_tasks_query = EmployeePerformanceRecord.objects.filter(date__year=year, date__month=month)
    kpis['tasks_completed'] = completed_tasks_query.filter(kpi__measurement_type='count_gt').aggregate(total=Sum('actual_value'))['total'] or 0

    # Calculate on-time percentage from relevant tasks
    tasks_with_due_date = Task.objects.filter(due_date__isnull=False, created_at__year=year, created_at__month=month)
    total_due = tasks_with_due_date.count()
    if total_due > 0:
        on_time_count = tasks_with_due_date.filter(completed_at__isnull=False, completed_at__date__lte=F('due_date')).count()
        kpis['on_time_percentage'] = (on_time_count / total_due) * 100 if total_due > 0 else 100

    # Calculate average IPAC score and total bonus from performance records
    ipac_kpi = KPI.objects.filter(measurement_type='composite_ipac').first()
    if ipac_kpi:
        ipac_records = EmployeePerformanceRecord.objects.filter(kpi=ipac_kpi, date__year=year, date__month=month)
        kpis['avg_ipac'] = ipac_records.aggregate(avg_val=Avg('actual_value'))['avg_val'] or 0

    kpis['total_bonus'] = EmployeePerformanceRecord.objects.filter(date__year=year, date__month=month).aggregate(total=Sum('bonus_awarded'))['total'] or 0

    # --- 2. Employee Ranking ---
    ranking_records = None
    if ipac_kpi:
        ranking_records = EmployeePerformanceRecord.objects.filter(
            kpi=ipac_kpi,
            date__year=year,
            date__month=month
        ).select_related('employee').order_by('-actual_value')[:5] # Top 5 employees

    # --- 3. Warning KPIs ---
    warning_kpis = KPI.objects.filter(is_warning_kpi=True)
    warning_records = EmployeePerformanceRecord.objects.filter(
        kpi__in=warning_kpis,
        target_met=False,
        date__year=year,
        date__month=month
    ).select_related('employee', 'kpi').order_by('employee__name')

    # --- 4. Trend Data (for chart) ---
    # Get IPAC trend for the last 6 months
    trend_data = {}
    if ipac_kpi:
        six_months_ago = (first_day_of_current_month - timedelta(days=6*30)).replace(day=1)

        trend_records = EmployeePerformanceRecord.objects.filter(
            kpi=ipac_kpi,
            date__gte=six_months_ago
        ).values('date__year', 'date__month').annotate(
            avg_value=Avg('actual_value')
        ).order_by('date__year', 'date__month')

        trend_labels = [date(year=r['date__year'], month=r['date__month'], day=1).strftime('%b %Y') for r in trend_records]
        trend_values = [float(r['avg_value']) for r in trend_records]

        trend_data = {
            'labels': json.dumps(trend_labels),
            'values': json.dumps(trend_values),
            'kpi_name': ipac_kpi.name
        }

    context = {
        'period_name': period_name,
        'kpis': kpis,
        'ranking_records': ranking_records,
        'warning_records': warning_records,
        'trend_data': trend_data,
    }
    return render(request, 'employees/strategic_dashboard.html', context)


@login_required
def employee_ranking(request):
    """
    Renders the employee ranking page based on a selected KPI.
    """
    all_kpis = KPI.objects.all()
    selected_kpi_id = request.GET.get('kpi_id')
    ranking_records = None
    selected_kpi = None
    period = None

    if selected_kpi_id:
        try:
            selected_kpi = KPI.objects.get(pk=selected_kpi_id)

            # Find the most recent date for which there are records for this KPI
            latest_date_info = EmployeePerformanceRecord.objects.filter(
                kpi=selected_kpi
            ).aggregate(max_date=Max('date'))

            latest_date = latest_date_info.get('max_date')

            if latest_date:
                period = latest_date.strftime('%B %Y')
                records_query = EmployeePerformanceRecord.objects.filter(
                    kpi=selected_kpi,
                    date=latest_date
                ).select_related('employee').order_by('-actual_value')

                # Adjust sorting for KPIs where lower is better
                if selected_kpi.measurement_type == 'count_lt':
                    records_query = records_query.order_by('actual_value')

                ranking_records = records_query

        except KPI.DoesNotExist:
            messages.error(request, "Selected KPI not found.")
            return redirect('employee_ranking')

    context = {
        'all_kpis': all_kpis,
        'selected_kpi_id': int(selected_kpi_id) if selected_kpi_id else None,
        'selected_kpi': selected_kpi,
        'ranking_records': ranking_records,
        'period': period,
    }
    return render(request, 'employees/employee_ranking.html', context)
