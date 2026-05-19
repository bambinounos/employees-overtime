import hashlib
import hmac
import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from .models import (
    DolibarrInstance, DolibarrUserIdentity, Employee, SalesRecord,
)


WEBHOOK_URL = '/api/webhook/dolibarr/'


class DolibarrWebhookIdempotencyTest(TestCase):
    """
    Regression tests for the Dolibarr webhook re-validation bug.

    When Dolibarr re-validates a PROPAL/BILL/ORDER, it re-sends the same event
    with the same (instance, dolibarr_id, status). Before the fix the webhook
    raised IntegrityError -> HTTP 500, which made the Dolibarr trigger rollback
    the source transaction and surface "BadValueForParameter" to the user.
    """

    def setUp(self):
        self.client = APIClient()
        self.instance = DolibarrInstance.objects.create(
            name='Test Instance',
            professional_id='test-pro',
            api_secret='secret-key-128',
        )
        self.employee = Employee.objects.create(
            name='Test Employee',
            email='dolibarr-test@example.com',
            hire_date=date(2024, 1, 1),
        )
        DolibarrUserIdentity.objects.create(
            employee=self.employee,
            dolibarr_instance=self.instance,
            dolibarr_user_id=5,
        )

    def _post(self, payload):
        body = json.dumps(payload).encode('utf-8')
        signature = hmac.new(
            key=self.instance.api_secret.encode('utf-8'),
            msg=body,
            digestmod=hashlib.sha256,
        ).hexdigest()
        return self.client.post(
            WEBHOOK_URL,
            data=body,
            content_type='application/json',
            HTTP_X_DOLIBARR_PROFESSIONAL_ID=self.instance.professional_id,
            HTTP_X_DOLIBARR_SIGNATURE=signature,
        )

    def _propal_payload(self, dolibarr_id=123, amount='1500.00', ref='PR2605-1319'):
        return {
            'trigger_code': 'PROPAL_VALIDATE',
            'object': {
                'id': dolibarr_id,
                'fk_user_author': 5,
                'ref': ref,
                'total_ht': amount,
                'date_validation': '2024-03-21',
            },
        }

    def _order_payload(self, dolibarr_id=200, amount='2000.00', ref='SO2605-001',
                       fk_propal=None):
        return {
            'trigger_code': 'ORDER_VALIDATE',
            'object': {
                'id': dolibarr_id,
                'fk_user_author': 5,
                'ref': ref,
                'total_ht': amount,
                'date_validation': '2024-03-22',
                'fk_propal': fk_propal,
            },
        }

    def _bill_payload(self, dolibarr_id=300, amount='1800.00', ref='FA24-001',
                      fk_propal=None, fk_commande=None):
        return {
            'trigger_code': 'BILL_VALIDATE',
            'object': {
                'id': dolibarr_id,
                'fk_user_author': 5,
                'ref': ref,
                'total_ht': amount,
                'date_validation': '2024-03-23',
                'type': 0,
                'fk_propal': fk_propal,
                'fk_commande': fk_commande,
            },
        }

    def test_propal_validate_creates_proforma(self):
        response = self._post(self._propal_payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SalesRecord.objects.filter(status='proforma').count(), 1)
        record = SalesRecord.objects.get(status='proforma')
        self.assertEqual(record.dolibarr_id, 123)
        self.assertEqual(record.amount_untaxed, Decimal('1500.00'))

    def test_propal_validate_revalidate_updates_in_place(self):
        # First validate
        r1 = self._post(self._propal_payload(amount='1500.00'))
        self.assertEqual(r1.status_code, 200)

        # Re-validate the same proforma with a different amount (user edited it)
        r2 = self._post(self._propal_payload(amount='1750.00', ref='PR2605-1319-v2'))
        self.assertEqual(r2.status_code, 200,
                         f'Re-validation must not crash with 500: {r2.content!r}')

        # Exactly one record, updated with the new amount and ref
        self.assertEqual(SalesRecord.objects.filter(status='proforma').count(), 1)
        record = SalesRecord.objects.get(status='proforma')
        self.assertEqual(record.amount_untaxed, Decimal('1750.00'))
        self.assertEqual(record.dolibarr_ref, 'PR2605-1319-v2')

    def test_order_validate_revalidate_idempotent(self):
        r1 = self._post(self._order_payload(amount='2000.00'))
        self.assertEqual(r1.status_code, 200)

        r2 = self._post(self._order_payload(amount='2200.00'))
        self.assertEqual(r2.status_code, 200, f'Body: {r2.content!r}')

        self.assertEqual(SalesRecord.objects.filter(status='order').count(), 1)
        record = SalesRecord.objects.get(status='order')
        self.assertEqual(record.amount_untaxed, Decimal('2200.00'))

    def test_bill_validate_revalidate_idempotent(self):
        # Create a proforma first (bills require an origin)
        self._post(self._propal_payload(dolibarr_id=400, amount='1000.00'))

        # First validate of the invoice
        r1 = self._post(self._bill_payload(dolibarr_id=500, amount='1000.00',
                                           fk_propal=400))
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(SalesRecord.objects.filter(status='invoiced').count(), 1)

        # Re-validate with edited amount
        r2 = self._post(self._bill_payload(dolibarr_id=500, amount='1100.00',
                                           fk_propal=400))
        self.assertEqual(r2.status_code, 200, f'Body: {r2.content!r}')

        self.assertEqual(SalesRecord.objects.filter(status='invoiced').count(), 1)
        record = SalesRecord.objects.get(status='invoiced')
        self.assertEqual(record.amount_untaxed, Decimal('1100.00'))

    @patch('employees.api_views.SalesRecord.objects.update_or_create')
    def test_handler_integrityerror_returns_200(self, mock_update_or_create):
        """If a future handler forgets update_or_create and raises IntegrityError,
        the view must still respond 200 so Dolibarr doesn't rollback."""
        from django.db import IntegrityError
        mock_update_or_create.side_effect = IntegrityError('duplicate key')

        response = self._post(self._propal_payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('status'), 'already_processed')
