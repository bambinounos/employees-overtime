from datetime import timedelta

from django.test import TestCase, Client
from django.utils import timezone
from django.contrib.auth.models import User

from psicoevaluacion.models import Evaluacion


class InicioEvaluacionViewTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_token_valido(self):
        ev = Evaluacion(nombres='Test', cedula='111', correo='t@t.com')
        ev.save()
        response = self.client.get(f'/psicoevaluacion/evaluar/{ev.token}/')
        self.assertEqual(response.status_code, 200)

    def test_token_invalido(self):
        response = self.client.get('/psicoevaluacion/evaluar/tokenfalso123/')
        self.assertEqual(response.status_code, 404)

    def test_token_expirado(self):
        ev = Evaluacion(
            nombres='Expirado', cedula='222', correo='e@e.com',
            fecha_expiracion=timezone.now() - timedelta(hours=1),
        )
        ev.save()
        response = self.client.get(f'/psicoevaluacion/evaluar/{ev.token}/')
        self.assertEqual(response.status_code, 410)

    def test_evaluacion_context(self):
        ev = Evaluacion(nombres='Contexto', cedula='333', correo='c@c.com')
        ev.save()
        response = self.client.get(f'/psicoevaluacion/evaluar/{ev.token}/')
        self.assertEqual(response.context['evaluacion'].pk, ev.pk)


class VerificarCandidatoViewTest(TestCase):

    def test_verificar_con_token_valido(self):
        ev = Evaluacion(nombres='Test', cedula='111', correo='t@t.com')
        ev.save()
        response = self.client.get(f'/psicoevaluacion/evaluar/{ev.token}/verificar/')
        self.assertEqual(response.status_code, 200)


class FinalizarEvaluacionViewTest(TestCase):

    def test_finalizar_con_token_valido(self):
        ev = Evaluacion(nombres='Test', cedula='111', correo='t@t.com')
        ev.save()
        response = self.client.get(f'/psicoevaluacion/evaluar/{ev.token}/finalizar/')
        self.assertEqual(response.status_code, 200)


class DashboardEvaluadorViewTest(TestCase):

    def test_requiere_login(self):
        response = self.client.get('/psicoevaluacion/panel/dashboard/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_acceso_con_login(self):
        User.objects.create_user('admin', 'a@a.com', 'pass123')
        self.client.login(username='admin', password='pass123')
        response = self.client.get('/psicoevaluacion/panel/dashboard/')
        self.assertEqual(response.status_code, 200)


class CrearEvaluacionViewTest(TestCase):

    def test_requiere_login(self):
        response = self.client.get('/psicoevaluacion/panel/crear/')
        self.assertEqual(response.status_code, 302)

    def test_acceso_con_login(self):
        User.objects.create_user('admin', 'a@a.com', 'pass123')
        self.client.login(username='admin', password='pass123')
        response = self.client.get('/psicoevaluacion/panel/crear/')
        self.assertEqual(response.status_code, 200)


class DetalleEvaluacionViewTest(TestCase):

    def test_requiere_login(self):
        ev = Evaluacion(nombres='Test', cedula='111', correo='t@t.com')
        ev.save()
        response = self.client.get(f'/psicoevaluacion/panel/evaluacion/{ev.pk}/')
        self.assertEqual(response.status_code, 302)

    def test_acceso_con_login(self):
        ev = Evaluacion(nombres='Test', cedula='111', correo='t@t.com')
        ev.save()
        User.objects.create_user('admin', 'a@a.com', 'pass123')
        self.client.login(username='admin', password='pass123')
        response = self.client.get(f'/psicoevaluacion/panel/evaluacion/{ev.pk}/')
        self.assertEqual(response.status_code, 200)


class ApiStubsTest(TestCase):

    def test_api_psicometrica_post_only(self):
        response = self.client.get('/psicoevaluacion/api/respuesta/psicometrica/')
        self.assertEqual(response.status_code, 405)

    def test_api_memoria_returns_501(self):
        response = self.client.post('/psicoevaluacion/api/respuesta/memoria/')
        self.assertEqual(response.status_code, 501)

    def test_api_matriz_returns_501(self):
        response = self.client.post('/psicoevaluacion/api/respuesta/matriz/')
        self.assertEqual(response.status_code, 501)

    def test_api_situacional_returns_501(self):
        response = self.client.post('/psicoevaluacion/api/respuesta/situacional/')
        self.assertEqual(response.status_code, 501)
