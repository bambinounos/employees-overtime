"""Radicale storage plugin backed by Django's CalendarEvent model."""
import os
import sys
import threading
import logging
from contextlib import contextmanager
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "salary_management.settings")

import django
try:
    django.setup()
except RuntimeError:
    pass

import vobject
import pytz
from radicale.storage import BaseStorage, BaseCollection
from radicale import item as radicale_item

logger = logging.getLogger(__name__)


def serialize_event_to_ical(event):
    """Convert a CalendarEvent to iCalendar string."""
    cal = vobject.iCalendar()
    vevent = cal.add('vevent')
    vevent.add('summary').value = event.title

    start = event.start_date
    end = event.end_date
    if start and hasattr(start, 'astimezone'):
        start = start.astimezone(pytz.UTC)
    if end and hasattr(end, 'astimezone'):
        end = end.astimezone(pytz.UTC)

    vevent.add('uid').value = event.uid or f"event-{event.id}@payroll"
    vevent.add('dtstart').value = start
    vevent.add('dtend').value = end
    vevent.add('description').value = event.description or ''

    if event.alarm_minutes:
        valarm = vevent.add('valarm')
        valarm.add('action').value = 'DISPLAY'
        valarm.add('description').value = event.title
        valarm.add('trigger').value = timedelta(minutes=-event.alarm_minutes)

    return cal.serialize()


def parse_ical_event(ical_text):
    """Parse iCalendar text and extract event fields."""
    cal = vobject.readOne(ical_text)
    vevent = cal.vevent

    uid = getattr(vevent, 'uid', None)
    uid = uid.value if uid else None

    title = vevent.summary.value
    start_date = vevent.dtstart.value
    end_date = vevent.dtend.value
    description = vevent.description.value if hasattr(vevent, 'description') else ''

    alarm_minutes = None
    if hasattr(vevent, 'valarm'):
        trigger = vevent.valarm.trigger.value
        if isinstance(trigger, timedelta):
            alarm_minutes = int(abs(trigger.total_seconds()) / 60)

    return {
        'uid': uid,
        'title': title,
        'start_date': start_date,
        'end_date': end_date,
        'description': description,
        'alarm_minutes': alarm_minutes,
    }


def _get_user(username):
    """Get Django User by username."""
    from django.contrib.auth.models import User
    try:
        return User.objects.get(username=username)
    except User.DoesNotExist:
        return None


def _get_event_model():
    """Lazy import to avoid circular imports."""
    from caldav.models import CalendarEvent
    return CalendarEvent


class Collection(BaseCollection):
    """A CalDAV collection backed by Django CalendarEvent model."""

    def __init__(self, storage, path, user=None, tag=None, props=None):
        self._storage = storage
        self._path = path
        self._user = user
        self._tag = tag or ""
        self._props = props or {}

    @property
    def path(self):
        return self._path

    @property
    def owner(self):
        parts = self._path.strip("/").split("/")
        return parts[0] if parts and parts[0] else ""

    @property
    def is_principal(self):
        parts = self._path.strip("/").split("/")
        return len(parts) == 1 and parts[0] != ""

    @property
    def tag(self):
        return self._tag

    @property
    def etag(self):
        if self._tag != "VCALENDAR" or not self._user:
            return ""
        CalendarEvent = _get_event_model()
        from django.db.models import Max, Count
        agg = CalendarEvent.objects.filter(user=self._user).aggregate(
            max_id=Max('id'), cnt=Count('id')
        )
        return f'"{agg["max_id"] or 0}-{agg["cnt"]}"'

    @property
    def last_modified(self):
        return ""

    def get_meta(self, key=None):
        meta = dict(self._props)
        if self._tag:
            meta["tag"] = self._tag
        if self._tag == "VCALENDAR":
            meta.setdefault("D:displayname", "Tareas")
        if key:
            return meta.get(key, "")
        return meta

    def set_meta(self, props):
        self._props.update(props)

    def get_all(self):
        if self._tag != "VCALENDAR" or not self._user:
            return
        CalendarEvent = _get_event_model()
        for event in CalendarEvent.objects.filter(user=self._user):
            href = f"{event.uid or f'event-{event.id}@payroll'}.ics"
            ical_text = serialize_event_to_ical(event)
            yield radicale_item.Item(
                collection_path=self._path,
                href=href,
                text=ical_text,
            )

    def get_multi(self, hrefs):
        if not self._user:
            return
        CalendarEvent = _get_event_model()
        for href in hrefs:
            uid = href.replace(".ics", "")
            try:
                event = CalendarEvent.objects.get(user=self._user, uid=uid)
                ical_text = serialize_event_to_ical(event)
                yield (href, radicale_item.Item(
                    collection_path=self._path,
                    href=href,
                    text=ical_text,
                ))
            except CalendarEvent.DoesNotExist:
                yield (href, None)

    def has_uid(self, uid):
        if not self._user:
            return False
        CalendarEvent = _get_event_model()
        return CalendarEvent.objects.filter(user=self._user, uid=uid).exists()

    def upload(self, href, item):
        """Upload/update an event. Returns (new_item, old_item_or_None)."""
        if not self._user:
            raise ValueError("Cannot upload to collection without user")

        CalendarEvent = _get_event_model()
        data = parse_ical_event(item.serialize())

        uid = data['uid']
        if not uid:
            import uuid
            uid = str(uuid.uuid4())

        # Check for existing event (for returning old_item)
        old_item = None
        try:
            existing = CalendarEvent.objects.get(user=self._user, uid=uid)
            old_ical = serialize_event_to_ical(existing)
            old_item = radicale_item.Item(
                collection_path=self._path,
                href=f"{uid}.ics",
                text=old_ical,
            )
        except CalendarEvent.DoesNotExist:
            pass

        # Create or update
        event, created = CalendarEvent.objects.update_or_create(
            uid=uid,
            user=self._user,
            defaults={
                'title': data['title'],
                'start_date': data['start_date'],
                'end_date': data['end_date'],
                'description': data['description'],
                'alarm_minutes': data['alarm_minutes'],
            }
        )

        # Bidirectional sync: update linked Task's due_date
        if event.task_id:
            task = event.task
            if task.due_date != data['start_date']:
                task.due_date = data['start_date']
                task._skip_calendar_sync = True
                task.save(update_fields=['due_date'])

        # Return new item
        new_ical = serialize_event_to_ical(event)
        new_href = f"{event.uid}.ics"
        new_item = radicale_item.Item(
            collection_path=self._path,
            href=new_href,
            text=new_ical,
        )
        return new_item, old_item

    def delete(self, href=None):
        if not self._user:
            return
        CalendarEvent = _get_event_model()
        if href:
            uid = href.replace(".ics", "")
            CalendarEvent.objects.filter(user=self._user, uid=uid).delete()
        # href=None would delete the collection — not supported

    def sync(self, old_token=""):
        if self._tag != "VCALENDAR" or not self._user:
            return "", []
        CalendarEvent = _get_event_model()
        events = CalendarEvent.objects.filter(user=self._user)
        token = self.etag.strip('"')
        hrefs = [f"{e.uid or f'event-{e.id}@payroll'}.ics" for e in events]
        return token, hrefs

    def serialize(self):
        if self._tag != "VCALENDAR":
            return ""
        return "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Payroll//CalDAV//EN\r\nEND:VCALENDAR\r\n"


