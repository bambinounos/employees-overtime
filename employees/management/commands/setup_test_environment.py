import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from employees.models import Employee, TaskBoard, TaskList, Task

class Command(BaseCommand):
    help = 'Sets up the database with a test user and task board for verification'

    def handle(self, *args, **options):
        self.stdout.write("Setting up the test environment...")

        # 1. Create a test user with staff permissions
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={
                'first_name': 'Test',
                'last_name': 'User',
                'email': 'test@example.com',
                'is_staff': True,
                'is_superuser': True, # Grant superuser for API simplicity in test
            }
        )
        if created:
            user.set_password('password')
            user.save()
            self.stdout.write(self.style.SUCCESS("Successfully created user 'testuser'"))
        else:
            if not user.is_superuser:
                user.is_superuser = True
                user.save()
            self.stdout.write("User 'testuser' already exists.")

        # 2. Create an Employee profile
        employee, created = Employee.objects.get_or_create(
            user=user,
            defaults={
                'name': 'Test User',
                'email': 'test@example.com',
                'hire_date': datetime.date(2023, 1, 1)
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Successfully created employee profile"))
        else:
            self.stdout.write("Employee profile already exists.")

        # 3. Create TaskBoard and default lists
        board, board_created = TaskBoard.objects.get_or_create(
            employee=employee,
            defaults={'name': f"Tablero de {employee.name}"}
        )

        TaskList.objects.get_or_create(board=board, name="Pendiente", defaults={'order': 1})
        TaskList.objects.get_or_create(board=board, name="En Progreso", defaults={'order': 2})
        TaskList.objects.get_or_create(board=board, name="Hecho", defaults={'order': 3})

        if board_created:
            self.stdout.write(self.style.SUCCESS("Successfully created task board"))
        else:
            self.stdout.write("Task board already exists.")

        # Clear any old test tasks to ensure a clean slate
        Task.objects.filter(assigned_to=employee).delete()
        self.stdout.write(self.style.SUCCESS("Cleared any pre-existing tasks for the test user."))
        self.stdout.write(self.style.SUCCESS("Test environment setup is complete."))