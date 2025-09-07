from django.contrib.auth.models import User
from wsgidav.dav_provider import DAVCollection, DAVNonCollection
from caldav.models import CalendarEvent
import vobject

class RootCollection(DAVCollection):
    def __init__(self, path, environ):
        super().__init__(path, environ)

    def get_member_names(self):
        # Return a list of usernames as calendar names
        return [user.username for user in User.objects.all()]

    def get_member(self, name):
        # Return a calendar resource for the given user
        try:
            user = User.objects.get(username=name)
            # Return a UserCalendarCollection resource
            return UserCalendarCollection(f"/{name}", self.environ, user)
        except User.DoesNotExist:
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

class CalendarEventResource(DAVNonCollection):
    def __init__(self, path, environ, event):
        super().__init__(path, environ)
        self.event = event

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
        return cal.serialize()
