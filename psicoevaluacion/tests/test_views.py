import json
from datetime import timedelta

from django.test import TestCase, Client
from django.utils import timezone
from django.contrib.auth.models import User

from psicoevaluacion.models import (
    Evaluacion, Prueba, Pregunta, Opcion,
    RespuestaPsicometrica, RespuestaSituacional,
    RespuestaMatriz, RespuestaMemoria, RespuestaProyectiva,
)


def _create_prueba(tipo='BIGFIVE', nombre='Big Five', orden=1, **kwargs):
    defaults = {
        'tipo': tipo,
        'nombre': nombre,
        'instrucciones': 'Instrucciones de prueba',
        'orden': orden,
        'activa': True,
    }
    defaults.update(kwargs)
    return Prueba.objects.create(**defaults)


def _create_evaluacion(**kwargs):
    defaults = {
        'nombres': 'Test Candidato',
        'cedula': '1234567890',
        'correo': 'test@test.com',
    }
    defaults.update(kwargs)
    return Evaluacion.objects.create(**defaults)


class InicioEvaluacionViewTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_token_valido(self):
        ev = _create_evaluacion()
        response = self.client.get(f'/psicoevaluacion/evaluar/{ev.token}/')
        self.assertEqual(response.status_code, 200)

    def test_token_invalido(self):
        response = self.client.get('/psicoevaluacion/evaluar/tokenfalso123/')
        self.assertEqual(response.status_code, 404)

    def test_token_expirado(self):
        ev = _create_evaluacion(
            fecha_expiracion=timezone.now() - timedelta(hours=1),
        )
        response = self.client.get(f'/psicoevaluacion/evaluar/{ev.token}/')
        self.assertEqual(response.status_code, 410)

    def test_evaluacion_context(self):
        ev = _create_evaluacion(nombres='Contexto')
        response = self.client.get(f'/psicoevaluacion/evaluar/{ev.token}/')
        self.assertEqual(response.context['evaluacion'].pk, ev.pk)

    def test_completada_redirige_a_finalizar(self):
        ev = _create_evaluacion(estado='COMPLETADA')
        response = self.client.get(f'/psicoevaluacion/evaluar/{ev.token}/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('finalizar', response.url)

    def test_en_curso_redirige_a_prueba(self):
        prueba = _create_prueba()
        ev = _create_evaluacion(estado='EN_CURSO', prueba_actual=prueba)
        response = self.client.get(f'/psicoevaluacion/evaluar/{ev.token}/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('prueba', response.url)

    def test_pendiente_muestra_pruebas_info(self):
        _create_prueba()
        ev = _create_evaluacion()
        response = self.client.get(f'/psicoevaluacion/evaluar/{ev.token}/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('pruebas_info', response.context)


class VerificarCandidatoViewTest(TestCase):

    def test_verificar_con_token_valido(self):
        ev = _create_evaluacion()
        response = self.client.get(f'/psicoevaluacion/evaluar/{ev.token}/verificar/')
        self.assertEqual(response.status_code, 200)

    def test_cedula_correcta_inicia_evaluacion(self):
        _create_prueba()
        ev = _create_evaluacion(cedula='9999999')
        response = self.client.post(
            f'/psicoevaluacion/evaluar/{ev.token}/verificar/',
            {'cedula': '9999999'}
        )
        self.assertEqual(response.status_code, 302)
        ev.refresh_from_db()
        self.assertEqual(ev.estado, 'EN_CURSO')
        self.assertIsNotNone(ev.fecha_inicio)
        self.assertIsNotNone(ev.preguntas_seleccionadas)

    def test_cedula_incorrecta_muestra_error(self):
        ev = _create_evaluacion(cedula='9999999')
        response = self.client.post(
            f'/psicoevaluacion/evaluar/{ev.token}/verificar/',
            {'cedula': '1111111'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no coincide')
        ev.refresh_from_db()
        self.assertEqual(ev.estado, 'PENDIENTE')

    def test_evaluacion_expirada_muestra_error(self):
        ev = _create_evaluacion(
            fecha_expiracion=timezone.now() - timedelta(hours=1),
        )
        response = self.client.get(f'/psicoevaluacion/evaluar/{ev.token}/verificar/')
        self.assertEqual(response.status_code, 410)

    def test_en_curso_redirige_a_inicio(self):
        ev = _create_evaluacion(estado='EN_CURSO')
        response = self.client.get(f'/psicoevaluacion/evaluar/{ev.token}/verificar/')
        self.assertEqual(response.status_code, 302)


class RealizarPruebaViewTest(TestCase):

    def setUp(self):
        self.prueba = _create_prueba()
        self.pregunta = Pregunta.objects.create(
            prueba=self.prueba, texto='Pregunta test',
            tipo_escala='LIKERT5', dimension='BF_RESP', orden=1)
        for i in range(1, 6):
            Opcion.objects.create(
                pregunta=self.pregunta, texto=str(i), valor=i, orden=i)
        self.ev = _create_evaluacion(
            estado='EN_CURSO',
            preguntas_seleccionadas=[self.pregunta.id],
            prueba_actual=self.prueba)

    def test_render_prueba_likert(self):
        response = self.client.get(
            f'/psicoevaluacion/evaluar/{self.ev.token}/prueba/bigfive/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('prueba', response.context)
        self.assertIn('preguntas', response.context)

    def test_no_en_curso_redirige(self):
        self.ev.estado = 'PENDIENTE'
        self.ev.save()
        response = self.client.get(
            f'/psicoevaluacion/evaluar/{self.ev.token}/prueba/bigfive/')
        self.assertEqual(response.status_code, 302)

    def test_tipo_invalido_404(self):
        response = self.client.get(
            f'/psicoevaluacion/evaluar/{self.ev.token}/prueba/inexistente/')
        self.assertEqual(response.status_code, 404)

    def test_tiene_siguiente_url(self):
        response = self.client.get(
            f'/psicoevaluacion/evaluar/{self.ev.token}/prueba/bigfive/')
        self.assertIn('siguiente_url', response.context)


class FinalizarEvaluacionViewTest(TestCase):

    def test_finalizar_con_token_valido(self):
        ev = _create_evaluacion()
        response = self.client.get(f'/psicoevaluacion/evaluar/{ev.token}/finalizar/')
        self.assertEqual(response.status_code, 200)

    def test_en_curso_marca_completada(self):
        ev = _create_evaluacion(estado='EN_CURSO')
        response = self.client.get(f'/psicoevaluacion/evaluar/{ev.token}/finalizar/')
        self.assertEqual(response.status_code, 200)
        ev.refresh_from_db()
        self.assertEqual(ev.estado, 'COMPLETADA')
        self.assertIsNotNone(ev.fecha_finalizacion)


class ApiGuardarPsicometricaTest(TestCase):

    def setUp(self):
        self.prueba = _create_prueba()
        self.pregunta = Pregunta.objects.create(
            prueba=self.prueba, texto='Test', tipo_escala='LIKERT5',
            dimension='BF_RESP', orden=1)
        self.opcion = Opcion.objects.create(
            pregunta=self.pregunta, texto='Opcion 3', valor=3, orden=1)
        self.ev = _create_evaluacion(estado='EN_CURSO')

    def test_guardar_respuesta_valida(self):
        response = self.client.post(
            '/psicoevaluacion/api/respuesta/psicometrica/',
            json.dumps({
                'evaluacion_token': self.ev.token,
                'pregunta_id': self.pregunta.id,
                'valor': 3,
                'opcion_id': self.opcion.id,
                'tiempo_respuesta_seg': 5,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertTrue(data['created'])
        self.assertEqual(
            RespuestaPsicometrica.objects.filter(evaluacion=self.ev).count(), 1)

    def test_update_or_create(self):
        RespuestaPsicometrica.objects.create(
            evaluacion=self.ev, pregunta=self.pregunta, valor=2)
        response = self.client.post(
            '/psicoevaluacion/api/respuesta/psicometrica/',
            json.dumps({
                'evaluacion_token': self.ev.token,
                'pregunta_id': self.pregunta.id,
                'valor': 4,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['created'])
        resp = RespuestaPsicometrica.objects.get(
            evaluacion=self.ev, pregunta=self.pregunta)
        self.assertEqual(resp.valor, 4)

    def test_token_invalido(self):
        response = self.client.post(
            '/psicoevaluacion/api/respuesta/psicometrica/',
            json.dumps({
                'evaluacion_token': 'falso',
                'pregunta_id': self.pregunta.id,
                'valor': 3,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)

    def test_evaluacion_no_en_curso(self):
        self.ev.estado = 'COMPLETADA'
        self.ev.save()
        response = self.client.post(
            '/psicoevaluacion/api/respuesta/psicometrica/',
            json.dumps({
                'evaluacion_token': self.ev.token,
                'pregunta_id': self.pregunta.id,
                'valor': 3,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 409)

    def test_campos_faltantes(self):
        response = self.client.post(
            '/psicoevaluacion/api/respuesta/psicometrica/',
            json.dumps({
                'evaluacion_token': self.ev.token,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_get_no_permitido(self):
        response = self.client.get('/psicoevaluacion/api/respuesta/psicometrica/')
        self.assertEqual(response.status_code, 405)


class ApiGuardarSituacionalTest(TestCase):

    def setUp(self):
        self.prueba = _create_prueba(tipo='SITUACIONAL', nombre='Situacional')
        self.pregunta = Pregunta.objects.create(
            prueba=self.prueba, texto='Escenario',
            tipo_escala='OPCION_MULTIPLE', dimension='SIT_RESP', orden=1)
        self.opcion = Opcion.objects.create(
            pregunta=self.pregunta, texto='Opcion A', valor=4, orden=1)
        self.ev = _create_evaluacion(estado='EN_CURSO')

    def test_guardar_valida(self):
        response = self.client.post(
            '/psicoevaluacion/api/respuesta/situacional/',
            json.dumps({
                'evaluacion_token': self.ev.token,
                'pregunta_id': self.pregunta.id,
                'opcion_id': self.opcion.id,
                'valor': 4,
                'justificacion': 'Porque si',
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(RespuestaSituacional.objects.count(), 1)
        resp = RespuestaSituacional.objects.first()
        self.assertEqual(resp.justificacion, 'Porque si')

    def test_token_invalido(self):
        response = self.client.post(
            '/psicoevaluacion/api/respuesta/situacional/',
            json.dumps({
                'evaluacion_token': 'falso',
                'pregunta_id': self.pregunta.id,
                'valor': 4,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)


class ApiGuardarMatrizTest(TestCase):

    def setUp(self):
        self.prueba = _create_prueba(tipo='MATRICES', nombre='Matrices')
        self.pregunta = Pregunta.objects.create(
            prueba=self.prueba, texto='Patron',
            tipo_escala='OPCION_MULTIPLE', dimension='GENERAL', orden=1)
        self.opcion_correcta = Opcion.objects.create(
            pregunta=self.pregunta, texto='A', valor=1, orden=1)
        self.opcion_incorrecta = Opcion.objects.create(
            pregunta=self.pregunta, texto='B', valor=0, orden=2)
        self.ev = _create_evaluacion(estado='EN_CURSO')

    def test_respuesta_correcta(self):
        response = self.client.post(
            '/psicoevaluacion/api/respuesta/matriz/',
            json.dumps({
                'evaluacion_token': self.ev.token,
                'pregunta_id': self.pregunta.id,
                'opcion_id': self.opcion_correcta.id,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        resp = RespuestaMatriz.objects.first()
        self.assertTrue(resp.es_correcta)

    def test_respuesta_incorrecta(self):
        response = self.client.post(
            '/psicoevaluacion/api/respuesta/matriz/',
            json.dumps({
                'evaluacion_token': self.ev.token,
                'pregunta_id': self.pregunta.id,
                'opcion_id': self.opcion_incorrecta.id,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        resp = RespuestaMatriz.objects.first()
        self.assertFalse(resp.es_correcta)

    def test_evaluacion_no_en_curso(self):
        self.ev.estado = 'PENDIENTE'
        self.ev.save()
        response = self.client.post(
            '/psicoevaluacion/api/respuesta/matriz/',
            json.dumps({
                'evaluacion_token': self.ev.token,
                'pregunta_id': self.pregunta.id,
                'opcion_id': self.opcion_correcta.id,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 409)


class ApiGuardarMemoriaTest(TestCase):

    def setUp(self):
        self.prueba = _create_prueba(tipo='MEMORIA', nombre='Memoria')
        self.pregunta = Pregunta.objects.create(
            prueba=self.prueba, texto='Recuerde la secuencia',
            tipo_escala='SECUENCIA', dimension='GENERAL', orden=1,
            secuencia_correcta=[3, 7, 2])
        self.ev = _create_evaluacion(estado='EN_CURSO')

    def test_respuesta_correcta(self):
        response = self.client.post(
            '/psicoevaluacion/api/respuesta/memoria/',
            json.dumps({
                'evaluacion_token': self.ev.token,
                'pregunta_id': self.pregunta.id,
                'secuencia_respondida': [3, 7, 2],
                'tiempo_respuesta_seg': 10,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['es_correcta'])
        resp = RespuestaMemoria.objects.first()
        self.assertTrue(resp.es_correcta)
        self.assertEqual(resp.longitud_secuencia, 3)

    def test_respuesta_incorrecta(self):
        response = self.client.post(
            '/psicoevaluacion/api/respuesta/memoria/',
            json.dumps({
                'evaluacion_token': self.ev.token,
                'pregunta_id': self.pregunta.id,
                'secuencia_respondida': [3, 2, 7],
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['es_correcta'])

    def test_token_invalido(self):
        response = self.client.post(
            '/psicoevaluacion/api/respuesta/memoria/',
            json.dumps({
                'evaluacion_token': 'falso',
                'pregunta_id': self.pregunta.id,
                'secuencia_respondida': [3, 7, 2],
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)


class ApiGuardarProyectivaTest(TestCase):

    def setUp(self):
        self.prueba = _create_prueba(
            tipo='ARBOL', nombre='Arbol', es_proyectiva=True)
        self.pregunta = Pregunta.objects.create(
            prueba=self.prueba, texto='Dibuje un arbol',
            tipo_escala='TEXTO_LIBRE', dimension='GENERAL', orden=1)
        self.ev = _create_evaluacion(estado='EN_CURSO')

    def test_guardar_dibujo(self):
        response = self.client.post(
            '/psicoevaluacion/api/respuesta/proyectiva/',
            json.dumps({
                'evaluacion_token': self.ev.token,
                'pregunta_id': self.pregunta.id,
                'prueba_id': self.prueba.id,
                'tipo': 'DIBUJO',
                'imagen_canvas': 'data:image/png;base64,abc123',
                'datos_trazo': {'strokes': []},
                'tiempo_total_seg': 120,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        resp = RespuestaProyectiva.objects.first()
        self.assertEqual(resp.tipo, 'DIBUJO')
        self.assertEqual(resp.imagen_canvas, 'data:image/png;base64,abc123')

    def test_guardar_texto(self):
        prueba_frases = _create_prueba(
            tipo='FRASES', nombre='Frases', es_proyectiva=True, orden=2)
        pregunta = Pregunta.objects.create(
            prueba=prueba_frases, texto='Yo siento que...',
            tipo_escala='TEXTO_LIBRE', dimension='FR_TRAB', orden=1)
        response = self.client.post(
            '/psicoevaluacion/api/respuesta/proyectiva/',
            json.dumps({
                'evaluacion_token': self.ev.token,
                'pregunta_id': pregunta.id,
                'prueba_id': prueba_frases.id,
                'tipo': 'TEXTO',
                'texto_respuesta': 'el trabajo es importante',
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        resp = RespuestaProyectiva.objects.first()
        self.assertEqual(resp.tipo, 'TEXTO')
        self.assertEqual(resp.texto_respuesta, 'el trabajo es importante')

    def test_evaluacion_no_en_curso(self):
        self.ev.estado = 'COMPLETADA'
        self.ev.save()
        response = self.client.post(
            '/psicoevaluacion/api/respuesta/proyectiva/',
            json.dumps({
                'evaluacion_token': self.ev.token,
                'prueba_id': self.prueba.id,
                'tipo': 'DIBUJO',
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 409)


class FlujoCompletoTest(TestCase):
    """Test the full candidate flow: inicio → verificar → prueba → finalizar."""

    def setUp(self):
        self.prueba = _create_prueba()
        self.pregunta = Pregunta.objects.create(
            prueba=self.prueba, texto='Soy responsable',
            tipo_escala='LIKERT5', dimension='BF_RESP', orden=1)
        for i in range(1, 6):
            Opcion.objects.create(
                pregunta=self.pregunta, texto=str(i), valor=i, orden=i)
        self.ev = _create_evaluacion(cedula='1234567890')

    def test_flujo_completo(self):
        # Step 1: Visit inicio
        response = self.client.get(
            f'/psicoevaluacion/evaluar/{self.ev.token}/')
        self.assertEqual(response.status_code, 200)

        # Step 2: Verify with correct cedula
        response = self.client.post(
            f'/psicoevaluacion/evaluar/{self.ev.token}/verificar/',
            {'cedula': '1234567890'})
        self.assertEqual(response.status_code, 302)
        self.ev.refresh_from_db()
        self.assertEqual(self.ev.estado, 'EN_CURSO')

        # Step 3: Access test
        response = self.client.get(
            f'/psicoevaluacion/evaluar/{self.ev.token}/prueba/bigfive/')
        self.assertEqual(response.status_code, 200)

        # Step 4: Save a response via API
        response = self.client.post(
            '/psicoevaluacion/api/respuesta/psicometrica/',
            json.dumps({
                'evaluacion_token': self.ev.token,
                'pregunta_id': self.pregunta.id,
                'valor': 4,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        # Step 5: Finalize
        response = self.client.get(
            f'/psicoevaluacion/evaluar/{self.ev.token}/finalizar/')
        self.assertEqual(response.status_code, 200)
        self.ev.refresh_from_db()
        self.assertEqual(self.ev.estado, 'COMPLETADA')


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
        ev = _create_evaluacion()
        response = self.client.get(f'/psicoevaluacion/panel/evaluacion/{ev.pk}/')
        self.assertEqual(response.status_code, 302)

    def test_acceso_con_login(self):
        ev = _create_evaluacion()
        User.objects.create_user('admin', 'a@a.com', 'pass123')
        self.client.login(username='admin', password='pass123')
        response = self.client.get(f'/psicoevaluacion/panel/evaluacion/{ev.pk}/')
        self.assertEqual(response.status_code, 200)
