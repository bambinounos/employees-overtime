import calendar
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient
from .models import (
    Employee, Salary, WorkLog, KPI, BonusRule, TaskBoard, TaskList, Task,
    ManualKpiEntry, EmployeePerformanceRecord
)
from decimal import Decimal
from datetime import date, datetime, timedelta
from django.utils import timezone

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

    def test_recurring_task_generation(self):
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

    def test_idempotent_task_generation(self):
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

    def test_superuser_generates_tasks_for_specific_employee(self):
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

        # Create KPI and Bonus Rule
        self.kpi = KPI.objects.create(name='Test KPI', measurement_type='count_gt', target_value=10)
        BonusRule.objects.create(kpi=self.kpi, bonus_amount=Decimal('200.00'), description='Test Bonus')

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
