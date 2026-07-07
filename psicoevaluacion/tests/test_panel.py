"""Tests de Fase 4: panel pro (crear evaluación, comparativo, filtros del dashboard)."""
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import Evaluacion, PerfilObjetivo, ResultadoFinal


class CrearEvaluacionPanelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('eva', 'eva@example.com', 'pass123')
        self.client.login(username='eva', password='pass123')
        self.perfil = PerfilObjetivo.objects.create(nombre='Cajero Test')

    def test_get_muestra_formulario(self):
        response = self.client.get(reverse('psicoevaluacion:crear_evaluacion'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Crear nueva evaluación')
        self.assertContains(response, 'name="nombres"')

    def test_post_crea_evaluacion_con_token_y_envia_email(self):
        response = self.client.post(reverse('psicoevaluacion:crear_evaluacion'), {
            'nombres': 'Juan Prueba',
            'cedula': '1712345678',
            'correo': 'juan@example.com',
            'telefono': '0999999999',
            'cargo_postulado': 'Guardia',
            'perfil_objetivo': self.perfil.id,
            'horas_validez': 72,
            'enviar_email': 'on',
        })
        evaluacion = Evaluacion.objects.get(cedula='1712345678')
        self.assertRedirects(response, reverse('psicoevaluacion:detalle_evaluacion',
                                               args=[evaluacion.pk]))
        self.assertEqual(len(evaluacion.token), 64)
        self.assertEqual(evaluacion.creado_por, self.user)
        # Expiración custom de 72h (con margen)
        delta = evaluacion.fecha_expiracion - timezone.now()
        self.assertAlmostEqual(delta.total_seconds() / 3600, 72, delta=1)
        # Email con el link
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(evaluacion.token, mail.outbox[0].body)
        evaluacion.refresh_from_db()
        self.assertIsNotNone(evaluacion.link_enviado_en)

    def test_post_sin_email_no_envia(self):
        self.client.post(reverse('psicoevaluacion:crear_evaluacion'), {
            'nombres': 'Sin Correo',
            'cedula': '1798765432',
            'correo': 'x@example.com',
            'horas_validez': 48,
            # enviar_email ausente = unchecked
        })
        self.assertTrue(Evaluacion.objects.filter(cedula='1798765432').exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_enviar_email_sin_correo_da_error_de_form(self):
        response = self.client.post(reverse('psicoevaluacion:crear_evaluacion'), {
            'nombres': 'Sin Correo',
            'cedula': '1711111111',
            'correo': '',
            'horas_validez': 48,
            'enviar_email': 'on',
        })
        self.assertEqual(response.status_code, 200)  # re-render con error
        self.assertFalse(Evaluacion.objects.filter(cedula='1711111111').exists())


class ComparativoTest(TestCase):
    def setUp(self):
        User.objects.create_superuser('eva', 'eva@example.com', 'pass123')
        self.client.login(username='eva', password='pass123')
        self.ev1 = Evaluacion.objects.create(nombres='Ana Uno', cedula='111')
        ResultadoFinal.objects.create(
            evaluacion=self.ev1, puntaje_responsabilidad=4.2, puntaje_amabilidad=3.5,
            puntaje_neuroticismo=2.1, puntaje_apertura=3.8, puntaje_extroversion=3.0,
            veredicto_automatico='APTO')
        self.ev2 = Evaluacion.objects.create(nombres='Beto Dos', cedula='222')
        ResultadoFinal.objects.create(
            evaluacion=self.ev2, puntaje_responsabilidad=2.9, puntaje_amabilidad=3.1,
            puntaje_neuroticismo=3.9, puntaje_apertura=2.5, puntaje_extroversion=2.8,
            veredicto_automatico='NO_APTO')
        # Sin resultado: no debe aparecer en el selector
        Evaluacion.objects.create(nombres='Casi Tres', cedula='333')

    def test_selector_solo_con_resultado(self):
        response = self.client.get(reverse('psicoevaluacion:comparativo'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ana Uno')
        self.assertContains(response, 'Beto Dos')
        self.assertNotContains(response, 'Casi Tres')

    def test_comparacion_renderiza_puntajes_y_radar(self):
        response = self.client.get(reverse('psicoevaluacion:comparativo'),
                                   {'ev': [self.ev1.pk, self.ev2.pk]})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'radarBigFive')
        self.assertContains(response, '4.2')  # responsabilidad de Ana
        self.assertContains(response, 'APTO')
        self.assertContains(response, 'NO_APTO')


class DashboardFiltrosTest(TestCase):
    def setUp(self):
        User.objects.create_superuser('eva', 'eva@example.com', 'pass123')
        self.client.login(username='eva', password='pass123')
        self.perfil = PerfilObjetivo.objects.create(nombre='Ventas Test')
        Evaluacion.objects.create(nombres='Pedro Pendiente', cedula='100')
        completada = Evaluacion.objects.create(
            nombres='Carla Completa', cedula='200', perfil_objetivo=self.perfil)
        completada.estado = 'COMPLETADA'
        completada.save()

    def test_filtro_por_estado(self):
        url = reverse('psicoevaluacion:dashboard_evaluador')
        response = self.client.get(url, {'estado': 'COMPLETADA'})
        self.assertContains(response, 'Carla Completa')
        self.assertNotContains(response, 'Pedro Pendiente')

    def test_busqueda_por_nombre_y_cedula(self):
        url = reverse('psicoevaluacion:dashboard_evaluador')
        response = self.client.get(url, {'q': 'pedro'})
        self.assertContains(response, 'Pedro Pendiente')
        self.assertNotContains(response, 'Carla Completa')
        response = self.client.get(url, {'q': '200'})
        self.assertContains(response, 'Carla Completa')

    def test_filtro_por_perfil(self):
        url = reverse('psicoevaluacion:dashboard_evaluador')
        response = self.client.get(url, {'perfil': self.perfil.id})
        self.assertContains(response, 'Carla Completa')
        self.assertNotContains(response, 'Pedro Pendiente')

    def test_dashboard_muestra_graficos(self):
        response = self.client.get(reverse('psicoevaluacion:dashboard_evaluador'))
        self.assertContains(response, 'chartMeses')
        self.assertContains(response, 'chartVeredictos')
