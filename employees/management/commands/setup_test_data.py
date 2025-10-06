from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from employees.models import Employee, TaskBoard, TaskList

class Command(BaseCommand):
    help = 'Sets up the initial data required for frontend verification'

    def handle(self, *args, **options):
        # 1. Create the test user
        user, user_created = User.objects.get_or_create(
            username='testuser',
            defaults={'is_staff': True, 'is_superuser': False}
        )
        if user_created:
            user.set_password('password')
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Successfully created user: {user.username}'))
        else:
            self.stdout.write(self.style.WARNING(f'User {user.username} already exists.'))

        # 2. Create the employee profile
        employee, employee_created = Employee.objects.get_or_create(
            user=user,
            defaults={
                'name': 'Test Employee',
                'email': 'test@example.com',
                'hire_date': '2024-01-01'
            }
        )
        if employee_created:
            self.stdout.write(self.style.SUCCESS(f'Successfully created employee: {employee.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'Employee for {user.username} already exists.'))

        # 3. Create the task board and lists
        board, board_created = TaskBoard.objects.get_or_create(
            employee=employee,
            defaults={'name': f"Tablero de {employee.name}"}
        )
        if board_created:
            TaskList.objects.create(board=board, name="Pendiente", order=1)
            TaskList.objects.create(board=board, name="En Progreso", order=2)
            TaskList.objects.create(board=board, name="Hecho", order=3)
            self.stdout.write(self.style.SUCCESS(f'Successfully created task board and lists for {employee.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'Task board for {employee.name} already exists.'))

        self.stdout.write(self.style.SUCCESS('Test data setup complete.'))