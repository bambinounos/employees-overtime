from django.test import TestCase
from django.contrib.auth.models import User
from caldav.models import CalendarEvent
from caldav.storage import Collection, Storage, serialize_event_to_ical, parse_ical_event
from employees.models import Employee, TaskBoard, TaskList, Task
from unittest.mock import Mock
from datetime import datetime, date, timedelta
import uuid
import pytz
import vobject


class StorageCollectionTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.storage = Mock()
        self.collection = Collection(
            self.storage, "testuser/default", user=self.user, tag="VCALENDAR"
        )
        self.utc = pytz.UTC

    def _create_ical(self, uid, summary, start, end, description='', alarm_minutes=None):
        cal = vobject.iCalendar()
        cal.add('vevent')
        vevent = cal.vevent
        vevent.add('uid').value = uid
        vevent.add('summary').value = summary
        vevent.add('dtstart').value = start
        vevent.add('dtend').value = end
        vevent.add('description').value = description
        if alarm_minutes:
            valarm = vevent.add('valarm')
            valarm.add('action').value = 'DISPLAY'
            valarm.add('description').value = summary
            valarm.add('trigger').value = timedelta(minutes=-alarm_minutes)
        return cal.serialize()

    def _make_item(self, ical_text, href=None):
        from radicale import item as radicale_item
        return radicale_item.Item(
            collection_path="testuser/default",
            href=href,
            text=ical_text,
        )

    def test_upload_creates_event(self):
        uid = str(uuid.uuid4())
        start = self.utc.localize(datetime(2024, 1, 1, 10))
        end = self.utc.localize(datetime(2024, 1, 1, 11))
        ical_text = self._create_ical(uid, 'New Event', start, end, 'A new event.')
        item = self._make_item(ical_text, href=f"{uid}.ics")

        new_item = self.collection.upload(f"{uid}.ics", item)

        self.assertEqual(CalendarEvent.objects.count(), 1)
        event = CalendarEvent.objects.first()
        self.assertEqual(event.uid, uid)
        self.assertEqual(event.title, 'New Event')
        self.assertIsNotNone(new_item)

    def test_upload_updates_event(self):
        uid = str(uuid.uuid4())
        start1 = self.utc.localize(datetime(2024, 1, 1, 10))
        end1 = self.utc.localize(datetime(2024, 1, 1, 11))
        ical1 = self._create_ical(uid, 'Original', start1, end1)
        self.collection.upload(f"{uid}.ics", self._make_item(ical1, f"{uid}.ics"))
        self.assertEqual(CalendarEvent.objects.count(), 1)

        start2 = self.utc.localize(datetime(2024, 1, 1, 12))
        end2 = self.utc.localize(datetime(2024, 1, 1, 13))
        ical2 = self._create_ical(uid, 'Updated', start2, end2)
        new_item = self.collection.upload(f"{uid}.ics", self._make_item(ical2, f"{uid}.ics"))

        self.assertEqual(CalendarEvent.objects.count(), 1)
        event = CalendarEvent.objects.get(uid=uid)
        self.assertEqual(event.title, 'Updated')
        self.assertEqual(event.start_date, start2)
        self.assertIsNotNone(new_item)

    def test_upload_parses_alarm(self):
        uid = str(uuid.uuid4())
        start = self.utc.localize(datetime(2024, 1, 1, 10))
        end = self.utc.localize(datetime(2024, 1, 1, 11))
        ical = self._create_ical(uid, 'Alarm Event', start, end, alarm_minutes=15)
        self.collection.upload(f"{uid}.ics", self._make_item(ical, f"{uid}.ics"))

        event = CalendarEvent.objects.get(uid=uid)
        self.assertEqual(event.alarm_minutes, 15)


class BidirectionalSyncTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='caluser', password='password')
        self.employee = Employee.objects.create(
            user=self.user, name='Cal User', email='cal@test.com', hire_date=date(2024, 1, 1)
        )
        self.board = TaskBoard.objects.create(employee=self.employee, name='Board')
        self.task_list = TaskList.objects.create(board=self.board, name='Pendiente', order=1)
        self.utc = pytz.UTC
        self.storage = Mock()
        self.collection = Collection(
            self.storage, "caluser/default", user=self.user, tag="VCALENDAR"
        )

    def _create_ical(self, uid, summary, start, end, description='', alarm_minutes=None):
        cal = vobject.iCalendar()
        cal.add('vevent')
        vevent = cal.vevent
        vevent.add('uid').value = uid
        vevent.add('summary').value = summary
        vevent.add('dtstart').value = start
        vevent.add('dtend').value = end
        vevent.add('description').value = description
        if alarm_minutes:
            valarm = vevent.add('valarm')
            valarm.add('action').value = 'DISPLAY'
            valarm.add('description').value = summary
            valarm.add('trigger').value = timedelta(minutes=-alarm_minutes)
        return cal.serialize()

    def _make_item(self, ical_text, href=None):
        from radicale import item as radicale_item
        return radicale_item.Item(
            collection_path="caluser/default",
            href=href,
            text=ical_text,
        )

    def test_reschedule_updates_task_due_date(self):
        """When a CalDAV client moves an event, the linked Task.due_date updates."""
        original_date = self.utc.localize(datetime(2024, 3, 1, 9, 0))
        task = Task.objects.create(
            list=self.task_list, assigned_to=self.employee,
            created_by=self.user, title='Review Report',
            order=1, due_date=original_date,
        )
        event = CalendarEvent.objects.get(task=task)
        self.assertEqual(event.start_date, original_date)

        new_date = self.utc.localize(datetime(2024, 3, 5, 14, 0))
        new_end = self.utc.localize(datetime(2024, 3, 5, 15, 0))
        ical = self._create_ical(event.uid, 'Review Report', new_date, new_end)
        self.collection.upload(f"{event.uid}.ics", self._make_item(ical, f"{event.uid}.ics"))

        task.refresh_from_db()
        self.assertEqual(task.due_date, new_date)
        event.refresh_from_db()
        self.assertEqual(event.start_date, new_date)

    def test_reschedule_no_loop(self):
        """Rescheduling should not cause duplicate events."""
        original_date = self.utc.localize(datetime(2024, 4, 1, 10, 0))
        task = Task.objects.create(
            list=self.task_list, assigned_to=self.employee,
            created_by=self.user, title='Team Meeting',
            order=1, due_date=original_date,
        )
        event = CalendarEvent.objects.get(task=task)

        new_date = self.utc.localize(datetime(2024, 4, 3, 16, 0))
        new_end = self.utc.localize(datetime(2024, 4, 3, 17, 0))
        ical = self._create_ical(event.uid, 'Team Meeting', new_date, new_end, alarm_minutes=10)
        self.collection.upload(f"{event.uid}.ics", self._make_item(ical, f"{event.uid}.ics"))

        self.assertEqual(CalendarEvent.objects.filter(task=task).count(), 1)
        event.refresh_from_db()
        self.assertEqual(event.start_date, new_date)
        self.assertEqual(event.alarm_minutes, 10)

    def test_unlinked_event_no_task_update(self):
        """PUT on an event without a linked task should not cause errors."""
        uid = str(uuid.uuid4())
        start = self.utc.localize(datetime(2024, 5, 1, 8, 0))
        end = self.utc.localize(datetime(2024, 5, 1, 9, 0))
        ical = self._create_ical(uid, 'Personal Event', start, end)
        self.collection.upload(f"{uid}.ics", self._make_item(ical, f"{uid}.ics"))

        event = CalendarEvent.objects.get(uid=uid)
        self.assertIsNone(event.task)
        self.assertEqual(event.start_date, start)
