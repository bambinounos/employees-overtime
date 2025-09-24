from django.db import models
from django.contrib.auth.models import User
from employees.models import Task

class CalendarEvent(models.Model):
    """Represents a calendar event."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    description = models.TextField(blank=True)
    is_personal = models.BooleanField(default=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, blank=True)
    alarm_minutes = models.IntegerField(null=True, blank=True, help_text="Minutes before the event to trigger an alarm.")
    uid = models.CharField(max_length=255, unique=True, null=True, blank=True)

    def __str__(self):
        return self.title
