from django.contrib.auth.models import User
from wsgidav.dav_provider import DAVProvider
from caldav.resources import RootCollection, UserCalendarCollection, CalendarEventResource
from caldav.models import CalendarEvent


class CalDAVProvider(DAVProvider):
    def __init__(self):
        super().__init__()

    def get_resource_inst(self, path, environ):
        # Normalize path
        path = path.rstrip("/")
        segments = [s for s in path.split("/") if s]

        if len(segments) == 0:
            # Root: /
            return RootCollection("/", environ)

        elif len(segments) == 1:
            # User calendar: /Admin-RH/
            username = segments[0]
            auth_user = environ.get("wsgidav.auth.user_name")
            if auth_user and username == auth_user:
                try:
                    user = User.objects.get(username=username)
                    return UserCalendarCollection(f"/{username}", environ, user)
                except User.DoesNotExist:
                    return None
            return None

        elif len(segments) == 2:
            # Event resource: /Admin-RH/123.ics
            username = segments[0]
            event_name = segments[1]
            auth_user = environ.get("wsgidav.auth.user_name")
            if auth_user and username == auth_user:
                try:
                    user = User.objects.get(username=username)
                    event_id = int(event_name.replace(".ics", ""))
                    event = CalendarEvent.objects.get(id=event_id, user=user)
                    return CalendarEventResource(path, environ, event)
                except (User.DoesNotExist, CalendarEvent.DoesNotExist, ValueError):
                    # For PUT requests (new events), return the collection so WsgiDAV calls put()
                    if environ.get("REQUEST_METHOD") == "PUT":
                        try:
                            user = User.objects.get(username=username)
                            return UserCalendarCollection(f"/{username}", environ, user)
                        except User.DoesNotExist:
                            return None
                    return None
            return None

        return None
