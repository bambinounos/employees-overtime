"""Tests del push de nómina hacia Dolibarr (módulo nativo de salarios)."""
from datetime import date
from decimal import Decimal
from unittest import mock

import httpx
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import (DolibarrInstance, DolibarrUserIdentity, Employee, Salary,
                     WorkLog)
from .nomina import enviar_recibos_dolibarr, generar_recibo


def _mock_resp(status_code=200, json_data=41):
    resp = mock.MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    return resp


class DolibarrPushTest(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser('boss', 'boss@example.com', 'password')
        self.instancia = DolibarrInstance.objects.create(
            name='Empresa', professional_id='PROF1', api_secret='hmac',
            api_base_url='https://erp.example.com', api_key='DOLKEY123')
        self.employee = Employee.objects.create(
            name='Ana Nómina', email='ana@example.com', hire_date=date(2023, 1, 1))
        Salary.objects.create(employee=self.employee, base_amount=Decimal('1600'),
                              effective_date=date(2023, 1, 1))
        for dia in range(1, 21):
            WorkLog.objects.create(employee=self.employee, date=date(2023, 1, dia),
                                   hours_worked=8)
        DolibarrUserIdentity.objects.create(
            employee=self.employee, dolibarr_instance=self.instancia, dolibarr_user_id=7)
        self.recibo = generar_recibo(self.employee, 2023, 1)

    def test_exito_guarda_id_y_payload(self):
        with mock.patch('employees.dolibarr_api.httpx.post',
                        return_value=_mock_resp(200, 41)) as post:
            resultado = enviar_recibos_dolibarr(2023, 1)

        self.assertEqual(len(resultado['enviados']), 1)
        self.recibo.refresh_from_db()
        self.assertEqual(self.recibo.dolibarr_salary_id, 41)
        self.assertIsNotNone(self.recibo.dolibarr_synced_at)
        self.assertEqual(self.recibo.dolibarr_error, '')

        _, kwargs = post.call_args
        self.assertEqual(kwargs['json']['fk_user'], 7)
        self.assertEqual(kwargs['json']['paye'], 0)
        self.assertIn('Nómina 2023-01', kwargs['json']['label'])
        self.assertIn('Ana Nómina', kwargs['json']['label'])
        self.assertEqual(kwargs['headers']['DOLAPIKEY'], 'DOLKEY123')

    def test_idempotente_no_reenvia(self):
        self.recibo.dolibarr_salary_id = 41
        self.recibo.save(update_fields=['dolibarr_salary_id'])
        with mock.patch('employees.dolibarr_api.httpx.post') as post:
            resultado = enviar_recibos_dolibarr(2023, 1)
        post.assert_not_called()
        self.assertEqual(len(resultado['ya_sincronizados']), 1)
        self.assertEqual(len(resultado['enviados']), 0)

    def test_sin_mapeo_se_omite(self):
        DolibarrUserIdentity.objects.all().delete()
        with mock.patch('employees.dolibarr_api.httpx.post') as post:
            resultado = enviar_recibos_dolibarr(2023, 1)
        post.assert_not_called()
        self.assertEqual([e.name for e in resultado['sin_mapeo']], ['Ana Nómina'])

    def test_error_http_no_aborta_lote(self):
        otro = Employee.objects.create(name='Beto', email='beto@example.com',
                                       hire_date=date(2023, 1, 1))
        Salary.objects.create(employee=otro, base_amount=Decimal('1000'),
                              effective_date=date(2023, 1, 1))
        for dia in range(1, 21):
            WorkLog.objects.create(employee=otro, date=date(2023, 1, dia), hours_worked=8)
        DolibarrUserIdentity.objects.create(
            employee=otro, dolibarr_instance=self.instancia, dolibarr_user_id=9)
        generar_recibo(otro, 2023, 1)

        # Ana (orden alfabético primero) falla con 403; Beto pasa OK.
        with mock.patch('employees.dolibarr_api.httpx.post',
                        side_effect=[_mock_resp(403, 'Forbidden'), _mock_resp(200, 42)]):
            resultado = enviar_recibos_dolibarr(2023, 1)

        self.assertEqual(len(resultado['con_error']), 1)
        self.assertEqual(len(resultado['enviados']), 1)
        self.recibo.refresh_from_db()
        self.assertIsNone(self.recibo.dolibarr_salary_id)
        self.assertIn('HTTP 403', self.recibo.dolibarr_error)

    def test_timeout_no_aborta_lote(self):
        with mock.patch('employees.dolibarr_api.httpx.post',
                        side_effect=httpx.ConnectTimeout('timeout')):
            resultado = enviar_recibos_dolibarr(2023, 1)
        self.assertEqual(len(resultado['con_error']), 1)
        self.recibo.refresh_from_db()
        self.assertIsNone(self.recibo.dolibarr_salary_id)
        self.assertTrue(self.recibo.dolibarr_error)

    def test_ambiguedad_varias_instancias(self):
        otra = DolibarrInstance.objects.create(
            name='Empresa2', professional_id='PROF2', api_secret='hmac2',
            api_base_url='https://erp2.example.com', api_key='DOLKEY456')
        DolibarrUserIdentity.objects.create(
            employee=self.employee, dolibarr_instance=otra, dolibarr_user_id=8)
        with mock.patch('employees.dolibarr_api.httpx.post') as post:
            resultado = enviar_recibos_dolibarr(2023, 1)
        post.assert_not_called()
        self.assertEqual(len(resultado['con_error']), 1)
        self.recibo.refresh_from_db()
        self.assertIn('varias instancias', self.recibo.dolibarr_error)

    def test_vista_solo_superuser(self):
        url = reverse('nomina_enviar_dolibarr')
        user = User.objects.create_user('normal', password='password')
        Employee.objects.create(user=user, name='Normal', email='n@example.com',
                                hire_date=date(2023, 1, 1))
        self.client.login(username='normal', password='password')
        self.assertEqual(self.client.post(url, {'year': 2023, 'month': 1}).status_code, 403)

        self.client.login(username='boss', password='password')
        with mock.patch('employees.dolibarr_api.httpx.post',
                        return_value=_mock_resp(200, 41)):
            response = self.client.post(url, {'year': 2023, 'month': 1})
        self.assertEqual(response.status_code, 302)

    def test_vista_get_no_tiene_efecto(self):
        self.client.login(username='boss', password='password')
        with mock.patch('employees.dolibarr_api.httpx.post') as post:
            response = self.client.get(reverse('nomina_enviar_dolibarr'))
        post.assert_not_called()
        self.assertEqual(response.status_code, 302)
