"""WSGI entry point for Radicale CalDAV server with Django backend."""
import os
import sys

# Add the project directory to the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up Django before Radicale loads plugins
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "salary_management.settings")
import django
django.setup()

from django.conf import settings
from radicale import config
from radicale.app import Application

configuration = config.load()
configuration.update({
    "auth": {"type": "caldav.radicale_auth"},
    "storage": {"type": "caldav.storage"},
    "rights": {"type": "owner_only"},
    "web": {"type": "none"},
    "server": {"hosts": "0.0.0.0:8080"},
    "logging": {"level": "info"},
}, "custom")

# Mount prefix where the reverse proxy exposes CalDAV (e.g. /caldav-server/).
# The proxy strips it from PATH_INFO (proxy_pass http://127.0.0.1:8080/), so
# Radicale would otherwise run with an empty base prefix and (a) emit hrefs
# without the prefix and (b) reject calendar-multiget hrefs that DO carry it,
# logging "Skipping invalid path ... doesn't start with ...". Telling Radicale
# its prefix via X-Script-Name keeps generated and validated hrefs consistent.
# Overridable in local_settings.py via CALDAV_SCRIPT_NAME (set "" to disable).
CALDAV_SCRIPT_NAME = getattr(settings, 'CALDAV_SCRIPT_NAME', '/caldav-server')


def with_script_name(app, script_name):
    """WSGI middleware that advertises the proxy mount prefix to Radicale."""
    if not script_name:
        return app

    def wrapper(environ, start_response):
        # Don't override an explicit header already set by the proxy.
        if 'HTTP_X_SCRIPT_NAME' not in environ:
            environ['HTTP_X_SCRIPT_NAME'] = script_name
        return app(environ, start_response)

    return wrapper


def with_moz_alarm_conflict_merge(app):
    """Prevent HTTP 412 Precondition Failed popups in Thunderbird when dismissing
    or snoozing reminders on shared/externally-updated calendars (e.g. licitaciones).
    If a PUT carries X-MOZ-LASTACK / X-MOZ-SNOOZE* with a stale If-Match ETag,
    merge only the Mozilla alarm properties onto the current server iCal."""
    import io
    from urllib.parse import unquote
    from caldav.models import CalendarEvent
    from caldav.storage import serialize_event_to_ical, merge_moz_alarm_props, _http_date
    from radicale import item as radicale_item

    def wrapper(environ, start_response):
        if environ.get('REQUEST_METHOD') == 'PUT' and environ.get('HTTP_IF_MATCH'):
            try:
                content_length = int(environ.get('CONTENT_LENGTH') or 0)
            except ValueError:
                content_length = 0
            if 0 < content_length <= 1024 * 1024 and 'wsgi.input' in environ:
                body_bytes = environ['wsgi.input'].read(content_length)
                environ['wsgi.input'] = io.BytesIO(body_bytes)
                body_text = body_bytes.decode('utf-8', errors='ignore')
                upper_body = body_text.upper()
                if 'X-MOZ-LASTACK' in upper_body or 'X-MOZ-SNOOZE' in upper_body:
                    path_info = unquote(environ.get('PATH_INFO') or '').strip('/')
                    segments = [s for s in path_info.split('/') if s]
                    if len(segments) == 3 and segments[1] == 'default' and segments[2].endswith('.ics'):
                        username, _, href = segments
                        uid = href[:-4]
                        ev = CalendarEvent.objects.filter(user__username=username, uid=uid).first()
                        if ev is not None:
                            server_ical = serialize_event_to_ical(ev)
                            cur_item = radicale_item.Item(
                                collection_path=f"{username}/default",
                                href=href,
                                text=server_ical,
                                last_modified=_http_date(ev),
                            )
                            if environ['HTTP_IF_MATCH'] != cur_item.etag:
                                merged_ical = merge_moz_alarm_props(server_ical, body_text)
                                merged_bytes = merged_ical.encode('utf-8')
                                environ['wsgi.input'] = io.BytesIO(merged_bytes)
                                environ['CONTENT_LENGTH'] = str(len(merged_bytes))
                                environ['HTTP_IF_MATCH'] = cur_item.etag
        return app(environ, start_response)

    return wrapper


application = with_script_name(with_moz_alarm_conflict_merge(Application(configuration)), CALDAV_SCRIPT_NAME)
