from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from caldav.models import CalendarEvent

@login_required
def calendar(request):
    events = CalendarEvent.objects.filter(user=request.user)
    context = {
        'events': events,
    }
    return render(request, 'caldav/calendar.html', context)
