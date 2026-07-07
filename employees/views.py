import csv
from django.http import HttpResponse
from django.shortcuts import render, redirect
from .models import Employee, WorkLog, TaskBoard, EmployeePerformanceRecord, CompanySettings, KPI, BonusRule
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from datetime import date, timedelta
from decimal import Decimal
from django.contrib import messages
import calendar
from django.db.models import Max, Sum, Q

def index(request):
    """Renders the home page."""
    return render(request, 'employees/index.html')

@login_required
def employee_list(request):
    """Renders the employee list page."""
    show_inactive = request.GET.get('show_inactive') == 'true'
    if show_inactive:
        employees = Employee.objects.all().order_by('name')
    else:
        employees = Employee.objects.filter(Q(end_date__isnull=True) | Q(end_date__gte=date.today())).order_by('name')

    context = {
        'employees': employees,
        'show_inactive': show_inactive
    }
    return render(request, 'employees/employee_list.html', context)

def _build_salary_context(employee, year, month):
    """Builds the salary breakdown + 'striking' metrics context shared by
    employee_salary and mi_panel."""
    salary = employee.calculate_salary(year, month)

    potential_bonus = Decimal('0.00')
    lost_bonus = Decimal('0.00')
    lost_lateness = Decimal('0.00')
    total_potential = Decimal('0.00')
    percentage_potential = 0

    commission_amount = Decimal('0.00')

    if salary:
        # 1. Potential Bonus (only for KPIs in employee's profile)
        if employee.profile:
            profile_kpis = employee.profile.kpis.all()
            potential_bonus = BonusRule.objects.filter(kpi__in=profile_kpis).aggregate(total=Sum('bonus_amount'))['total'] or Decimal('0.00')
        else:
            potential_bonus = Decimal('0.00')

        # 2. Lost Bonus
        earned_bonus = salary.get('performance_bonus', Decimal('0.00'))
        lost_bonus = max(Decimal('0.00'), potential_bonus - earned_bonus)

        # 3. Lost due to Lateness/Absence
        base_salary = salary.get('base_salary', Decimal('0.00'))
        work_pay = salary.get('work_pay', Decimal('0.00'))
        lost_lateness = max(Decimal('0.00'), base_salary - work_pay)

        # 4. Commission
        commission_amount = salary.get('commission_amount', Decimal('0.00'))

        # 5. Total Potential (Base + Potential Bonus + Commission)
        total_potential = base_salary + potential_bonus + commission_amount

        # 6. Percentage Reached
        total_earned = salary.get('total_salary', Decimal('0.00'))
        if total_potential > 0:
            percentage_potential = (total_earned / total_potential) * 100
        else:
            percentage_potential = 0

    return {
        'employee': employee,
        'year': year,
        'month': month,
        'salary': salary,
        'potential_bonus': potential_bonus,
        'lost_bonus': lost_bonus,
        'lost_lateness': lost_lateness,
        'total_potential': total_potential,
        'percentage_potential': percentage_potential,
        'commission_amount': commission_amount,
    }


@login_required
def employee_salary(request, employee_id):
    """Renders the salary calculation page for a specific employee."""
    employee = Employee.objects.get(pk=employee_id)

    # Salary data is only visible to its owner or a superuser
    if not request.user.is_superuser and getattr(request.user, 'employee', None) != employee:
        raise PermissionDenied

    today = date.today()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    context = _build_salary_context(employee, year, month)
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
        all_employees = Employee.objects.filter(Q(end_date__isnull=True) | Q(end_date__gte=date.today()))
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

    # --- Smart filtering ---
    filtered_lists = []
    completed_range = request.GET.get('completed_range', '7')
    status_filter = request.GET.get('status', '')

    if board:
        cutoff_days = {'7': 7, '30': 30, '90': 90}
        cutoff = None
        if completed_range in cutoff_days:
            from django.utils import timezone
            cutoff = timezone.now() - timedelta(days=cutoff_days[completed_range])

        for tl in board.lists.all():
            tasks = tl.tasks.filter(is_recurring=False)

            if status_filter:
                tasks = tasks.filter(status=status_filter)

            hidden_count = 0
            if tl.name == 'Hecho' and cutoff is not None:
                total = tasks.count()
                tasks = tasks.filter(Q(completed_at__gte=cutoff) | Q(completed_at__isnull=True))
                hidden_count = total - tasks.count()

            filtered_lists.append({
                'id': tl.id,
                'name': tl.name,
                'tasks': tasks.order_by('order'),
                'hidden_count': hidden_count,
            })

    context = {
        'board': board,
        'filtered_lists': filtered_lists,
        'completed_range': completed_range,
        'status_filter': status_filter,
        'all_employees': all_employees,
        'selected_employee_id': selected_employee_id,
    }
    return render(request, 'employees/task_board.html', context)

