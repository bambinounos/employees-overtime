from django.contrib import admin
from .models import CalendarEvent


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'start_date', 'end_date', 'task', 'alarm_minutes')
    list_filter = ('user', 'start_date')
    search_fields = ('title', 'user__username', 'uid')
    readonly_fields = ('uid',)
    date_hierarchy = 'start_date'
