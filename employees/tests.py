import calendar
from unittest import mock
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient
from .models import (
    Employee, Salary, WorkLog, KPI, BonusRule, KPIBonusTier, TaskBoard, TaskList, Task,
    ManualKpiEntry, EmployeePerformanceRecord, JobProfile
)
from .sugerencias import build_sugerencias
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone as dt_timezone
from django.utils import timezone

# Instante fijo a mediodía local (TIME_ZONE=America/Mexico_City, UTC-6):
# 18:00 UTC == 12:00 local, así fecha UTC == fecha local y no hay frontera de
# medianoche que haga flaky la generación de tareas recurrentes.
FROZEN_NOW = datetime(2025, 6, 16, 18, 0, 0, tzinfo=dt_timezone.utc)

class PerformanceAndSalaryTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.employee = Employee.objects.create(user=self.user, name='Test Employee', email='test@example.com', hire_date=date(2024, 1, 1))
        self.salary = Salary.objects.create(employee=self.employee, base_amount=Decimal('1600.00'), effective_date=date(2024, 1, 1))

        # KPIs and Bonus Rules
        self.kpi_tasks = KPI.objects.create(name="Productividad General", measurement_type='percentage', target_value=Decimal('90.00'))
        self.kpi_errors = KPI.objects.create(name="Calidad Administrativa", measurement_type='count_lt', target_value=Decimal('3.00'))
        BonusRule.objects.create(kpi=self.kpi_tasks, bonus_amount=Decimal('50.00'))
        BonusRule.objects.create(kpi=self.kpi_errors, bonus_amount=Decimal('50.00'))

        # Assign profile with KPIs to employee
        self.profile = JobProfile.objects.create(name='Test Profile')
        self.profile.kpis.add(self.kpi_tasks, self.kpi_errors)
        self.employee.profile = self.profile
        self.employee.save()

        # Task Board Setup
        self.board = TaskBoard.objects.create(employee=self.employee, name=f"Board for {self.employee.name}")
        self.list_todo = TaskList.objects.create(board=self.board, name="To Do", order=1)
        self.list_done = TaskList.objects.create(board=self.board, name="Hecho", order=2)

    def test_calculate_performance_bonus(self):
        # --- Simulate performance for a month (e.g., August 2024) ---
        # 1. Task Performance: 9 out of 10 tasks completed = 90%
        due_datetime = timezone.make_aware(datetime(2024, 8, 15))
        for i in range(9):
            Task.objects.create(list=self.list_done, assigned_to=self.employee, kpi=self.kpi_tasks, title=f"Task {i}", order=i, due_date=due_datetime, completed_at=timezone.now())
        Task.objects.create(list=self.list_todo, assigned_to=self.employee, kpi=self.kpi_tasks, title="Task 10", order=10, due_date=due_datetime)

        # 2. Manual Entry Performance: 2 errors logged (target is < 3)
        ManualKpiEntry.objects.create(employee=self.employee, kpi=self.kpi_errors, date=date(2024, 8, 10), value=1)
        ManualKpiEntry.objects.create(employee=self.employee, kpi=self.kpi_errors, date=date(2024, 8, 20), value=1)

        # --- Calculate Bonus ---
        bonus = self.employee.calculate_performance_bonus(2024, 8)

        # --- Assertions ---
        # Should get $50 for tasks and $50 for errors
        self.assertEqual(bonus, Decimal('100.00'))

        # Verify that records were created
        task_record = EmployeePerformanceRecord.objects.get(employee=self.employee, kpi=self.kpi_tasks, date=date(2024, 8, 31))
        self.assertTrue(task_record.target_met)
        self.assertEqual(task_record.actual_value, Decimal('90.00'))

        error_record = EmployeePerformanceRecord.objects.get(employee=self.employee, kpi=self.kpi_errors, date=date(2024, 8, 31))
        self.assertTrue(error_record.target_met)
        self.assertEqual(error_record.actual_value, Decimal('2.00'))

    def test_full_salary_calculation(self):
        # Log some work hours
        WorkLog.objects.create(employee=self.employee, date=date(2024, 8, 5), hours_worked=40, overtime_hours=5) # weekly log

        # Simulate performance data that yields a $50 bonus
        ManualKpiEntry.objects.create(employee=self.employee, kpi=self.kpi_errors, date=date(2024, 8, 10), value=1) # 1 error is < 3, so bonus is met

        # --- Calculate Salary ---
        # Expected:
        # Base pay: 1600 / 160 hours = $10/hr. 40 hours = $400.
        # Overtime pay: 5 hours * ($10 * 1.5) = $75.
        # Bonus: $50 for meeting the error KPI.
        # Total = 400 + 75 + 50 = $525
        salary_details = self.employee.calculate_salary(2024, 8)
        self.assertEqual(salary_details['total_salary'], Decimal('525.00'))

    def test_count_lt_tier_premia_a_los_mejores(self):
        """En un KPI 'menos es mejor', el escalón se alcanza con MENOS errores."""
        # Escalón: 1 error o menos -> $80 (mejor que el estándar de $50).
        KPIBonusTier.objects.create(kpi=self.kpi_errors, threshold=Decimal('1'),
                                    bonus_amount=Decimal('80.00'))
        ManualKpiEntry.objects.create(employee=self.employee, kpi=self.kpi_errors,
                                      date=date(2024, 8, 10), value=1)  # 1 error

        self.employee.calculate_performance_bonus(2024, 8)
        record = EmployeePerformanceRecord.objects.get(
            employee=self.employee, kpi=self.kpi_errors, date=date(2024, 8, 31))
        self.assertTrue(record.target_met)
        self.assertEqual(record.bonus_awarded, Decimal('80.00'))

    def test_count_lt_tier_no_paga_a_los_peores(self):
        """Regresión: con MÁS errores que el umbral (y que la meta) no hay bono.

        Con el bug anterior, 3 errores >= umbral 1 pagaba erróneamente el escalón."""
        KPIBonusTier.objects.create(kpi=self.kpi_errors, threshold=Decimal('1'),
                                    bonus_amount=Decimal('80.00'))
        for dia in (5, 15, 25):  # 3 errores: falla la meta (<3) y el escalón (<=1)
            ManualKpiEntry.objects.create(employee=self.employee, kpi=self.kpi_errors,
                                          date=date(2024, 8, dia), value=1)

        self.employee.calculate_performance_bonus(2024, 8)
        record = EmployeePerformanceRecord.objects.get(
            employee=self.employee, kpi=self.kpi_errors, date=date(2024, 8, 31))
        self.assertFalse(record.target_met)
        self.assertEqual(record.bonus_awarded, Decimal('0.00'))


class ViewsAndAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.employee = Employee.objects.create(user=self.user, name='Test Employee', email='test@example.com', hire_date=date(2023, 1, 1))
        self.client.login(username='testuser', password='password')
        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    def test_all_views_load_ok(self):
        # Note: The calendar view test is now included here.
        # The key is that the app containing the templatetag (`django_year_calendar`) must be in INSTALLED_APPS
        # for the test runner to find it. No special loading is needed in the test itself.
        urls = [
            reverse('index'),
            reverse('employee_list'),
            reverse('employee_salary', args=[self.employee.id]),
            reverse('task_board'),
            reverse('performance_report'),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, f"View for {url} failed to load.")

    def test_task_move_api(self):
        board = TaskBoard.objects.create(employee=self.employee, name="Test Board")
        list1 = TaskList.objects.create(board=board, name="List 1", order=1)
        list2 = TaskList.objects.create(board=board, name="List 2", order=2)
        task = Task.objects.create(list=list1, assigned_to=self.employee, title="My Task", order=1)

        url = reverse('task-move', args=[task.id])
        data = {'list_id': list2.id, 'order': 0}
        response = self.api_client.post(url, data, format='json')

        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.list, list2)
        self.assertEqual(task.order, 0)


class EmployeeDeactivationTest(TestCase):

    def setUp(self):
        self.superuser = User.objects.create_superuser('admin', 'admin@example.com', 'password')
        self.active_employee = Employee.objects.create(name='Active Employee', email='active@example.com', hire_date=date(2023, 1, 1))
        self.inactive_employee = Employee.objects.create(name='Inactive Employee', email='inactive@example.com', hire_date=date(2023, 1, 1), end_date=date(2024, 1, 1))

    def test_employee_list_view(self):
        self.client.login(username='admin', password='password')

        # Test default view (should only show active employees)
        response = self.client.get(reverse('employee_list'))
        self.assertContains(response, self.active_employee.name)
        self.assertNotContains(response, self.inactive_employee.name)

        # Test view with show_inactive=true
        response = self.client.get(reverse('employee_list') + '?show_inactive=true')
        self.assertContains(response, self.active_employee.name)
        self.assertContains(response, self.inactive_employee.name)

    def test_terminate_employee_view(self):
        self.client.login(username='admin', password='password')

        # Terminate the active employee
        response = self.client.post(reverse('terminate_employee', args=[self.active_employee.id]))
        self.assertEqual(response.status_code, 302) # Should redirect

        self.active_employee.refresh_from_db()
        self.assertIsNotNone(self.active_employee.end_date)

    def test_dropdowns_only_show_active_employees(self):
        self.client.login(username='admin', password='password')

        # Test task board view
        response = self.client.get(reverse('task_board'))
        self.assertContains(response, self.active_employee.name)
        self.assertNotContains(response, self.inactive_employee.name)

        # Test performance report view
        response = self.client.get(reverse('performance_report'))
        self.assertContains(response, self.active_employee.name)
        self.assertNotContains(response, self.inactive_employee.name)

    def test_task_serializer_filters_inactive_employees(self):
        """
        Verify that the TaskSerializer's 'assigned_to' field only allows active employees.
        """
        api_client = APIClient()
        api_client.force_authenticate(user=self.superuser)

        board = TaskBoard.objects.create(employee=self.active_employee, name="Test Board")
        task_list = TaskList.objects.create(board=board, name="To Do", order=1)

        # Case 1: Try to assign a task to an INACTIVE employee (should fail)
        invalid_data = {
            'title': 'Test Task for Inactive Employee',
            'list': task_list.id,
            'assigned_to': self.inactive_employee.id,
            'order': 1
        }
        url = reverse('task-list')
        response = api_client.post(url, invalid_data, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('assigned_to', response.data)
        # Check for the Spanish translation of the error message.
        self.assertTrue('inválid' in str(response.data['assigned_to'][0]))

        # Case 2: Try to assign a task to an ACTIVE employee (should succeed)
        valid_data = {
            'title': 'Test Task for Active Employee',
            'list': task_list.id,
            'assigned_to': self.active_employee.id,
            'order': 1
        }
        response = api_client.post(url, valid_data, format='json')

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Task.objects.count(), 1)
        self.assertEqual(Task.objects.first().assigned_to, self.active_employee)


