from django.test import TestCase
from django.contrib.auth.models import User
from caldav.models import CalendarEvent
from caldav.resources import UserCalendarCollection
from io import BytesIO
import vobject
from unittest.mock import Mock
from datetime import datetime, timedelta
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