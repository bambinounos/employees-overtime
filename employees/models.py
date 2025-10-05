from django.db import models
from django.contrib.auth.models import User
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import F, Avg, Sum
from django.db.models.functions import Coalesce

class Employee(models.Model):
    """Represents an employee in the company."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    hire_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.name

    def calculate_ipac(self, year, month):
        """
        Calculates the Quality-Adjusted Productivity Index (IPAC) for a given month.
        IPAC = (Completed Tasks * On-time Factor * Quality Factor) / Avg. Execution Time (in hours)
        """
        # 1. Get all tasks completed in the given month and year
        completed_tasks = Task.objects.filter(
            assigned_to=self,
            completed_at__year=year,
            completed_at__month=month
        )
        num_completed_tasks = completed_tasks.count()

        if num_completed_tasks == 0:
            return Decimal('0.00')

        # 2. On-time Factor (considers tasks with a due date)
        tasks_with_due_date = completed_tasks.exclude(due_date__isnull=True)
        num_tasks_with_due_date = tasks_with_due_date.count()
        if num_tasks_with_due_date > 0:
            on_time_count = tasks_with_due_date.filter(completed_at__date__lte=F('due_date')).count()
            on_time_factor = Decimal(on_time_count) / Decimal(num_tasks_with_due_date)
        else:
            on_time_factor = Decimal('1.0') # Assume 100% if no due dates are set

        # 3. Quality Factor (based on manually logged errors)
        # This assumes that any KPI measured as 'count_lt' (less is better) is an error-tracking KPI.
        error_kpis = KPI.objects.filter(measurement_type='count_lt')
        num_errors = ManualKpiEntry.objects.filter(
            employee=self,
            kpi__in=error_kpis,
            date__year=year,
            date__month=month
        ).aggregate(total_errors=Coalesce(Sum('value'), Decimal('0')))['total_errors']

        error_rate = Decimal(num_errors) / Decimal(num_completed_tasks)
        quality_factor = max(Decimal('0.0'), Decimal('1.0') - error_rate)

        # 4. Average Execution Time (in hours)
        avg_duration = completed_tasks.aggregate(
            avg_duration=Avg(F('completed_at') - F('created_at'))
        )['avg_duration']

        if not avg_duration:
            avg_duration = timedelta(hours=1) # Fallback to 1 hour to prevent errors

        avg_execution_hours = Decimal(avg_duration.total_seconds()) / Decimal('3600')

        # Prevent division by zero or extremely small denominators
        MIN_AVG_HOURS = Decimal('0.01') # ~36 seconds
        if avg_execution_hours < MIN_AVG_HOURS:
            avg_execution_hours = MIN_AVG_HOURS

        # 5. Final IPAC Calculation
        # The formula provided is: (Tareas Completadas × Puntualidad % × (100% - % Errores)) / Tiempo Promedio
        # To make the scale reasonable, we use factors (0-1) and the raw number of tasks.
        numerator = Decimal(num_completed_tasks) * on_time_factor * quality_factor
        ipac_score = numerator / avg_execution_hours

        return ipac_score.quantize(Decimal('0.01'))

    def calculate_performance_bonus(self, year, month):
        """
        Calculates the total performance bonus for a given employee, year, and month.
        It also creates EmployeePerformanceRecord entries for each KPI.
        """
        total_bonus = Decimal('0.00')
        all_bonus_rules = BonusRule.objects.all().select_related('kpi')

        # Use the last day of the month for the record date
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        record_date = date(year, month, last_day)

        for rule in all_bonus_rules:
            kpi = rule.kpi
            target_met = False
            actual_value = 0

            # --- Evaluate KPI based on its measurement type ---

            if kpi.measurement_type == 'percentage':
                # e.g., "Productividad General"
                tasks = Task.objects.filter(assigned_to=self, kpi=kpi, due_date__year=year, due_date__month=month)
                total_tasks = tasks.count()
                if total_tasks > 0:
                    completed_tasks = tasks.filter(completed_at__isnull=False, list__name__iexact="Hecho").count()
                    actual_value = (completed_tasks / total_tasks) * 100
                    if actual_value >= kpi.target_value:
                        target_met = True

            elif kpi.measurement_type == 'count_lt':
                # e.g., "Calidad Administrativa" (fewer than X errors)
                entries = ManualKpiEntry.objects.filter(employee=self, kpi=kpi, date__year=year, date__month=month)
                actual_value = sum(entry.value for entry in entries)
                if actual_value < kpi.target_value:
                    target_met = True

            elif kpi.measurement_type == 'count_gt':
                # e.g., "Gestión Comercial Pública" (more than X offers)
                # Automated based on completed tasks with this KPI
                actual_value = Task.objects.filter(
                    assigned_to=self,
                    kpi=kpi,
                    completed_at__year=year,
                    completed_at__month=month
                ).count()
                if actual_value >= kpi.target_value:
                    target_met = True

            elif kpi.measurement_type == 'composite_ipac':
                # This KPI is calculated by its own complex method
                actual_value = self.calculate_ipac(year, month)
                # For composite KPIs, higher is better
                if actual_value >= kpi.target_value:
                    target_met = True

            # --- Award bonus and save record ---

            bonus_awarded = rule.bonus_amount if target_met else Decimal('0.00')
            if target_met:
                total_bonus += rule.bonus_amount

            EmployeePerformanceRecord.objects.update_or_create(
                employee=self,
                kpi=kpi,
                date=record_date,
                defaults={
                    'actual_value': actual_value,
                    'target_met': target_met,
                    'bonus_awarded': bonus_awarded
                }
            )

        return total_bonus

    def calculate_salary(self, year, month):
        """
        Calculates the final salary for a given month and year, including base pay,
        overtime, and performance bonus.
        Returns a dictionary with a detailed breakdown of the salary.
        """
        try:
            base_salary = self.salary.base_amount
        except Salary.DoesNotExist:
            return None # Return None if no base salary is set

        # 1. Calculate pay from worked hours and overtime
        work_logs = WorkLog.objects.filter(employee=self, date__year=year, date__month=month)
        total_hours_worked = sum(log.hours_worked for log in work_logs)
        total_overtime_hours = sum(log.overtime_hours for log in work_logs)

        # Load company settings to determine the basis for salary calculation
        settings = CompanySettings.load()
        monthly_hours = Decimal('0.00')
        work_days_in_month = 0

        if settings.calculation_basis == 'monthly':
            monthly_hours = settings.base_hours
        elif settings.calculation_basis == 'weekly':
            # Approximate monthly hours by multiplying by the average number of weeks in a month
            monthly_hours = settings.base_hours * Decimal('4.333')
        elif settings.calculation_basis == 'daily':
            # Calculate the number of working days (Mon-Fri) in the given month and year
            import calendar
            cal = calendar.Calendar()
            for day in cal.itermonthdays2(year, month):
                if day[0] != 0 and day[1] < 5: # day[1] is the weekday (0=Mon, 6=Sun)
                    work_days_in_month += 1
            monthly_hours = settings.base_hours * Decimal(work_days_in_month)

        if monthly_hours <= 0:
             # Fallback to a default if hours are not set, to avoid division by zero
            monthly_hours = Decimal('160')

        hourly_rate = base_salary / monthly_hours
        overtime_rate = hourly_rate * Decimal(1.5)

        work_pay = total_hours_worked * hourly_rate
        overtime_pay = total_overtime_hours * overtime_rate

        # 2. Calculate performance bonus
        performance_bonus = self.calculate_performance_bonus(year, month)

        # 3. Calculate final total salary
        total_salary = work_pay + overtime_pay + performance_bonus

        # 4. Return a detailed dictionary
        return {
            'base_salary': base_salary,
            'work_pay': work_pay,
            'overtime_pay': overtime_pay,
            'performance_bonus': performance_bonus,
            'total_salary': total_salary,
            'total_hours_worked': total_hours_worked,
            'total_overtime_hours': total_overtime_hours,
            'hourly_rate': hourly_rate,
            'overtime_rate': overtime_rate,
            'calculation_basis': settings.calculation_basis,
            'base_hours': settings.base_hours,
            'monthly_hours': monthly_hours,
            'work_days_in_month': work_days_in_month,
        }

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

# --- Trello-like & Performance Management Models ---

class KPI(models.Model):
    """Key Performance Indicator."""
    name = models.CharField(max_length=255, help_text="E.g., Productividad General")
    description = models.TextField(blank=True, help_text="E.g., Porcentaje de tareas completadas a tiempo.")

    MEASUREMENT_CHOICES = [
        ('percentage', 'Percentage'),
        ('count_lt', 'Count (Less Than)'),
        ('count_gt', 'Count (Greater Than)'),
        ('composite_ipac', 'Composite IPAC'),
    ]
    measurement_type = models.CharField(max_length=20, choices=MEASUREMENT_CHOICES)
    target_value = models.DecimalField(max_digits=10, decimal_places=2, help_text="E.g., 95 for percentage, 3 for count.")
    is_warning_kpi = models.BooleanField(default=False, help_text="Check if this KPI represents a disciplinary warning that should trigger an email.")

    def __str__(self):
        return self.name

class BonusRule(models.Model):
    """Rule that links a KPI to a bonus amount."""
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE)
    bonus_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount of the bonus if the KPI target is met.")
    description = models.CharField(max_length=255, help_text="E.g., 'Completar >= 95% de las tareas'")

    def __str__(self):
        return f"{self.kpi.name} - ${self.bonus_amount}"

class TaskBoard(models.Model):
    """A board for an employee's tasks."""
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class TaskList(models.Model):
    """A list (column) on a task board."""
    board = models.ForeignKey(TaskBoard, related_name='lists', on_delete=models.CASCADE)
    name = models.CharField(max_length=255, help_text="E.g., Pendiente, En Progreso, Hecho")
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.name} ({self.board.employee.name})"