class RecurringTaskTest(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser('admin', 'admin@example.com', 'password')
        self.employee = Employee.objects.create(name='Recurring Task Employee', email='recurring@example.com', hire_date=date(2023, 1, 1))
        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.superuser)

        self.board = TaskBoard.objects.create(employee=self.employee, name="Test Board")
        self.task_list = TaskList.objects.create(board=self.board, name="To Do", order=1)

    @mock.patch('django.utils.timezone.now', return_value=FROZEN_NOW)
    def test_recurring_task_generation(self, mock_now):
        # 1. Create a weekly recurring task
        start_datetime = timezone.now() - timedelta(days=10)
        end_date = (timezone.now() + timedelta(days=20)).date()
        task_data = {
            'title': 'Weekly Report',
            'list': self.task_list.id,
            'assigned_to': self.employee.id,
            'order': 1,
            'is_recurring': True,
            'recurrence_frequency': 'weekly',
            'due_date': start_datetime.isoformat(),
            'recurrence_end_date': end_date.isoformat()
        }
        url = reverse('task-list')
        response = self.api_client.post(url, task_data, format='json')
        self.assertEqual(response.status_code, 201)

        # 2. Verify initial creation
        # Should have one parent task and one child instance
        self.assertEqual(Task.objects.filter(is_recurring=True).count(), 1)
        self.assertEqual(Task.objects.filter(is_recurring=False).count(), 1)

        # 3. Trigger on-demand generation by accessing the task list
        self.api_client.get(url)

        # 4. Assert that the next task instance is created
        # We expect two instances to have been created: one for last week and one for this week.
        self.assertEqual(Task.objects.filter(is_recurring=False).count(), 2)

    @mock.patch('django.utils.timezone.now', return_value=FROZEN_NOW)
    def test_idempotent_task_generation(self, mock_now):
        # 1. Create a daily recurring task that should have started 3 days ago
        start_datetime = timezone.now() - timedelta(days=3)
        end_date = (timezone.now() + timedelta(days=10)).date()
        task_data = {
            'title': 'Daily Standup',
            'list': self.task_list.id,
            'assigned_to': self.employee.id,
            'order': 1,
            'is_recurring': True,
            'recurrence_frequency': 'daily',
            'due_date': start_datetime.isoformat(),
            'recurrence_end_date': end_date.isoformat()
        }
        url = reverse('task-list')
        response = self.api_client.post(url, task_data, format='json')
        self.assertEqual(response.status_code, 201)

        # On creation, one "template" and one instance are made.
        self.assertEqual(Task.objects.filter(is_recurring=True).count(), 1)
        self.assertEqual(Task.objects.filter(is_recurring=False).count(), 1)

        # 2. Trigger generation
        self.api_client.get(url)

        # After GET, tasks for day -2, -1, and 0 (today) should be created.
        # The initial instance for day -3 already exists. So, 3 new tasks.
        # Total instances = 1 (initial) + 3 (generated) = 4
        self.assertEqual(Task.objects.filter(is_recurring=False).count(), 4)

        # 3. Trigger generation again
        self.api_client.get(url)

        # The number of tasks should not change, proving idempotency.
        self.assertEqual(Task.objects.filter(is_recurring=False).count(), 4)

    @mock.patch('django.utils.timezone.now', return_value=FROZEN_NOW)
    def test_superuser_generates_tasks_for_specific_employee(self, mock_now):
        # 1. Create a recurring task for a specific employee
        start_datetime = timezone.now() - timedelta(days=2)
        end_date = (timezone.now() + timedelta(days=10)).date()
        task_data = {
            'title': 'Employee-Specific Task',
            'list': self.task_list.id,
            'assigned_to': self.employee.id,
            'order': 1,
            'is_recurring': True,
            'recurrence_frequency': 'daily',
            'due_date': start_datetime.isoformat(),
            'recurrence_end_date': end_date.isoformat()
        }
        url = reverse('task-list')
        response = self.api_client.post(url, task_data, format='json')
        self.assertEqual(response.status_code, 201)

        # 2. Access the API as a superuser for that specific employee
        # This should trigger the generation of missing tasks for that employee.
        url_with_param = f"{url}?employee_id={self.employee.id}"
        self.api_client.get(url_with_param)

        # 3. Assert that tasks were generated
        # Initial task (day -2) + generated tasks (day -1, day 0) = 3 tasks
        self.assertEqual(Task.objects.filter(is_recurring=False, assigned_to=self.employee).count(), 3)


