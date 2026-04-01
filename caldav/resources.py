from django.contrib.auth.models import User
from wsgidav.dav_provider import DAVCollection, DAVNonCollection
from caldav.models import CalendarEvent
import vobject
from datetime import timedelta
import hashlib
import logging
import uuid

logger = logging.getLogger(__name__)


class RootCollection(DAVCollection):
    """Root: / — lists authenticated user's principal."""
    def __init__(self, path, environ):
        super().__init__(path, environ)

    def get_member_names(self):
        if self.environ.get("wsgidav.auth.user_name"):
            return [self.environ["wsgidav.auth.user_name"]]
        return []

    def get_member(self, name):
        auth_user = self.environ.get("wsgidav.auth.user_name")
        if auth_user and name == auth_user:
            try:
                user = User.objects.get(username=name)
                return UserPrincipal(f"/{name}", self.environ, user)
            except User.DoesNotExist:
                return None
        return None


class UserPrincipal(DAVCollection):
    """Principal: /username/ — lists the user's calendars (just one: 'default')."""
    def __init__(self, path, environ, user):
        super().__init__(path, environ)
        self.user = user

    def get_member_names(self):
        return ['default']

    def get_member(self, name):
        if name == 'default':
            return CalendarCollection(f"{self.path}/default", self.environ, self.user)
        return None


class CalendarCollection(DAVCollection):
    """Calendar: /username/default/ — contains the actual events."""
    def __init__(self, path, environ, user):
        super().__init__(path, environ)
        self.user = user

    def get_member_names(self):
        events = CalendarEvent.objects.filter(user=self.user)
        return [f"{event.id}.ics" for event in events]

    def get_member(self, name):
        try:
            event_id = int(name.replace(".ics", ""))
            event = CalendarEvent.objects.get(id=event_id, user=self.user)
            return CalendarEventResource(f"{self.path}/{name}", self.environ, event)
        except (ValueError, CalendarEvent.DoesNotExist):
            return None

    def put(self, name, data, content_type):
        # Parse iCalendar data with error handling
        try:
            raw_data = data.read().decode('utf-8')
        except (UnicodeDecodeError, AttributeError) as e:
            logger.warning("CalDAV PUT: invalid encoding: %s", e)
            return None

        try:
            cal = vobject.readOne(raw_data)
            vevent = cal.vevent
        except Exception as e:
            logger.warning("CalDAV PUT: malformed iCalendar data: %s", e)
            return None

        # Extract required fields with validation
        try:
            title = vevent.summary.value
            start_date = vevent.dtstart.value
            end_date = vevent.dtend.value
        except AttributeError as e:
            logger.warning("CalDAV PUT: missing required field: %s", e)
            return None

        # UID: required by RFC 5545, generate if missing
        uid = getattr(vevent, 'uid', None)
        if uid:
            uid = uid.value
        if not uid:
            uid = str(uuid.uuid4())

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
                task._skip_calendar_sync = True
                task.save(update_fields=['due_date'])

        return CalendarEventResource(f"{self.path}/{event.id}.ics", self.environ, event)


class CalendarEventResource(DAVNonCollection):
    """Event: /username/default/123.ics — individual calendar event."""
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
        import pytz
        cal = vobject.iCalendar()
        vevent = cal.add('vevent')
        vevent.add('summary').value = self.event.title
        # Convert to pytz.UTC so vobject can resolve the TZID
        start = self.event.start_date
        end = self.event.end_date
        if start and hasattr(start, 'astimezone'):
            start = start.astimezone(pytz.UTC)
        if end and hasattr(end, 'astimezone'):
            end = end.astimezone(pytz.UTC)
        vevent.add('uid').value = self.event.uid or f"event-{self.event.id}@payroll"
        vevent.add('dtstart').value = start
        vevent.add('dtend').value = end
        vevent.add('description').value = self.event.description or ''

        if self.event.alarm_minutes:
            valarm = vevent.add('valarm')
            valarm.add('action').value = 'DISPLAY'
            valarm.add('description').value = self.event.title
            trigger = f"-PT{self.event.alarm_minutes}M"
            valarm.add('trigger').value = trigger

        return cal.serialize()
