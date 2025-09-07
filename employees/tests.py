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
from datetime import date, datetime
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
        total_salary = self.employee.calculate_salary(2024, 8)
        self.assertEqual(total_salary, Decimal('525.00'))

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
