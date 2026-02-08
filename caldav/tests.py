from django.test import TestCase
from django.contrib.auth.models import User
from caldav.models import CalendarEvent
from caldav.resources import UserCalendarCollection
from employees.models import Employee, TaskBoard, TaskList, Task
from io import BytesIO
import vobject
from unittest.mock import Mock
from datetime import datetime, date, timedelta
import uuid
import pytz

class CalDAVPutTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        provider = Mock()
        self.environ = {"wsgidav.provider": provider}
        self.collection = UserCalendarCollection(f"/{self.user.username}", self.environ, self.user)
        self.utc = pytz.UTC

    def _create_ical(self, uid, summary, start, end, description, alarm_minutes=None):
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
        return cal.serialize().encode('utf-8')

    def test_put_creates_event(self):
        uid = str(uuid.uuid4())
        start_time = self.utc.localize(datetime(2024, 1, 1, 10))
        end_time = self.utc.localize(datetime(2024, 1, 1, 11))
        ical_data = self._create_ical(uid, 'New Event', start_time, end_time, 'A new event.')
        data_stream = BytesIO(ical_data)

        self.collection.put('new_event.ics', data_stream, 'text/calendar')

        self.assertEqual(CalendarEvent.objects.count(), 1)
        event = CalendarEvent.objects.first()
        self.assertEqual(event.uid, uid)
        self.assertEqual(event.title, 'New Event')

    def test_put_updates_event(self):
        uid = str(uuid.uuid4())
        # Create initial event
        start_time1 = self.utc.localize(datetime(2024, 1, 1, 10))
        end_time1 = self.utc.localize(datetime(2024, 1, 1, 11))
        ical_data1 = self._create_ical(uid, 'Original Title', start_time1, end_time1, 'Original desc.')
        self.collection.put('event.ics', BytesIO(ical_data1), 'text/calendar')

        self.assertEqual(CalendarEvent.objects.count(), 1)

        # Update event
        start_time2 = self.utc.localize(datetime(2024, 1, 1, 12))
        end_time2 = self.utc.localize(datetime(2024, 1, 1, 13))
        ical_data2 = self._create_ical(uid, 'Updated Title', start_time2, end_time2, 'Updated desc.')
        self.collection.put('event.ics', BytesIO(ical_data2), 'text/calendar')

        self.assertEqual(CalendarEvent.objects.count(), 1)
        event = CalendarEvent.objects.get(uid=uid)
        self.assertEqual(event.title, 'Updated Title')
        self.assertEqual(event.start_date, start_time2)

    def test_put_parses_alarm(self):
        uid = str(uuid.uuid4())
        start_time = self.utc.localize(datetime(2024, 1, 1, 10))
        end_time = self.utc.localize(datetime(2024, 1, 1, 11))
        ical_data = self._create_ical(uid, 'Alarm Event', start_time, end_time, 'Event with alarm', alarm_minutes=15)
        data_stream = BytesIO(ical_data)

        self.collection.put('alarm_event.ics', data_stream, 'text/calendar')

        event = CalendarEvent.objects.get(uid=uid)
        self.assertEqual(event.alarm_minutes, 15)


class CalDAVBidirectionalSyncTest(TestCase):
    """Tests that changes from CalDAV clients (e.g. Thunderbird) sync back to Task."""

    def setUp(self):
        self.user = User.objects.create_user(username='caluser', password='password')
        self.employee = Employee.objects.create(
            user=self.user, name='Cal User', email='cal@test.com', hire_date=date(2024, 1, 1)
        )
        self.board = TaskBoard.objects.create(employee=self.employee, name='Board')
        self.task_list = TaskList.objects.create(board=self.board, name='Pendiente', order=1)
        self.utc = pytz.UTC

        provider = Mock()
        self.environ = {"wsgidav.provider": provider}
        self.collection = UserCalendarCollection(f"/{self.user.username}", self.environ, self.user)

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
        return cal.serialize().encode('utf-8')

    def test_thunderbird_reschedule_updates_task_due_date(self):
        """When Thunderbird moves an event, the linked Task.due_date should update."""
        original_date = self.utc.localize(datetime(2024, 3, 1, 9, 0))
        task = Task.objects.create(
            list=self.task_list, assigned_to=self.employee,
            created_by=self.user, title='Review Report',
            order=1, due_date=original_date,
        )

        # A CalendarEvent should have been auto-created by the signal
        event = CalendarEvent.objects.get(task=task)
        self.assertEqual(event.start_date, original_date)

        # Simulate Thunderbird rescheduling the event to a new date
        new_date = self.utc.localize(datetime(2024, 3, 5, 14, 0))
        new_end = self.utc.localize(datetime(2024, 3, 5, 15, 0))
        ical_data = self._create_ical(event.uid, 'Review Report', new_date, new_end)
        self.collection.put('event.ics', BytesIO(ical_data), 'text/calendar')

        # Verify Task.due_date was updated
        task.refresh_from_db()
        self.assertEqual(task.due_date, new_date)

        # Verify CalendarEvent also reflects the new date
        event.refresh_from_db()
        self.assertEqual(event.start_date, new_date)

    def test_thunderbird_reschedule_no_loop(self):
        """Rescheduling from Thunderbird should not cause a redundant CalendarEvent update."""
        original_date = self.utc.localize(datetime(2024, 4, 1, 10, 0))
        task = Task.objects.create(
            list=self.task_list, assigned_to=self.employee,
            created_by=self.user, title='Team Meeting',
            order=1, due_date=original_date,
        )
        event = CalendarEvent.objects.get(task=task)

        new_date = self.utc.localize(datetime(2024, 4, 3, 16, 0))
        new_end = self.utc.localize(datetime(2024, 4, 3, 17, 0))
        ical_data = self._create_ical(event.uid, 'Team Meeting', new_date, new_end, alarm_minutes=10)
        self.collection.put('event.ics', BytesIO(ical_data), 'text/calendar')

        # Only 1 CalendarEvent should exist (no duplicates from signal loop)
        self.assertEqual(CalendarEvent.objects.filter(task=task).count(), 1)
        event.refresh_from_db()
        self.assertEqual(event.start_date, new_date)
        self.assertEqual(event.alarm_minutes, 10)

    def test_unlinked_event_no_task_update(self):
        """PUT on an event without a linked task should not cause errors."""
        uid = str(uuid.uuid4())
        start = self.utc.localize(datetime(2024, 5, 1, 8, 0))
        end = self.utc.localize(datetime(2024, 5, 1, 9, 0))
        ical_data = self._create_ical(uid, 'Personal Event', start, end)
        self.collection.put('personal.ics', BytesIO(ical_data), 'text/calendar')

        event = CalendarEvent.objects.get(uid=uid)
        self.assertIsNone(event.task)
        self.assertEqual(event.start_date, start)