class SalaryViewTest(TestCase):
    def setUp(self):
        # Create user and employee
        self.user = User.objects.create_user(username='testuser2', password='password')
        self.employee = Employee.objects.create(
            user=self.user,
            name='John Doe',
            email='john@example.com',
            hire_date=date(2023, 1, 1)
        )
        self.client.login(username='testuser2', password='password')

        # Create Base Salary
        Salary.objects.create(employee=self.employee, base_amount=Decimal('1600.00'), effective_date=date(2023, 1, 1))
        # Assuming 160 hours monthly base (default setting), so rate is $10/hr.

        # Create Work Logs (Underworked to simulate lateness)
        # Worked 150 hours instead of 160. Lost 10 hours * $10 = $100.
        # Note: hours_worked has max_digits=4 (max 99.99), so we split into multiple logs.
        WorkLog.objects.create(employee=self.employee, date=date(2023, 1, 1), hours_worked=75, overtime_hours=0)
        WorkLog.objects.create(employee=self.employee, date=date(2023, 1, 2), hours_worked=75, overtime_hours=0)

        # Create KPI, Bonus Rule, and assign profile
        self.kpi = KPI.objects.create(name='Test KPI', measurement_type='count_gt', target_value=10)
        BonusRule.objects.create(kpi=self.kpi, bonus_amount=Decimal('200.00'), description='Test Bonus')

        profile = JobProfile.objects.create(name='Test Salary Profile')
        profile.kpis.add(self.kpi)
        self.employee.profile = profile
        self.employee.save()

        # No performance record created, so target not met. Lost Bonus = $200.

    def test_salary_view_calculations(self):
        url = reverse('employee_salary', args=[self.employee.id])
        response = self.client.get(url, {'year': 2023, 'month': 1})

        self.assertEqual(response.status_code, 200)
        context = response.context

        # Check Base Calculations
        self.assertAlmostEqual(context['salary']['base_salary'], Decimal('1600.00'))
        self.assertAlmostEqual(context['salary']['work_pay'], Decimal('1500.00')) # 150 * 10

        # Check Striking Metrics
        # Lost Lateness: 1600 - 1500 = 100
        self.assertAlmostEqual(context['lost_lateness'], Decimal('100.00'))

        # Potential Bonus: 200
        self.assertAlmostEqual(context['potential_bonus'], Decimal('200.00'))

        # Earned Bonus: 0 (Target not met)
        self.assertAlmostEqual(context['salary']['performance_bonus'], Decimal('0.00'))

        # Lost Bonus: 200 - 0 = 200
        self.assertAlmostEqual(context['lost_bonus'], Decimal('200.00'))

        # Total Potential: Base (1600) + Potential Bonus (200) = 1800
        self.assertAlmostEqual(context['total_potential'], Decimal('1800.00'))

        # Percentage: Earned (1500) / Potential (1800)
        expected_percentage = (Decimal('1500') / Decimal('1800')) * 100
        self.assertAlmostEqual(context['percentage_potential'], expected_percentage)

    def test_overtime_does_not_reduce_loss(self):
        # Case where overtime makes total pay > base, but lateness logic should still capture lost base hours?
        # My logic: lost_lateness = max(0, base_salary - work_pay).
        # work_pay = normal_hours * rate.
        # If I work 150 normal hours + 20 overtime hours.
        # work_pay is based on 150 hours. Overtime is separate.
        # So lost_lateness should still be 100.

        # Update log
        WorkLog.objects.filter(employee=self.employee).delete()
        # Split 150 hours to fit max_digits=4
        WorkLog.objects.create(employee=self.employee, date=date(2023, 1, 1), hours_worked=75, overtime_hours=10)
        WorkLog.objects.create(employee=self.employee, date=date(2023, 1, 2), hours_worked=75, overtime_hours=10)

        url = reverse('employee_salary', args=[self.employee.id])
        response = self.client.get(url, {'year': 2023, 'month': 1})

        # work_pay is still 1500. Overtime pay is extra.
        self.assertAlmostEqual(response.context['lost_lateness'], Decimal('100.00'))
        self.assertAlmostEqual(response.context['salary']['overtime_pay'], Decimal('300.00')) # 20 * 15 (1.5x)


