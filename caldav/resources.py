from django.contrib.auth.models import User
from wsgidav.dav_provider import DAVCollection, DAVNonCollection
from caldav.models import CalendarEvent
import vobject
from datetime import timedelta
import hashlib

class RootCollection(DAVCollection):
    def __init__(self, path, environ):
        super().__init__(path, environ)

    def get_member_names(self):
        # Only list the authenticated user's calendar
        if self.environ.get("wsgidav.auth.user_name"):
            return [self.environ["wsgidav.auth.user_name"]]
        return []

    def get_member(self, name):
        # Return a calendar resource for the given user, only if authenticated
        auth_user = self.environ.get("wsgidav.auth.user_name")
        if auth_user and name == auth_user:
            try:
                user = User.objects.get(username=name)
                return UserCalendarCollection(f"/{name}", self.environ, user)
            except User.DoesNotExist:
                return None
        return None

class UserCalendarCollection(DAVCollection):
    def __init__(self, path, environ, user):
        super().__init__(path, environ)
        self.user = user

    def get_member_names(self):
        # Return a list of calendar events for this user
        events = CalendarEvent.objects.filter(user=self.user)
        return [f"{event.id}.ics" for event in events]

    def get_member(self, name):
        # Return a calendar event resource
        try:
            event_id = int(name.replace(".ics", ""))
            event = CalendarEvent.objects.get(id=event_id, user=self.user)
            return CalendarEventResource(f"{self.path}/{name}", self.environ, event)
        except (ValueError, CalendarEvent.DoesNotExist):
            return None

    def put(self, name, data, content_type):
        # This method handles PUT requests to create or update events.
        cal = vobject.readOne(data.read().decode('utf-8'))
        vevent = cal.vevent

        uid = vevent.uid.value
        title = vevent.summary.value
        start_date = vevent.dtstart.value
        end_date = vevent.dtend.value
        description = vevent.description.value if hasattr(vevent, 'description') else ""

        alarm_minutes = None
        if hasattr(vevent, 'valarm'):
            trigger = vevent.valarm.trigger.value
            if isinstance(trigger, timedelta):
                alarm_minutes = int(abs(trigger.total_seconds()) / 60)

        event, created = CalendarEvent.objects.update_or_create(
            uid=uid,
            user=self.user,
            defaults={
                'title': title,
                'start_date': start_date,
                'end_date': end_date,
                'description': description,
                'alarm_minutes': alarm_minutes,
            }
        )

        # Bidirectional sync: propagate date changes back to the linked Task
        if event.task_id:
            task = event.task
            if task.due_date != start_date:
                task.due_date = start_date
                task._skip_calendar_sync = True  # Prevent signal from re-updating CalendarEvent
                task.save(update_fields=['due_date'])

        return CalendarEventResource(f"{self.path}/{event.id}.ics", self.environ, event)

class CalendarEventResource(DAVNonCollection):
    def __init__(self, path, environ, event):
        super().__init__(path, environ)
        self.event = event

    def support_etag(self):
        return True

    def get_etag(self):
        content = self.get_content()
        if isinstance(content, str):
            content = content.encode('utf-8')
        return hashlib.md5(content).hexdigest()

    def get_content_type(self):
        return "text/calendar"

    def get_content_length(self):
        return len(self.get_content().read())

    def get_content(self):
        cal = vobject.iCalendar()
        vevent = cal.add('vevent')
        vevent.add('summary').value = self.event.title
        vevent.add('dtstart').value = self.event.start_date
        vevent.add('dtend').value = self.event.end_date
        vevent.add('description').value = self.event.description

        if self.event.alarm_minutes:
            valarm = vevent.add('valarm')
            valarm.add('action').value = 'DISPLAY'
            valarm.add('description').value = self.event.title
            trigger = f"-PT{self.event.alarm_minutes}M"
            valarm.add('trigger').value = trigger

        return cal.serialize()