class Task(models.Model):
    """A task (card) on a task list."""
    RECURRENCE_CHOICES = [
        ('daily', 'Daily'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('unfulfilled', 'Unfulfilled'),
    ]

    list = models.ForeignKey(TaskList, related_name='tasks', on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(Employee, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tasks', null=True)
    kpi = models.ForeignKey(KPI, on_delete=models.SET_NULL, null=True, blank=True, help_text="The KPI this task contributes to.")

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField()
    due_date = models.DateTimeField(null=True, blank=True)  # Changed to DateTimeField
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending') # New status field
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by_manager = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Recurrence fields
    is_recurring = models.BooleanField(default=False)
    recurrence_frequency = models.CharField(max_length=10, choices=RECURRENCE_CHOICES, null=True, blank=True)
    recurrence_end_date = models.DateField(null=True, blank=True)

    # For tracking the chain of recurring tasks
    parent_task = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')


    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title

class Checklist(models.Model):
    """A checklist within a task."""
    task = models.ForeignKey(Task, related_name='checklists', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)

    def __str__(self):
        return self.title

class ChecklistItem(models.Model):
    """An item in a checklist."""
    checklist = models.ForeignKey(Checklist, related_name='items', on_delete=models.CASCADE)
    text = models.CharField(max_length=255)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return self.text

class Comment(models.Model):
    """A comment on a task."""
    task = models.ForeignKey(Task, related_name='comments', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user.username} on {self.task.title}"

class EmployeePerformanceRecord(models.Model):
    """A record of an employee's performance for a specific KPI in a given month."""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE)
    date = models.DateField(help_text="The month and year this record applies to (e.g., 2024-08-31).")
    actual_value = models.DecimalField(max_digits=10, decimal_places=2, help_text="The measured performance value.")
    target_met = models.BooleanField(default=False, help_text="Was the KPI target met for this period?")
    bonus_awarded = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ('employee', 'kpi', 'date')

    def __str__(self):
        return f"{self.employee.name} - {self.kpi.name} - {self.date.strftime('%Y-%m')}"

class ManualKpiEntry(models.Model):
    """Represents a single, manually logged data point for a KPI."""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    kpi = models.ForeignKey(KPI, on_delete=models.CASCADE, help_text="The KPI this entry is for, e.g., 'Calidad Administrativa'.")
    date = models.DateField(default=date.today, help_text="Date the event occurred.")
    value = models.DecimalField(max_digits=10, decimal_places=2, default=1, help_text="The value of the entry, e.g., '1' for one error.")
    notes = models.TextField(blank=True, help_text="Additional context or comments.")

    def __str__(self):
        return f"Entry for {self.employee.name} regarding {self.kpi.name} on {self.date}"

class CompanySettings(models.Model):
    """Singleton model to store company-wide settings."""
    name = models.CharField(max_length=255, default="Default Settings", unique=True)

    CALCULATION_BASIS_CHOICES = [
        ('monthly', 'Monthly'),
        ('weekly', 'Weekly'),
        ('daily', 'Daily'),
    ]
    calculation_basis = models.CharField(
        max_length=10,
        choices=CALCULATION_BASIS_CHOICES,
        default='monthly',
        help_text="The basis for salary calculation (e.g., monthly, weekly, or daily hours)."
    )
    base_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=160.00,
        help_text="The number of base hours corresponding to the selected calculation basis."
    )

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Enforce a single instance of settings
        self.pk = 1
        super(CompanySettings, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        # Convenience method to get the single settings object
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

class SiteConfiguration(models.Model):
    """Singleton model to store site-wide configuration, like the favicon."""
    favicon = models.ImageField(upload_to='favicons/', null=True, blank=True, help_text="Upload a custom favicon for the site.")

    def __str__(self):
        return "Site Configuration"

    def save(self, *args, **kwargs):
        # Enforce a single instance of settings
        self.pk = 1
        super(SiteConfiguration, self).save(*args, **kwargs)

    @classmethod
    def load(cls):
        # Convenience method to get the single settings object
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