class ApiSecurityTest(TestCase):
    """Fase 0 hardening: la API DRF exige sesión y cada empleado solo ve lo suyo."""

    def setUp(self):
        self.user_a = User.objects.create_user(username='emp_a', password='password')
        self.employee_a = Employee.objects.create(
            user=self.user_a, name='Employee A', email='a@example.com', hire_date=date(2023, 1, 1))
        self.user_b = User.objects.create_user(username='emp_b', password='password')
        self.employee_b = Employee.objects.create(
            user=self.user_b, name='Employee B', email='b@example.com', hire_date=date(2023, 1, 1))
        self.superuser = User.objects.create_superuser('boss', 'boss@example.com', 'password')
        WorkLog.objects.create(employee=self.employee_a, date=date(2023, 5, 2), hours_worked=8)
        WorkLog.objects.create(employee=self.employee_b, date=date(2023, 5, 2), hours_worked=8)

    def test_anonymous_cannot_access_worklogs(self):
        response = APIClient().get('/api/worklogs/')
        self.assertEqual(response.status_code, 403)

    def test_employee_only_sees_own_worklogs(self):
        client = APIClient()
        client.force_authenticate(user=self.user_a)
        response = client.get('/api/worklogs/')
        self.assertEqual(response.status_code, 200)
        employees_in_response = {row['employee'] for row in response.json()}
        self.assertEqual(employees_in_response, {self.employee_a.id})

    def test_employee_cannot_create_worklog_for_other(self):
        client = APIClient()
        client.force_authenticate(user=self.user_a)
        response = client.post('/api/worklogs/', {
            'employee': self.employee_b.id, 'date': '2023-05-03',
            'hours_worked': 8, 'overtime_hours': 0}, format='json')
        self.assertEqual(response.status_code, 201)
        # employee is forced to the requester regardless of the payload
        self.assertEqual(response.json()['employee'], self.employee_a.id)

    def test_superuser_sees_all_worklogs(self):
        client = APIClient()
        client.force_authenticate(user=self.superuser)
        response = client.get('/api/worklogs/')
        self.assertEqual(len(response.json()), 2)

    def test_salary_view_blocks_other_employee(self):
        self.client.login(username='emp_a', password='password')
        response = self.client.get(reverse('employee_salary', args=[self.employee_b.id]))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('employee_salary', args=[self.employee_a.id]))
        self.assertEqual(response.status_code, 200)

    def test_kpi_history_blocks_other_employee(self):
        client = APIClient()
        client.force_authenticate(user=self.user_a)
        response = client.get(f'/api/employees/{self.employee_b.id}/kpi-history/')
        self.assertEqual(response.status_code, 403)
        response = client.get(f'/api/employees/{self.employee_a.id}/kpi-history/')
        self.assertEqual(response.status_code, 200)

    def test_performance_report_blocks_other_employee(self):
        self.client.login(username='emp_a', password='password')
        url = reverse('performance_report')
        response = self.client.get(url, {'employee_id': self.employee_b.id})
        self.assertEqual(response.status_code, 403)
        response = self.client.get(url, {'employee_id': self.employee_a.id})
        self.assertEqual(response.status_code, 200)

    def test_superuser_can_see_any_salary_and_report(self):
        self.client.login(username='boss', password='password')
        response = self.client.get(reverse('employee_salary', args=[self.employee_a.id]))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('performance_report'), {'employee_id': self.employee_a.id})
        self.assertEqual(response.status_code, 200)


class PostLoginRedirectTest(TestCase):
    """El aterrizaje post-login redirige por rol y respeta ?next=."""

    def setUp(self):
        self.boss = User.objects.create_superuser('boss', 'boss@example.com', 'password')
        self.user_emp = User.objects.create_user('empleado', password='password')
        Employee.objects.create(user=self.user_emp, name='Empleada', email='e@example.com',
                                hire_date=date(2023, 1, 1))
        self.user_solo = User.objects.create_user('solo', password='password')

    def test_superuser_aterriza_en_dashboard(self):
        response = self.client.post(reverse('login'),
                                    {'username': 'boss', 'password': 'password', 'next': ''},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request['PATH_INFO'], reverse('strategic_dashboard'))

    def test_empleado_aterriza_en_mi_panel(self):
        response = self.client.post(reverse('login'),
                                    {'username': 'empleado', 'password': 'password', 'next': ''},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request['PATH_INFO'], reverse('mi_panel'))

    def test_usuario_sin_employee_no_da_403(self):
        response = self.client.post(reverse('login'),
                                    {'username': 'solo', 'password': 'password', 'next': ''},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request['PATH_INFO'], reverse('index'))

    def test_respeta_next(self):
        response = self.client.post(reverse('login'),
                                    {'username': 'empleado', 'password': 'password',
                                     'next': reverse('task_board')},
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.request['PATH_INFO'], reverse('task_board'))