class Storage(BaseStorage):
    """Radicale storage backed by Django CalendarEvent model."""

    _lock = threading.Lock()

    def __init__(self, configuration):
        super().__init__(configuration)

    @contextmanager
    def acquire_lock(self, mode, user="", *args, **kwargs):
        if mode == "w":
            with self._lock:
                yield
        else:
            yield

    def discover(self, path, depth="0", child_context_manager=None,
                 user_groups=set()):
        path = path.strip("/")
        segments = [s for s in path.split("/") if s]

        if len(segments) == 0:
            # Root
            col = Collection(self, "", tag="")
            yield col
            if depth != "0":
                # We don't list users at root level for security
                pass

        elif len(segments) == 1:
            # Principal: /username/
            username = segments[0]
            user = _get_user(username)
            if user:
                col = Collection(self, username, user=user, tag="")
                yield col
                if depth != "0":
                    # Yield the default calendar
                    cal = Collection(self, f"{username}/default", user=user, tag="VCALENDAR")
                    yield cal

        elif len(segments) == 2:
            # Calendar collection: /username/default/
            username, cal_name = segments
            if cal_name != "default":
                return
            user = _get_user(username)
            if user:
                col = Collection(self, f"{username}/default", user=user, tag="VCALENDAR")
                yield col
                if depth != "0":
                    # Yield all events
                    yield from col.get_all()

        elif len(segments) == 3:
            # Individual event: /username/default/uid.ics
            username, cal_name, event_href = segments
            if cal_name != "default":
                return
            user = _get_user(username)
            if user:
                CalendarEvent = _get_event_model()
                uid = event_href.replace(".ics", "")
                try:
                    event = CalendarEvent.objects.get(user=user, uid=uid)
                    ical_text = serialize_event_to_ical(event)
                    yield radicale_item.Item(
                        collection_path=f"{username}/default",
                        href=event_href,
                        text=ical_text,
                    )
                except CalendarEvent.DoesNotExist:
                    return

    def move(self, item, to_collection, to_href):
        raise NotImplementedError("Moving events between collections not supported")

    def create_collection(self, href, items=None, props=None):
        """No-op: collections are virtual (backed by DB queries)."""
        path = href.strip("/")
        segments = [s for s in path.split("/") if s]

        user = None
        tag = ""
        if segments:
            user = _get_user(segments[0])
        if len(segments) >= 2 and segments[1] == "default":
            tag = "VCALENDAR"

        col = Collection(self, path, user=user, tag=tag, props=props or {})

        # Process initial items if provided
        items_map = {}
        errors = []
        if items:
            for item in items:
                try:
                    new_item, _ = col.upload(item.href, item)
                    items_map[item.href] = new_item
                except Exception as e:
                    errors.append(str(e))

        return col, items_map, errors

    def verify(self):
        return True