@login_required
def performance_report(request):
    """
    Renders the performance report page or handles CSV export.
    """
    all_employees = Employee.objects.filter(Q(end_date__isnull=True) | Q(end_date__gte=date.today()))
    selected_employee_id = request.GET.get('employee_id')

    # Non-superusers can only report on themselves
    if not request.user.is_superuser:
        own = getattr(request.user, 'employee', None)
        if own is None:
            raise PermissionDenied
        all_employees = all_employees.filter(pk=own.pk)
        if selected_employee_id and int(selected_employee_id) != own.pk:
            raise PermissionDenied

    records = None
    if selected_employee_id:
        records = EmployeePerformanceRecord.objects.filter(
            employee_id=selected_employee_id
        ).order_by('-date', 'kpi__name').select_related('employee', 'kpi')

        export_format = request.GET.get('format')
        if export_format in ('csv', 'xlsx'):
            headers = ['Period', 'KPI', 'Result', 'Target Met', 'Bonus Awarded']
            rows = [
                [record.date.strftime('%Y-%m'), record.kpi.name, record.actual_value,
                 'Yes' if record.target_met else 'No', record.bonus_awarded]
                for record in records
            ]

            if export_format == 'xlsx':
                from .exports import rows_to_xlsx
                contenido = rows_to_xlsx(
                    headers, rows, sheet_name='Desempeño',
                    title=f"Reporte de desempeño — {records[0].employee.name}" if rows else "Reporte de desempeño")
                response = HttpResponse(
                    contenido,
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = f'attachment; filename="performance_report_{selected_employee_id}.xlsx"'
                return response

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="performance_report_{selected_employee_id}.csv"'
            writer = csv.writer(response)
            writer.writerow(headers)
            for row in rows:
                writer.writerow(row)
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
            Q(employee__end_date__isnull=True) | Q(employee__end_date__gte=date.today()),
            kpi=ipac_kpi,
            date__year=year,
            date__month=month,
        ).select_related('employee').order_by('-actual_value')[:5] # Top 5 employees

    # --- 3. Warning KPIs ---
    warning_kpis = KPI.objects.filter(is_warning_kpi=True)
    warning_records = EmployeePerformanceRecord.objects.filter(
        Q(employee__end_date__isnull=True) | Q(employee__end_date__gte=date.today()),
        kpi__in=warning_kpis,
        target_met=False,
        date__year=year,
        date__month=month,
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
                    Q(employee__end_date__isnull=True) | Q(employee__end_date__gte=date.today()),
                    kpi=selected_kpi,
                    date=latest_date,
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


@login_required
def terminate_employee(request, employee_id):
    """
    Sets the end date for an employee's contract to the current date.
    """
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('employee_list')

    if request.method == 'POST':
        try:
            employee = Employee.objects.get(pk=employee_id)
            # Use the is_active property to prevent terminating an already inactive employee
            if employee.is_active:
                employee.end_date = date.today()
                employee.save()
                messages.success(request, f"El contrato de {employee.name} ha sido terminado.")
            else:
                messages.warning(request, f"{employee.name} ya se encuentra inactivo.")
        except Employee.DoesNotExist:
            messages.error(request, "Empleado no encontrado.")

    return redirect('employee_list')


# ============================================================================
# Autoservicio del empleado: ausencias, recibos y panel personal
# ============================================================================

def _own_employee_or_403(request):
    employee = getattr(request.user, 'employee', None)
    if employee is None:
        raise PermissionDenied
    return employee


@login_required
def mis_ausencias(request):
    """Portal del empleado: saldo de vacaciones, historial y nueva solicitud."""
    from .forms import SolicitudAusenciaForm
    from . import ausencias as svc

    employee = _own_employee_or_403(request)

    if request.method == 'POST':
        if request.POST.get('accion') == 'cancelar':
            solicitud = employee.solicitudes_ausencia.filter(
                pk=request.POST.get('solicitud_id'), estado='PENDIENTE').first()
            if solicitud:
                svc.cancelar_solicitud(solicitud, request.user)
                messages.success(request, "Solicitud cancelada.")
            else:
                messages.error(request, "Solo se pueden cancelar solicitudes pendientes.")
            return redirect('mis_ausencias')

        form = SolicitudAusenciaForm(request.POST, employee=employee)
        if form.is_valid():
            solicitud = form.save(commit=False)
            solicitud.employee = employee
            solicitud.save()
            messages.success(request, "Solicitud enviada. Queda pendiente de aprobación.")
            return redirect('mis_ausencias')
    else:
        form = SolicitudAusenciaForm(employee=employee)

    context = {
        'employee': employee,
        'form': form,
        'saldo': employee.saldo_vacaciones(),
        'solicitudes': employee.solicitudes_ausencia.all()[:50],
    }
    return render(request, 'employees/ausencias.html', context)


@login_required
def ausencias_pendientes(request):
    """Bandeja del aprobador (superuser): solicitudes pendientes de decisión."""
    from .models import SolicitudAusencia

    if not request.user.is_superuser:
        raise PermissionDenied

    pendientes = SolicitudAusencia.objects.filter(estado='PENDIENTE').select_related(
        'employee', 'tipo').order_by('fecha_inicio')
    recientes = SolicitudAusencia.objects.exclude(estado='PENDIENTE').select_related(
        'employee', 'tipo')[:20]
    context = {'pendientes': pendientes, 'recientes': recientes}
    return render(request, 'employees/ausencias_aprobar.html', context)


@login_required
def decidir_ausencia(request, solicitud_id):
    """Aprueba o rechaza una solicitud (POST, solo superuser)."""
    from .models import SolicitudAusencia
    from . import ausencias as svc

    if not request.user.is_superuser:
        raise PermissionDenied
    if request.method != 'POST':
        return redirect('ausencias_pendientes')

    try:
        solicitud = SolicitudAusencia.objects.get(pk=solicitud_id)
    except SolicitudAusencia.DoesNotExist:
        messages.error(request, "Solicitud no encontrada.")
        return redirect('ausencias_pendientes')

    decision = request.POST.get('decision')
    comentario = request.POST.get('comentario', '')
    try:
        if decision == 'aprobar':
            svc.aprobar_solicitud(solicitud, request.user, comentario)
            messages.success(request, f"Ausencia de {solicitud.employee.name} aprobada.")
        elif decision == 'rechazar':
            svc.rechazar_solicitud(solicitud, request.user, comentario)
            messages.success(request, f"Ausencia de {solicitud.employee.name} rechazada.")
        else:
            messages.error(request, "Decisión inválida.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect('ausencias_pendientes')


@login_required
def mis_recibos(request):
    """Lista de recibos de nómina del empleado autenticado."""
    employee = _own_employee_or_403(request)
    context = {
        'employee': employee,
        'recibos': employee.recibos.all()[:36],
    }
    return render(request, 'employees/mis_recibos.html', context)


@login_required
def recibo_pdf(request, employee_id, year, month):
    """Descarga el PDF de un recibo (dueño o superuser)."""
    from .models import ReciboNomina
    from .report_pdf import generar_recibo_pdf

    try:
        recibo = ReciboNomina.objects.select_related('employee').get(
            employee_id=employee_id, year=year, month=month)
    except ReciboNomina.DoesNotExist:
        messages.error(request, "Ese recibo todavía no fue emitido.")
        return redirect('mis_recibos')

    if not request.user.is_superuser and getattr(request.user, 'employee', None) != recibo.employee:
        raise PermissionDenied

    pdf = generar_recibo_pdf(recibo)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="recibo_{recibo.employee_id}_{year}_{month:02d}.pdf"')
    return response


@login_required
def mi_panel(request):
    """Panel personal del empleado: salario del mes, saldo y recibos."""
    employee = _own_employee_or_403(request)

    today = date.today()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    context = _build_salary_context(employee, year, month)
    context.update({
        'saldo_vacaciones': employee.saldo_vacaciones(),
        'recibos': employee.recibos.all()[:12],
        'ausencias_pendientes': employee.solicitudes_ausencia.filter(estado='PENDIENTE').count(),
    })
    return render(request, 'employees/mi_panel.html', context)


@login_required
def nomina_cierre(request):
    """Pantalla de cierre de mes (superuser): genera los recibos del período."""
    from .nomina import generar_recibos_mes
    from .models import ReciboNomina

    if not request.user.is_superuser:
        raise PermissionDenied

    today = date.today()
    year = int(request.POST.get('year') or request.GET.get('year') or today.year)
    month = int(request.POST.get('month') or request.GET.get('month') or today.month)

    if request.method == 'POST':
        generados, omitidos = generar_recibos_mes(year, month, generado_por=request.user)
        messages.success(request, f"{len(generados)} recibos generados para {month:02d}/{year}.")
        if omitidos:
            nombres = ', '.join(e.name for e in omitidos)
            messages.warning(request, f"Sin salario configurado (omitidos): {nombres}")
        return redirect(f"{request.path}?year={year}&month={month}")

    recibos = ReciboNomina.objects.filter(year=year, month=month).select_related('employee')
    context = {'year': year, 'month': month, 'recibos': recibos}
    return render(request, 'employees/nomina.html', context)


@login_required
def nomina_planilla(request):
    """Descarga la planilla de nómina XLSX del período (superuser)."""
    from .exports import PlanillaSinRecibosError, generar_planilla_xlsx

    if not request.user.is_superuser:
        raise PermissionDenied

    today = date.today()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))

    try:
        contenido, preliminar = generar_planilla_xlsx(year, month)
    except PlanillaSinRecibosError as exc:
        from django.urls import reverse
        messages.error(request, str(exc))
        return redirect(f"{reverse('nomina_cierre')}?year={year}&month={month}")

    sufijo = '_PRELIMINAR' if preliminar else ''
    response = HttpResponse(
        contenido,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = (
        f'attachment; filename="planilla_nomina_{year}_{month:02d}{sufijo}.xlsx"')
    return response
