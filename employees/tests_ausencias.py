"""Tests de Fase 1: ausencias, recibos de nómina (snapshot) y clawback de comisiones."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .ausencias import aprobar_solicitud, rechazar_solicitud, cancelar_solicitud
from .models import (
    CommissionBalance, DolibarrInstance, Employee, ReciboNomina, Salary,
    SalesRecord, SolicitudAusencia, TipoAusencia, WorkLog,
)
from .nomina import generar_recibo, generar_recibos_mes


def _mk_employee(name='Emp', email=None, with_user=True, commission=0):
    user = None
    if with_user:
        user = User.objects.create_user(username=name.lower().replace(' ', '_'), password='password')
    return Employee.objects.create(
        user=user, name=name, email=email or f"{name.lower().replace(' ', '_')}@example.com",
        hire_date=date(2023, 1, 1), commission_percentage=Decimal(commission))


class AusenciasServiceTest(TestCase):
    def setUp(self):
        self.employee = _mk_employee('Vacacionista')
        self.aprobador = User.objects.create_superuser('jefa', 'jefa@example.com', 'password')
        self.vacaciones = TipoAusencia.objects.get(nombre='Vacaciones')
        self.sin_sueldo = TipoAusencia.objects.get(nombre='Permiso sin sueldo')

    def _solicitud(self, inicio, fin, tipo=None):
        return SolicitudAusencia.objects.create(
            employee=self.employee, tipo=tipo or self.vacaciones,
            fecha_inicio=inicio, fecha_fin=fin)

    def test_dias_habiles_calculados_al_guardar(self):
        # Lunes 2026-06-01 a domingo 2026-06-07: 5 días hábiles
        s = self._solicitud(date(2026, 6, 1), date(2026, 6, 7))
        self.assertEqual(s.dias_habiles, Decimal('5'))

    def test_aprobar_crea_worklogs_solo_dias_habiles(self):
        s = self._solicitud(date(2026, 6, 1), date(2026, 6, 7))
        aprobar_solicitud(s, self.aprobador)
        logs = WorkLog.objects.filter(ausencia=s)
        self.assertEqual(logs.count(), 5)
        self.assertTrue(all(log.hours_worked == 8 for log in logs))
        self.assertTrue(all(log.date.weekday() < 5 for log in logs))

    def test_aprobar_no_pisa_worklog_existente(self):
        WorkLog.objects.create(employee=self.employee, date=date(2026, 6, 2),
                               hours_worked=4, overtime_hours=2)
        s = self._solicitud(date(2026, 6, 1), date(2026, 6, 5))
        aprobar_solicitud(s, self.aprobador)
        manual = WorkLog.objects.get(employee=self.employee, date=date(2026, 6, 2))
        self.assertEqual(manual.hours_worked, 4)  # el registro manual gana
        self.assertIsNone(manual.ausencia)
        self.assertEqual(WorkLog.objects.filter(ausencia=s).count(), 4)

    def test_ausencia_no_remunerada_no_crea_worklogs(self):
        s = self._solicitud(date(2026, 6, 1), date(2026, 6, 5), tipo=self.sin_sueldo)
        aprobar_solicitud(s, self.aprobador)
        self.assertEqual(WorkLog.objects.filter(employee=self.employee).count(), 0)

    def test_cancelar_aprobada_borra_solo_sus_worklogs(self):
        WorkLog.objects.create(employee=self.employee, date=date(2026, 6, 2), hours_worked=8)
        s = self._solicitud(date(2026, 6, 1), date(2026, 6, 5))
        aprobar_solicitud(s, self.aprobador)
        cancelar_solicitud(s, self.aprobador)
        self.assertEqual(WorkLog.objects.filter(ausencia=s).count(), 0)
        # El registro manual sobrevive
        self.assertTrue(WorkLog.objects.filter(
            employee=self.employee, date=date(2026, 6, 2)).exists())

    def test_rechazar_no_crea_worklogs(self):
        s = self._solicitud(date(2026, 6, 1), date(2026, 6, 5))
        rechazar_solicitud(s, self.aprobador, 'sin cobertura')
        self.assertEqual(WorkLog.objects.count(), 0)
        s.refresh_from_db()
        self.assertEqual(s.estado, 'RECHAZADA')
        self.assertEqual(s.comentario_decision, 'sin cobertura')

    def test_no_se_aprueba_dos_veces(self):
        s = self._solicitud(date(2026, 6, 1), date(2026, 6, 5))
        aprobar_solicitud(s, self.aprobador)
        with self.assertRaises(ValueError):
            aprobar_solicitud(s, self.aprobador)

    def test_solapamiento_bloqueado_en_clean(self):
        self._solicitud(date(2026, 6, 1), date(2026, 6, 5))
        solapada = SolicitudAusencia(
            employee=self.employee, tipo=self.vacaciones,
            fecha_inicio=date(2026, 6, 4), fecha_fin=date(2026, 6, 10))
        with self.assertRaises(ValidationError):
            solapada.full_clean()

    def test_saldo_vacaciones(self):
        self.assertEqual(self.employee.saldo_vacaciones(2026), Decimal('15'))
        s = self._solicitud(date(2026, 6, 1), date(2026, 6, 5))  # 5 hábiles
        aprobar_solicitud(s, self.aprobador)
        self.assertEqual(self.employee.saldo_vacaciones(2026), Decimal('10'))
        # El permiso sin sueldo no descuenta saldo
        s2 = self._solicitud(date(2026, 7, 1), date(2026, 7, 3), tipo=self.sin_sueldo)
        aprobar_solicitud(s2, self.aprobador)
        self.assertEqual(self.employee.saldo_vacaciones(2026), Decimal('10'))

    def test_aprobacion_crea_evento_caldav(self):
        from caldav.models import CalendarEvent
        s = self._solicitud(date(2026, 6, 1), date(2026, 6, 5))
        aprobar_solicitud(s, self.aprobador)
        self.assertTrue(CalendarEvent.objects.filter(uid=f"ausencia-{s.pk}@payroll").exists())
        cancelar_solicitud(s, self.aprobador)
        self.assertFalse(CalendarEvent.objects.filter(uid=f"ausencia-{s.pk}@payroll").exists())


class AusenciasViewsTest(TestCase):
    def setUp(self):
        self.employee = _mk_employee('Solicitante')
        self.superuser = User.objects.create_superuser('boss', 'boss@example.com', 'password')
        self.vacaciones = TipoAusencia.objects.get(nombre='Vacaciones')

    def test_flujo_solicitud_y_aprobacion(self):
        self.client.login(username='solicitante', password='password')
        response = self.client.post(reverse('mis_ausencias'), {
            'tipo': self.vacaciones.id,
            'fecha_inicio': '2026-06-01',
            'fecha_fin': '2026-06-05',
            'motivo': 'Descanso',
        })
        self.assertEqual(response.status_code, 302)
        solicitud = SolicitudAusencia.objects.get()
        self.assertEqual(solicitud.employee, self.employee)
        self.assertEqual(solicitud.estado, 'PENDIENTE')

        self.client.login(username='boss', password='password')
        response = self.client.post(
            reverse('decidir_ausencia', args=[solicitud.id]),
            {'decision': 'aprobar', 'comentario': 'ok'})
        self.assertEqual(response.status_code, 302)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'APROBADA')
        self.assertEqual(WorkLog.objects.filter(ausencia=solicitud).count(), 5)

    def test_empleado_no_puede_decidir(self):
        solicitud = SolicitudAusencia.objects.create(
            employee=self.employee, tipo=self.vacaciones,
            fecha_inicio=date(2026, 6, 1), fecha_fin=date(2026, 6, 5))
        self.client.login(username='solicitante', password='password')
        response = self.client.post(
            reverse('decidir_ausencia', args=[solicitud.id]), {'decision': 'aprobar'})
        self.assertEqual(response.status_code, 403)

    def test_bandeja_aprobacion_solo_superuser(self):
        self.client.login(username='solicitante', password='password')
        self.assertEqual(self.client.get(reverse('ausencias_pendientes')).status_code, 403)
        self.client.login(username='boss', password='password')
        self.assertEqual(self.client.get(reverse('ausencias_pendientes')).status_code, 200)


class ReciboNominaTest(TestCase):
    def setUp(self):
        self.employee = _mk_employee('Asalariado', commission=10)
        self.superuser = User.objects.create_superuser('boss', 'boss@example.com', 'password')
        Salary.objects.create(employee=self.employee, base_amount=Decimal('1600'),
                              effective_date=date(2023, 1, 1))
        # 20 días de 8h en enero 2023 = 160h → base completa (base_hours default 160)
        for dia in range(1, 21):
            WorkLog.objects.create(employee=self.employee, date=date(2023, 1, dia),
                                   hours_worked=8, overtime_hours=0)

    def test_snapshot_inmutable_ante_cambio_de_reglas(self):
        recibo = generar_recibo(self.employee, 2023, 1)
        total_original = recibo.total
        self.assertEqual(total_original, Decimal('1600.00'))

        # Cambia una regla después del cierre: el snapshot NO cambia
        self.employee.commission_percentage = Decimal('50')
        self.employee.save()
        recibo.refresh_from_db()
        self.assertEqual(recibo.total, total_original)
        self.assertEqual(Decimal(recibo.datos['work_pay']), Decimal('1600.00'))

    def test_generar_recibos_mes_omite_sin_salario(self):
        sin_salario = _mk_employee('Nuevo Sin Sueldo')
        generados, omitidos = generar_recibos_mes(2023, 1)
        self.assertEqual({r.employee for r in generados}, {self.employee})
        self.assertIn(sin_salario, omitidos)

    def test_regenerar_actualiza_en_vez_de_duplicar(self):
        generar_recibo(self.employee, 2023, 1)
        generar_recibo(self.employee, 2023, 1)
        self.assertEqual(ReciboNomina.objects.filter(
            employee=self.employee, year=2023, month=1).count(), 1)

    def test_pdf_solo_dueno_o_superuser(self):
        generar_recibo(self.employee, 2023, 1)
        otro = _mk_employee('Fisgon')

        self.client.login(username='asalariado', password='password')
        response = self.client.get(reverse('recibo_pdf', args=[self.employee.id, 2023, 1]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

        self.client.login(username='fisgon', password='password')
        response = self.client.get(reverse('recibo_pdf', args=[self.employee.id, 2023, 1]))
        self.assertEqual(response.status_code, 403)

        self.client.login(username='boss', password='password')
        response = self.client.get(reverse('recibo_pdf', args=[self.employee.id, 2023, 1]))
        self.assertEqual(response.status_code, 200)

    def test_mi_panel_carga(self):
        self.client.login(username='asalariado', password='password')
        response = self.client.get(reverse('mi_panel'), {'year': 2023, 'month': 1})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Asalariado')

    def test_cierre_nomina_solo_superuser(self):
        self.client.login(username='asalariado', password='password')
        self.assertEqual(self.client.get(reverse('nomina_cierre')).status_code, 403)
        self.client.login(username='boss', password='password')
        response = self.client.post(reverse('nomina_cierre'), {'year': 2023, 'month': 1})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ReciboNomina.objects.count(), 1)


class CommissionClawbackTest(TestCase):
    """Cubre el hueco de tests de calculate_commissions/clawback."""

    def setUp(self):
        self.employee = _mk_employee('Vendedor', commission=10)
        self.instance = DolibarrInstance.objects.create(
            name='ERP', professional_id='RUC-1', api_secret='secret')

    def _venta(self, dolibarr_id, amount, status='invoiced', fecha=None, pago=None):
        return SalesRecord.objects.create(
            employee=self.employee, dolibarr_instance=self.instance,
            dolibarr_id=dolibarr_id, dolibarr_ref=f"FA-{dolibarr_id}", status=status,
            amount_untaxed=Decimal(amount), date=fecha or date(2026, 5, 10),
            payment_date=pago)

    def test_comision_solo_sobre_facturas_pagadas(self):
        self._venta(1, '1000', pago=date(2026, 5, 20))   # confirmada
        self._venta(2, '2000', pago=None)                # provisional
        result = self.employee.calculate_commissions(2026, 5)
        self.assertEqual(result['commission_amount'], Decimal('100.00'))
        self.assertEqual(result['provisional_invoiced'], Decimal('2000'))

    def test_nota_de_credito_resta(self):
        self._venta(1, '1000', pago=date(2026, 5, 20))
        self._venta(3, '-400', status='credit_note', fecha=date(2026, 5, 25))
        result = self.employee.calculate_commissions(2026, 5)
        # (1000 - 400) * 10% = 60
        self.assertEqual(result['commission_amount'], Decimal('60.00'))

    def test_clawback_arrastra_deuda_al_mes_siguiente(self):
        # Mayo: solo una nota de crédito grande → deuda
        self._venta(3, '-1000', status='credit_note', fecha=date(2026, 5, 25))
        result_mayo = self.employee.calculate_commissions(2026, 5)
        self.assertEqual(result_mayo['commission_amount'], Decimal('0.00'))
        self.assertEqual(result_mayo['remaining_debt'], Decimal('-100.00'))

        balance = CommissionBalance.objects.get(employee=self.employee)
        self.assertEqual(balance.balance, Decimal('-100.00'))

        # Junio: factura pagada de 1500 → comisión 150 - 100 de deuda = 50
        self._venta(4, '1500', fecha=date(2026, 6, 5), pago=date(2026, 6, 10))
        result_junio = self.employee.calculate_commissions(2026, 6)
        self.assertEqual(result_junio['commission_amount'], Decimal('50.00'))
        balance.refresh_from_db()
        self.assertEqual(balance.balance, Decimal('0.00'))

    def test_recalculo_mismo_mes_es_idempotente(self):
        self._venta(1, '1000', pago=date(2026, 5, 20))
        primero = self.employee.calculate_commissions(2026, 5)
        segundo = self.employee.calculate_commissions(2026, 5)
        self.assertEqual(primero['commission_amount'], segundo['commission_amount'])
