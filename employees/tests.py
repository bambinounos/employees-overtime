from django.test import TestCase
from django.contrib.auth.models import User
from .models import Employee, Salary, WorkLog
from decimal import Decimal
from datetime import date

class EmployeeModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.employee = Employee.objects.create(name='Test Employee', email='test@example.com', hire_date=date(2023, 1, 1))
        self.salary = Salary.objects.create(employee=self.employee, base_amount=Decimal('3520.00'), effective_date=date(2023, 1, 1))

    def test_calculate_salary(self):
        # Create some work logs for a specific month
        WorkLog.objects.create(employee=self.employee, date=date(2023, 1, 2), hours_worked=8, overtime_hours=0)
        WorkLog.objects.create(employee=self.employee, date=date(2023, 1, 3), hours_worked=8, overtime_hours=2)
        WorkLog.objects.create(employee=self.employee, date=date(2023, 1, 4), hours_worked=8, overtime_hours=1)

        # Expected calculation:
        # Base salary: 3520
        # Monthly hours: 22 * 8 = 176
        # Hourly rate: 3520 / 176 = 20
        # Overtime rate: 20 * 1.5 = 30
        #
        # Regular pay: (8 + 8 + 8) * 20 = 24 * 20 = 480
        # Overtime pay: (0 + 2 + 1) * 30 = 3 * 30 = 90
        # Total salary: 480 + 90 = 570

        calculated_salary = self.employee.calculate_salary(2023, 1)
        self.assertEqual(calculated_salary, Decimal('570.00'))

class ViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.login(username='testuser', password='password')
        self.employee = Employee.objects.create(name='Test Employee', email='test@example.com', hire_date=date(2023, 1, 1))

    def test_index_view(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_employee_list_view(self):
        response = self.client.get('/employees/')
        self.assertEqual(response.status_code, 200)

    # def test_employee_calendar_view(self):
    #     response = self.client.get(f'/employees/{self.employee.id}/calendar/')
    #     self.assertEqual(response.status_code, 200)

    def test_employee_salary_view(self):
        response = self.client.get(f'/employees/{self.employee.id}/salary/')
        self.assertEqual(response.status_code, 200)
