from django.db import models
from django.contrib.auth.models import User
from datetime import date
from decimal import Decimal

class Employee(models.Model):
    """Represents an employee in the company."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    hire_date = models.DateField()

    def __str__(self):
        return self.name

    def calculate_salary(self, year, month):
        """Calculates the salary for a given month and year."""
        try:
            base_salary = self.salary.base_amount
        except Salary.DoesNotExist:
            return 0

        work_logs = WorkLog.objects.filter(employee=self, date__year=year, date__month=month)

        total_hours_worked = sum(log.hours_worked for log in work_logs)
        total_overtime_hours = sum(log.overtime_hours for log in work_logs)

        # Assuming 22 working days in a month and 8 hours per day
        monthly_hours = 22 * 8
        hourly_rate = base_salary / Decimal(monthly_hours)
        overtime_rate = hourly_rate * Decimal(1.5)

        regular_pay = total_hours_worked * hourly_rate
        overtime_pay = total_overtime_hours * overtime_rate

        total_salary = regular_pay + overtime_pay

        return total_salary

class Salary(models.Model):
    """Represents the base salary for an employee."""
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, primary_key=True)
    base_amount = models.DecimalField(max_digits=10, decimal_places=2)
    effective_date = models.DateField()

    def __str__(self):
        return f"{self.employee.name} - ${self.base_amount}"

class WorkLog(models.Model):
    """Logs the hours worked and overtime for an employee on a specific day."""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.DateField()
    hours_worked = models.DecimalField(max_digits=4, decimal_places=2, default=8)
    overtime_hours = models.DecimalField(max_digits=4, decimal_places=2, default=0)

    class Meta:
        unique_together = ('employee', 'date')

    def __str__(self):
        return f"{self.employee.name} on {self.date}"
