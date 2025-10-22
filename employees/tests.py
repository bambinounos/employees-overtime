import calendar
from django.test import TestCase
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
        for i in range(9):
            Task.objects.create(list=self.list_done, assigned_to=self.employee, kpi=self.kpi_tasks, title=f"Task {i}", order=i, due_date=date(2024, 8, 15), completed_at=timezone.now())
        Task.objects.create(list=self.list_todo, assigned_to=self.employee, kpi=self.kpi_tasks, title="Task 10", order=10, due_date=date(2024, 8, 15))

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
        start_date = date.today() - timedelta(days=10)
        end_date = date.today() + timedelta(days=20)
        task_data = {
            'title': 'Weekly Report',
            'list': self.task_list.id,
            'assigned_to': self.employee.id,
            'order': 1,
            'is_recurring': True,
            'recurrence_frequency': 'weekly',
            'due_date': start_date,
            'recurrence_end_date': end_date
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