class IPACFormulaTest(TestCase):
    """IPAC = (completadas x puntualidad x calidad) / dias habiles.

    Regresion: la version anterior dividia por horas creado->completado,
    lo que castigaba crear tareas con anticipacion."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.employee = Employee.objects.create(user=self.user, name='Test Employee',
                                                email='test@example.com', hire_date=date(2024, 1, 1))
        self.kpi_errors = KPI.objects.create(name="Calidad Administrativa",
                                             measurement_type='count_lt', target_value=Decimal('2.00'))
        self.board = TaskBoard.objects.create(employee=self.employee, name="Board")
        self.list_done = TaskList.objects.create(board=self.board, name="Hecho", order=1)

    def _tarea(self, due, completada):
        return Task.objects.create(list=self.list_done, assigned_to=self.employee,
                                   title="T", order=0, due_date=due, completed_at=completada)

    def test_ipac_dias_habiles(self):
        # Agosto 2024 tiene 22 dias habiles. 10 tareas: 5 a tiempo, 5 tarde,
        # 1 error -> 10 x 0.5 x 0.9 / 22 = 0.20
        due = timezone.make_aware(datetime(2024, 8, 15))
        for _ in range(5):
            self._tarea(due, timezone.make_aware(datetime(2024, 8, 14, 12)))
        for _ in range(5):
            self._tarea(due, timezone.make_aware(datetime(2024, 8, 20, 12)))
        ManualKpiEntry.objects.create(employee=self.employee, kpi=self.kpi_errors,
                                      date=date(2024, 8, 10), value=1)
        self.assertEqual(self.employee.calculate_ipac(2024, 8), Decimal('0.20'))

    def test_ipac_no_castiga_planificacion_anticipada(self):
        # Tareas creadas 30 dias antes: mismo resultado que si se crearan hoy.
        # 4 tareas a tiempo, sin errores -> 4 x 1 x 1 / 22 = 0.18
        due = timezone.make_aware(datetime(2024, 8, 15))
        tarea = self._tarea(due, timezone.make_aware(datetime(2024, 8, 14, 12)))
        tarea.created_at = timezone.make_aware(datetime(2024, 7, 15))
        tarea.save()
        for _ in range(3):
            self._tarea(due, timezone.make_aware(datetime(2024, 8, 14, 12)))
        self.assertEqual(self.employee.calculate_ipac(2024, 8), Decimal('0.18'))

    def test_ipac_sin_tareas_es_cero(self):
        self.assertEqual(self.employee.calculate_ipac(2024, 8), Decimal('0.00'))

    def test_ipac_tareas_sin_fecha_no_cuentan(self):
        # Una tarea sin vencimiento no acredita productividad: IPAC = 0.
        for _ in range(2):
            Task.objects.create(list=self.list_done, assigned_to=self.employee,
                                title="S/F", order=0,
                                completed_at=timezone.make_aware(datetime(2024, 8, 14, 12)))
        self.assertEqual(self.employee.calculate_ipac(2024, 8), Decimal('0.00'))

    def test_ipac_solo_cuenta_tareas_con_fecha(self):
        # 2 con fecha (a tiempo) + 3 sin fecha -> solo cuentan las 2 primeras.
        # 2 x 1 x 1 / 22 = 0.09
        due = timezone.make_aware(datetime(2024, 8, 15))
        for _ in range(2):
            self._tarea(due, timezone.make_aware(datetime(2024, 8, 14, 12)))
        for _ in range(3):
            Task.objects.create(list=self.list_done, assigned_to=self.employee,
                                title="S/F", order=0,
                                completed_at=timezone.make_aware(datetime(2024, 8, 14, 12)))
        self.assertEqual(self.employee.calculate_ipac(2024, 8), Decimal('0.09'))

    @mock.patch('employees.models.timezone.now', return_value=FROZEN_NOW)
    def test_ipac_mes_en_curso_usa_dias_transcurridos(self, _now):
        # FROZEN_NOW = lun 16-jun-2025 12:00 local. Dias habiles transcurridos: 11.
        # 2 tareas a tiempo, sin errores -> 2 / 11 = 0.18
        due = timezone.make_aware(datetime(2025, 6, 16, 18))
        for _ in range(2):
            self._tarea(due, FROZEN_NOW)
        self.assertEqual(self.employee.calculate_ipac(2025, 6), Decimal('0.18'))


class SugerenciasTest(TestCase):
    """La tarjeta 'Cómo mejorar su bono' y el email semanal comparten
    employees.sugerencias.build_sugerencias."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.employee = Employee.objects.create(user=self.user, name='Test Employee',
                                                email='test@example.com', hire_date=date(2024, 1, 1))
        self.kpi_prod = KPI.objects.create(name="Productividad General",
                                           measurement_type='percentage', target_value=Decimal('95.00'))
        self.kpi_err = KPI.objects.create(name="Calidad Administrativa",
                                          measurement_type='count_lt', target_value=Decimal('2.00'))
        self.kpi_pub = KPI.objects.create(name="Publicaciones",
                                          measurement_type='count_gt', target_value=Decimal('5.00'))
        BonusRule.objects.create(kpi=self.kpi_prod, bonus_amount=Decimal('50.00'))
        BonusRule.objects.create(kpi=self.kpi_err, bonus_amount=Decimal('30.00'))
        BonusRule.objects.create(kpi=self.kpi_pub, bonus_amount=Decimal('100.00'))
        self.profile = JobProfile.objects.create(name='Perfil Test')
        self.profile.kpis.add(self.kpi_prod, self.kpi_err, self.kpi_pub)
        self.employee.profile = self.profile
        self.employee.save()

        self.board = TaskBoard.objects.create(employee=self.employee, name="Board")
        self.list_todo = TaskList.objects.create(board=self.board, name="Pendiente", order=1)
        self.list_done = TaskList.objects.create(board=self.board, name="Hecho", order=2)

    def _por_titulo(self, sugerencias, titulo):
        return next(s for s in sugerencias if s['titulo'] == titulo)

    def test_sugerencias_por_kpi(self):
        due = timezone.make_aware(datetime(2024, 8, 15))
        # Productividad: 1 de 2 completada -> accion
        Task.objects.create(list=self.list_done, assigned_to=self.employee, kpi=self.kpi_prod,
                            title="A", order=0, due_date=due,
                            completed_at=timezone.make_aware(datetime(2024, 8, 14, 12)))
        Task.objects.create(list=self.list_todo, assigned_to=self.employee, kpi=self.kpi_prod,
                            title="B", order=1, due_date=due)
        # Calidad: 1 error con maximo 1 permitido -> warning al limite
        ManualKpiEntry.objects.create(employee=self.employee, kpi=self.kpi_err,
                                      date=date(2024, 8, 10), value=1)
        # Publicaciones: 3 de 5 -> faltan 2
        for _ in range(3):
            Task.objects.create(list=self.list_done, assigned_to=self.employee, kpi=self.kpi_pub,
                                title="P", order=0, due_date=due,
                                completed_at=timezone.make_aware(datetime(2024, 8, 14, 12)))

        sugerencias = build_sugerencias(self.employee, 2024, 8)
        tipos = [s['tipo'] for s in sugerencias]
        # El warning (al limite) va primero
        self.assertEqual(tipos[0], 'warning')

        s_prod = self._por_titulo(sugerencias, 'Productividad General')
        self.assertEqual(s_prod['tipo'], 'action')
        self.assertIn('Le quedan 1 de 2 tareas', s_prod['detalle'])

        s_err = self._por_titulo(sugerencias, 'Calidad Administrativa')
        self.assertEqual(s_err['tipo'], 'warning')
        self.assertEqual(s_err['monto'], Decimal('30.00'))

        s_pub = self._por_titulo(sugerencias, 'Publicaciones')
        self.assertEqual(s_pub['tipo'], 'action')
        self.assertIn('Le faltan 2', s_pub['detalle'])

    def test_sugerencias_lenguaje_formal_de_usted(self):
        """Los mensajes van dirigidos de usted: sin formas de tú."""
        due = timezone.make_aware(datetime(2024, 8, 15))
        Task.objects.create(list=self.list_todo, assigned_to=self.employee, kpi=self.kpi_prod,
                            title="B", order=1, due_date=due)
        ManualKpiEntry.objects.create(employee=self.employee, kpi=self.kpi_err,
                                      date=date(2024, 8, 10), value=1)
        for sugerencia in build_sugerencias(self.employee, 2024, 8):
            for informal in ('Te quedan', 'Te faltan', 'tus tareas', 'Completaste',
                             'Llevas ', 'tu IPAC', 'tu bono'):
                self.assertNotIn(informal, sugerencia['detalle'])

    def test_sugerencias_bono_perdido(self):
        # 2 errores con target 2 -> bono perdido
        ManualKpiEntry.objects.create(employee=self.employee, kpi=self.kpi_err,
                                      date=date(2024, 8, 10), value=1)
        ManualKpiEntry.objects.create(employee=self.employee, kpi=self.kpi_err,
                                      date=date(2024, 8, 20), value=1)
        sugerencias = build_sugerencias(self.employee, 2024, 8)
        s_err = self._por_titulo(sugerencias, 'Calidad Administrativa')
        self.assertEqual(s_err['tipo'], 'lost')

    def test_sugerencias_sin_perfil(self):
        self.employee.profile = None
        self.employee.save()
        self.assertEqual(build_sugerencias(self.employee, 2024, 8), [])

    def test_coaching_semanal_dry_run(self):
        from django.core.management import call_command
        from io import StringIO
        ManualKpiEntry.objects.create(employee=self.employee, kpi=self.kpi_err,
                                      date=date.today(), value=1)
        out = StringIO()
        call_command('coaching_semanal', '--dry-run', stdout=out)
        self.assertIn('DRY RUN', out.getvalue())


