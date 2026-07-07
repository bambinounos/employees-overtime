"""Tests de Fase 2: notificaciones por email (commands cron + inline)."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .ausencias import aprobar_solicitud
from .models import (Employee, KPI, ManualKpiEntry, SolicitudAusencia, Task,
                     TaskBoard, TaskList, TipoAusencia)


def _mk_employee(name, password='password'):
    user = User.objects.create_user(username=name.lower(), password=password,
                                    email=f"{name.lower()}@example.com")
    return Employee.objects.create(user=user, name=name,
                                   email=f"{name.lower()}@example.com",
                                   hire_date=date(2023, 1, 1))


def _mk_task(employee, title, due_delta_days, status='pending'):
    board, _ = TaskBoard.objects.get_or_create(employee=employee, defaults={'name': 'B'})
    lista, _ = TaskList.objects.get_or_create(board=board, name='Pendiente', defaults={'order': 1})
    return Task.objects.create(
        list=lista, assigned_to=employee, title=title, order=1, status=status,
        due_date=timezone.now() + timedelta(days=due_delta_days))


class NotificarTareasTest(TestCase):
    def setUp(self):
        self.employee = _mk_employee('Notificado')

    def test_envia_solo_vencidas_y_de_hoy(self):
        _mk_task(self.employee, 'Vencida', -2)
        _mk_task(self.employee, 'De hoy', 0)
        _mk_task(self.employee, 'Futura', 5)

        call_command('notificar_tareas')

        self.assertEqual(len(mail.outbox), 1)
        cuerpo = mail.outbox[0].body
        self.assertIn('Vencida', cuerpo)
        self.assertIn('De hoy', cuerpo)
        self.assertNotIn('Futura', cuerpo)
        self.assertEqual(mail.outbox[0].to, ['notificado@example.com'])

    def test_idempotente_mismo_dia(self):
        _mk_task(self.employee, 'Vencida', -1)
        call_command('notificar_tareas')
        call_command('notificar_tareas')
        self.assertEqual(len(mail.outbox), 1)

    def test_no_notifica_completadas(self):
        task = _mk_task(self.employee, 'Hecha', -1, status='completed')
        task.completed_at = timezone.now()
        task.save()
        call_command('notificar_tareas')
        self.assertEqual(len(mail.outbox), 0)

    def test_dry_run_no_envia_ni_marca(self):
        task = _mk_task(self.employee, 'Vencida', -1)
        call_command('notificar_tareas', '--dry-run')
        self.assertEqual(len(mail.outbox), 0)
        task.refresh_from_db()
        self.assertIsNone(task.reminder_sent_at)


class ResumenSemanalTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('boss', 'boss@example.com', 'password')
        self.employee = _mk_employee('Operario')

    def test_envia_resumen_a_superusers(self):
        _mk_task(self.employee, 'Atrasada', -3)
        call_command('resumen_semanal')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['boss@example.com'])
        self.assertIn('1', mail.outbox[0].body)  # 1 tarea vencida

    def test_dry_run_no_envia(self):
        call_command('resumen_semanal', '--dry-run')
        self.assertEqual(len(mail.outbox), 0)


class AusenciaEmailTest(TestCase):
    def setUp(self):
        self.employee = _mk_employee('Vacacionero')
        self.aprobador = User.objects.create_superuser('jefa', 'jefa@example.com', 'password')
        self.vacaciones = TipoAusencia.objects.get(nombre='Vacaciones')

    def test_aprobar_envia_email(self):
        s = SolicitudAusencia.objects.create(
            employee=self.employee, tipo=self.vacaciones,
            fecha_inicio=date(2026, 6, 1), fecha_fin=date(2026, 6, 5))
        # TestCase envuelve en transacción: capturamos los callbacks on_commit
        with self.captureOnCommitCallbacks(execute=True):
            aprobar_solicitud(s, self.aprobador)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['vacacionero@example.com'])
        self.assertIn('APROBADA', mail.outbox[0].body)


class AdvertenciaDisciplinariaTest(TestCase):
    def setUp(self):
        self.employee = _mk_employee('Advertido')
        self.kpi_warning = KPI.objects.create(
            name='Advertencia disciplinaria', measurement_type='count_lt',
            target_value=Decimal('3'), is_warning_kpi=True)
        self.kpi_normal = KPI.objects.create(
            name='Errores de facturación', measurement_type='count_lt',
            target_value=Decimal('3'))

    def test_entrada_de_warning_kpi_envia_email(self):
        ManualKpiEntry.objects.create(
            employee=self.employee, kpi=self.kpi_warning,
            notes='Llegada tarde sin justificación')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['advertido@example.com'])
        self.assertIn('Llegada tarde sin justificación', mail.outbox[0].body)
        self.assertIn('Advertencia disciplinaria', mail.outbox[0].subject)

    def test_entrada_de_kpi_normal_no_envia(self):
        ManualKpiEntry.objects.create(employee=self.employee, kpi=self.kpi_normal)
        self.assertEqual(len(mail.outbox), 0)

    def test_editar_entrada_no_reenvia(self):
        entry = ManualKpiEntry.objects.create(
            employee=self.employee, kpi=self.kpi_warning, notes='Original')
        entry.notes = 'Corregida'
        entry.save()
        self.assertEqual(len(mail.outbox), 1)

    def test_fallo_smtp_no_rompe_el_guardado(self):
        with self.settings(EMAIL_BACKEND='employees.tests_notificaciones.BrokenEmailBackend'):
            entry = ManualKpiEntry.objects.create(
                employee=self.employee, kpi=self.kpi_warning, notes='SMTP caído')
        self.assertIsNotNone(entry.pk)


class BrokenEmailBackend:
    """Backend que siempre falla, para probar que el guardado no se rompe."""
    def __init__(self, *args, **kwargs):
        raise ConnectionError('SMTP caído (simulado)')


class EnviarLinkEvaluacionTest(TestCase):
    def setUp(self):
        from psicoevaluacion.models import Evaluacion
        self.admin = User.objects.create_superuser('boss', 'boss@example.com', 'password')
        self.evaluacion = Evaluacion.objects.create(
            nombres='Cándida Postulante', cedula='1712345678',
            correo='candida@example.com', cargo_postulado='Cajera')

    def test_envio_estampa_link_enviado_en(self):
        self.client.login(username='boss', password='password')
        response = self.client.post(
            reverse('psicoevaluacion:enviar_link', args=[self.evaluacion.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['candida@example.com'])
        self.assertIn(self.evaluacion.token, mail.outbox[0].body)
        self.evaluacion.refresh_from_db()
        self.assertIsNotNone(self.evaluacion.link_enviado_en)

    def test_no_envia_si_completada(self):
        self.evaluacion.estado = 'COMPLETADA'
        self.evaluacion.save()
        self.client.login(username='boss', password='password')
        self.client.post(reverse('psicoevaluacion:enviar_link', args=[self.evaluacion.pk]))
        self.assertEqual(len(mail.outbox), 0)

    def test_sin_correo_no_envia(self):
        self.evaluacion.correo = ''
        self.evaluacion.save()
        self.client.login(username='boss', password='password')
        self.client.post(reverse('psicoevaluacion:enviar_link', args=[self.evaluacion.pk]))
        self.assertEqual(len(mail.outbox), 0)
