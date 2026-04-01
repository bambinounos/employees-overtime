from django.contrib.auth.models import User
from wsgidav.dav_provider import DAVProvider
from caldav.resources import RootCollection, UserPrincipal, CalendarCollection, CalendarEventResource
from caldav.models import CalendarEvent


class CalDAVProvider(DAVProvider):
    def __init__(self):
        super().__init__()

    def get_resource_inst(self, path, environ):
        # Normalize path
        path = path.rstrip("/")
        segments = [s for s in path.split("/") if s]

        auth_user = environ.get("wsgidav.auth.user_name")

        if len(segments) == 0:
            # Root: /
            return RootCollection("/", environ)

        username = segments[0]
        if not auth_user or username != auth_user:
            return None

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return None

        if len(segments) == 1:
            # Principal: /username/
            return UserPrincipal(f"/{username}", environ, user)

        elif len(segments) == 2:
            # Calendar collection: /username/default/
            cal_name = segments[1]
            if cal_name == 'default':
                return CalendarCollection(f"/{username}/default", environ, user)
            return None

        elif len(segments) == 3:
            # Event: /username/default/123.ics
            cal_name = segments[1]
            event_name = segments[2]
            if cal_name != 'default':
                return None
            try:
                event_id = int(event_name.replace(".ics", ""))
                event = CalendarEvent.objects.get(id=event_id, user=user)
                return CalendarEventResource(f"/{username}/default/{event_name}", environ, event)
            except (CalendarEvent.DoesNotExist, ValueError):
                # For PUT requests (new events), return the collection
                if environ.get("REQUEST_METHOD") == "PUT":
                    return CalendarCollection(f"/{username}/default", environ, user)
                return None

        return None