class TaskApiPermissionsTest(TestCase):
    """Anti-gaming IPAC: los empleados no pueden auto-crearse tareas ni
    editar due_date. Solo pueden moverlas en su tablero (y con ello
    completarlas)."""

    def setUp(self):
        self.user = User.objects.create_user(username='empleado', password='password')
        self.employee = Employee.objects.create(user=self.user, name='Empleado',
                                                email='emp@example.com', hire_date=date(2024, 1, 1))
        self.boss = User.objects.create_superuser('boss', 'boss@example.com', 'password')
        self.board = TaskBoard.objects.create(employee=self.employee, name="Board")
        self.list_todo = TaskList.objects.create(board=self.board, name="Pendiente", order=1)
        self.list_done = TaskList.objects.create(board=self.board, name="Hecho", order=2)
        self.task = Task.objects.create(list=self.list_todo, assigned_to=self.employee,
                                        title="Tarea RH", order=0,
                                        due_date=timezone.make_aware(datetime(2024, 8, 15)))

    def test_empleado_no_puede_crear_tareas(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.post('/api/tasks/', {
            'title': 'Tarea inflada', 'list': self.list_done.id,
            'assigned_to': self.employee.id, 'order': 0}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Task.objects.filter(title='Tarea inflada').exists())

    def test_empleado_no_puede_editar_ni_borrar(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.patch(f'/api/tasks/{self.task.id}/',
                                {'due_date': '2030-12-31T12:00:00'}, format='json')
        self.assertEqual(response.status_code, 403)
        response = client.delete(f'/api/tasks/{self.task.id}/')
        self.assertEqual(response.status_code, 403)
        self.task.refresh_from_db()
        self.assertEqual(self.task.due_date.year, 2024)

    def test_empleado_puede_mover_tareas(self):
        # Mover a "Hecho" es el flujo normal del tablero: debe seguir abierto.
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.post(f'/api/tasks/{self.task.id}/move/',
                               {'list_id': self.list_done.id, 'order': 0}, format='json')
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.completed_at)

    def test_supervisor_puede_crear_tareas(self):
        client = APIClient()
        client.force_authenticate(user=self.boss)
        response = client.post('/api/tasks/', {
            'title': 'Tarea de RH', 'list': self.list_todo.id,
            'assigned_to': self.employee.id, 'order': 0,
            'due_date': '2024-08-20T12:00:00'}, format='json')
        self.assertEqual(response.status_code, 201)


class SugerenciaIpacSinFechaTest(TestCase):
    """Si todas las tareas completadas carecen de fecha, la sugerencia lo
    dice en vez de fingir puntualidad del 100%."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.employee = Employee.objects.create(user=self.user, name='Test Employee',
                                                email='test@example.com', hire_date=date(2024, 1, 1))
        self.kpi_ipac = KPI.objects.create(name="IPAC", measurement_type='composite_ipac',
                                           target_value=Decimal('1.20'))
        BonusRule.objects.create(kpi=self.kpi_ipac, bonus_amount=Decimal('50.00'))
        self.profile = JobProfile.objects.create(name='Perfil Test')
        self.profile.kpis.add(self.kpi_ipac)
        self.employee.profile = self.profile
        self.employee.save()
        self.board = TaskBoard.objects.create(employee=self.employee, name="Board")
        self.list_done = TaskList.objects.create(board=self.board, name="Hecho", order=1)

    def test_info_cuando_todas_sin_fecha(self):
        Task.objects.create(list=self.list_done, assigned_to=self.employee,
                            title="S/F", order=0,
                            completed_at=timezone.make_aware(datetime(2024, 8, 14, 12)))
        sugerencia = build_sugerencias(self.employee, 2024, 8)[0]
        self.assertEqual(sugerencia['tipo'], 'info')
        self.assertIn('no tienen fecha', sugerencia['detalle'])

    def test_errores_mencionan_factor_calidad(self):
        # 2 tareas (1 a tiempo) + 2 errores -> factor calidad 0: la sugerencia
        # debe explicar que los errores anulan el indice y como recuperarlo.
        kpi_err = KPI.objects.create(name="Calidad Administrativa",
                                     measurement_type='count_lt', target_value=Decimal('2.00'))
        due = timezone.make_aware(datetime(2024, 8, 15))
        Task.objects.create(list=self.list_done, assigned_to=self.employee,
                            title="A", order=0, due_date=due,
                            completed_at=timezone.make_aware(datetime(2024, 8, 14, 12)))
        Task.objects.create(list=self.list_done, assigned_to=self.employee,
                            title="B", order=1, due_date=due,
                            completed_at=timezone.make_aware(datetime(2024, 8, 20, 12)))
        for _ in range(2):
            ManualKpiEntry.objects.create(employee=self.employee, kpi=kpi_err,
                                          date=date(2024, 8, 10), value=1)
        sugerencia = build_sugerencias(self.employee, 2024, 8)[0]
        self.assertEqual(sugerencia['tipo'], 'action')
        self.assertIn('errores registrados', sugerencia['detalle'])
        self.assertIn('factor calidad 0.00', sugerencia['detalle'])
        self.assertIn('sin errores nuevos lo recupera', sugerencia['detalle'])
        # Con calidad 0 el "subiria de X a ~Y" no aporta: no debe incluirlo.
        self.assertNotIn('subiría', sugerencia['detalle'])
